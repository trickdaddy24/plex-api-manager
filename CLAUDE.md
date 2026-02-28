# Plex API Manager — CLAUDE.md

## Project Overview

A Python CLI tool that manages multiple Plex Media Server instances via the Plex HTTP API. All interaction happens through a colorized terminal menu. The app is a single self-contained script with no build step.

**Entry point:** `plex_menu.py`
**Run with:** `python plex_menu.py`

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
| 7 | `discord_settings_menu()` | Discord webhook config and test |
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
- Current version: `v0.0.10`

---

## Discord Notifications

`notify_discord(message, title, color)` sends rich embeds to the configured webhook. Called automatically on:
- App startup / server switch
- Version adds
- Library lists

Webhook stored in `discord_creds.json`. Silently skipped if not configured.

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

Python stdlib: `subprocess`, `sys`, `json`, `logging`, `datetime`, `pathlib`

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
