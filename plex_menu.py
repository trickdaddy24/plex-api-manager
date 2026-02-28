import os
import subprocess
import sys
import json
import logging
import platform
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────
#  AUTO-INSTALL REQUIREMENTS
# ─────────────────────────────────────────
REQUIRED = ["requests", "colorama"]

def install_requirements():
    missing = []
    for pkg in REQUIRED:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"📦 Installing missing packages: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        print("✅ All packages installed!\n")
    else:
        print("✅ All requirements already satisfied.\n")

install_requirements()

# ─────────────────────────────────────────
#  THIRD-PARTY IMPORTS
# ─────────────────────────────────────────
import requests
from colorama import init, Fore, Style
init(autoreset=True)

# ─────────────────────────────────────────
#  PATHS
# ─────────────────────────────────────────
_script_dir = Path(__file__).parent
if (_script_dir / "versions.json").exists():
    BASE_DIR = _script_dir                          # dev / git-clone mode
else:
    BASE_DIR = Path(os.environ.get(               # pip-installed mode
        "PLEX_MANAGER_HOME", Path.home() / ".plex-manager"
    ))
    BASE_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR       = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE      = LOG_DIR / "plex.log"
SERVERS_FILE  = BASE_DIR / "plex_servers.json"   # replaces plex_creds.json
DISCORD_FILE  = BASE_DIR / "discord_creds.json"
VERSIONS_FILE  = BASE_DIR / "versions.json"
WATCHLIST_FILE  = BASE_DIR / "watchlist.json"
MOVIE_LIST_FILE    = BASE_DIR / "movie_list.json"
RADARR_FILE        = BASE_DIR / "radarr_creds.json"
API_KEYS_FILE      = BASE_DIR / "api_keys.json"
MOVIE_DB_FILE      = BASE_DIR / "movie_db.json"
MOVIE_DB_PROG_FILE = BASE_DIR / "movie_db_progress.json"
MOVIE_DB_LOG_DIR   = LOG_DIR / "movie_db"
MOVIE_DB_TASK_NAME = "PlexMovieDBScan"
TMDB_DAILY_LIMIT   = 1000
MAX_SERVERS        = 10
GITHUB_REPO        = "trickdaddy24/plex-api-manager"
GITHUB_RAW_BASE    = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"
UPDATE_FILES       = [
    "plex_menu.py",
    "movie_db_scan.py",
    "heartbeat_scheduler.py",
    "system_info_notify.py",
    "versions.json",
]

# ─────────────────────────────────────────
#  LOGGING SETUP
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("plex")

# ─────────────────────────────────────────
#  COLOR HELPERS
# ─────────────────────────────────────────
def c(text, color):          return f"{color}{text}{Style.RESET_ALL}"
def cyan(t):                 return c(t, Fore.CYAN)
def yellow(t):               return c(t, Fore.YELLOW)
def green(t):                return c(t, Fore.GREEN)
def red(t):                  return c(t, Fore.RED)
def magenta(t):              return c(t, Fore.MAGENTA)
def blue(t):                 return c(t, Fore.BLUE)
def white(t):                return c(t, Fore.WHITE)
def header(t):               return c(t, Fore.CYAN + Style.BRIGHT)
def divider(char="═", n=52): return c(char * n, Fore.BLUE + Style.BRIGHT)

# ─────────────────────────────────────────
#  SYSTEM INFO
# ─────────────────────────────────────────
def get_system_info():
    """Return OS name/version and external public IP address."""
    os_name    = platform.system()
    os_release = platform.release()
    os_version = platform.version()
    os_str     = f"{os_name} {os_release} ({os_version})"
    ip = "Unknown"
    for url in ["https://api.ipify.org", "https://ifconfig.me/ip", "https://ipecho.net/plain"]:
        try:
            ip = requests.get(url, timeout=5).text.strip()
            break
        except Exception:
            continue
    return {"os": os_str, "ip": ip}

def get_active_stream_count():
    """Return the number of active Plex streams. Returns 0 on error."""
    try:
        res = requests.get(f"{ACTIVE['url']}/status/sessions", headers=headers(), timeout=5)
        res.raise_for_status()
        return res.json()["MediaContainer"].get("size", 0)
    except Exception:
        return 0

# ─────────────────────────────────────────
#  VERSION HELPERS
# ─────────────────────────────────────────
def load_versions():
    if VERSIONS_FILE.exists():
        try:
            with open(VERSIONS_FILE) as f:
                return json.load(f)
        except Exception:
            return []
    initial = [{"version": "0.0.1", "date": datetime.now().strftime("%Y-%m-%d"), "notes": "Initial commit"}]
    save_versions(initial)
    return initial

def save_versions(data):
    with open(VERSIONS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_app_version():
    versions = load_versions()
    return versions[-1]["version"] if versions else "0.0.1"

def suggest_next_version():
    versions = load_versions()
    if not versions:
        return "0.0.2"
    last = versions[-1]["version"]
    try:
        parts = last.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    except Exception:
        return last

# ─────────────────────────────────────────
#  SELF-UPDATE SYSTEM
# ─────────────────────────────────────────
def _version_tuple(v):
    """Convert '0.0.27' → (0, 0, 27) for comparison."""
    try:
        return tuple(int(x) for x in str(v).split("."))
    except Exception:
        return (0, 0, 0)

def _detect_install_method():
    """Return 'git', 'pip', or 'raw' based on how the app was installed."""
    import shutil as _shutil
    if (BASE_DIR / ".git").exists():
        return "git"
    if _shutil.which("plex-manager"):
        return "pip"
    return "raw"

def check_for_updates(silent=False):
    """
    Fetch versions.json from GitHub and compare to local version.
    Returns dict with update info if update is available, else None.
    """
    try:
        res = requests.get(f"{GITHUB_RAW_BASE}/versions.json", timeout=5)
        res.raise_for_status()
        remote_versions = res.json()
        if not remote_versions:
            return None
        remote_latest = remote_versions[-1]
        remote_ver    = remote_latest["version"]
        local_ver     = get_app_version()
        if _version_tuple(remote_ver) > _version_tuple(local_ver):
            new_entries = [v for v in remote_versions if _version_tuple(v["version"]) > _version_tuple(local_ver)]
            return {
                "local":        local_ver,
                "remote":       remote_ver,
                "remote_notes": remote_latest["notes"],
                "remote_date":  remote_latest["date"],
                "all_new":      new_entries,
            }
        return None
    except Exception as e:
        if not silent:
            log.warning(f"Update check failed: {e}")
        return None

def perform_update(update_info):
    """
    Download and apply the latest version from GitHub.
    Backs up current files to old/ before replacing.
    Offers to restart after a successful update.
    """
    import shutil as _shutil
    local_ver  = update_info["local"]
    remote_ver = update_info["remote"]
    method     = _detect_install_method()

    print(f"\n{header('  🔄  UPDATING TO v' + remote_ver)}\n" + divider("-", 52))
    print(f"  {white('Install method:')} {cyan(method)}")
    print(f"  {white('Current version:')} {yellow('v' + local_ver)}")
    print(f"  {white('New version:')}     {green('v' + remote_ver)}")

    # ── Changelog for all new versions ──────────────────────
    if update_info.get("all_new"):
        print(f"\n  {white('What changed:')}")
        for v in update_info["all_new"]:
            print(f"    {green('v' + v['version'])}  {blue(v['date'])}  {white(v['notes'])}")

    # ── Backup current files ─────────────────────────────────
    print(f"\n  {white('Backing up current files...')}")
    backup_dir = BASE_DIR / "old"
    backup_dir.mkdir(exist_ok=True)
    ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
    backed_up  = []
    for fname in UPDATE_FILES:
        src = BASE_DIR / fname
        if src.exists():
            dst = backup_dir / f"{src.stem}_v{local_ver}_{ts}{src.suffix}"
            try:
                _shutil.copy2(src, dst)
                backed_up.append(dst.name)
            except Exception as e:
                log.warning(f"Backup failed for {fname}: {e}")
    if backed_up:
        print(f"  {green('✅ Backed up')} {yellow(str(len(backed_up)))} file(s) to {blue('old/')}")

    # ── Apply update ─────────────────────────────────────────
    success = False
    print(divider("-", 52))

    if method == "git":
        try:
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                capture_output=True, text=True, cwd=str(BASE_DIR),
            )
            if result.returncode == 0:
                print(green(f"  ✅ git pull succeeded."))
                log.info(f"Updated via git pull: v{local_ver} → v{remote_ver}")
                success = True
            else:
                print(red(f"  ❌ git pull failed:\n{result.stderr.strip()}"))
                log.error(f"git pull failed: {result.stderr.strip()}")
        except Exception as e:
            print(red(f"  ❌ git error: {e}"))
            log.error(f"Update git error: {e}")

    elif method == "pip":
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade",
                 f"git+https://github.com/{GITHUB_REPO}.git"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                print(green("  ✅ pip upgrade succeeded."))
                log.info(f"Updated via pip: v{local_ver} → v{remote_ver}")
                success = True
            else:
                print(red("  ❌ pip upgrade failed."))
                log.error(f"pip upgrade failed: {result.stderr.strip()}")
        except Exception as e:
            print(red(f"  ❌ pip error: {e}"))
            log.error(f"Update pip error: {e}")

    else:
        # Raw file download — write to .tmp then move
        all_ok = True
        for fname in UPDATE_FILES:
            url = f"{GITHUB_RAW_BASE}/{fname}"
            dst = BASE_DIR / fname
            tmp = dst.with_suffix(".update_tmp")
            try:
                res = requests.get(url, timeout=15)
                res.raise_for_status()
                tmp.write_bytes(res.content)
                _shutil.move(str(tmp), str(dst))
                print(f"  {green('✅')} {white(fname)}")
                log.info(f"Downloaded update: {fname}")
            except Exception as e:
                if tmp.exists():
                    tmp.unlink()
                print(red(f"  ❌ {fname}: {e}"))
                log.error(f"Update download failed: {fname}: {e}")
                all_ok = False
        success = all_ok

    # ── Post-update ──────────────────────────────────────────
    if success:
        print(f"\n  {green('✅ Update complete!')}  {yellow('v'+local_ver)} → {green('v'+remote_ver)}")
        log.info(f"Update applied: v{local_ver} → v{remote_ver} ({method})")
        notify_discord(
            f"🆙 **App Updated Successfully**\n\n"
            f"📦 `v{local_ver}` → `v{remote_ver}`\n"
            f"📝 {update_info['remote_notes']}\n"
            f"🔄 Method: `{method}`",
            title="🆙 Plex Manager Updated", color=0x57F287,
        )
        restart = input(f"\n  {cyan('Restart now to apply changes? (y/n)')}: ").strip().lower()
        if restart == "y":
            print(yellow("  Restarting..."))
            log.info("Restarting after update.")
            os.execv(sys.executable, [sys.executable] + sys.argv)
    else:
        print(red("\n  ❌ Update failed. Original files are backed up in old/ and unchanged."))
        log.error(f"Update failed: v{local_ver} → v{remote_ver} ({method})")

    return success

# ─────────────────────────────────────────
#  MULTI-SERVER MANAGEMENT
# ─────────────────────────────────────────
def load_servers():
    """Load all saved servers from plex_servers.json."""
    if SERVERS_FILE.exists():
        try:
            with open(SERVERS_FILE) as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception as e:
            log.warning(f"Could not read servers file: {e}")
    return []

def save_servers(servers):
    with open(SERVERS_FILE, "w") as f:
        json.dump(servers, f, indent=2)

def get_active_server(servers):
    """Return the server marked as active, or the first one."""
    for s in servers:
        if s.get("active"):
            return s
    return servers[0] if servers else None

def make_headers(token):
    return {"X-Plex-Token": token, "Accept": "application/json"}

def probe_server(url, token):
    """Try to connect to a server and return its friendly name and library count."""
    headers = make_headers(token)
    try:
        r = requests.get(f"{url}/", headers=headers, timeout=5)
        r.raise_for_status()
        name = r.json()["MediaContainer"].get("friendlyName", "Plex Server")

        r2 = requests.get(f"{url}/identity", headers=headers, timeout=5)
        r2.raise_for_status()
        version = r2.json()["MediaContainer"].get("version", "Unknown")

        r3 = requests.get(f"{url}/library/sections", headers=headers, timeout=5)
        r3.raise_for_status()
        lib_count = len(r3.json()["MediaContainer"].get("Directory", []))

        return {"ok": True, "name": name, "version": version, "lib_count": lib_count}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ─────────────────────────────────────────
#  ACTIVE SERVER STATE  (loaded at startup)
# ─────────────────────────────────────────
ACTIVE = {
    "url":     "",
    "token":   "",
    "name":    "Unknown",
    "version": "Unknown",
    "lib_count": 0,
}

def refresh_active(server: dict):
    """Populate ACTIVE dict from a server entry."""
    ACTIVE["url"]   = server["url"]
    ACTIVE["token"] = server["token"]
    info = probe_server(server["url"], server["token"])
    if info["ok"]:
        ACTIVE["name"]      = info["name"]
        ACTIVE["version"]   = info["version"]
        ACTIVE["lib_count"] = info["lib_count"]
        server["name"]      = info["name"]   # keep saved name fresh
    else:
        ACTIVE["name"]      = server.get("name", "Unknown")
        ACTIVE["version"]   = "Unknown"
        ACTIVE["lib_count"] = 0

def headers():
    return make_headers(ACTIVE["token"])

# ─────────────────────────────────────────
#  DISCORD NOTIFICATION
# ─────────────────────────────────────────
def load_discord_webhook():
    if DISCORD_FILE.exists():
        try:
            with open(DISCORD_FILE) as f:
                return json.load(f).get("webhook_url", "").strip()
        except Exception:
            return ""
    return ""

def save_discord_webhook(url):
    with open(DISCORD_FILE, "w") as f:
        json.dump({"webhook_url": url}, f, indent=2)

def notify_discord(message: str, title: str = "Plex API Manager", color: int = 0x00b0f4):
    webhook_url = load_discord_webhook()
    if not webhook_url:
        return
    app_ver = get_app_version()
    payload = {
        "embeds": [{
            "title": title,
            "description": message,
            "color": color,
            "fields": [
                {"name": "🖥️ Server",     "value": ACTIVE["name"],            "inline": True},
                {"name": "📚 Libraries",  "value": str(ACTIVE["lib_count"]),  "inline": True},
                {"name": "🔢 App Version","value": f"v{app_ver}",             "inline": True},
            ],
            "footer": {"text": f"Plex API Manager v{app_ver} — {ACTIVE['name']}"},
            "timestamp": datetime.utcnow().isoformat()
        }]
    }
    try:
        res = requests.post(webhook_url, json=payload, timeout=5)
        if res.status_code in (200, 204):
            log.info(f"Discord notification sent: {title}")
        else:
            log.warning(f"Discord webhook returned {res.status_code}")
    except Exception as e:
        log.warning(f"Discord notification failed: {e}")

