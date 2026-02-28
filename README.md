# 🎬 Plex API Manager

A colorized Python CLI for managing multiple Plex Media Server instances via the Plex HTTP API. No web UI, no config files to hand-edit — just run the script and navigate the menu.

**Current version:** `v0.0.20`

---

## Features

- **Multi-server support** — store up to 10 Plex servers, switch between them on the fly
- **Library browser** — list all libraries with type and item counts
- **Library scanner & smart diff** — snapshot full metadata to disk, then diff against live to detect added/removed/changed items
- **Search** — search across cached library snapshots
- **Recently added** — see what's been added to any library
- **Playback sessions** — view active streams and kill them if needed
- **Watchlist / Favorites** — track items you want to watch, export in multiple formats
- **Discord notifications** — rich embeds on startup, server switch, library list, version adds, and stream kills
- **System info on startup** — OS version, external public IP, and active stream count sent to Discord automatically
- **Daily heartbeat** — cross-platform scheduler fires `system_info_notify.py` once daily at a random time between 00:00–11:59, self-rescheduling after each run
- **Version manager** — track your own changelog entries inside the app

---

## Requirements

- Python 3.8+
- Dependencies are auto-installed on first run (`requests`, `colorama`)

---

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/trickdaddy24/plex-api-manager.git
cd plex-api-manager
```

**2. Run the script**
```bash
python plex_menu.py
```

On first launch you'll be prompted to enter your Plex server URL and token. These are saved locally to `plex_servers.json` (not committed).

**Finding your Plex token:** Sign into Plex, browse to any media item, click ··· → Get Info → View XML. The token is in the URL as `X-Plex-Token=`.

---

## Configuration Files

| File | Description | Committed |
|---|---|---|
| `plex_servers.json` | Server list with tokens | ❌ (use example) |
| `plex_servers.example.json` | Template for setup | ✅ |
| `discord_creds.json` | Discord webhook URL | ❌ |
| `versions.json` | App version history | ✅ |
| `watchlist.json` | Your watchlist | ✅ |

To configure servers manually, copy the example file:
```bash
cp plex_servers.example.json plex_servers.json
```
Then edit `plex_servers.json` with your server details.

---

## Menu Overview

```
╔════════════════════════════════════════════════════╗
║         🎬  PLEX API MANAGER                       ║
║         v0.0.18  ·  MyServer  ·  12 libraries      ║
╠════════════════════════════════════════════════════╣
║  [1]  List All Libraries                           ║
║  [2]  Search My Library with Totals                ║
║  [3]  Get Recently Added                           ║
║  [4]  Get Active Playback Sessions                 ║
║  [5]  Watchlist / Favorites                        ║
╠────────────────────────────────────────────────────╣
║  [6]  Version Manager                              ║
║  [7]  Discord Notification Settings                ║
║  [8]  Server Manager                               ║
╠────────────────────────────────────────────────────╣
║  [0]  Exit                                         ║
╚════════════════════════════════════════════════════╝
```

---

## Discord Notifications

Set a webhook URL via **Menu → 7 → Discord Notification Settings**.

### Automatic (on startup)
Every launch sends a Discord embed containing:
- Plex server version and library count
- Active stream count
- Host OS version
- External public IP (queried via ipify → ifconfig.me → ipecho.net)

### Discord Settings Menu (option 7)

```
  [1]  Set / Update Webhook URL
  [2]  Send Test Notification
  [3]  Remove Webhook
  [4]  Send System Info  (OS · IP · Active Streams)
```

Option `[4]` lets you fire a system info embed on demand at any time.

### Other automatic triggers
- Server switch
- Library listings
- Version entries added
- Stream kills

---

## Library Cache & Diff

**Menu → 2 → Search My Library** includes options to:
- **Scan** a library — fetches full metadata for every item and saves a snapshot to `library_cache/`
- **Diff** — compares the snapshot against live Plex data, reports added/removed/changed items
- Diff results are saved as `{Library}_DIFF_{timestamp}.json`

---

## Project Structure

```
plex_menu.py              # Main script — everything lives here
system_info_notify.py     # Standalone heartbeat — OS, IP, streams → Discord
heartbeat_scheduler.py    # Cross-platform scheduler (Windows/Linux)
heartbeat.json            # Stores next scheduled run time (auto-generated)
plex_servers.example.json # Server config template
versions.json             # Changelog / version history
watchlist.json            # Saved watchlist items
CLAUDE.md                 # Project context for Claude Code
library_cache/            # Per-library metadata snapshots (gitignored)
watchlist_exports/        # Exported watchlist files (gitignored)
logs/plex.log             # Log file (gitignored)
```

---

## Version History

| Version | Notes |
|---|---|
| v0.0.20 | Add heartbeat_scheduler.py — cross-platform daily scheduling, random time 00:00–11:59 |
| v0.0.19 | Recreated system_info_notify.py with OS, external IP, and active stream count |
| v0.0.18 | Moved system info into Discord settings menu option 4, removed standalone py |
| v0.0.17 | Added active stream count to Discord |
| v0.0.16 | Show active stream count in startup Discord notification |
| v0.0.15 | Created standalone system_info_notify.py |
| v0.0.14 | Removed socket (no longer needed) |
| v0.0.13 | OS & IP sent to Discord on startup |
| v0.0.12 | External public IP lookup via ipify / ifconfig.me / ipecho.net |
| v0.0.11 | OS detection at startup via platform module |
| v0.0.10 | Add kill stream option in playback sessions |
| v0.0.9 | Add smart diff (option 4) |
| v0.0.8 | Add scan, search & scan library |
| v0.0.7 | Add/change/delete servers |
| v0.0.6 | Fixed search endpoint |
| v0.0.5 | Credential prompting, no hardcoded placeholders |
| v0.0.4 | Add logging to logs/plex.log |
| v0.0.3 | Add server connectivity check |
| v0.0.2 | Add Python version check |
| v0.0.1 | Initial commit |
