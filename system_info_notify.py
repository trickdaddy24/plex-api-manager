import json
import platform
from datetime import datetime
from pathlib import Path

import requests

BASE_DIR     = Path(__file__).parent
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

def send(webhook_url, sysinfo, stream_count):
    payload = {
        "embeds": [{
            "title": "🖥️ System Info",
            "description": (
                f"🖥️ OS: `{sysinfo['os']}`\n"
                f"🌐 IP: `{sysinfo['ip']}`\n"
                f"▶️ Active streams: `{stream_count}`"
            ),
            "color": 0x5865F2,
            "footer": {"text": "system_info_notify.py"},
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
if __name__ == "__main__":
    print("🔍 Gathering system info...")
    sysinfo      = get_system_info()
    stream_count = get_active_stream_count()

    print(f"  OS      : {sysinfo['os']}")
    print(f"  IP      : {sysinfo['ip']}")
    print(f"  Streams : {stream_count}")

    webhook = load_webhook()
    if not webhook:
        print("⚠️  No webhook found in discord_creds.json")
    else:
        send(webhook, sysinfo, stream_count)
