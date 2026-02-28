# 🎬 Plex API Manager

A colorized Python CLI for managing multiple Plex Media Server instances via the Plex HTTP API. No web UI, no config files to hand-edit — just run the script and navigate the menu.

**Current version:** `v0.0.10`

---

## Features

- **Multi-server support** — store up to 10 Plex servers, switch between them on the fly
- **Library browser** — list all libraries with type and item counts
- **Library scanner & smart diff** — snapshot full metadata to disk, then diff against live to detect added/removed/changed items
- **Search** — search across cached library snapshots
- **Recently added** — see what's been added to any library
- **Playback sessions** — view active streams and kill them if needed
- **Watchlist / Favorites** — track items you want to watch, export in multiple formats
- **Discord notifications** — rich embeds sent to a webhook on key events
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
║         v0.0.10  ·  MyServer  ·  12 libraries      ║
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

Set a webhook URL via **Menu → 7 → Discord Notification Settings**. Notifications fire on:
- App startup / server switch
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
plex_servers.example.json # Server config template
versions.json             # Changelog / version history
watchlist.json            # Saved watchlist items
library_cache/            # Per-library metadata snapshots (gitignored)
watchlist_exports/        # Exported watchlist files (gitignored)
logs/plex.log             # Log file (gitignored)
```

---

## Version History

| Version | Notes |
|---|---|
| v0.0.10 | Add kill stream option |
| v0.0.9 | Add smart diff (option 4) |
| v0.0.8 | Add scan, search & scan library |
| v0.0.7 | Add/change/delete servers |
| v0.0.6 | Fixed search endpoint |
| v0.0.5 | Credential prompting, no hardcoded placeholders |
| v0.0.4 | Add logging to logs/plex.log |
| v0.0.3 | Add server connectivity check |
| v0.0.2 | Add Python version check |
| v0.0.1 | Initial commit |
