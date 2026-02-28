import json
import platform
from datetime import datetime
from pathlib import Path

import requests

BASE_DIR      = Path(__file__).parent
DISCORD_FILE  = BASE_DIR / "discord_creds.json"

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

def send(webhook_url: str, sysinfo: dict):
    payload = {
        "embeds": [{
            "title": "🖥️ System Info",
            "description": f"🖥️ OS: `{sysinfo['os']}`\n🌐 IP: `{sysinfo['ip']}`",
            "color": 0x57F287,
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
    sysinfo = get_system_info()
    print(f"OS : {sysinfo['os']}")
    print(f"IP : {sysinfo['ip']}")

    webhook = load_webhook()
    if not webhook:
        print("⚠️  No webhook found in discord_creds.json")
    else:
        send(webhook, sysinfo)
