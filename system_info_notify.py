import json
import os
import platform
from datetime import datetime, timedelta
from pathlib import Path

import requests

# ── Base directory — dev clone vs pip install ─────────────────
_script_dir = Path(__file__).parent
if (_script_dir / "versions.json").exists():
    BASE_DIR = _script_dir
else:
    BASE_DIR = Path(os.environ.get(
        "PLEX_MANAGER_HOME", Path.home() / ".plex-manager"
    ))
    BASE_DIR.mkdir(parents=True, exist_ok=True)

DISCORD_FILE = BASE_DIR / "discord_creds.json"
SERVERS_FILE = BASE_DIR / "plex_servers.json"

# ─────────────────────────────────────────
#  SYSTEM INFO
# ─────────────────────────────────────────
def get_system_info():
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

# ─────────────────────────────────────────
#  ACTIVE STREAM COUNT
# ─────────────────────────────────────────
def get_active_stream_count():
    if not SERVERS_FILE.exists():
        return 0
    try:
        with open(SERVERS_FILE) as f:
            servers = json.load(f)
        server = next((s for s in servers if s.get("active")), servers[0] if servers else None)
        if not server:
            return 0
        hdrs = {"X-Plex-Token": server["token"], "Accept": "application/json"}
        res  = requests.get(f"{server['url']}/status/sessions", headers=hdrs, timeout=5)
        res.raise_for_status()
        return res.json()["MediaContainer"].get("size", 0)
    except Exception:
        return 0

# ─────────────────────────────────────────
#  DISCORD
# ─────────────────────────────────────────
def load_webhook():
    if DISCORD_FILE.exists():
        try:
            with open(DISCORD_FILE) as f:
                return json.load(f).get("webhook_url", "").strip()
        except Exception:
            return ""
    return ""

def send(webhook_url, sysinfo, stream_count, next_run=None):
    footer_text = f"Next heartbeat: {next_run}" if next_run else "system_info_notify.py"
    payload = {
        "embeds": [{
            "title": "💓 Heartbeat",
            "description": (
                f"🖥️ OS: `{sysinfo['os']}`\n"
                f"🌐 IP: `{sysinfo['ip']}`\n"
                f"▶️ Active streams: `{stream_count}`"
            ),
            "color": 0x5865F2,
            "footer": {"text": footer_text},
            "timestamp": datetime.utcnow().isoformat()
        }]
    }
    res = requests.post(webhook_url, json=payload, timeout=5)
    if res.status_code in (200, 204):
        print("✅ Sent to Discord.")
    else:
        print(f"❌ Discord returned {res.status_code}: {res.text}")

# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────
def main():
    print("🔍 Gathering system info...")
    sysinfo      = get_system_info()
    stream_count = get_active_stream_count()

    print(f"  OS      : {sysinfo['os']}")
    print(f"  IP      : {sysinfo['ip']}")
    print(f"  Streams : {stream_count}")

    # Schedule next heartbeat and get the chosen time for the Discord footer
    next_run_label = None
    try:
        from heartbeat_scheduler import schedule_next
        print("\n🗓️  Scheduling next heartbeat...")
        next_time      = schedule_next()
        tomorrow       = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        next_run_label = f"{tomorrow} at {next_time}"
    except Exception as e:
        print(f"  ⚠️  Scheduler error: {e}")

    webhook = load_webhook()
    if not webhook:
        print("⚠️  No webhook found in discord_creds.json")
    else:
        send(webhook, sysinfo, stream_count, next_run=next_run_label)

if __name__ == "__main__":
    main()
