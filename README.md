# 🎬 Plex API Manager

A colorized Python CLI for managing multiple Plex Media Server instances via the Plex HTTP API. No web UI, no config files to hand-edit — just run the script and navigate the menu.

**Current version:** `v0.0.37`

---

## Features

- **Multi-server support** — store up to 10 Plex servers, switch between them on the fly
- **Library browser** — list all libraries with type and item counts
- **Library scanner & smart diff** — snapshot full metadata to disk, then diff against live to detect added/removed/changed items
- **Search** — search across cached library snapshots
- **Recently added** — see what's been added to any library
- **Playback sessions** — view active streams and kill them if needed
- **Watchlist / Favorites** — track items you want to watch, export in multiple formats
- **Movie Search List** — search TMDB, auto-fill metadata (title, year, IMDB/RT ratings, runtime, MPAA rating), assign internal IDs (ms000001), and send directly to Radarr
- **Movie Database** — bulk-enriches your entire Plex movie library with TMDB + OMDB metadata; respects 1000-call/day quota with automatic scheduler continuation; searchable local JSON; add any result to your Movie Search List; dedicated `logs/movie_db/` log folder
- **Color themes** — 10 built-in presets (Plex Classic, Midnight, Hacker, Sunset, Neon, Dracula, Monochrome, Ocean, Amber, Cherry) plus a fully custom role editor; press `[T]` from the main menu; saved to `theme.json`
- **Self-update** — checks GitHub on startup (1hr cache); update banner + `[U]` shortcut in main menu; shows full changelog before applying; skip a version, toggle auto-check, or force-check via Version Manager `[6] → [5/6]`; backs up to `old/`, restarts in-place; supports git pull, pip upgrade, and raw download
- **Discord notifications** — rich embeds on startup, server switch, library list, version adds, and stream kills
- **System info on startup** — OS version, external public IP, and active stream count sent to Discord automatically
- **Daily heartbeat** — cross-platform scheduler fires once daily at a random time between 00:00–11:59, self-rescheduling after each run
- **Version manager** — track your own changelog entries inside the app
- **pip installable** — install directly from GitHub, works on Windows and Ubuntu

---

## Requirements

- Python 3.8+
- `requests` and `colorama` — auto-installed on first run

