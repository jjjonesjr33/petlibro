"""Event handling class for PETLIBRO."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

EVENT_UPDATE = "update"


@dataclass
class Event:
    """Abstract event class properties and methods."""

    _listeners: dict[str, list[Callable]] = field(default_factory=dict)

    def emit(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Run all callbacks for an event."""
        for listener in self._listeners.get(event_name, []):
            try:  # noqa: SIM105
                listener(*args, **kwargs)
            except:  # pragma: no cover # pylint: disable=bare-except  # noqa: E722, S110
                pass

    def on(  # pylint: disable=invalid-name
        self, event_name: str, callback: Callable
    ) -> Callable:
        """Register an event callback."""
        listeners: list = self._listeners.setdefault(event_name, [])
        listeners.append(callback)

        def unsubscribe() -> None:
            """Unsubscribe listeners."""
            if callback in listeners:
                listeners.remove(callback)

        return unsubscribe