# ─────────────────────────────────────────
#  SERVER MANAGER MENU
# ─────────────────────────────────────────
def server_manager_menu():
    global ACTIVE
    while True:
        servers = load_servers()
        active  = get_active_server(servers)
        print("\n" + divider())
        print(header("  🖥️   SERVER MANAGER"))
        print(divider())
        # List current servers
        if servers:
            for i, s in enumerate(servers):
                marker = green(" ◀ active") if s.get("active") else ""
                status = cyan(s.get("name", s["url"]))
                print(f"  {yellow(f'[{i+1}]')}  {status}  {blue(s['url'])}{marker}")
        else:
            print(f"  {yellow('No servers configured yet.')}")
        print(divider("-", 52))
        print(f"  {green('[A]')}  {white('Add New Server')}  {blue(f'({len(servers)}/{MAX_SERVERS})')}")
        if servers:
            print(f"  {yellow('[S]')}  {white('Switch Active Server')}")
            print(f"  {yellow('[E]')}  {white('Edit a Server')}")
            print(f"  {red('[D]')}  {white('Delete a Server')}")
        print(f"  {red('[0]')}  {white('Back to Main Menu')}")
        print(divider())
        choice = input(f"  {cyan('Select an option')}: ").strip().upper()

        # ── ADD ──────────────────────────────
        if choice == "A":
            if len(servers) >= MAX_SERVERS:
                print(red(f"  ❌ Maximum of {MAX_SERVERS} servers reached."))
                continue
            print("\n" + header("  ➕  ADD NEW SERVER"))
            url   = input(f"  {cyan('Plex URL (e.g. http://192.168.1.10:32400)')}: ").strip()
            token = input(f"  {cyan('Plex Token')}: ").strip()
            nick  = input(f"  {cyan('Nickname (optional, press Enter to auto-detect)')}: ").strip()
            if not url or not token:
                print(red("  ❌ URL and Token are required."))
                continue
            print(yellow("  🔌 Testing connection..."))
            info = probe_server(url, token)
            if not info["ok"]:
                print(red(f"  ❌ Could not connect: {info['error']}"))
                cont = input(f"  {yellow('Save anyway? (y/n)')}: ").strip().lower()
                if cont != "y":
                    continue
                name = nick if nick else "Unknown Server"
            else:
                name = nick if nick else info["name"]
                print(green(f"  ✅ Connected to {cyan(name)}  —  {info['lib_count']} libraries  |  v{info['version']}"))

            is_first = len(servers) == 0
            entry = {"url": url, "token": token, "name": name, "active": is_first}
            servers.append(entry)
            save_servers(servers)
            log.info(f"Server added: {name} ({url})")
            if is_first:
                refresh_active(entry)
                print(green(f"  ✅ '{name}' saved and set as active server."))
            else:
                print(green(f"  ✅ '{name}' saved as server [{len(servers)}]."))

        # ── SWITCH ───────────────────────────
        elif choice == "S" and servers:
            print("\n" + header("  🔄  SWITCH ACTIVE SERVER"))
            for i, s in enumerate(servers):
                marker = green(" ◀ active") if s.get("active") else ""
                print(f"  {yellow(f'[{i+1}]')}  {cyan(s.get('name', s['url']))}  {blue(s['url'])}{marker}")
            sel = input(f"\n  {cyan('Enter server number')}: ").strip()
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(servers):
                    raise ValueError
            except ValueError:
                print(red("  ❌ Invalid selection."))
                continue
            # Deactivate all, activate chosen
            for s in servers:
                s["active"] = False
            servers[idx]["active"] = True
            save_servers(servers)
            print(yellow("  🔌 Connecting to new server..."))
            refresh_active(servers[idx])
            save_servers(servers)
            log.info(f"Switched active server to: {ACTIVE['name']} ({ACTIVE['url']})")
            notify_discord(
                f"🔄 Switched active server\n\n📡 Now connected to **{ACTIVE['name']}**\n🔗 `{ACTIVE['url']}`",
                title="Server Switched", color=0x5865F2
            )
            print(green(f"  ✅ Now connected to {cyan(ACTIVE['name'])}  —  {ACTIVE['lib_count']} libraries"))

        # ── EDIT ─────────────────────────────
        elif choice == "E" and servers:
            print("\n" + header("  ✏️   EDIT SERVER"))
            for i, s in enumerate(servers):
                print(f"  {yellow(f'[{i+1}]')}  {cyan(s.get('name', s['url']))}  {blue(s['url'])}")
            sel = input(f"\n  {cyan('Enter server number to edit')}: ").strip()
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(servers):
                    raise ValueError
            except ValueError:
                print(red("  ❌ Invalid selection."))
                continue
            s = servers[idx]
            print(f"\n  {white('Editing:')} {cyan(s.get('name', s['url']))}")
            new_url   = input(f"  {cyan(f'New URL [Enter to keep]')}: ").strip()
            new_token = input(f"  {cyan(f'New Token [Enter to keep]')}: ").strip()
            current_nick = s.get("name", "")
            new_nick  = input(f"  {cyan('New Nickname [Enter to keep: ' + current_nick + ']')}: ").strip()
            if new_url:   s["url"]   = new_url
            if new_token: s["token"] = new_token
            if new_nick:  s["name"]  = new_nick
            servers[idx] = s
            save_servers(servers)
            if s.get("active"):
                refresh_active(s)
            log.info(f"Server edited: [{idx+1}] {s.get('name')} ({s['url']})")
            print(green(f"  ✅ Server [{idx+1}] updated."))

        # ── DELETE ───────────────────────────
        elif choice == "D" and servers:
            print("\n" + header("  🗑️   DELETE SERVER"))
            for i, s in enumerate(servers):
                marker = red(" ◀ active") if s.get("active") else ""
                print(f"  {yellow(f'[{i+1}]')}  {cyan(s.get('name', s['url']))}  {blue(s['url'])}{marker}")
            sel = input(f"\n  {cyan('Enter server number to delete')}: ").strip()
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(servers):
                    raise ValueError
            except ValueError:
                print(red("  ❌ Invalid selection."))
                continue
            was_active = servers[idx].get("active", False)
            removed    = servers.pop(idx)
            # If we removed the active server, make the first remaining one active
            if was_active and servers:
                servers[0]["active"] = True
                refresh_active(servers[0])
            elif not servers:
                ACTIVE["url"] = ACTIVE["token"] = ACTIVE["name"] = ""
                ACTIVE["lib_count"] = 0
            save_servers(servers)
            log.info(f"Server deleted: {removed.get('name')} ({removed['url']})")
            print(yellow(f"  🗑️  '{removed.get('name')}' removed."))
            if was_active and servers:
                print(green(f"  ✅ Active server switched to: {cyan(ACTIVE['name'])}"))

        elif choice == "0":
            break
        else:
            print(red("  ⚠️  Invalid option."))

# ─────────────────────────────────────────
#  STARTUP — LOAD / PROMPT FOR SERVERS
# ─────────────────────────────────────────
def startup_servers():
    """On launch, ensure at least one server exists and set the active one."""
    servers = load_servers()

    # Migrate legacy plex_creds.json → plex_servers.json
    legacy = BASE_DIR / "plex_creds.json"
    if not servers and legacy.exists():
        try:
            with open(legacy) as f:
                old = json.load(f)
            url   = old.get("PLEX_URL", "").strip()
            token = old.get("PLEX_TOKEN", "").strip()
            if url and token:
                servers = [{"url": url, "token": token, "name": "My Plex Server", "active": True}]
                save_servers(servers)
                log.info("Migrated legacy plex_creds.json → plex_servers.json")
                print(yellow("  ℹ️  Migrated your existing credentials to the new multi-server format.\n"))
        except Exception:
            pass

    if not servers:
        print("\n" + divider())
        print(header("  🔐  PLEX SERVER SETUP"))
        print(divider())
        print(f"  {white('No servers configured. Add your first Plex server.')}\n")
        url   = input(f"  {cyan('Plex URL (e.g. http://192.168.1.10:32400)')}: ").strip()
        token = input(f"  {cyan('Plex Token')}: ").strip()
        nick  = input(f"  {cyan('Nickname (optional)')}: ").strip()
        if not url or not token:
            print(red("  ❌ URL and Token are required. Exiting."))
            sys.exit(0)
        print(yellow("  🔌 Testing connection..."))
        info = probe_server(url, token)
        name = nick if nick else (info["name"] if info["ok"] else "My Plex Server")
        servers = [{"url": url, "token": token, "name": name, "active": True}]
        save_servers(servers)
        log.info(f"First server saved: {name} ({url})")
        if info["ok"]:
            print(green(f"  ✅ Connected to {cyan(name)}  —  {info['lib_count']} libraries\n"))
        else:
            print(yellow(f"  ⚠️  Saved but could not connect: {info.get('error','')}\n"))

    # Set active server into ACTIVE dict
    active = get_active_server(servers)
    if not active:
        servers[0]["active"] = True
        active = servers[0]
        save_servers(servers)

    refresh_active(active)
    save_servers(servers)  # persist any name updates from probe

    app_ver = get_app_version()
    log.info(f"Active server: {ACTIVE['name']} ({ACTIVE['url']}) | v{ACTIVE['version']} | {ACTIVE['lib_count']} libs | App v{app_ver}")
    print(green(f"  ✅ Connected to {cyan(ACTIVE['name'])}"))
    print(f"     {white('Server:')} {blue(ACTIVE['version'])}  {white('Libraries:')} {magenta(str(ACTIVE['lib_count']))}  {white('App:')} {cyan('v'+app_ver)}\n")
    sysinfo      = get_system_info()
    stream_count = get_active_stream_count()
    log.info(f"System: {sysinfo['os']} | IP: {sysinfo['ip']} | Active streams: {stream_count}")
    notify_discord(
        f"✅ Connected successfully\n\n"
        f"📡 Server version: `{ACTIVE['version']}`\n"
        f"📚 Libraries: `{ACTIVE['lib_count']}`\n"
        f"▶️ Active streams: `{stream_count}`\n\n"
        f"🖥️ OS: `{sysinfo['os']}`\n"
        f"🌐 IP: `{sysinfo['ip']}`",
        title=f"🎬 Plex Manager Started — {ACTIVE['name']}",
        color=0x57F287
    )

    # Silent update check — notify if update is available, don't block startup
    update = check_for_updates(silent=True)
    if update:
        print(f"\n  {yellow('💡 Update available:')}  {white('v'+update['local'])} → {green('v'+update['remote'])}")
        print(f"     {white(update['remote_notes'])}")
        print(f"     {blue('Go to Version Manager [6] → [5] Check for Updates')}\n")

# ─────────────────────────────────────────
#  VERSION MANAGER MENU
# ─────────────────────────────────────────
def version_menu():
    while True:
        versions = load_versions()
        app_ver  = get_app_version()
        print("\n" + divider())
        print(header(f"  📋  VERSION MANAGER  —  App v{app_ver}"))
        print(divider())
        print(f"  {yellow('[1]')}  {white('List All Versions')}")
        print(f"  {yellow('[2]')}  {white('Add New Version Entry')}")
        print(f"  {yellow('[3]')}  {white('Edit Existing Version')}")
        print(f"  {yellow('[4]')}  {white('Track / Snapshot to Log & Discord')}")
        print(divider("-", 52))
        print(f"  {green('[5]')}  {white('Check for Updates / Update Now')}")
        print(f"  {red('[0]')}  {white('Back to Main Menu')}")
        print(divider())
        choice = input(f"  {cyan('Select an option')}: ").strip()

        if choice == "0":
            break

        elif choice == "1":
            print("\n" + divider("-", 52))
            print(header("  📜  VERSION HISTORY"))
            print(divider("-", 52))
            if not versions:
                print(red("  No versions recorded."))
            else:
                for i, v in enumerate(versions):
                    log_id = f"log.{i+1:03d}"
                    marker = green("◀ current") if v["version"] == app_ver else ""
                    print(f"  {green(log_id)}  {yellow('v'+v['version'])}  {blue(v['date'])}  {marker}")
                    print(f"          {white(v['notes'])}\n")

        elif choice == "2":
            suggested = suggest_next_version()
            print("\n" + header("  ➕  ADD NEW VERSION"))
            print(f"  {white('Suggested next version:')} {cyan(suggested)}")
            ver_input = input(f"  {cyan(f'Version [Enter for {suggested}]')}: ").strip()
            ver       = ver_input if ver_input else suggested
            date_inp  = input(f"  {cyan('Date (YYYY-MM-DD) [Enter for today]')}: ").strip()
            date      = date_inp if date_inp else datetime.now().strftime("%Y-%m-%d")
            notes     = input(f"  {cyan('What was added/changed')}: ").strip()
            if not notes:
                print(red("  ⚠️  Notes are required."))
                continue
            versions.append({"version": ver, "date": date, "notes": notes})
            save_versions(versions)
            log_id  = f"log.{len(versions):03d}"
            new_ver = get_app_version()
            log.info(f"Version added: {log_id} v{ver} — {notes} | App now v{new_ver}")
            notify_discord(
                f"**New version entry added**\n\n📦 Version: `v{ver}`\n📅 Date: {date}\n📝 {notes}",
                title=f"🆕 Version v{ver} Added", color=0x57F287
            )
            print(green(f"\n  ✅ v{ver} saved as {log_id}  |  App version is now {cyan('v'+new_ver)}"))

        elif choice == "3":
            if not versions:
                print(red("  No versions to edit."))
                continue
            print("\n" + header("  ✏️  EDIT VERSION"))
            for i, v in enumerate(versions):
                print(f"  {green(f'log.{i+1:03d}')}  {yellow('v'+v['version'])}  {blue(v['date'])}  {white(v['notes'])}")
            idx_inp = input(f"\n  {cyan('Enter log ID to edit (e.g. log.002)')}: ").strip().lower()
            try:
                num = int(idx_inp.replace("log.", "")) - 1
                if num < 0 or num >= len(versions): raise ValueError
            except ValueError:
                print(red("  ❌ Invalid log ID."))
                continue
            entry     = versions[num]
            new_ver   = input(f"  {cyan('New version [Enter to keep '+entry['version']+']')}: ").strip()
            new_date  = input(f"  {cyan('New date [Enter to keep '+entry['date']+']')}: ").strip()
            new_notes = input(f"  {cyan('New notes [Enter to keep current]')}: ").strip()
            if new_ver:   entry["version"] = new_ver
            if new_date:  entry["date"]    = new_date
            if new_notes: entry["notes"]   = new_notes
            versions[num] = entry
            save_versions(versions)
            new_app = get_app_version()
            log.info(f"Version edited: log.{num+1:03d} → v{entry['version']} | App now v{new_app}")
            print(green(f"  ✅ log.{num+1:03d} updated  |  App version is now {cyan('v'+new_app)}"))

        elif choice == "4":
            app_ver = get_app_version()
            log.info(f"=== VERSION HISTORY SNAPSHOT (App v{app_ver}) ===")
            lines = []
            for i, v in enumerate(versions):
                log.info(f"  log.{i+1:03d}  v{v['version']}  {v['date']}  {v['notes']}")
                lines.append(f"`log.{i+1:03d}` **v{v['version']}** — {v['notes']} _{v['date']}_")
            log.info("=== END SNAPSHOT ===")
            notify_discord("\n".join(lines), title=f"📋 Version Snapshot — App v{app_ver}", color=0xFEE75C)
            print(green(f"  ✅ Snapshot written to plex.log and Discord  |  App v{cyan(app_ver)}"))

        elif choice == "5":
            print(f"\n  {cyan('🔍 Checking for updates...')}")
            update = check_for_updates(silent=False)
            if not update:
                print(green(f"  ✅ You are on the latest version (v{get_app_version()})."))
            else:
                print(f"\n{header('  🆙  UPDATE AVAILABLE')}\n" + divider("-", 52))
                print(f"  {white('Current:')} {yellow('v' + update['local'])}")
                print(f"  {white('Latest:')}  {green('v' + update['remote'])}  {blue(update['remote_date'])}")
                print(f"\n  {white('What changed:')}")
                for v in update.get("all_new", []):
                    print(f"    {green('v' + v['version'])}  {blue(v['date'])}")
                    print(f"    {white(v['notes'])}")
                print(divider("-", 52))
                confirm = input(f"\n  {cyan('Update now? (y/n)')}: ").strip().lower()
                if confirm == "y":
                    perform_update(update)
                else:
                    print(yellow("  Update skipped."))

        else:
            print(red("  ⚠️  Invalid option."))

# ─────────────────────────────────────────
#  DISCORD SETTINGS MENU
# ─────────────────────────────────────────
def discord_settings_menu():
    while True:
        current = load_discord_webhook()
        status  = green("Connected ✅") if current else red("Not configured ❌")
        print("\n" + divider())
        print(header("  🔔  DISCORD NOTIFICATION SETTINGS"))
        print(divider())
        print(f"  {white('Status:')}  {status}")
        if current:
            print(f"  {white('Webhook:')} {blue(current[:50]+('...' if len(current)>50 else ''))}")
        print()
        print(f"  {yellow('[1]')}  {white('Set / Update Webhook URL')}")
        print(f"  {yellow('[2]')}  {white('Send Test Notification')}")
        print(f"  {yellow('[3]')}  {white('Remove Webhook')}")
        print(f"  {yellow('[4]')}  {white('Send System Info')}  {blue('(OS · IP · Active Streams)')}")
        print(f"  {red('[0]')}  {white('Back')}")
        print(divider())
        choice = input(f"  {cyan('Select an option')}: ").strip()

        if choice == "0":
            break
        elif choice == "1":
            url = input(f"  {cyan('Enter Discord Webhook URL')}: ").strip()
            if url:
                save_discord_webhook(url)
                log.info("Discord webhook URL saved.")
                print(green("  ✅ Webhook saved!"))
            else:
                print(red("  ⚠️  No URL entered."))
        elif choice == "2":
            notify_discord(
                "🔔 This is a test notification from **Plex API Manager**!\n\nIf you see this, your webhook is working correctly.",
                title="🧪 Test Notification", color=0xEB459E
            )
            print(green("  ✅ Test notification sent!"))
        elif choice == "3":
            if DISCORD_FILE.exists():
                DISCORD_FILE.unlink()
                log.info("Discord webhook removed.")
            print(yellow("  Webhook removed."))
        elif choice == "4":
            print(yellow("  🔍 Gathering system info..."))
            sysinfo      = get_system_info()
            stream_count = get_active_stream_count()
            log.info(f"System info requested — OS: {sysinfo['os']} | IP: {sysinfo['ip']} | Streams: {stream_count}")
            print(f"  {white('OS:')}      {cyan(sysinfo['os'])}")
            print(f"  {white('IP:')}      {cyan(sysinfo['ip'])}")
            print(f"  {white('Streams:')} {cyan(str(stream_count))}")
            notify_discord(
                f"🖥️ OS: `{sysinfo['os']}`\n"
                f"🌐 IP: `{sysinfo['ip']}`\n"
                f"▶️ Active streams: `{stream_count}`",
                title="🖥️ System Info", color=0x5865F2
            )
            print(green("  ✅ System info sent to Discord!"))
        else:
            print(red("  ⚠️  Invalid option."))

