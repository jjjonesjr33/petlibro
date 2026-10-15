"""Run the PETLIBRO go2rtc camera transport for Granary camera feeders.

The feeder's camera speaks a Kalay/TUTK-family UDP protocol. Home Assistant's
bundled go2rtc does not understand it, so this module runs a separate go2rtc
build that adds a clean-room ``petlibro://`` source (MIT licensed, from
https://github.com/tannerln7/Petlibro-Home-Assistant). The binary is static,
so it runs inside the Home Assistant container on any libc.

The binary is downloaded once from a pinned release and verified against a
pinned SHA-256 before it is ever executed. go2rtc listens on 127.0.0.1 only;
Home Assistant reads the RTSP stream from there.
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import platform
import socket
from collections.abc import Mapping
from urllib.parse import quote

from aiohttp import ClientError, ClientTimeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

GO2RTC_RELEASE = "go2rtc-v0.3.12"
GO2RTC_URL = (
    "https://github.com/KadenThomp36/Petlibro-Home-Assistant/releases/download/"
    f"{GO2RTC_RELEASE}/{{asset}}"
)

# platform.machine() -> (release asset, sha256)
GO2RTC_ASSETS: dict[str, tuple[str, str]] = {
    "x86_64": (
        "petlibro-go2rtc_linux_amd64",
        "2d86fc3f2d6eebe5886b2ecfdbb6ff1663e844b679266eb6052f6115ecb8b527",
    ),
    "aarch64": (
        "petlibro-go2rtc_linux_arm64",
        "0327abfcf0142542047c45408e6b23a706741cecb22db8122b251592ac59b769",
    ),
    "armv7l": (
        "petlibro-go2rtc_linux_armv7",
        "7be23d1874771e2d743ff319b85c9138e08bb9ba142f79c006f247ae135480af",
    ),
}

RESTART_DELAY = 30


class Go2rtcUnavailable(Exception):
    """The go2rtc transport cannot run on this system."""


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def petlibro_source(uid: str, host: str | None) -> str:
    """Build a petlibro:// source. Without a host, go2rtc discovers the
    camera by UID on the local broadcast domain."""
    return f"petlibro://{host or ''}?uid={quote(uid)}&quality=hd&audio=1"


class Go2rtcRunner:
    """Download, run, and supervise one go2rtc process for a config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self._dir = hass.config.path(".petlibro", "go2rtc")
        self._config_path = os.path.join(self._dir, f"{entry_id}.json")
        self._streams: dict[str, str] = {}
        self._api_port = 0
        self._rtsp_port = 0
        self._binary: str | None = None
        self._proc: asyncio.subprocess.Process | None = None
        self._supervisor: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._stopping = False

    def rtsp_url(self, name: str) -> str:
        return f"rtsp://127.0.0.1:{self._rtsp_port}/{quote(name)}"

    def frame_url(self, name: str) -> str:
        return f"http://127.0.0.1:{self._api_port}/api/frame.jpeg?src={quote(name)}"

    async def async_prepare(self) -> None:
        """Fetch the binary ahead of time so the first view starts quickly."""
        async with self._lock:
            if self._binary is None:
                self._binary = await self._async_get_binary()

    async def async_ensure_stream(self, name: str, source: str) -> str:
        """Make sure go2rtc serves ``source`` as ``name``; return its RTSP URL."""
        async with self._lock:
            if self._streams.get(name) != source or not self._running:
                self._streams[name] = source
                await self._async_restart()
        return self.rtsp_url(name)

    async def async_stop(self) -> None:
        self._stopping = True
        if self._supervisor:
            self._supervisor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._supervisor
            self._supervisor = None
        await self._async_kill()

    @property
    def _running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def _async_restart(self) -> None:
        if self._supervisor:
            self._supervisor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._supervisor
        await self._async_kill()
        if self._binary is None:
            self._binary = await self._async_get_binary()
        if not self._api_port:
            # Chosen once so a restart never changes the URLs handed to HA.
            self._api_port, self._rtsp_port = _free_port(), _free_port()
        config = {
            "log": {"format": "text", "level": "info"},
            "api": {"listen": f"127.0.0.1:{self._api_port}"},
            "rtsp": {"listen": f"127.0.0.1:{self._rtsp_port}"},
            "webrtc": {"listen": ""},
            "srtp": {"listen": ""},
            "streams": dict(self._streams),
        }
        await self.hass.async_add_executor_job(self._write_config, config)
        self._proc = await asyncio.create_subprocess_exec(
            self._binary,
            "-config",
            self._config_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self._supervisor = self.hass.async_create_background_task(
            self._async_supervise(self._proc), "petlibro go2rtc"
        )
        await self._async_wait_ready()

    async def _async_wait_ready(self) -> None:
        session = async_get_clientsession(self.hass)
        url = f"http://127.0.0.1:{self._api_port}/api"
        for _ in range(50):
            if not self._running:
                raise Go2rtcUnavailable("go2rtc exited during startup")
            with contextlib.suppress(ClientError, asyncio.TimeoutError):
                async with session.get(url, timeout=ClientTimeout(total=1)) as resp:
                    if resp.status == 200:
                        return
            await asyncio.sleep(0.1)
        raise Go2rtcUnavailable("go2rtc did not become ready")

    async def _async_supervise(self, proc: asyncio.subprocess.Process) -> None:
        """Forward go2rtc's log and restart it if it dies unexpectedly."""
        assert proc.stdout
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            if " ERR " in line or " WRN " in line:
                _LOGGER.warning("go2rtc: %s", line)
            else:
                _LOGGER.debug("go2rtc: %s", line)
        await proc.wait()
        if self._stopping:
            return
        _LOGGER.warning(
            "go2rtc exited with code %s; restarting in %ss", proc.returncode, RESTART_DELAY
        )
        await asyncio.sleep(RESTART_DELAY)
        async with self._lock:
            if not self._stopping and not self._running:
                self._supervisor = None
                try:
                    await self._async_restart()
                except Go2rtcUnavailable as err:
                    # The next stream request tries again.
                    _LOGGER.error("Could not restart go2rtc: %s", err)

    async def _async_kill(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None or proc.returncode is not None:
            return
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), 5)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()

    def _write_config(self, config: Mapping) -> None:
        os.makedirs(self._dir, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as file:
            json.dump(config, file)

    async def _async_get_binary(self) -> str:
        machine = platform.machine()
        if machine not in GO2RTC_ASSETS:
            raise Go2rtcUnavailable(f"no go2rtc build for architecture {machine}")
        asset, sha256 = GO2RTC_ASSETS[machine]
        path = os.path.join(self._dir, GO2RTC_RELEASE, asset)
        if await self.hass.async_add_executor_job(_verified, path, sha256):
            return path

        _LOGGER.info("Downloading %s %s", GO2RTC_RELEASE, asset)
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                GO2RTC_URL.format(asset=asset), timeout=ClientTimeout(total=300)
            ) as resp:
                resp.raise_for_status()
                data = await resp.read()
        except (ClientError, asyncio.TimeoutError) as err:
            raise Go2rtcUnavailable(f"download failed: {err}") from err
        if hashlib.sha256(data).hexdigest() != sha256:
            raise Go2rtcUnavailable(f"checksum mismatch for {asset}")
        await self.hass.async_add_executor_job(_install, path, data)
        return path


def _verified(path: str, sha256: str) -> bool:
    if not os.path.isfile(path):
        return False
    with open(path, "rb") as file:
        return hashlib.sha256(file.read()).hexdigest() == sha256


def _install(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "wb") as file:
        file.write(data)
    os.chmod(tmp, 0o755)
    os.replace(tmp, path)