| Platform | Python | Notes |
|---|---|---|
| macOS | `brew install python` | Homebrew required for one-liner install |
| Ubuntu / Linux | `sudo apt install python3` | pipx handled by installer |
| Windows | [python.org](https://www.python.org/downloads/) | Run with `python plex_menu.py` |

---

## Install

### Option A — macOS / Ubuntu / Linux (one-liner)

The installer auto-detects your OS and sets up Python + pipx + global commands.

```bash
bash <(curl -sL https://raw.githubusercontent.com/trickdaddy24/plex-api-manager/main/install.sh)
```

After install, three global commands are registered and `~/.plex-manager/` is created with a config template:

```bash
plex-manager      # interactive menu
plex-heartbeat    # send system info to Discord now
plex-scheduler    # manage daily heartbeat schedule
```

#### macOS prerequisites

macOS requires [Homebrew](https://brew.sh) — the installer will check for it and exit with instructions if it's missing. Install Homebrew first if you don't have it:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

The installer then handles Python 3 and pipx automatically via `brew install`.

> **Shell note:** macOS uses `zsh` by default. If `plex-manager` isn't found after install, run `source ~/.zshrc` (or `source ~/.bash_profile` if you use bash).

#### Ubuntu / Linux prerequisites

Python 3 must be installed. The installer handles pipx via `apt-get`.

```bash
sudo apt install python3   # if not already installed
```

### Option B — Git clone (Windows / macOS / local dev)

```bash
git clone https://github.com/trickdaddy24/plex-api-manager.git
cd plex-api-manager
python3 plex_menu.py      # macOS / Linux
python  plex_menu.py      # Windows
```

Dependencies (`requests`, `colorama`) are installed automatically on first run. Data files stay in the cloned directory.

### Option C — Docker

```bash
git clone https://github.com/trickdaddy24/plex-api-manager.git
cd plex-api-manager
docker compose build
docker compose run --rm plex-manager
```

All user data (config, logs, cache, exports) is stored in `./data/` on the host — nothing is baked into the image.

---

## First-Time Setup

1. Edit `plex_servers.json` (clone) or `~/.plex-manager/plex_servers.json` (pip) with your Plex URL and token
2. Launch `plex-manager` or `python plex_menu.py`
3. Go to **option 7** → set your Discord webhook
4. Run `plex-scheduler` to activate the daily heartbeat

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
| `heartbeat.json` | Next scheduled run time | ❌ (auto-generated) |

---

## Menu Overview

```
╔════════════════════════════════════════════════════╗
║         🎬  PLEX API MANAGER                       ║
║         v0.0.21  ·  MyServer  ·  12 libraries      ║
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

### Other automatic triggers
- Server switch
- Library listings
- Version entries added
- Stream kills

---

## Daily Heartbeat

Runs `system_info_notify.py` once per day at a random time between 00:00–11:59. After each run it reschedules itself for the next day at a new random time.

```bash
plex-scheduler            # set up / reschedule
plex-scheduler --status   # show next scheduled run
plex-scheduler --remove   # remove the task entirely
```

| Platform | Mechanism |
|---|---|
| Windows | Task Scheduler (`schtasks`) |
| Linux / Ubuntu | crontab |

---

## Docker

A full Docker setup is included. All user data lives in `./data/` on the host via a bind mount — the image itself contains no secrets.

### Build

```bash
docker compose build
```

### Interactive CLI

```bash
docker compose run --rm plex-manager
```

### Movie DB enrichment scan (one-shot)

```bash
docker compose run --rm --profile scan movie-db-scan
```

### Movie DB scan status

```bash
docker compose run --rm --profile scan movie-db-status
```

### Send heartbeat to Discord (one-shot)

```bash
docker compose run --rm --profile heartbeat heartbeat
```

### First-time Docker setup

On the very first run the entrypoint automatically:
1. Creates `./data/logs/movie_db/`, `./data/library_cache/`, `./data/watchlist_exports/`, `./data/old/`
2. Seeds `./data/versions.json` from the bundled default
3. Seeds `./data/plex_servers.json` from `plex_servers.example.json`

Then edit `./data/plex_servers.json` with your Plex URL and token before launching.

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
movie_db_scan.py          # Standalone movie DB enrichment scan
system_info_notify.py     # Standalone heartbeat — OS, IP, streams → Discord
heartbeat_scheduler.py    # Cross-platform scheduler (Windows/Linux)
pyproject.toml            # pip package definition + entry points
install.sh                # Ubuntu one-liner installer
Dockerfile                # Docker image definition
docker-compose.yml        # Docker Compose services
docker-entrypoint.sh      # Container entrypoint — seeds /data on first run
.dockerignore             # Excludes secrets and caches from build context
plex_servers.example.json # Server config template
versions.json             # Changelog / version history
watchlist.json            # Saved watchlist items
CLAUDE.md                 # Project context for Claude Code
data/                     # Docker bind-mount target (host-side user data)
library_cache/            # Per-library metadata snapshots (gitignored)
watchlist_exports/        # Exported watchlist files (gitignored)
logs/plex.log             # Log file (gitignored)
```

---

## Version History

| Version | Notes |
|---|---|
| v0.0.37 | Fix About screen alignment — drop right-border box (ANSI codes break `len()` padding); use left-border style so description lines never overflow |
| v0.0.36 | Fix self-update for pip/pipx — replace broken `pip install --upgrade git+...` with direct GitHub Raw download that overwrites the running script in-place |
| v0.0.35 | Add About screen (`[A]` in main menu) — script-header style box with title, author, revised date, description, version, entry point, GitHub link, and license |
| v0.0.34 | Fix pip/pipx version display — embed `APP_VERSION` constant; startup auto-sync of stale `versions.json` from GitHub; sync after pip upgrade |
| v0.0.33 | Overhaul self-update system — persistent banner + `[U]` shortcut, changelog before confirm, skip-version, auto-check toggle, 1hr cache, Update Settings submenu in Version Manager |
| v0.0.32 | Update install.sh for macOS — auto-detects Darwin vs Linux, Homebrew for Python/pipx, correct shell reload hint per platform |
| v0.0.31 | Add color theme system — 10 presets + custom role editor; `[T]` in main menu; saved to theme.json |
| v0.0.30 | docker-compose.yml — add port mapping 9998:9991 to plex-manager service |
| v0.0.29 | Add Docker support — Dockerfile, docker-compose.yml, docker-entrypoint.sh, .dockerignore; data volume at ./data/; profiles for scan and heartbeat |
| v0.0.28 | Add self-update system — startup check, Version Manager [5], git/pip/raw download, backup to old/, in-place restart, Discord notify |
| v0.0.27 | Add Movie Database — enriches all Plex movies with TMDB/OMDB, 1000/day quota, scheduler continuation, Discord notifications, dedicated log folder |
| v0.0.26 | Add Movie Search List (option 9) — TMDB search, OMDB ratings, ms000001 IDs, Radarr API send |
| v0.0.25 | Fix pyproject.toml build backend — use setuptools.build_meta for broader compatibility |
| v0.0.24 | Fix install.sh for Ubuntu 24.04 PEP 668 — switch from pip3 to pipx |
| v0.0.23 | Make repo public, restore curl one-liner install |
| v0.0.22 | Fix install.sh for private repo — local clone install, copies example config from repo |
| v0.0.21 | pip installable via pyproject.toml + install.sh, smart BASE_DIR, main() entry points |
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