# ─────────────────────────────────────────
#  1. LIST ALL LIBRARIES
# ─────────────────────────────────────────
def list_libraries():
    log.info(f"List Libraries — {ACTIVE['name']}")
    print("\n" + header("  📚  ALL LIBRARIES") + "\n" + divider("-", 52))
    try:
        res = requests.get(f"{ACTIVE['url']}/library/sections", headers=headers(), timeout=10)
        res.raise_for_status()
        sections = res.json()["MediaContainer"].get("Directory", [])
        if not sections:
            print(red("  No libraries found."))
            return
        discord_lines = []
        for lib in sections:
            cr = requests.get(f"{ACTIVE['url']}/library/sections/{lib['key']}/all", headers=headers(), timeout=10)
            cr.raise_for_status()
            total = cr.json()["MediaContainer"].get("size", 0)
            print(f"  {green('['+lib['key']+']')} {yellow(lib['title'])}")
            print(f"       {white('Type:')} {cyan(lib['type'].capitalize())}  {white('Items:')} {magenta(str(total))}\n")
            log.info(f"Library: {lib['title']} | {lib['type']} | {total} items")
            discord_lines.append(f"📁 **{lib['title']}** — {lib['type'].capitalize()} | {total} items")
        notify_discord("\n".join(discord_lines), title="📚 Libraries", color=0x00b0f4)
    except requests.RequestException as e:
        log.error(f"List libraries error: {e}")
        print(red(f"  ❌ Error: {e}"))

# ─────────────────────────────────────────
#  LIBRARY SCANNER — extract full metadata
# ─────────────────────────────────────────
LIBRARY_CACHE_DIR = BASE_DIR / "library_cache"
LIBRARY_CACHE_DIR.mkdir(exist_ok=True)

def _shorten_path(path, max_parts=4):
    """Keep only the last N parts of a file path."""
    if not path:
        return "N/A"
    parts = Path(path).parts
    if len(parts) <= max_parts:
        return path
    return ".../" + "/".join(parts[-max_parts:])

def _fmt_size(bytes_val):
    """Format bytes to human-readable size."""
    try:
        b = int(bytes_val)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} PB"
    except Exception:
        return "N/A"

def _fmt_duration(ms):
    """Format milliseconds to HH:MM:SS."""
    try:
        s   = int(ms) // 1000
        h   = s // 3600
        m   = (s % 3600) // 60
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"
    except Exception:
        return "N/A"

def _extract_item_metadata(item, detail=None):
    """
    Build a full metadata dict from a Plex item.
    Pass detail=full_item_json if already fetched; otherwise supply the summary item.
    """
    d = detail if detail else item

    # ── Basic info ──────────────────────────────
    title          = d.get("title", "Unknown")
    year           = d.get("year", "N/A")
    studio         = d.get("studio", "N/A")
    rating         = d.get("rating", "N/A")
    summary        = d.get("summary", "N/A")
    duration_ms    = d.get("duration", 0)
    content_rating = d.get("contentRating", "N/A")
    genres         = [g.get("tag", "") for g in d.get("Genre", [])]

    # ── Media / file info ───────────────────────
    media_list = d.get("Media", [])
    media_entries = []
    for media in media_list:
        resolution    = f"{media.get('videoResolution', 'N/A')}p" if media.get("videoResolution") else "N/A"
        video_codec   = media.get("videoCodec", "N/A")
        aspect_ratio  = media.get("aspectRatio", "N/A")
        audio_codec   = media.get("audioCodec", "N/A")
        audio_channels= media.get("audioChannels", "N/A")
        audio_profile = media.get("audioProfile", "N/A")
        container     = media.get("container", "N/A")

        parts_list = []
        for part in media.get("Part", []):
            file_path  = part.get("file", "N/A")
            file_size  = _fmt_size(part.get("size", 0))
            file_short = _shorten_path(file_path)

            # Stream details
            streams    = []
            subtitles  = []
            for stream in part.get("Stream", []):
                stype = stream.get("streamType")
                if stype == 1:   # video
                    streams.append({
                        "type":         "video",
                        "codec":        stream.get("codec", "N/A"),
                        "profile":      stream.get("codecID", "N/A"),
                        "resolution":   f"{stream.get('width','?')}x{stream.get('height','?')}",
                        "frame_rate":   stream.get("frameRate", "N/A"),
                        "bit_depth":    stream.get("bitDepth", "N/A"),
                        "color_space":  stream.get("colorSpace", "N/A"),
                    })
                elif stype == 2: # audio
                    streams.append({
                        "type":         "audio",
                        "codec":        stream.get("codec", "N/A"),
                        "channels":     stream.get("channels", "N/A"),
                        "language":     stream.get("language", "N/A"),
                        "profile":      stream.get("audioChannelLayout", "N/A"),
                        "sample_rate":  stream.get("samplingRate", "N/A"),
                    })
                elif stype == 3: # subtitle
                    subtitles.append({
                        "codec":    stream.get("codec", "N/A"),
                        "language": stream.get("language", "N/A"),
                        "format":   stream.get("format", "N/A"),
                        "forced":   stream.get("forced", False),
                        "default":  stream.get("default", False),
                    })

            parts_list.append({
                "file_path":      file_path,
                "file_path_short": file_short,
                "file_size":      file_size,
                "container":      container,
                "streams":        streams,
                "subtitles":      subtitles,
            })

        media_entries.append({
            "resolution":     resolution,
            "video_codec":    video_codec,
            "aspect_ratio":   str(aspect_ratio),
            "audio_codec":    audio_codec,
            "audio_channels": str(audio_channels),
            "audio_profile":  audio_profile,
            "container":      container,
            "parts":          parts_list,
        })

    return {
        "title":          title,
        "year":           year,
        "studio":         studio,
        "rating":         str(rating),
        "content_rating": content_rating,
        "summary":        summary,
        "duration":       _fmt_duration(duration_ms),
        "genres":         genres,
        "media":          media_entries,
    }

def _categorise(item):
    """Return movies / tv_shows / others based on Plex type."""
    t = item.get("type", "")
    if t == "movie":   return "movies"
    if t in ("show", "episode", "season"): return "tv_shows"
    return "others"

def _fetch_full_item(rating_key):
    """Fetch full metadata for a single item by ratingKey."""
    try:
        r = requests.get(
            f"{ACTIVE['url']}/library/metadata/{rating_key}",
            headers=headers(), timeout=10
        )
        r.raise_for_status()
        items = r.json()["MediaContainer"].get("Metadata", [])
        return items[0] if items else {}
    except Exception:
        return {}

def scan_and_save_library(lib_key, lib_title, lib_type):
    """Scan every item in a library, extract full metadata, save categorised JSON."""
    print(f"\n  {yellow('📡 Fetching all items from')} {cyan(lib_title)} {yellow('...')}") 
    try:
        r = requests.get(
            f"{ACTIVE['url']}/library/sections/{lib_key}/all",
            headers=headers(), timeout=30
        )
        r.raise_for_status()
        items = r.json()["MediaContainer"].get("Metadata", [])
    except Exception as e:
        print(red(f"  ❌ Failed to fetch library: {e}"))
        return

    total  = len(items)
    result = {"movies": [], "tv_shows": [], "others": []}

    print(f"  {white('Found')} {magenta(str(total))} {white('items. Scanning full metadata...')}\n")

    for idx, item in enumerate(items, 1):
        rk        = item.get("ratingKey")
        full_item = _fetch_full_item(rk) if rk else item
        metadata  = _extract_item_metadata(item, full_item)
        category  = _categorise(full_item if full_item else item)
        result[category].append(metadata)

        # Progress bar
        pct  = int((idx / total) * 40)
        bar  = "█" * pct + "░" * (40 - pct)
        print(f"\n[{bar}] {idx}/{total} — {metadata['title'][:30]:<30}", end="", flush=True)

    print()  # newline after progress

    # Save to library_cache/<server>_<lib_title>.json
    safe_server = ACTIVE["name"].replace(" ", "_")
    safe_lib    = lib_title.replace(" ", "_")
    out_file    = LIBRARY_CACHE_DIR / f"{safe_server}_{safe_lib}.json"

    summary = {
        "scanned_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "server":      ACTIVE["name"],
        "library":     lib_title,
        "library_type": lib_type,
        "total_items": total,
        "movies":      len(result["movies"]),
        "tv_shows":    len(result["tv_shows"]),
        "others":      len(result["others"]),
        "data":        result,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4, ensure_ascii=False)

    log.info(f"Library scan saved: {out_file.name} | {total} items | movies:{len(result['movies'])} tv:{len(result['tv_shows'])} other:{len(result['others'])}")
    print(f"\n{green('✅ Scan complete!')}")
    print(f"     {white('Movies:')}  {magenta(str(len(result['movies'])))}  "
          f"{white('TV Shows:')} {cyan(str(len(result['tv_shows'])))}  "
          f"{white('Others:')}  {blue(str(len(result['others'])))}")
    print(f"     {white('Saved to:')} {green(str(out_file))}\n")
    return out_file

def search_cached_library(out_file, query):
    """Search a previously scanned library JSON by title. Offers add-to-Movie-List for movie matches."""
    if not out_file or not Path(out_file).exists():
        print(red("  ❌ No scan file found."))
        return
    with open(out_file, encoding="utf-8") as f:
        data = json.load(f)

    query_lower  = query.lower()
    grand_total  = 0
    movie_matches = []
    for category in ("movies", "tv_shows", "others"):
        matches = [i for i in data["data"].get(category, []) if query_lower in i.get("title","").lower()]
        if not matches:
            continue
        label = category.replace("_", " ").title()
        print(f"\n{magenta('📁 '+label)} {yellow(f'({len(matches)} result'+('s' if len(matches)!=1 else '')+')')}")
        for m in matches:
            genres_str = ", ".join(m.get("genres", [])) or "N/A"
            print(f"      {cyan('•')} {yellow(m['title'])} {blue('('+str(m['year'])+')')}")
            print(f"          {white('Rating:')} {m['rating']}  {white('Duration:')} {m['duration']}  {white('Genres:')} {genres_str}")
            for med in m.get("media", []):
                for part in med.get("parts", []):
                    print(f"          {white('File:')} {green(part['file_path_short'])}  {white('Size:')} {part['file_size']}")
                    break
                break
            if category == "movies":
                movie_matches.append(m)
        grand_total += len(matches)

    print(f"\n{green('✅ Grand Total:')} {yellow(str(grand_total))} result{'s' if grand_total!=1 else ''}")

    # Offer add-to-Movie-List for movie results
    if movie_matches:
        print(divider("-", 52))
        print(f"  {white('Add a movie to your Movie Search List?')}")
        for i, m in enumerate(movie_matches[:10], 1):
            yr = m.get("year", "?")
            print(f"  {yellow(f'[{i}]')}  {white(m['title'])}  {blue(f'({yr})')}")
        print(f"  {red('[0]')}  {white('Skip')}")
        sel = input(f"  {cyan('Select movie to add (or 0 to skip)')}: ").strip()
        if sel != "0" and sel.isdigit():
            try:
                idx   = int(sel) - 1
                if 0 <= idx < len(movie_matches[:10]):
                    picked     = movie_matches[idx]
                    movie_list = load_movie_list()
                    dupes = [x for x in movie_list if x["title"].lower() == picked["title"].lower()]
                    if dupes:
                        print(yellow(f"  ⚠️  '{picked['title']}' already in Movie List ({dupes[0]['id']})."))
                    else:
                        # Check movie_db for enriched data
                        db      = load_movie_db()
                        db_hit  = next((v for v in db.values() if v.get("title","").lower() == picked["title"].lower()), None)
                        new_id  = _next_movie_id(movie_list)
                        entry   = {
                            "id":          new_id,
                            "title":       picked["title"],
                            "year":        str(picked.get("year", "N/A")),
                            "tmdb_id":     db_hit["tmdb_id"] if db_hit else "N/A",
                            "imdb_id":     db_hit.get("imdb_id","N/A") if db_hit else "N/A",
                            "mpaa_rating": db_hit.get("mpaa_rating","N/A") if db_hit else picked.get("content_rating","N/A"),
                            "runtime":     db_hit.get("runtime","N/A") if db_hit else picked.get("duration","N/A"),
                            "imdb_rating": db_hit.get("imdb_rating","N/A") if db_hit else "N/A",
                            "rt_rating":   db_hit.get("rt_rating","N/A") if db_hit else "N/A",
                            "description": db_hit.get("description","N/A") if db_hit else picked.get("summary","N/A"),
                            "added_at":    datetime.now().strftime("%Y-%m-%d"),
                        }
                        movie_list.append(entry)
                        save_movie_list(movie_list)
                        log.info(f"Added to Movie List from library scan: {entry['title']} [{new_id}]")
                        src = "enriched from DB" if db_hit else "basic info only — run Movie Database scan to enrich"
                        print(green(f"  ✅ '{entry['title']}' added as {new_id}. ({src})"))
            except (ValueError, IndexError):
                print(red("  ❌ Invalid selection."))

# ─────────────────────────────────────────
#  LIBRARY DIFF ENGINE
# ─────────────────────────────────────────

def _build_fingerprint_set(cached_data):
    """
    Build a set of fingerprints from cached JSON.
    Each fingerprint is: (title, year, file_path)
    Returns a dict keyed by file_path for fast lookup.
    """
    index = {}
    for category in ("movies", "tv_shows", "others"):
        for item in cached_data.get("data", {}).get(category, []):
            title = item.get("title", "")
            year  = str(item.get("year", ""))
            for media in item.get("media", []):
                for part in media.get("parts", []):
                    fp = part.get("file_path", "")
                    if fp and fp != "N/A":
                        index[fp] = {
                            "title":     title,
                            "year":      year,
                            "category":  category,
                            "file_size": part.get("file_size", "N/A"),
                            "duration":  item.get("duration", "N/A"),
                        }
    return index


def _build_live_fingerprint_set(lib_key):
    """
    Fetch current library items from Plex and build the same fingerprint index.
    Uses /library/sections/{key}/all with includeMedia=1 to get file paths quickly.
    """
    index = {}
    try:
        r = requests.get(
            f"{ACTIVE['url']}/library/sections/{lib_key}/all",
            headers=headers(),
            params={"includeMedia": 1, "includeAllConcepts": 0},
            timeout=30
        )
        r.raise_for_status()
        items = r.json()["MediaContainer"].get("Metadata", [])
        for item in items:
            title    = item.get("title", "")
            year     = str(item.get("year", ""))
            category = _categorise(item)
            for media in item.get("Media", []):
                for part in media.get("Part", []):
                    fp   = part.get("file", "")
                    size = _fmt_size(part.get("size", 0))
                    if fp:
                        index[fp] = {
                            "title":     title,
                            "year":      year,
                            "category":  category,
                            "file_size": size,
                            "duration":  _fmt_duration(item.get("duration", 0)),
                        }
    except Exception as e:
        log.error(f"Live fingerprint fetch failed: {e}")
    return index


