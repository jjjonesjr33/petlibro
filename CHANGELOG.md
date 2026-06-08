# Changelog

All notable changes to this fork of [jjjonesjr33/petlibro](https://github.com/jjjonesjr33/petlibro) are documented here.
Forked from upstream version **1.2.32**.

---

## [Unreleased] — forked from 1.2.32

### Security
- **Fixed:** Auth token no longer written to HA logs at DEBUG level (`api.py`, `config_flow.py`). The token appeared in three separate log statements; all three replaced with message-only equivalents. Anyone who followed the README's troubleshooting steps (enabling debug logging) was silently leaking their live session token into HA's log files.
- **Fixed:** Avatar URL is now validated before fetch (`pets/entity.py`). Only `https://` URLs from `petlibro.com` or `*.petlibro.com` are allowed. Rejects anything else with a warning and falls back to the bundled default avatar. Prevents a compromised PetLibro API from directing HA to make arbitrary outbound requests (SSRF).

### Added
- **Change login credentials** option in the options flow gear menu (`config_flow.py`). Pre-fills the current email, accepts new email + password, validates against the API, updates the stored credentials, and reloads the integration. Accessible via Settings → Devices & Services → PETLIBRO → ⚙.
- **Reconfigure** flow accessible via the three-dot menu on the integration card (`config_flow.py`). Same credential-update behaviour, following the HA 2024.3+ standard pattern.

### Removed
- Dead code: `make_api_call()` function removed from `api.py`. The function was an unauthenticated, headerless POST to an arbitrary URL that was never called. Its unused import was also removed from all 11 files that had copied it in (`binary_sensor.py`, `button.py`, `select.py`, `text.py`, `update.py`, and all device files under `devices/feeders/` and `devices/fountains/`).
