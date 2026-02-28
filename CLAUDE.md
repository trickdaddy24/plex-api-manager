# Plex API Manager — CLAUDE.md

## Project Overview

A Python CLI tool that manages multiple Plex Media Server instances via the Plex HTTP API. All interaction happens through a colorized terminal menu. The app is a single self-contained script with no build step.

**Entry point:** `plex_menu.py`
**Run with:** `python plex_menu.py`

---

## Commit Workflow — ALWAYS follow this order

Every time code changes are made and pushed to GitHub, all three of these must be updated in the same commit:

1. **`versions.json`** — add a new entry for the change (next patch version, today's date, short note)
2. **`README.md`** — bump `Current version:` and add a row to the Version History table
3. **`plex_menu.py`** (or whichever file changed) — the actual code

Never commit code changes without updating `versions.json` and `README.md` in the same commit.

**Current version:** `v0.0.19`

---

## Architecture

Single-file architecture — everything lives in `plex_menu.py`. No packages, no modules, no imports from local files.

### Key Data Files

| File | Purpose |
|---|---|
| `plex_servers.json` | Multi-server list; `"active": true` marks the current server |
| `plex_creds.json` | Legacy single-server creds (auto-migrated to `plex_servers.json` on first run) |
| `discord_creds.json` | Discord webhook URL |
| `versions.json` | App version history (drives the displayed version) |
| `watchlist.json` | User watchlist / favorites |
| `library_cache/*.json` | Per-library full metadata snapshots (`{SERVER}_{Library}.json`) |
| `logs/plex.log` | Rotating log file |
| `watchlist_exports/` | Exported watchlist files |
| `old/` | Old versions of the script (reference only) |
| `system_info_notify.py` | Standalone script — sends OS, external IP, active streams to Discord |

### Global State

```python
ACTIVE = {"url": "", "token": "", "name": "", "version": "", "lib_count": 0}
```

Populated at startup by `startup_servers()` → `refresh_active()`. All API calls use `headers()` which reads from `ACTIVE`.

### Constants

- `MAX_SERVERS = 10`
- `BASE_DIR = Path(__file__).parent`
- `LIBRARY_CACHE_DIR = BASE_DIR / "library_cache"`

---

## Main Menu Options

| Key | Function | Description |
|---|---|---|
| 1 | `list_libraries()` | Lists all Plex libraries with item counts |
| 2 | `search_library()` | Search across cached libraries; scan/diff submenus |
| 3 | `recently_added()` | Recently added items |
| 4 | `playback_sessions()` | Active streams; can kill streams |
| 5 | `watchlist_menu()` | Watchlist / favorites management |
| 6 | `version_menu()` | App version history management |
| 7 | `discord_settings_menu()` | Discord webhook config, test, and system info |
| 8 | `server_manager_menu()` | Add/switch/edit/delete Plex servers |

---

## Multi-Server System

- Up to 10 servers stored in `plex_servers.json`
- Only one server has `"active": true` at a time
- `probe_server(url, token)` tests connectivity and returns name, version, library count
- `refresh_active(server)` populates the global `ACTIVE` dict
- On startup: migrates `plex_creds.json` if `plex_servers.json` is empty

**Three configured servers:**
- `THEBEAST` — `192.168.4.59:32400`
- `DESKTOP-17L8GVL-WIN11` — `192.168.4.9:32400`
- `BLACK_OP` — `192.168.7.107:32400` (currently active)

---

## Library Cache & Diff System

- `scan_and_save_library()` — fetches full metadata for every item in a library, saves to `library_cache/{SERVER}_{Library}.json`
- `diff_library()` — compares cached snapshot against live Plex data; detects added/removed/changed items
- `_build_fingerprint_set()` / `_build_live_fingerprint_set()` — fingerprinting for diff
- `_detect_changed_metadata()` — detects metadata changes between cache and live
- Diff results saved as `{Library}_DIFF_{timestamp}.json` in `library_cache/`
- `search_cached_library()` — searches within a cached JSON file

---

## Version System

- `versions.json` is the source of truth for app version
- Current version = last entry in the array
- `get_app_version()` returns the last version string
- `suggest_next_version()` auto-increments the patch number
- Log IDs use format `log.001`, `log.002`, etc.
- **Current version: `v0.0.19`**

---

## Discord Notifications

`notify_discord(message, title, color)` sends rich embeds to the configured webhook. Called automatically on:
- App startup — includes OS version, external public IP, active stream count
- Server switch
- Version adds
- Library lists
- Stream kills

Discord Settings Menu (option 7) sub-options:
- `[1]` Set / Update Webhook URL
- `[2]` Send Test Notification
- `[3]` Remove Webhook
- `[4]` Send System Info on demand (OS · IP · Active Streams)

Webhook stored in `discord_creds.json`. Silently skipped if not configured.

---

## System Info

`get_system_info()` — returns OS name/release/version via `platform` and external public IP via:
1. `https://api.ipify.org`
2. `https://ifconfig.me/ip`
3. `https://ipecho.net/plain`

`get_active_stream_count()` — hits `/status/sessions` on the active server, returns stream count (0 on error).

Both called at startup and via Discord menu option 4.
`system_info_notify.py` is a standalone script with the same logic, loading server config directly from `plex_servers.json`.

---

## Watchlist

- Stored in `watchlist.json`
- Supports types: movie, show, episode, other
- `watchlist_menu()` — add/remove/search/export
- `_export_watchlist()` — exports to `watchlist_exports/` in multiple formats

---

## Dependencies

Auto-installed on startup via `install_requirements()`:
- `requests`
- `colorama`

Python stdlib: `subprocess`, `sys`, `json`, `logging`, `datetime`, `pathlib`, `platform`

---

## Code Conventions

- All color output via helper functions: `cyan()`, `yellow()`, `green()`, `red()`, `magenta()`, `blue()`, `white()`, `header()`, `divider()`
- Section dividers use `═` (double) and `-` (single) via `divider()`
- All API calls use `timeout=10` (listings) or `timeout=5` (quick probes)
- Logging goes to both `logs/plex.log` and stdout
- Menu loops use `while True` with `break` on back/exit
- No argparse — purely interactive

---

## Platform

- Windows 11 (dev machine)
- Run directly: `python plex_menu.py`
- No virtual environment required (auto-installs deps)