def _detect_changed_metadata(cached_data, lib_key):
    """
    For items that exist in both cached and live — check if title/year/size changed.
    Returns list of changed items.
    """
    changed = []
    try:
        r = requests.get(
            f"{ACTIVE['url']}/library/sections/{lib_key}/all",
            headers=headers(),
            params={"includeMedia": 1},
            timeout=30
        )
        r.raise_for_status()
        live_items = r.json()["MediaContainer"].get("Metadata", [])
    except Exception:
        return []

    # Build live lookup by file_path
    live_by_path = {}
    for item in live_items:
        for media in item.get("Media", []):
            for part in media.get("Part", []):
                fp = part.get("file", "")
                if fp:
                    live_by_path[fp] = item

    # Compare against cached
    for category in ("movies", "tv_shows", "others"):
        for cached_item in cached_data.get("data", {}).get(category, []):
            c_title = cached_item.get("title", "")
            c_year  = str(cached_item.get("year", ""))
            c_size  = ""
            c_path  = ""
            for media in cached_item.get("media", []):
                for part in media.get("parts", []):
                    c_path = part.get("file_path", "")
                    c_size = part.get("file_size", "")
                    break
                break

            if c_path and c_path in live_by_path:
                live = live_by_path[c_path]
                l_title = live.get("title", "")
                l_year  = str(live.get("year", ""))
                l_size  = ""
                for media in live.get("Media", []):
                    for part in media.get("Part", []):
                        l_size = _fmt_size(part.get("size", 0))
                        break
                    break

                diffs = []
                if c_title != l_title:
                    diffs.append(f"title: {c_title!r} → {l_title!r}")
                if c_year != l_year:
                    diffs.append(f"year: {c_year} → {l_year}")
                if c_size != l_size and l_size:
                    diffs.append(f"size: {c_size} → {l_size}")

                if diffs:
                    changed.append({
                        "title":    c_title,
                        "category": category,
                        "path":     _shorten_path(c_path),
                        "changes":  diffs,
                    })
    return changed


def diff_library(scan_file_path, lib_key):
    """
    Main diff function.
    Compares a cached JSON scan against the current live Plex library.
    Reports: NEW items, MISSING items, CHANGED metadata.
    Saves a diff report to library_cache/<name>_DIFF_<timestamp>.json
    """
    print(f"\n  {yellow('🔄 Loading cached scan...')}")
    try:
        with open(scan_file_path, encoding="utf-8") as f:
            cached = json.load(f)
    except Exception as e:
        print(red(f"  ❌ Could not read scan file: {e}"))
        return

    lib_name       = cached.get("library", "Unknown")
    scanned_at     = cached.get("scanned_at", "Unknown")
    cached_total   = cached.get("total_items", 0)

    print(f"  {white('Cached scan:')} {cyan(lib_name)}  {blue(scanned_at)}  {magenta(str(cached_total) + ' items')}")
    print(f"  {yellow('📡 Fetching live library from Plex...')}")

    cached_index = _build_fingerprint_set(cached)
    live_index   = _build_live_fingerprint_set(lib_key)

    cached_paths = set(cached_index.keys())
    live_paths   = set(live_index.keys())

    missing = cached_paths - live_paths   # in cache but not live → removed/missing
    new     = live_paths   - cached_paths # in live but not cache  → added
    both    = cached_paths & live_paths   # in both → check for metadata changes

    print(f"\n  {white('Comparing')} {magenta(str(len(cached_paths)))} {white('cached vs')} {cyan(str(len(live_paths)))} {white('live files...')}")

    # ── CHANGED ──────────────────────────────────────────
    print(f"\n  {yellow('🔍 Checking for metadata changes...')}")
    changed = _detect_changed_metadata(cached, lib_key)

    # ── DISPLAY RESULTS ──────────────────────────────────
    print("\n" + divider("─", 52))
    print(header(f"  📊  DIFF REPORT — {lib_name}"))
    print(divider("─", 52))
    print(f"  {white('Scanned:')}     {blue(scanned_at)}")
    print(f"  {white('Cached items:')} {magenta(str(len(cached_paths)))}")
    print(f"  {white('Live items:')}   {cyan(str(len(live_paths)))}")
    print(divider("─", 52))

    # NEW
    if new:
        print(f"\n  {green('✅ NEW — ' + str(len(new)) + ' item(s) added since last scan:')}")
        for path in sorted(new):
            info = live_index[path]
            print(f"    {green('+')} {yellow(info['title'])} {blue('(' + info['year'] + ')')}  {white(info['category'].replace('_',' ').title())}")
            print(f"        {white(_shorten_path(path))}  {info['file_size']}")
    else:
        print(f"\n  {green('✅ No new items.')}")

    # MISSING
    if missing:
        print(f"\n  {red('❌ MISSING — ' + str(len(missing)) + ' item(s) removed/missing since last scan:')}")
        for path in sorted(missing):
            info = cached_index[path]
            print(f"    {red('-')} {yellow(info['title'])} {blue('(' + info['year'] + ')')}  {white(info['category'].replace('_',' ').title())}")
            print(f"        {white(_shorten_path(path))}  {info['file_size']}")
    else:
        print(f"\n  {green('✅ No missing items.')}")

    # CHANGED
    if changed:
        print(f"\n  {yellow('⚠️  CHANGED — ' + str(len(changed)) + ' item(s) with metadata changes:')}")
        for c in changed:
            print(f"    {yellow('~')} {cyan(c['title'])}  {white(c['category'].replace('_',' ').title())}")
            print(f"        {white('Path:')} {c['path']}")
            for diff in c["changes"]:
                print(f"        {yellow('→')} {diff}")
    else:
        print(f"\n  {green('✅ No metadata changes detected.')}")

    print("\n" + divider("─", 52))
    net_change = len(live_paths) - len(cached_paths)
    net_str    = (green(f"+{net_change}") if net_change > 0 else red(str(net_change))) if net_change != 0 else green("0")
    print(f"  {white('Net change:')} {net_str} items  |  {white('Changed metadata:')} {yellow(str(len(changed)))} items")
    print(divider("─", 52))

    # ── SAVE DIFF REPORT ─────────────────────────────────
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_lib = lib_name.replace(" ", "_")
    diff_out = LIBRARY_CACHE_DIR / f"{safe_lib}_DIFF_{ts}.json"

    report = {
        "diff_run_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "library":        lib_name,
        "original_scan":  scanned_at,
        "cached_total":   len(cached_paths),
        "live_total":     len(live_paths),
        "new_count":      len(new),
        "missing_count":  len(missing),
        "changed_count":  len(changed),
        "new_items": [
            {"title": live_index[p]["title"], "year": live_index[p]["year"],
             "category": live_index[p]["category"], "file_path": p,
             "file_size": live_index[p]["file_size"]}
            for p in sorted(new)
        ],
        "missing_items": [
            {"title": cached_index[p]["title"], "year": cached_index[p]["year"],
             "category": cached_index[p]["category"], "file_path": p,
             "file_size": cached_index[p]["file_size"]}
            for p in sorted(missing)
        ],
        "changed_items": changed,
    }

    with open(diff_out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)

    log.info(f"Diff report saved: {diff_out.name} | +{len(new)} new | -{len(missing)} missing | ~{len(changed)} changed")

    # Discord notification
    discord_msg = (
        f"📊 **Diff Report — {lib_name}**\n"
        f"Original scan: `{scanned_at}`\n\n"
        f"✅ New: `{len(new)}`  |  ❌ Missing: `{len(missing)}`  |  ⚠️ Changed: `{len(changed)}`\n\n"
    )
    if new:
        discord_msg += "**New items (first 5):**\n" + "\n".join([f"+ {live_index[p]['title']} ({live_index[p]['year']})" for p in list(sorted(new))[:5]]) + "\n"
    if missing:
        discord_msg += "**Missing items (first 5):**\n" + "\n".join([f"- {cached_index[p]['title']} ({cached_index[p]['year']})" for p in list(sorted(missing))[:5]])
    notify_discord(discord_msg, title=f"🔄 Library Diff — {lib_name}", color=0xFFA500)

    print(f"\n  {green('📁 Diff report saved:')} {cyan(str(diff_out))}")
    return diff_out


# ─────────────────────────────────────────
#  2. SEARCH PERSONAL LIBRARY WITH TOTALS
# ─────────────────────────────────────────
def search_library():
    while True:
        print("\n" + divider())
        print(header("  🔍  SEARCH & SCAN LIBRARY"))
        print(divider())
        print(f"  {yellow('[1]')}  {white('Quick Search — search across all libraries (live)')}")
        print(f"  {yellow('[2]')}  {white('Scan a Library — index & categorise all items to JSON')}")
        print(f"  {yellow('[3]')}  {white('Search a Scanned Library — search saved JSON')}")
        print(f"  {yellow('[4]')}  {white('Smart Diff — detect new, missing & changed since last scan')}")
        print(f"  {red('[0]')}  {white('Back')}")
        print(divider())
        choice = input(f"  {cyan('Select an option')}: ").strip()

        if choice == "0":
            break

        # ── QUICK SEARCH ──────────────────────
        elif choice == "1":
            query = input(f"\n  {cyan('🔍 Enter search term')}: ").strip()
            if not query:
                print(yellow("  ⚠️  No search term entered."))
                continue
            log.info(f"Quick search '{query}' — {ACTIVE['name']}")
            print(f"\n{header('  🔍 SEARCH: ' + query)}\n" + divider("-", 52))
            try:
                res = requests.get(f"{ACTIVE['url']}/search", headers=headers(), params={"query": query}, timeout=10)
                res.raise_for_status()
                all_items     = res.json()["MediaContainer"].get("Metadata", [])
                grouped       = {}
                for item in all_items:
                    lt = item.get("librarySectionTitle", "Unknown Library")
                    grouped.setdefault(lt, []).append(item)
                grand_total   = 0
                discord_lines = []
                for lt, items in grouped.items():
                    lib_total    = len(items)
                    grand_total += lib_total
                    print(f"  {magenta('📁 '+lt)} {yellow(f'({lib_total} result'+(' s' if lib_total!=1 else '')+')')}") 
                    discord_lines.append(f"📁 **{lt}** — {lib_total} result{'s' if lib_total!=1 else ''}")
                    log.info(f"Search '{query}' in '{lt}': {lib_total} results")
                    for item in items:
                        print(f"      {cyan('•')} {white(item.get('title','Unknown'))} {blue('('+str(item.get('year','N/A'))+')')} {green('— '+item.get('type','unknown').capitalize())}")
                    print()
                print(f"  {green('✅ Grand Total:')} {yellow(str(grand_total))} result{'s' if grand_total!=1 else ''}")
                log.info(f"Quick search '{query}' total: {grand_total}")
                notify_discord(
                    f"🔍 Query: `{query}`\n\n" + "\n".join(discord_lines) + f"\n\n**Total: {grand_total} results**",
                    title="🔍 Search Results", color=0x5865F2
                )
            except requests.RequestException as e:
                log.error(f"Search error: {e}")
                print(red(f"  ❌ Error: {e}"))

        # ── SCAN LIBRARY ──────────────────────
        elif choice == "2":
            print(f"\n{header('  📡  SELECT LIBRARY TO SCAN')}\n" + divider("-", 52))
            try:
                r = requests.get(f"{ACTIVE['url']}/library/sections", headers=headers(), timeout=10)
                r.raise_for_status()
                sections = r.json()["MediaContainer"].get("Directory", [])
                if not sections:
                    print(red("  No libraries found."))
                    continue
                for i, s in enumerate(sections):
                    print(f"  {yellow(f'[{i+1}]')}  {cyan(s['title'])}  {blue(s['type'].capitalize())}")
                print(f"  {red('[0]')}  {white('Cancel')}")
                sel = input(f"\n  {cyan('Select library')}: ").strip()
                if sel == "0":
                    continue
                try:
                    idx = int(sel) - 1
                    if idx < 0 or idx >= len(sections): raise ValueError
                except ValueError:
                    print(red("  ❌ Invalid selection."))
                    continue
                lib   = sections[idx]
                lib_name = lib["title"]
                lib_type_str = lib["type"]
                confirm = input(f"  {yellow('Scan ' + lib_name + ' (' + lib_type_str + ')? This may take a while. (y/n)')}: ").strip().lower()
                if confirm != "y":
                    continue
                out = scan_and_save_library(lib["key"], lib["title"], lib["type"])
            except requests.RequestException as e:
                log.error(f"Library scan error: {e}")
                print(red(f"  ❌ Error: {e}"))

        # ── SEARCH SCANNED ────────────────────
        elif choice == "3":
            # List available scan files
            scan_files = sorted(LIBRARY_CACHE_DIR.glob("*.json"))
            if not scan_files:
                print(yellow("  ⚠️  No scanned libraries found. Run option [2] first."))
                continue
            print(f"\n{header('  📂  SELECT SCANNED LIBRARY')}\n" + divider("-", 52))
            for i, f in enumerate(scan_files):
                # Read just the summary keys
                try:
                    with open(f) as fh:
                        meta = json.load(fh)
                    info = f"  {yellow(f'[{i+1}]')}  {cyan(meta.get('library',f.stem))}  {blue('('+str(meta.get('total_items','?'))+' items)')}  {green(meta.get('scanned_at',''))}"
                except Exception:
                    info = f"  {yellow(f'[{i+1}]')}  {cyan(f.stem)}"
                print(info)
            print(f"  {red('[0]')}  {white('Cancel')}")
            sel = input(f"\n  {cyan('Select library')}: ").strip()
            if sel == "0":
                continue
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(scan_files): raise ValueError
            except ValueError:
                print(red("  ❌ Invalid selection."))
                continue
            query = input(f"  {cyan('🔍 Enter search term')}: ").strip()
            if not query:
                print(yellow("  ⚠️  No search term entered."))
                continue
            search_cached_library(scan_files[idx], query)

        # ── SMART DIFF ───────────────────────
        elif choice == "4":
            scan_files = sorted(LIBRARY_CACHE_DIR.glob("*.json"))
            # Filter out diff reports
            scan_files = [f for f in scan_files if "_DIFF_" not in f.name]
            if not scan_files:
                print(yellow("  ⚠️  No scanned libraries found. Run option [2] first."))
                continue
            print(f"\n{header('  🔄  SMART DIFF — SELECT LIBRARY SCAN')}\n" + divider("-", 52))
            for i, f in enumerate(scan_files):
                try:
                    with open(f) as fh:
                        meta = json.load(fh)
                    scanned_at = meta.get("scanned_at", "?")
                    total      = meta.get("total_items", "?")
                    lib_name   = meta.get("library", f.stem)
                    print(f"  {yellow(f'[{i+1}]')}  {cyan(lib_name)}  {blue('('+str(total)+' items)')}  {green(scanned_at)}")
                except Exception:
                    print(f"  {yellow(f'[{i+1}]')}  {cyan(f.stem)}")
            print(f"  {red('[0]')}  {white('Cancel')}")
            sel = input(f"\n  {cyan('Select scan to diff against')}: ").strip()
            if sel == "0":
                continue
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(scan_files): raise ValueError
            except ValueError:
                print(red("  ❌ Invalid selection."))
                continue

            # Need to know the library key — fetch sections and match by name
            chosen_file = scan_files[idx]
            try:
                with open(chosen_file) as fh:
                    meta = json.load(fh)
                lib_name_cached = meta.get("library", "")
            except Exception:
                lib_name_cached = ""

            try:
                r = requests.get(f"{ACTIVE['url']}/library/sections", headers=headers(), timeout=10)
                r.raise_for_status()
                sections = r.json()["MediaContainer"].get("Directory", [])
                lib_key  = None
                for s in sections:
                    if s["title"].strip().lower() == lib_name_cached.strip().lower():
                        lib_key = s["key"]
                        break
                if not lib_key:
                    # Fallback: show picker
                    print(f"\n  {yellow('Could not auto-match library. Please select it manually:')}")
                    for i, s in enumerate(sections):
                        print(f"  {yellow(f'[{i+1}]')}  {cyan(s['title'])}")
                    sel2 = input(f"  {cyan('Select library')}: ").strip()
                    try:
                        lib_key = sections[int(sel2)-1]["key"]
                    except Exception:
                        print(red("  ❌ Invalid selection."))
                        continue
            except requests.RequestException as e:
                print(red(f"  ❌ Could not fetch library list: {e}"))
                continue

            diff_library(chosen_file, lib_key)

        else:
            print(red("  ⚠️  Invalid option."))


# ─────────────────────────────────────────
#  3. RECENTLY ADDED
# ─────────────────────────────────────────
def recently_added():
    log.info(f"Recently Added — {ACTIVE['name']}")
    print("\n" + header("  🆕  RECENTLY ADDED (Top 20)") + "\n" + divider("-", 52))
    try:
        res = requests.get(
            f"{ACTIVE['url']}/library/recentlyAdded",
            headers=headers(),
            params={"X-Plex-Container-Start": 0, "X-Plex-Container-Size": 20},
            timeout=10
        )
        res.raise_for_status()
        items = res.json()["MediaContainer"].get("Metadata", [])
        if not items:
            print(yellow("  No recently added items found."))
            return
        discord_lines = []
        for i, item in enumerate(items, 1):
            title     = item.get("title", "Unknown")
            mtype     = item.get("type", "unknown").capitalize()
            lib_title = item.get("librarySectionTitle", "Unknown Library")
            added_at  = item.get("addedAt")
            date_str  = datetime.fromtimestamp(added_at).strftime("%Y-%m-%d %H:%M") if added_at else "N/A"
            print(f"  {cyan(f'{i:>2}.')} {yellow(title)}")
            print(f"       {white('Type:')} {green(mtype)}  {white('Library:')} {magenta(lib_title)}  {white('Added:')} {blue(date_str)}\n")
            log.info(f"Recently added [{i}]: {title} | {mtype} | {lib_title} | {date_str}")
            discord_lines.append(f"`{i:>2}.` **{title}** ({mtype}) — {date_str}")
        notify_discord("\n".join(discord_lines[:10]), title="🆕 Recently Added (Top 10)", color=0x57F287)
    except requests.RequestException as e:
        log.error(f"Recently added error: {e}")
        print(red(f"  ❌ Error: {e}"))

# ─────────────────────────────────────────
#  4. ACTIVE PLAYBACK SESSIONS
# ─────────────────────────────────────────

def _sanitize_reason(msg):
    """
    Sanitize the kill-stream message.
    Blocks URLs, domains, promotional text, and special characters.
    Returns cleaned message or a safe fallback.
    """
    import re
    if not msg or not msg.strip():
        return "Your stream has been stopped by an administrator."

    # Block URLs (http/https/ftp)
    if re.search(r'https?://|ftp://', msg, re.IGNORECASE):
        log.warning(f"Kill stream message blocked — contains URL: {msg!r}")
        return None

    # Block bare domains (e.g. TheyAreHuge.com, site.net, x.org)
    if re.search(r'[\w\-]+\.(com|net|org|io|tv|co|me|info|biz|xyz|gg|app|dev|uk|ca|au)', msg, re.IGNORECASE):
        log.warning(f"Kill stream message blocked — contains domain: {msg!r}")
        return None

    # Block IP addresses
    if re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', msg):
        log.warning(f"Kill stream message blocked — contains IP address: {msg!r}")
        return None

    # Strip any HTML tags
    msg = re.sub(r'<[^>]+>', '', msg)

    # Strip non-printable / control characters
    msg = re.sub(r'[^ -~ -￿]', '', msg)

    # Limit length
    msg = msg.strip()[:200]

    if not msg:
        return "Your stream has been stopped by an administrator."

    return msg


def _kill_stream(session_id, reason="Stream terminated by admin."):
    """
    Terminate a Plex stream.
    Plex API: GET /status/sessions/terminate?sessionId=<Session.id>&reason=<msg>
    Note: Plex uses GET (not DELETE) for this endpoint despite being a destructive action.
    sessionId must be the Session object's 'id' field (e.g. "abc123xyz"),
    NOT the integer sessionKey.
    """
    try:
        res = requests.get(
            f"{ACTIVE['url']}/status/sessions/terminate",
            headers=headers(),
            params={"sessionId": session_id, "reason": reason},
            timeout=10
        )
        # Plex returns 200 or 204 on success
        if res.status_code in (200, 204):
            return True, None
        return False, f"HTTP {res.status_code}"
    except Exception as e:
        return False, str(e)


def playback_sessions():
    while True:
        log.info(f"Playback Sessions — {ACTIVE['name']}")
        print("\n" + header("  ▶️   ACTIVE PLAYBACK SESSIONS") + "\n" + divider("-", 52))
        try:
            res = requests.get(f"{ACTIVE['url']}/status/sessions", headers=headers(), timeout=10)
            res.raise_for_status()
            data     = res.json()["MediaContainer"]
            sessions = data.get("Metadata", [])
            count    = data.get("size", 0)

            if count == 0 or not sessions:
                print(yellow("  No active sessions right now."))
                log.info("No active sessions.")
                break

            print(f"  {green('Active Sessions:')} {yellow(str(count))}\n")
            discord_lines  = []
            session_map    = {}   # display index → session data

            for i, s in enumerate(sessions, 1):
                title        = s.get("title", "Unknown")
                user         = s.get("User", {}).get("title", "Unknown User")
                player       = s.get("Player", {})
                device       = player.get("title", "Unknown Device")
                state        = player.get("state", "unknown").capitalize()
                # Plex terminate endpoint needs Session.id (the string token),
                # NOT the integer sessionKey. Session.id is inside the "Session" object.
                session_id   = s.get("Session", {}).get("id", "") or s.get("sessionKey", "")
                session_key  = s.get("sessionKey", "")  # keep for display only
                duration     = s.get("duration", 0)
                view_off     = s.get("viewOffset", 0)
                progress     = round((view_off / duration) * 100, 1) if duration else 0
                media        = s.get("Media", [{}])[0]
                parts        = media.get("Part", [{}])[0]
                stream_type  = "Direct Play"
                for stream in parts.get("Stream", []):
                    if stream.get("decision") == "transcode":
                        stream_type = "Transcoding"
                        break

                session_map[str(i)] = {
                    "title":       title,
                    "user":        user,
                    "device":      device,
                    "session_id":  session_id,   # used to terminate
                    "session_key": session_key,  # display only
                    "progress":    progress,
                    "stream_type": stream_type,
                }

                print(f"  {cyan(str(i)+'.')} {yellow(title)}")
                print(f"     {white('User:')}     {green(user)}  {white('Device:')} {blue(device)}")
                print(f"     {white('State:')}    {magenta(state)}  {white('Progress:')} {cyan(str(progress)+'%')}  {white('Stream:')} {green(stream_type)}")
                print(f"     {white('Session ID:')} {blue(session_id)}  {white('Key:')} {blue(session_key)}\n")
                log.info(f"Session [{i}]: {title} | {user} | {state} | {progress}% | {stream_type} | key:{session_key}")
                discord_lines.append(f"▶️ **{title}** — {user} | {state} | {progress}% | {stream_type}")

            notify_discord("\n".join(discord_lines), title=f"▶️ Active Sessions ({count})", color=0xFEE75C)

            # ── KILL MENU ─────────────────────────────────────────
            print(divider("-", 52))
            print(f"  {red('[K]')}  {white('Kill a stream')}  {yellow('|')}  {red('[0]')}  {white('Back')}")
            print(divider("-", 52))
            action = input(f"  {cyan('Select an option')}: ").strip().upper()

            if action == "0":
                break

            elif action == "K":
                print("\n" + header("  🔴  KILL STREAM"))
                sel = input(f"  {cyan('Enter session number to kill (or 0 to cancel)')}: ").strip()
                if sel == "0":
                    continue
                if sel not in session_map:
                    print(red("  ❌ Invalid session number."))
                    continue

                target = session_map[sel]

                # Default messages
                default_msgs = [
                    "Your stream has been stopped by an administrator.",
                    "Too many streams. Please try again later.",
                    "Stream limit reached. Please wait before resuming.",
                    "Unauthorized stream detected.",
                    "Server maintenance in progress. Please reconnect shortly.",
                ]

                print(f"\n  {white('Killing stream for:')} {yellow(target['user'])} {white('watching')} {cyan(target['title'])}")
                print(f"\n  {white('Choose a message to send to their screen:')}")
                for mi, msg in enumerate(default_msgs, 1):
                    print(f"  {yellow(f'[{mi}]')}  {white(msg)}")
                print(f"  {yellow('[C]')}  {white('Custom message')}")
                print(f"  {red('[0]')}  {white('Cancel')}")

                msg_choice = input(f"\n  {cyan('Select message')}: ").strip().upper()

                if msg_choice == "0":
                    continue
                elif msg_choice == "C":
                    raw = input(f"  {cyan('Enter custom message')}: ").strip()
                    reason = _sanitize_reason(raw)
                    if reason is None:
                        print(red("  ❌ Message blocked — contains a URL or domain name. Not allowed."))
                        log.warning(f"Custom kill message rejected: {raw!r}")
                        continue
                    if not reason:
                        reason = "Your stream has been stopped by an administrator."
                elif msg_choice.isdigit() and 1 <= int(msg_choice) <= len(default_msgs):
                    reason = default_msgs[int(msg_choice) - 1]
                else:
                    print(red("  ❌ Invalid selection."))
                    continue

                # Confirm before killing
                print(f"\n  {white('Message:')} {yellow(reason)}")
                confirm = input(f"  {red('Confirm kill stream for ' + target['user'] + '? (y/n)')}: ").strip().lower()
                if confirm != "y":
                    print(yellow("  Cancelled."))
                    continue

                ok, err = _kill_stream(target["session_id"], reason)
                if ok:
                    log.info(f"Stream killed: {target['title']} | {target['user']} | reason: {reason}")
                    notify_discord(
                        f"🔴 **Stream Terminated**\n\n"
                        f"👤 User: `{target['user']}`\n"
                        f"🎬 Title: `{target['title']}`\n"
                        f"📱 Device: `{target['device']}`\n"
                        f"💬 Message sent: _{reason}_",
                        title="🔴 Stream Killed",
                        color=0xED4245
                    )
                    print(green(f"\n  ✅ Stream terminated. Message sent to {target['user']}'s screen."))
                else:
                    log.error(f"Kill stream failed: {err}")
                    print(red(f"\n  ❌ Failed to kill stream: {err}"))
            else:
                print(red("  ⚠️  Invalid option."))

        except requests.RequestException as e:
            log.error(f"Playback sessions error: {e}")
            print(red(f"  ❌ Error: {e}"))
            break

# ─────────────────────────────────────────
#  WATCHLIST / FAVORITES
# ─────────────────────────────────────────
def load_watchlist():
    """Load saved watchlist from watchlist.json."""
    if WATCHLIST_FILE.exists():
        try:
            with open(WATCHLIST_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception as e:
            log.warning(f"Could not read watchlist: {e}")
    return []

def save_watchlist(items):
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)

def _watchlist_type_label(t):
    return "🎬 Movie" if t == "movie" else "📺 Show" if t == "show" else "❓ Unknown"

def _print_watchlist(items, show_index=True):
    if not items:
        print(yellow("  Your watchlist is empty."))
        return
    movies = [i for i in items if i.get("type") == "movie"]
    shows  = [i for i in items if i.get("type") == "show"]
    other  = [i for i in items if i.get("type") not in ("movie", "show")]
    offset = 1
    for group_label, group in [("🎬  MOVIES", movies), ("📺  TV SHOWS", shows), ("❓  OTHER", other)]:
        if not group:
            continue
        print(f"\n  {header(group_label)}")
        for entry in group:
            idx_str = f"{cyan(str(offset)+'.')}" if show_index else " "
            notes   = f"  {blue('— ' + entry['notes'])}" if entry.get("notes") else ""
            year    = f" {blue('('+str(entry['year'])+')')}" if entry.get("year") else ""
            status  = f"  {green('[' + entry['status'] + ']')}" if entry.get("status") else ""
            print(f"  {idx_str} {yellow(entry['title'])}{year}{notes}{status}")
            if show_index:
                offset += 1

def watchlist_menu():
    while True:
        items = load_watchlist()
        movies_count = sum(1 for i in items if i.get("type") == "movie")
        shows_count  = sum(1 for i in items if i.get("type") == "show")
        print("\n" + divider())
        print(header("  ⭐  WATCHLIST / FAVORITES"))
        print(cyan(f"         {len(items)} items  ·  {movies_count} movies  ·  {shows_count} shows"))
        print(divider())
        print(f"  {yellow('[1]')}  {white('View Watchlist')}")
        print(f"  {yellow('[2]')}  {white('Add Item Manually')}")
        print(f"  {yellow('[3]')}  {white('Add from Plex Search')}")
        print(f"  {yellow('[4]')}  {white('Edit / Add Notes to Item')}")
        print(f"  {yellow('[5]')}  {white('Remove Item')}")
        print(divider("-", 52))
        print(f"  {magenta('[6]')}  {white('Export for Radarr  (movies → CSV / JSON)')}")
        print(f"  {magenta('[7]')}  {white('Export for Sonarr  (shows  → CSV / JSON)')}")
        print(divider("-", 52))
        print(f"  {red('[0]')}  {white('Back to Main Menu')}")
        print(divider())
        choice = input(f"  {cyan('Select an option')}: ").strip()

        if choice == "0":
            break

        # ── VIEW ────────────────────────────────
        elif choice == "1":
            print("\n" + divider("-", 52))
            print(header("  ⭐  YOUR WATCHLIST"))
            print(divider("-", 52))
            _print_watchlist(items)
            print()

        # ── ADD MANUALLY ────────────────────────
        elif choice == "2":
            print("\n" + header("  ➕  ADD ITEM MANUALLY"))
            title = input(f"  {cyan('Title')}: ").strip()
            if not title:
                print(red("  ❌ Title is required."))
                continue
            print(f"  {white('Type:')}  {yellow('[1]')} Movie   {yellow('[2]')} TV Show")
            t_choice = input(f"  {cyan('Select')}: ").strip()
            media_type = "movie" if t_choice == "1" else "show" if t_choice == "2" else "unknown"
            year_inp   = input(f"  {cyan('Year (optional)')}: ").strip()
            year       = int(year_inp) if year_inp.isdigit() else None
            notes      = input(f"  {cyan('Notes (optional)')}: ").strip()
            status_choices = ["Waiting", "Downloading", "Watching", "Completed", "Dropped"]
            print(f"  {white('Status:')} " + "  ".join(f"{yellow(f'[{i+1}]')} {white(s)}" for i, s in enumerate(status_choices)))
            s_inp   = input(f"  {cyan('Select status (Enter to skip)')}: ").strip()
            status  = status_choices[int(s_inp)-1] if s_inp.isdigit() and 1 <= int(s_inp) <= len(status_choices) else ""
            entry = {
                "title":    title,
                "type":     media_type,
                "year":     year,
                "notes":    notes,
                "status":   status,
                "added_at": datetime.now().strftime("%Y-%m-%d"),
                "source":   "manual",
            }
            items.append(entry)
            save_watchlist(items)
            log.info(f"Watchlist add (manual): {title} [{media_type}]")
            print(green(f"  ✅ '{title}' added to watchlist."))

        # ── ADD FROM PLEX SEARCH ─────────────────
        elif choice == "3":
            query = input(f"\n  {cyan('🔍 Search Plex for title')}: ").strip()
            if not query:
                print(yellow("  ⚠️  No search term entered."))
                continue
            try:
                res = requests.get(f"{ACTIVE['url']}/search", headers=headers(), params={"query": query}, timeout=10)
                res.raise_for_status()
                all_items = res.json()["MediaContainer"].get("Metadata", [])
                # Filter to movies and shows only
                all_items = [i for i in all_items if i.get("type") in ("movie", "show")]
                if not all_items:
                    print(yellow("  No movies or shows found."))
                    continue
                print(f"\n{header('  🔍 RESULTS')}\n" + divider("-", 52))
                for i, item in enumerate(all_items, 1):
                    t    = item.get("type", "")
                    icon = "🎬" if t == "movie" else "📺"
                    print(f"  {yellow(f'[{i}]')}  {icon}  {white(item.get('title','?'))} {blue('('+str(item.get('year','?'))+')')}  {cyan(item.get('librarySectionTitle',''))}")
                print(f"  {red('[0]')}  {white('Cancel')}")
                sel = input(f"\n  {cyan('Select item to add')}: ").strip()
                if sel == "0":
                    continue
                try:
                    idx = int(sel) - 1
                    if idx < 0 or idx >= len(all_items):
                        raise ValueError
                except ValueError:
                    print(red("  ❌ Invalid selection."))
                    continue
                picked = all_items[idx]
                title  = picked.get("title", "Unknown")
                year   = picked.get("year")
                mtype  = picked.get("type", "unknown")
                # Check for duplicate
                dupes = [i for i in items if i["title"].lower() == title.lower() and i.get("type") == mtype]
                if dupes:
                    print(yellow(f"  ⚠️  '{title}' is already in your watchlist."))
                    continue
                notes  = input(f"  {cyan('Notes (optional)')}: ").strip()
                status_choices = ["Waiting", "Downloading", "Watching", "Completed", "Dropped"]
                print(f"  {white('Status:')} " + "  ".join(f"{yellow(f'[{i+1}]')} {white(s)}" for i, s in enumerate(status_choices)))
                s_inp  = input(f"  {cyan('Select status (Enter to skip)')}: ").strip()
                status = status_choices[int(s_inp)-1] if s_inp.isdigit() and 1 <= int(s_inp) <= len(status_choices) else ""
                # Grab TMDB/TVDB id from Plex GUID if available
                guids  = picked.get("Guid", []) or []
                tmdb_id = next((g["id"].split("//")[-1] for g in guids if "tmdb" in g.get("id","")), None)
                tvdb_id = next((g["id"].split("//")[-1] for g in guids if "tvdb" in g.get("id","")), None)
                imdb_id = next((g["id"].split("//")[-1] for g in guids if "imdb" in g.get("id","")), None)
                entry = {
                    "title":    title,
                    "type":     mtype,
                    "year":     year,
                    "notes":    notes,
                    "status":   status,
                    "added_at": datetime.now().strftime("%Y-%m-%d"),
                    "source":   "plex",
                    "tmdb_id":  tmdb_id,
                    "tvdb_id":  tvdb_id,
                    "imdb_id":  imdb_id,
                }
                items.append(entry)
                save_watchlist(items)
                log.info(f"Watchlist add (plex): {title} [{mtype}] tmdb:{tmdb_id} tvdb:{tvdb_id}")
                print(green(f"  ✅ '{title}' added to watchlist."))
            except requests.RequestException as e:
                log.error(f"Watchlist Plex search error: {e}")
                print(red(f"  ❌ Plex search failed: {e}"))

        # ── EDIT ────────────────────────────────
        elif choice == "4":
            if not items:
                print(yellow("  Watchlist is empty."))
                continue
            print("\n" + header("  ✏️   EDIT ITEM"))
            _print_watchlist(items)
            sel = input(f"\n  {cyan('Enter item number to edit')}: ").strip()
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(items):
                    raise ValueError
            except ValueError:
                print(red("  ❌ Invalid selection."))
                continue
            entry = items[idx]
            print(f"\n  {white('Editing:')} {yellow(entry['title'])}")
            new_notes = input(f"  {cyan('Notes [Enter to keep: ' + (entry.get('notes') or 'none') + ']')}: ").strip()
            status_choices = ["Waiting", "Downloading", "Watching", "Completed", "Dropped"]
            print(f"  {white('Status:')} " + "  ".join(f"{yellow(f'[{i+1}]')} {white(s)}" for i, s in enumerate(status_choices)))
            s_inp = input(f"  {cyan('Select new status (Enter to keep: ' + (entry.get('status') or 'none') + ')')}: ").strip()
            if new_notes:
                entry["notes"] = new_notes
            if s_inp.isdigit() and 1 <= int(s_inp) <= len(status_choices):
                entry["status"] = status_choices[int(s_inp)-1]
            items[idx] = entry
            save_watchlist(items)
            log.info(f"Watchlist edited: {entry['title']}")
            print(green(f"  ✅ '{entry['title']}' updated."))

        # ── REMOVE ──────────────────────────────
        elif choice == "5":
            if not items:
                print(yellow("  Watchlist is empty."))
                continue
            print("\n" + header("  🗑️   REMOVE ITEM"))
            _print_watchlist(items)
            sel = input(f"\n  {cyan('Enter item number to remove (or 0 to cancel)')}: ").strip()
            if sel == "0":
                continue
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(items):
                    raise ValueError
            except ValueError:
                print(red("  ❌ Invalid selection."))
                continue
            removed = items.pop(idx)
            save_watchlist(items)
            log.info(f"Watchlist removed: {removed['title']}")
            print(yellow(f"  🗑️  '{removed['title']}' removed from watchlist."))

        # ── EXPORT RADARR ───────────────────────
        elif choice == "6":
            movies = [i for i in items if i.get("type") == "movie"]
            if not movies:
                print(yellow("  No movies in watchlist to export."))
                continue
            _export_watchlist(movies, "radarr")

        # ── EXPORT SONARR ───────────────────────
        elif choice == "7":
            shows = [i for i in items if i.get("type") == "show"]
            if not shows:
                print(yellow("  No TV shows in watchlist to export."))
                continue
            _export_watchlist(shows, "sonarr")

        else:
            print(red("  ⚠️  Invalid option."))


def _export_watchlist(items, target):
    """
    Export watchlist items for Radarr (movies) or Sonarr (shows).
    Produces both a CSV (importable via the *arr List Import feature) and a
    JSON file with full metadata for scripted API imports.
    """
    import csv, re
    label    = "Radarr" if target == "radarr" else "Sonarr"
    id_field = "tmdb_id" if target == "radarr" else "tvdb_id"
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir  = BASE_DIR / "watchlist_exports"
    out_dir.mkdir(exist_ok=True)

    csv_path  = out_dir / f"{target}_import_{ts}.csv"
    json_path = out_dir / f"{target}_import_{ts}.json"

    print(f"\n{header(f'  📤  EXPORT FOR {label.upper()}')}\n" + divider("-", 52))
    print(f"  {white('Items to export:')} {yellow(str(len(items)))}\n")

    # ── CSV ──────────────────────────────────────────────────────────────────
    # Radarr/Sonarr "Custom List" CSV format: Title, Year, TmdbId / TvdbId
    csv_rows = []
    missing_ids = []
    for item in items:
        ext_id = item.get(id_field)
        row = {
            "Title": item["title"],
            "Year":  item.get("year") or "",
            id_field.replace("_id", "Id").replace("tmdb", "TmdbId").replace("tvdb", "TvdbId"): ext_id or "",
            "ImdbId": item.get("imdb_id") or "",
        }
        # Normalise key names to match *arr expectations exactly
        if target == "radarr":
            row = {"Title": item["title"], "Year": item.get("year") or "", "TmdbId": ext_id or "", "ImdbId": item.get("imdb_id") or ""}
        else:
            row = {"Title": item["title"], "Year": item.get("year") or "", "TvdbId": ext_id or "", "ImdbId": item.get("imdb_id") or ""}
        csv_rows.append(row)
        if not ext_id:
            missing_ids.append(item["title"])

    fieldnames = list(csv_rows[0].keys()) if csv_rows else []
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    # ── JSON ─────────────────────────────────────────────────────────────────
    # Full metadata dump — useful for scripted API imports via Radarr/Sonarr REST API
    json_export = {
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target":      target,
        "total":       len(items),
        "items": [
            {
                "title":    i["title"],
                "year":     i.get("year"),
                "tmdb_id":  i.get("tmdb_id"),
                "tvdb_id":  i.get("tvdb_id"),
                "imdb_id":  i.get("imdb_id"),
                "notes":    i.get("notes"),
                "status":   i.get("status"),
                "added_at": i.get("added_at"),
            }
            for i in items
        ],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_export, f, indent=2, ensure_ascii=False)

    log.info(f"Watchlist exported for {label}: {len(items)} items → {csv_path.name} + {json_path.name}")

    # ── DISPLAY SUMMARY ──────────────────────────────────────────────────────
    print(f"  {green('✅ CSV  →')} {cyan(str(csv_path))}")
    print(f"  {green('✅ JSON →')} {cyan(str(json_path))}\n")

    if missing_ids:
        print(f"  {yellow('⚠️  These items have no ' + ('TMDB' if target=='radarr' else 'TVDB') + ' ID (added manually):')} ")
        for t in missing_ids:
            print(f"      {red('•')} {white(t)}")
        print(f"\n  {white('Tip: Add them via')} {cyan('[3] Add from Plex Search')} {white('to auto-populate IDs.')}\n")

    print(divider("-", 52))
    print(f"  {white('How to import into ' + label + ':')}")
    if target == "radarr":
        print(f"  {blue('Movies → Import Lists → Custom CSV → upload the .csv file')}")
        print(f"  {blue('Or use the JSON with the Radarr API: POST /api/v3/movie')}")
    else:
        print(f"  {blue('Series → Import Lists → Custom CSV → upload the .csv file')}")
        print(f"  {blue('Or use the JSON with the Sonarr API: POST /api/v3/series')}")
    print()

    notify_discord(
        f"📤 **Watchlist exported for {label}**\n\n"
        f"🎬 Items: `{len(items)}`\n"
        f"📁 CSV: `{csv_path.name}`\n"
        f"📁 JSON: `{json_path.name}`",
        title=f"📤 {label} Export", color=0x5865F2
    )


# ─────────────────────────────────────────
#  MOVIE DATABASE — HELPERS
# ─────────────────────────────────────────
def load_movie_db():
    if MOVIE_DB_FILE.exists():
        try:
            with open(MOVIE_DB_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"Could not read movie_db: {e}")
    return {}

def save_movie_db(db):
    with open(MOVIE_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def load_movie_db_progress():
    if MOVIE_DB_PROG_FILE.exists():
        try:
            with open(MOVIE_DB_PROG_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_movie_db_progress(data):
    with open(MOVIE_DB_PROG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _tmdb_quota_check(prog):
    """Reset quota counter if date changed, then return updated prog."""
    today = datetime.now().strftime("%Y-%m-%d")
    if prog.get("quota_date") != today:
        prog["quota_date"]  = today
        prog["quota_used"]  = 0
    return prog

def _fetch_plex_movie_list():
    """Return all movie items from all Plex movie libraries, each tagged with _plex_library."""
    all_movies = []
    try:
        r = requests.get(f"{ACTIVE['url']}/library/sections", headers=headers(), timeout=10)
        r.raise_for_status()
        sections   = r.json()["MediaContainer"].get("Directory", [])
        movie_libs = [s for s in sections if s.get("type") == "movie"]
        for lib in movie_libs:
            lib_key   = lib.get("key")
            lib_title = lib.get("title", "?")
            res = requests.get(
                f"{ACTIVE['url']}/library/sections/{lib_key}/all",
                headers=headers(),
                params={"includeGuids": 1},
                timeout=30,
            )
            res.raise_for_status()
            items = res.json()["MediaContainer"].get("Metadata", [])
            for item in items:
                item["_plex_library"] = lib_title
            all_movies.extend(items)
            log.info(f"Fetched {len(items)} movies from library '{lib_title}'")
    except Exception as e:
        log.error(f"_fetch_plex_movie_list error: {e}")
    return all_movies

def _extract_guids(item):
    """Extract TMDB and IMDB IDs from a Plex Guid list."""
    tmdb_id = None
    imdb_id = None
    for g in item.get("Guid", []):
        gid = g.get("id", "")
        if gid.startswith("tmdb://"):
            tmdb_id = gid.split("tmdb://")[-1]
        elif gid.startswith("imdb://"):
            imdb_id = gid.split("imdb://")[-1]
    return tmdb_id, imdb_id

def _schedule_movie_db_scan():
    """Register movie_db_scan.py with the OS scheduler for tomorrow."""
    import shutil, random
    from datetime import timedelta
    h, m     = random.randint(0, 5), random.randint(0, 59)
    run_time = f"{h:02d}:{m:02d}"
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    ep = shutil.which("plex-movie-scan")
    cmd = ep if ep else f"{sys.executable} \"{str(BASE_DIR / 'movie_db_scan.py')}\""

    if platform.system() == "Windows":
        start_date = datetime.now().strftime("%m/%d/%Y")
        subprocess.run(
            ["schtasks", "/create", "/tn", MOVIE_DB_TASK_NAME,
             "/tr", cmd, "/sc", "ONCE", "/sd", start_date, "/st", run_time, "/f"],
            capture_output=True,
        )
    else:
        cron_line = f"{m} {h} * * * {cmd}  # {MOVIE_DB_TASK_NAME}"
        result    = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing  = result.stdout if result.returncode == 0 else ""
        lines     = [l for l in existing.splitlines() if MOVIE_DB_TASK_NAME not in l]
        lines.append(cron_line)
        subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True)

    log.info(f"Movie DB scan scheduled: {tomorrow} {run_time}")
    return f"{tomorrow} {run_time}"

def _get_movie_db_logger():
    """Return (or create) a dedicated logger for the movie DB scan."""
    MOVIE_DB_LOG_DIR.mkdir(exist_ok=True)
    db_log = logging.getLogger("movie_db")
    if not db_log.handlers:
        h = logging.FileHandler(MOVIE_DB_LOG_DIR / "movie_db_scan.log", encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
        db_log.addHandler(h)
        db_log.setLevel(logging.INFO)
    return db_log

def _show_movie_db_status(prog, db):
    """Print a formatted status block for the movie database scan."""
    status   = prog.get("status", "idle")
    total    = prog.get("total_plex_movies", 0)
    done     = prog.get("processed_count", 0)
    failed   = prog.get("failed_count", 0)
    pending  = len(prog.get("pending_rating_keys", []))
    q_used   = prog.get("quota_used", 0)
    q_date   = prog.get("quota_date", "N/A")
    next_run = prog.get("next_scheduled_run", "Not scheduled")
    started  = prog.get("scan_started_at", "N/A")
    sc       = green if status == "complete" else yellow if status == "paused" else cyan
    print(f"\n{header('  📊  MOVIE DB STATUS')}\n" + divider("-", 52))
    print(f"  {white('Status:')}           {sc(status)}")
    print(f"  {white('Scan started:')}     {blue(started)}")
    print(f"  {white('Total in Plex:')}    {yellow(str(total))}")
    print(f"  {white('Processed:')}        {green(str(done))}")
    print(f"  {white('Failed / skipped:')} {red(str(failed))}")
    print(f"  {white('Pending:')}          {yellow(str(pending))}")
    print(f"  {white('In database:')}      {cyan(str(len(db)))}")
    print(f"  {white('TMDB calls today:')} {yellow(str(q_used))} / {str(TMDB_DAILY_LIMIT)}  {blue(f'({q_date})')}")
    print(f"  {white('Next scheduled:')}   {blue(next_run)}")
    print(f"  {white('Log folder:')}       {green(str(MOVIE_DB_LOG_DIR))}")
    print()

def _run_movie_db_scan_interactive():
    """Interactive movie DB enrichment scan — runs from inside the menu."""
    api_keys = load_api_keys()
    tmdb_key = api_keys.get("tmdb_key", "")
    omdb_key = api_keys.get("omdb_key", "")
    if not tmdb_key:
        print(red("  ❌ TMDB API key required. Go to Movie Search List → [7] API Keys."))
        return

    db_log = _get_movie_db_logger()
    db     = load_movie_db()
    prog   = load_movie_db_progress()
    prog   = _tmdb_quota_check(prog)

    quota_remaining = TMDB_DAILY_LIMIT - prog.get("quota_used", 0)
    if quota_remaining <= 0:
        print(red(f"  ❌ TMDB daily quota exhausted ({TMDB_DAILY_LIMIT} calls used). Resets tomorrow."))
        next_run = _schedule_movie_db_scan()
        prog["next_scheduled_run"] = next_run
        prog["status"] = "paused"
        save_movie_db_progress(prog)
        print(yellow(f"  ⏰ Scan scheduled to continue: {next_run}"))
        return

    # Get pending list — start fresh if empty
    pending_keys = prog.get("pending_rating_keys", [])
    if not pending_keys:
        print(cyan("  📡 Fetching all movies from Plex libraries..."))
        plex_movies = _fetch_plex_movie_list()
        if not plex_movies:
            print(red("  ❌ No movies found in Plex libraries. Check server connection."))
            return
        pending_keys = [str(m.get("ratingKey", "")) for m in plex_movies if m.get("ratingKey")]
        prog.update({
            "pending_rating_keys": pending_keys,
            "total_plex_movies":   len(pending_keys),
            "processed_count":     0,
            "failed_count":        0,
            "status":              "scanning",
            "scan_started_at":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "next_scheduled_run":  None,
        })
        save_movie_db_progress(prog)
        print(green(f"  ✅ Found {len(pending_keys)} movies across all Plex movie libraries."))
        notify_discord(
            f"📀 **Movie DB Scan Started**\n\n"
            f"🎬 Total movies: `{len(pending_keys)}`\n"
            f"🔑 TMDB quota remaining: `{quota_remaining}`",
            title="📀 Movie DB Scan — Started", color=0x57F287,
        )
        db_log.info(f"Scan started — {len(pending_keys)} movies to process")
    else:
        print(yellow(f"  ▶️  Resuming — {len(pending_keys)} movies remaining."))
        notify_discord(
            f"▶️ **Movie DB Scan Resumed**\n\n"
            f"🎬 Remaining: `{len(pending_keys)}`\n"
            f"🔑 TMDB quota remaining: `{quota_remaining}`",
            title="📀 Movie DB Scan — Resumed", color=0xFEE75C,
        )
        db_log.info(f"Scan resumed — {len(pending_keys)} movies remaining")

    print(divider("-", 52))
    processed_this_run = 0
    failed_this_run    = 0

    while pending_keys and (TMDB_DAILY_LIMIT - prog.get("quota_used", 0)) > 0:
        rating_key = pending_keys[0]
        plex_item  = _fetch_full_item(rating_key)
        if not plex_item:
            pending_keys.pop(0)
            failed_this_run += 1
            prog["failed_count"] = prog.get("failed_count", 0) + 1
            db_log.warning(f"Could not fetch Plex item ratingKey={rating_key}")
            continue

        tmdb_id, imdb_id = _extract_guids(plex_item)
        if not tmdb_id:
            pending_keys.pop(0)
            prog["processed_count"] = prog.get("processed_count", 0) + 1
            db_log.info(f"No TMDB ID — skipped: {plex_item.get('title','?')}")
            continue

        # Skip if already enriched today
        if str(tmdb_id) in db and db[str(tmdb_id)].get("last_updated") == datetime.now().strftime("%Y-%m-%d"):
            pending_keys.pop(0)
            prog["processed_count"] = prog.get("processed_count", 0) + 1
            continue

        details = _tmdb_details(tmdb_id, tmdb_key)
        prog["quota_used"] = prog.get("quota_used", 0) + 1
        if not details:
            pending_keys.pop(0)
            failed_this_run += 1
            prog["failed_count"] = prog.get("failed_count", 0) + 1
            db_log.warning(f"TMDB details failed — ratingKey={rating_key} tmdb={tmdb_id}")
            save_movie_db_progress(prog)
            continue

        eff_imdb = details.get("imdb_id") or imdb_id or "N/A"
        ratings  = {"imdb_rating": "N/A", "rt_rating": "N/A"}
        if omdb_key and eff_imdb and eff_imdb != "N/A":
            ratings = _omdb_ratings(eff_imdb, omdb_key)

        db[str(tmdb_id)] = {
            "tmdb_id":        str(tmdb_id),
            "imdb_id":        eff_imdb,
            "title":          details["title"],
            "year":           details["year"],
            "runtime":        details["runtime"],
            "mpaa_rating":    details["mpaa_rating"],
            "imdb_rating":    ratings["imdb_rating"],
            "rt_rating":      ratings["rt_rating"],
            "description":    details["description"],
            "plex_rating_key": str(rating_key),
            "plex_library":   plex_item.get("_plex_library", "N/A"),
            "plex_server":    ACTIVE["name"],
            "last_updated":   datetime.now().strftime("%Y-%m-%d"),
        }
        pending_keys.pop(0)
        prog["processed_count"] = prog.get("processed_count", 0) + 1
        processed_this_run += 1
        db_log.info(f"Enriched: {details['title']} ({details['year']}) tmdb:{tmdb_id} imdb:{eff_imdb} IMDB:{ratings['imdb_rating']} RT:{ratings['rt_rating']}")
        print(f"  {green('✅')} {white(details['title'][:38]):<40} {blue(str(details['year']))}  "
              f"{yellow('IMDB:')} {ratings['imdb_rating']}  {green('RT:')} {ratings['rt_rating']}  {magenta(details['mpaa_rating'])}")

        if processed_this_run % 10 == 0:
            save_movie_db(db)
            prog["pending_rating_keys"] = pending_keys
            save_movie_db_progress(prog)

    # Final save
    save_movie_db(db)
    prog["pending_rating_keys"] = pending_keys
    save_movie_db_progress(prog)
    print(divider("-", 52))

    if not pending_keys:
        prog["status"] = "complete"
        prog["next_scheduled_run"] = None
        save_movie_db_progress(prog)
        msg = (f"✅ **Movie DB Scan Complete!**\n\n"
               f"🎬 This run: `{processed_this_run}` processed, `{failed_this_run}` failed\n"
               f"📀 Total in database: `{len(db)}`")
        db_log.info(f"Scan complete — processed:{processed_this_run} failed:{failed_this_run} db_size:{len(db)}")
        print(f"  {green('✅ Scan complete!')}  {white(str(processed_this_run))} processed, {red(str(failed_this_run))} failed.")
        notify_discord(msg, title="📀 Movie DB Scan — Complete", color=0x57F287)
    else:
        next_run = _schedule_movie_db_scan()
        prog["status"] = "paused"
        prog["next_scheduled_run"] = next_run
        save_movie_db_progress(prog)
        msg = (f"⏸️ **Movie DB Scan Paused — Daily Quota Reached**\n\n"
               f"🎬 This run: `{processed_this_run}` processed\n"
               f"⏳ Remaining: `{len(pending_keys)}`\n"
               f"⏰ Next run scheduled: `{next_run}`")
        db_log.info(f"Scan paused (quota) — this_run:{processed_this_run} remaining:{len(pending_keys)} next:{next_run}")
        print(f"  {yellow('⏸️  Daily quota reached.')} {white(str(processed_this_run))} processed this run, {yellow(str(len(pending_keys)))} remaining.")
        print(f"  {cyan('Next run scheduled:')} {next_run}")
        notify_discord(msg, title="📀 Movie DB Scan — Paused", color=0xFEE75C)

# ─────────────────────────────────────────
#  MOVIE DATABASE MENU
# ─────────────────────────────────────────
def movie_db_menu():
    while True:
        db      = load_movie_db()
        prog    = load_movie_db_progress()
        prog    = _tmdb_quota_check(prog)
        status  = prog.get("status", "idle")
        pending = len(prog.get("pending_rating_keys", []))
        q_rem   = TMDB_DAILY_LIMIT - prog.get("quota_used", 0)
        next_run = prog.get("next_scheduled_run")
        sc      = green if status == "complete" else yellow if status == "paused" else cyan

        print("\n" + divider())
        print(header("  📀  MOVIE DATABASE"))
        print(cyan(f"         {len(db)} enriched movies  ·  Status: {sc(status)}  ·  TMDB quota: {q_rem}/{TMDB_DAILY_LIMIT} today"))
        if pending:
            print(yellow(f"         {pending} movies pending enrichment"))
        if next_run:
            print(blue(f"         Next scheduled scan: {next_run}"))
        print(divider())
        print(f"  {yellow('[1]')}  {white('Search Database')}")
        print(f"  {yellow('[2]')}  {white('Build / Update Database from Plex')}  {blue('(enriches with TMDB + OMDB)')}")
        print(f"  {yellow('[3]')}  {white('Scan Status')}")
        print(f"  {yellow('[4]')}  {white('Schedule Continuation')}")
        print(f"  {red('[0]')}  {white('Back')}")
        print(divider())
        choice = input(f"  {cyan('Select')}: ").strip()

        if choice == "0":
            break

        # ── SEARCH DATABASE ─────────────────────
        elif choice == "1":
            if not db:
                print(yellow("  Database is empty. Run [2] to build it first."))
                continue
            query = input(f"\n  {cyan('🔍 Search movie database')}: ").strip().lower()
            if not query:
                continue
            matches = [(k, v) for k, v in db.items() if query in v.get("title", "").lower()]
            if not matches:
                print(yellow(f"  No results for '{query}'."))
                continue
            display = matches[:20]
            print(f"\n{header('  🔍 DATABASE RESULTS')}\n" + divider("-", 52))
            for i, (tid, m) in enumerate(display, 1):
                yr = m.get("year", "?")
                print(f"  {yellow(f'[{i}]')}  {white(m.get('title','?'))}  {blue(f'({yr})')}"
                      f"  {yellow('IMDB:')} {m.get('imdb_rating','N/A')}  {green('RT:')} {m.get('rt_rating','N/A')}"
                      f"  {magenta(m.get('mpaa_rating','N/A'))}  {white(m.get('runtime','N/A'))}")
            print(f"  {red('[0]')}  {white('Cancel')}")
            sel = input(f"\n  {cyan('Add to Movie List (number) or 0 to cancel')}: ").strip()
            if sel == "0":
                continue
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(display):
                    raise ValueError
            except ValueError:
                print(red("  ❌ Invalid selection."))
                continue
            tid, m       = display[idx]
            movie_list   = load_movie_list()
            dupes        = [x for x in movie_list if str(x.get("tmdb_id", "")) == str(tid)]
            if dupes:
                print(yellow(f"  ⚠️  '{m['title']}' already in Movie List ({dupes[0]['id']})."))
                continue
            new_id = _next_movie_id(movie_list)
            entry  = {
                "id":          new_id,
                "title":       m.get("title", "N/A"),
                "year":        m.get("year", "N/A"),
                "tmdb_id":     str(tid),
                "imdb_id":     m.get("imdb_id", "N/A"),
                "mpaa_rating": m.get("mpaa_rating", "N/A"),
                "runtime":     m.get("runtime", "N/A"),
                "imdb_rating": m.get("imdb_rating", "N/A"),
                "rt_rating":   m.get("rt_rating", "N/A"),
                "description": m.get("description", "N/A"),
                "added_at":    datetime.now().strftime("%Y-%m-%d"),
            }
            movie_list.append(entry)
            save_movie_list(movie_list)
            log.info(f"Added to Movie List from DB: {entry['title']} [{new_id}]")
            print(green(f"  ✅ '{entry['title']}' added as {new_id}."))

        # ── BUILD / UPDATE ──────────────────────
        elif choice == "2":
            _run_movie_db_scan_interactive()

        # ── STATUS ──────────────────────────────
        elif choice == "3":
            _show_movie_db_status(prog, db)

        # ── SCHEDULE ────────────────────────────
        elif choice == "4":
            if pending == 0:
                print(yellow("  No pending movies. Database is up to date or scan has not started."))
                continue
            next_run = _schedule_movie_db_scan()
            prog["next_scheduled_run"] = next_run
            save_movie_db_progress(prog)
            print(green(f"  ✅ Scan scheduled for {next_run}"))
            notify_discord(
                f"⏰ **Movie DB Scan Scheduled**\n\nNext run: `{next_run}`\nPending: `{pending}` movies",
                title="📀 Movie DB Scheduler", color=0xFEE75C,
            )

        else:
            print(red("  ⚠️  Invalid option."))


# ─────────────────────────────────────────
#  MOVIE LIST — HELPERS
# ─────────────────────────────────────────
def load_movie_list():
    if MOVIE_LIST_FILE.exists():
        try:
            with open(MOVIE_LIST_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception as e:
            log.warning(f"Could not read movie list: {e}")
    return []

def save_movie_list(data):
    with open(MOVIE_LIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_api_keys():
    if API_KEYS_FILE.exists():
        try:
            with open(API_KEYS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_api_keys(data):
    with open(API_KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_radarr_creds():
    if RADARR_FILE.exists():
        try:
            with open(RADARR_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_radarr_creds(data):
    with open(RADARR_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _next_movie_id(items):
    """Generate next internal movie ID in ms000001 format."""
    ids = []
    for item in items:
        mid = item.get("id", "")
        if mid.startswith("ms") and mid[2:].isdigit():
            ids.append(int(mid[2:]))
    return f"ms{(max(ids) + 1):06d}" if ids else "ms000001"

def _tmdb_search(query, tmdb_key):
    """Search TMDB for movies. Returns list of results or None on error."""
    try:
        res = requests.get(
            "https://api.themoviedb.org/3/search/movie",
            params={"api_key": tmdb_key, "query": query, "language": "en-US"},
            timeout=10,
        )
        res.raise_for_status()
        return res.json().get("results", [])
    except Exception as e:
        log.warning(f"TMDB search error: {e}")
        return None

def _tmdb_details(tmdb_id, tmdb_key):
    """Fetch full TMDB movie details including runtime and MPAA rating."""
    try:
        res = requests.get(
            f"https://api.themoviedb.org/3/movie/{tmdb_id}",
            params={"api_key": tmdb_key, "language": "en-US", "append_to_response": "release_dates"},
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()
        # Extract MPAA rating from US theatrical or digital release
        mpaa = "N/A"
        for country in data.get("release_dates", {}).get("results", []):
            if country.get("iso_3166_1") == "US":
                for rel in country.get("release_dates", []):
                    cert = rel.get("certification", "").strip()
                    if cert and rel.get("type") in (3, 4):
                        mpaa = cert
                        break
                break
        runtime_min = data.get("runtime") or 0
        return {
            "title":       data.get("title", "N/A"),
            "year":        (data.get("release_date") or "")[:4] or "N/A",
            "description": data.get("overview") or "N/A",
            "runtime":     f"{runtime_min} min" if runtime_min else "N/A",
            "mpaa_rating": mpaa,
            "imdb_id":     data.get("imdb_id") or "N/A",
            "tmdb_id":     str(tmdb_id),
        }
    except Exception as e:
        log.warning(f"TMDB details error: {e}")
        return None

def _omdb_ratings(imdb_id, omdb_key):
    """Fetch IMDB and Rotten Tomatoes ratings from OMDB."""
    if not imdb_id or imdb_id == "N/A":
        return {"imdb_rating": "N/A", "rt_rating": "N/A"}
    try:
        res = requests.get(
            "http://www.omdbapi.com/",
            params={"apikey": omdb_key, "i": imdb_id},
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()
        if data.get("Response") == "False":
            return {"imdb_rating": "N/A", "rt_rating": "N/A"}
        rt = "N/A"
        for r in data.get("Ratings", []):
            if r.get("Source") == "Rotten Tomatoes":
                rt = r.get("Value", "N/A")
                break
        return {"imdb_rating": data.get("imdbRating") or "N/A", "rt_rating": rt}
    except Exception as e:
        log.warning(f"OMDB ratings error: {e}")
        return {"imdb_rating": "N/A", "rt_rating": "N/A"}

def _print_movie_list(items):
    """Display movie list in a readable format."""
    if not items:
        print(yellow("  No movies in your list yet."))
        return
    print()
    for i, m in enumerate(items, 1):
        title   = m.get("title", "?")
        year    = m.get("year", "N/A")
        mid     = m.get("id", "?")
        imdb    = m.get("imdb_rating", "N/A")
        rt      = m.get("rt_rating", "N/A")
        mpaa    = m.get("mpaa_rating", "N/A")
        runtime = m.get("runtime", "N/A")
        print(f"  {yellow(f'[{i}]')}  {cyan(mid)}  {white(title)}  {blue(f'({year})')}")
        print(f"        {yellow('IMDB:')} {imdb}  {green('RT:')} {rt}  {magenta(mpaa)}  {white(runtime)}")
    print()

# ─────────────────────────────────────────
#  MOVIE LIST MENU
# ─────────────────────────────────────────
def movie_list_menu():
    while True:
        items      = load_movie_list()
        api_keys   = load_api_keys()
        radarr     = load_radarr_creds()
        count      = len(items)
        tmdb_set   = "✅" if api_keys.get("tmdb_key") else "❌"
        omdb_set   = "✅" if api_keys.get("omdb_key") else "❌"
        radarr_set = "✅" if radarr.get("url") and radarr.get("api_key") else "❌"
        print("\n" + divider())
        print(header("  🎬   MOVIE SEARCH LIST"))
        print(cyan(f"         {count} movie{'s' if count != 1 else ''} in list  ·  TMDB {tmdb_set}  OMDB {omdb_set}  Radarr {radarr_set}"))
        print(divider())
        print(f"  {yellow('[1]')}  {white('View List')}")
        print(f"  {yellow('[2]')}  {white('Add Movie')}")
        print(f"  {yellow('[3]')}  {white('Edit Movie')}")
        print(f"  {yellow('[4]')}  {white('Remove Movie')}")
        print(divider("-", 52))
        print(f"  {magenta('[5]')}  {white('Send to Radarr')}")
        print(f"  {magenta('[6]')}  {white('Radarr Settings')}")
        print(f"  {magenta('[7]')}  {white('API Keys  (TMDB / OMDB)')}")
        db_count = len(load_movie_db())
        print(f"  {magenta('[8]')}  {white('Movie Database')}  {blue(f'({db_count} enriched movies)')}")
        print(divider("-", 52))
        print(f"  {red('[0]')}  {white('Back to Main Menu')}")
        print(divider())
        choice = input(f"  {cyan('Select an option')}: ").strip()

        if choice == "0":
            break

        # ── VIEW ────────────────────────────────
        elif choice == "1":
            print("\n" + divider("-", 52))
            print(header("  🎬  YOUR MOVIE LIST"))
            print(divider("-", 52))
            _print_movie_list(items)

        # ── ADD MOVIE ───────────────────────────
        elif choice == "2":
            tmdb_key = api_keys.get("tmdb_key", "")
            if not tmdb_key:
                print(red("  ❌ TMDB API key not set. Go to [7] API Keys first."))
                continue
            query = input(f"\n  {cyan('🔍 Search TMDB for movie title')}: ").strip()
            if not query:
                print(yellow("  ⚠️  No search term entered."))
                continue
            print(cyan("  Searching TMDB..."))
            results = _tmdb_search(query, tmdb_key)
            if results is None:
                print(red("  ❌ TMDB search failed. Check your API key and connection."))
                continue
            if not results:
                print(yellow("  No results found."))
                continue
            display = results[:10]
            print(f"\n{header('  🔍 TMDB RESULTS')}\n" + divider("-", 52))
            for i, r in enumerate(display, 1):
                yr = (r.get("release_date") or "")[:4] or "?"
                print(f"  {yellow(f'[{i}]')}  {white(r.get('title','?'))}  {blue(f'({yr})')}")
            print(f"  {red('[0]')}  {white('Cancel')}")
            sel = input(f"\n  {cyan('Select movie')}: ").strip()
            if sel == "0":
                continue
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(display):
                    raise ValueError
            except ValueError:
                print(red("  ❌ Invalid selection."))
                continue
            picked  = display[idx]
            tmdb_id = picked.get("id")
            print(cyan("  Fetching details from TMDB..."))
            details = _tmdb_details(tmdb_id, tmdb_key)
            if not details:
                print(red("  ❌ Could not fetch movie details."))
                continue
            omdb_key = api_keys.get("omdb_key", "")
            ratings  = {"imdb_rating": "N/A", "rt_rating": "N/A"}
            if omdb_key and details.get("imdb_id") and details["imdb_id"] != "N/A":
                print(cyan("  Fetching ratings from OMDB..."))
                ratings = _omdb_ratings(details["imdb_id"], omdb_key)
            dupes = [m for m in items if str(m.get("tmdb_id", "")) == str(tmdb_id)]
            if dupes:
                print(yellow(f"  ⚠️  '{details['title']}' is already in your list ({dupes[0]['id']})."))
                continue
            new_id = _next_movie_id(items)
            print(f"\n{divider('-', 52)}")
            print(f"  {cyan('ID:')}          {new_id}")
            print(f"  {cyan('Title:')}       {details['title']} ({details['year']})")
            print(f"  {cyan('TMDB ID:')}     {tmdb_id}")
            print(f"  {cyan('IMDB ID:')}     {details['imdb_id']}")
            print(f"  {cyan('Rating:')}      {details['mpaa_rating']}")
            print(f"  {cyan('Runtime:')}     {details['runtime']}")
            print(f"  {cyan('IMDB Score:')}  {ratings['imdb_rating']}")
            print(f"  {cyan('RT Score:')}    {ratings['rt_rating']}")
            print(f"  {cyan('Overview:')}    {details['description'][:120]}{'...' if len(details['description']) > 120 else ''}")
            print(divider("-", 52))
            confirm = input(f"  {green('Save to movie list? (y/n)')}: ").strip().lower()
            if confirm != "y":
                print(yellow("  Cancelled."))
                continue
            entry = {
                "id":          new_id,
                "title":       details["title"],
                "year":        details["year"],
                "tmdb_id":     str(tmdb_id),
                "imdb_id":     details["imdb_id"],
                "mpaa_rating": details["mpaa_rating"],
                "runtime":     details["runtime"],
                "imdb_rating": ratings["imdb_rating"],
                "rt_rating":   ratings["rt_rating"],
                "description": details["description"],
                "added_at":    datetime.now().strftime("%Y-%m-%d"),
            }
            items.append(entry)
            save_movie_list(items)
            log.info(f"Movie list add: {entry['title']} ({entry['year']}) [{entry['id']}] tmdb:{tmdb_id}")
            print(green(f"  ✅ '{entry['title']}' added as {entry['id']}."))

        # ── EDIT ────────────────────────────────
        elif choice == "3":
            if not items:
                print(yellow("  Movie list is empty."))
                continue
            _print_movie_list(items)
            sel = input(f"  {cyan('Enter movie number to edit')}: ").strip()
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(items):
                    raise ValueError
            except ValueError:
                print(red("  ❌ Invalid selection."))
                continue
            entry = items[idx]
            print(f"\n  {white('Editing:')} {yellow(entry['title'])}  {cyan(entry['id'])}")
            print(f"  {white('Editable fields:')} title · year · mpaa_rating · imdb_rating · rt_rating · runtime · description")
            field = input(f"  {cyan('Field to edit')}: ").strip().lower()
            if field not in ("title", "year", "mpaa_rating", "imdb_rating", "rt_rating", "runtime", "description"):
                print(red("  ❌ Unknown field."))
                continue
            cur     = entry.get(field, "N/A")
            new_val = input(f"  {cyan(f'New value [{cur}]')}: ").strip()
            if new_val:
                entry[field] = new_val
                items[idx]   = entry
                save_movie_list(items)
                log.info(f"Movie list edit: {entry['id']} {field} → {new_val}")
                print(green(f"  ✅ '{entry['title']}' updated."))
            else:
                print(yellow("  No change made."))

        # ── REMOVE ──────────────────────────────
        elif choice == "4":
            if not items:
                print(yellow("  Movie list is empty."))
                continue
            _print_movie_list(items)
            sel = input(f"  {cyan('Enter movie number to remove (or 0 to cancel)')}: ").strip()
            if sel == "0":
                continue
            try:
                idx = int(sel) - 1
                if idx < 0 or idx >= len(items):
                    raise ValueError
            except ValueError:
                print(red("  ❌ Invalid selection."))
                continue
            removed = items.pop(idx)
            save_movie_list(items)
            log.info(f"Movie list remove: {removed['title']} [{removed['id']}]")
            print(yellow(f"  🗑️  '{removed['title']}' removed."))

        # ── SEND TO RADARR ──────────────────────
        elif choice == "5":
            if not items:
                print(yellow("  Movie list is empty."))
                continue
            if not radarr.get("url") or not radarr.get("api_key"):
                print(red("  ❌ Radarr not configured. Go to [6] Radarr Settings first."))
                continue
            print(f"\n{header('  📡  SEND TO RADARR')}\n" + divider("-", 52))
            _print_movie_list(items)
            print(f"  {yellow('[A]')}  {white('Send ALL movies')}")
            print(f"  {red('[0]')}  {white('Cancel')}")
            sel = input(f"  {cyan('Enter movie number or A for all')}: ").strip().upper()
            if sel == "0":
                continue
            if sel == "A":
                targets = items
            else:
                try:
                    idx = int(sel) - 1
                    if idx < 0 or idx >= len(items):
                        raise ValueError
                    targets = [items[idx]]
                except ValueError:
                    print(red("  ❌ Invalid selection."))
                    continue
            radarr_url  = radarr["url"].rstrip("/")
            radarr_key  = radarr["api_key"]
            qp_id       = radarr.get("quality_profile_id", 1)
            root_folder = radarr.get("root_folder_path", "/movies")
            r_headers   = {"X-Api-Key": radarr_key, "Content-Type": "application/json"}
            sent = 0
            for movie in targets:
                if not movie.get("tmdb_id"):
                    print(yellow(f"  ⚠️  Skipping '{movie['title']}' — no TMDB ID."))
                    continue
                payload = {
                    "title":            movie["title"],
                    "year":             int(movie.get("year") or 0),
                    "tmdbId":           int(movie["tmdb_id"]),
                    "qualityProfileId": int(qp_id),
                    "rootFolderPath":   root_folder,
                    "monitored":        True,
                    "addOptions":       {"searchForMovie": True},
                }
                try:
                    res = requests.post(
                        f"{radarr_url}/api/v3/movie",
                        json=payload,
                        headers=r_headers,
                        timeout=10,
                    )
                    if res.status_code in (200, 201):
                        print(green(f"  ✅ '{movie['title']}' sent to Radarr."))
                        log.info(f"Radarr add: {movie['title']} tmdb:{movie['tmdb_id']}")
                        sent += 1
                    elif res.status_code == 400 and "already" in res.text.lower():
                        print(yellow(f"  ⚠️  '{movie['title']}' already exists in Radarr."))
                    else:
                        print(red(f"  ❌ '{movie['title']}' failed: HTTP {res.status_code}"))
                        log.warning(f"Radarr add failed: {movie['title']} — {res.status_code} {res.text[:100]}")
                except Exception as e:
                    print(red(f"  ❌ '{movie['title']}' error: {e}"))
                    log.error(f"Radarr send error: {e}")
            print(f"\n  {green(f'Sent {sent} of {len(targets)} movie(s) to Radarr.')}")

        # ── RADARR SETTINGS ─────────────────────
        elif choice == "6":
            while True:
                radarr   = load_radarr_creds()
                cur_url  = radarr.get("url", "")
                cur_key  = radarr.get("api_key", "")
                cur_qp   = radarr.get("quality_profile_id", 1)
                cur_rf   = radarr.get("root_folder_path", "/movies")
                print(f"\n{header('  ⚙️   RADARR SETTINGS')}\n" + divider("-", 52))
                print(f"  {white('URL:')}               {cyan(cur_url or 'Not set')}")
                print(f"  {white('API Key:')}           {cyan(cur_key[:8] + '...' if cur_key else 'Not set')}")
                print(f"  {white('Quality Profile ID:')} {cyan(str(cur_qp))}")
                print(f"  {white('Root Folder Path:')}  {cyan(cur_rf)}")
                print(divider("-", 52))
                print(f"  {yellow('[1]')}  {white('Set URL and API Key')}")
                print(f"  {yellow('[2]')}  {white('Set Quality Profile ID')}")
                print(f"  {yellow('[3]')}  {white('Set Root Folder Path')}")
                print(f"  {yellow('[4]')}  {white('Test Connection  (shows profiles & folders)')}")
                print(f"  {red('[0]')}  {white('Back')}")
                sub = input(f"  {cyan('Select')}: ").strip()
                if sub == "0":
                    break
                elif sub == "1":
                    new_url = input(f"  {cyan('Radarr URL (e.g. http://192.168.1.x:7878)')}: ").strip()
                    new_key = input(f"  {cyan('Radarr API Key')}: ").strip()
                    if new_url:
                        radarr["url"] = new_url.rstrip("/")
                    if new_key:
                        radarr["api_key"] = new_key
                    save_radarr_creds(radarr)
                    print(green("  ✅ Radarr credentials saved."))
                elif sub == "2":
                    new_qp = input(f"  {cyan(f'Quality Profile ID [{cur_qp}]')}: ").strip()
                    if new_qp.isdigit():
                        radarr["quality_profile_id"] = int(new_qp)
                        save_radarr_creds(radarr)
                        print(green("  ✅ Quality Profile ID saved."))
                elif sub == "3":
                    new_rf = input(f"  {cyan(f'Root Folder Path [{cur_rf}]')}: ").strip()
                    if new_rf:
                        radarr["root_folder_path"] = new_rf
                        save_radarr_creds(radarr)
                        print(green("  ✅ Root Folder Path saved."))
                elif sub == "4":
                    if not cur_url or not cur_key:
                        print(red("  ❌ URL and API Key must be set first."))
                        continue
                    try:
                        r = requests.get(
                            f"{cur_url.rstrip('/')}/api/v3/system/status",
                            headers={"X-Api-Key": cur_key},
                            timeout=5,
                        )
                        r.raise_for_status()
                        info = r.json()
                        print(green(f"  ✅ Connected to Radarr v{info.get('version','?')}"))
                        rp = requests.get(f"{cur_url.rstrip('/')}/api/v3/qualityprofile", headers={"X-Api-Key": cur_key}, timeout=5)
                        if rp.ok:
                            print(f"\n  {white('Quality Profiles:')}")
                            for p in rp.json():
                                print(f"    {yellow(str(p['id']))}  {white(p['name'])}")
                        rr = requests.get(f"{cur_url.rstrip('/')}/api/v3/rootfolder", headers={"X-Api-Key": cur_key}, timeout=5)
                        if rr.ok:
                            print(f"\n  {white('Root Folders:')}")
                            for folder in rr.json():
                                print(f"    {cyan(folder['path'])}")
                    except Exception as e:
                        print(red(f"  ❌ Connection failed: {e}"))

        # ── API KEYS ────────────────────────────
        elif choice == "7":
            while True:
                api_keys = load_api_keys()
                cur_tmdb = api_keys.get("tmdb_key", "")
                cur_omdb = api_keys.get("omdb_key", "")
                print(f"\n{header('  🔑  API KEYS')}\n" + divider("-", 52))
                print(f"  {white('TMDB Key:')}  {cyan(cur_tmdb[:8] + '...' if cur_tmdb else 'Not set')}")
                print(f"  {white('OMDB Key:')}  {cyan(cur_omdb[:8] + '...' if cur_omdb else 'Not set')}")
                print(f"  {blue('  TMDB → themoviedb.org  |  OMDB → omdbapi.com  (both free)')}")
                print(divider("-", 52))
                print(f"  {yellow('[1]')}  {white('Set TMDB API Key')}")
                print(f"  {yellow('[2]')}  {white('Set OMDB API Key')}")
                print(f"  {red('[0]')}  {white('Back')}")
                sub = input(f"  {cyan('Select')}: ").strip()
                if sub == "0":
                    break
                elif sub == "1":
                    key = input(f"  {cyan('TMDB API Key')}: ").strip()
                    if key:
                        api_keys["tmdb_key"] = key
                        save_api_keys(api_keys)
                        print(green("  ✅ TMDB API key saved."))
                elif sub == "2":
                    key = input(f"  {cyan('OMDB API Key')}: ").strip()
                    if key:
                        api_keys["omdb_key"] = key
                        save_api_keys(api_keys)
                        print(green("  ✅ OMDB API key saved."))

        # ── MOVIE DATABASE ───────────────────────
        elif choice == "8":
            movie_db_menu()

        else:
            print(red("  ⚠️  Invalid option."))


# ─────────────────────────────────────────
#  MAIN MENU
# ─────────────────────────────────────────
def menu():
    while True:
        versions = load_versions()
        app_ver  = get_app_version()
        latest   = versions[-1] if versions else {"version": "0.0.1", "notes": "Initial commit"}
        log_id   = f"log.{len(versions):03d}"
        servers  = load_servers()
        srv_info = f"{ACTIVE['name']}  ·  {ACTIVE['lib_count']} libraries"

        print("\n" + divider())
        print(header(f"         🎬  PLEX API MANAGER"))
        print(cyan( f"         v{app_ver}  ·  {srv_info}"))
        print(blue( f"         {log_id}  {latest['notes']}"))
        print(divider())
        watchlist_count  = len(load_watchlist())
        movie_list_count = len(load_movie_list())
        print(f"  {yellow('[1]')}  {white('List All Libraries')}")
        print(f"  {yellow('[2]')}  {white('Search My Library with Totals')}")
        print(f"  {yellow('[3]')}  {white('Get Recently Added')}")
        print(f"  {yellow('[4]')}  {white('Get Active Playback Sessions')}")
        print(f"  {yellow('[5]')}  {white('Watchlist / Favorites')}  {blue(f'({watchlist_count} item' + ('s' if watchlist_count != 1 else '') + ')')}")
        print(f"  {yellow('[9]')}  {white('Movie Search List')}  {blue(f'({movie_list_count} movie' + ('s' if movie_list_count != 1 else '') + ')')}")
        print(divider("-", 52))
        print(f"  {magenta('[6]')}  {white('Version Manager')}")
        print(f"  {magenta('[7]')}  {white('Discord Notification Settings')}")
        print(f"  {magenta('[8]')}  {white('Server Manager')}  {blue(f'({len(servers)} server' + ('s' if len(servers)!=1 else '') + ' configured)')}")
        print(divider("-", 52))
        print(f"  {red('[0]')}  {white('Exit')}")
        print(divider())

        choice = input(f"  {cyan('Select an option')}: ").strip()

        if   choice == "0": log.info("User exited."); print(green("\n  Goodbye! 👋\n")); break
        elif choice == "1": list_libraries()
        elif choice == "2": search_library()
        elif choice == "3": recently_added()
        elif choice == "4": playback_sessions()
        elif choice == "5": watchlist_menu()
        elif choice == "6": version_menu()
        elif choice == "7": discord_settings_menu()
        elif choice == "8": server_manager_menu()
        elif choice == "9": movie_list_menu()
        else:               print(red("  ⚠️  Invalid option. Please try again."))

# ─────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────
def main():
    app_ver = get_app_version()
    log.info(f"=== Plex API Manager v{app_ver} started ===")
    startup_servers()
    menu()
    log.info(f"=== Plex API Manager v{app_ver} closed ===")

if __name__ == "__main__":
    main()