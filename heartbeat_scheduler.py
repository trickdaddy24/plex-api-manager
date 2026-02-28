"""
heartbeat_scheduler.py
Cross-platform scheduler for system_info_notify.py.
Picks a random time between 00:00–11:59 and registers a daily task
with the OS so the heartbeat fires automatically every 24 hours.

Usage:
  python heartbeat_scheduler.py          # schedule next run and exit
  python heartbeat_scheduler.py --status # show next scheduled run
  python heartbeat_scheduler.py --remove # remove the scheduled task

  # or when installed via pip:
  plex-scheduler
  plex-scheduler --status
  plex-scheduler --remove
"""

import json
import os
import platform
import random
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Base directory — dev clone vs pip install ─────────────────
_script_dir = Path(__file__).parent
if (_script_dir / "versions.json").exists():
    BASE_DIR = _script_dir
else:
    BASE_DIR = Path(os.environ.get(
        "PLEX_MANAGER_HOME", Path.home() / ".plex-manager"
    ))
    BASE_DIR.mkdir(parents=True, exist_ok=True)

HEARTBEAT_FILE = BASE_DIR / "heartbeat.json"
TASK_NAME      = "PlexHeartbeat"

# ─────────────────────────────────────────
#  HEARTBEAT COMMAND RESOLVER
#  Finds the right command to run system_info_notify:
#  - pip install → uses the plex-heartbeat entry point (full path)
#  - git clone   → uses python <script path>
# ─────────────────────────────────────────
def _heartbeat_cmd():
    ep = shutil.which("plex-heartbeat")
    if ep:
        return [ep]
    return [sys.executable, str(_script_dir / "system_info_notify.py")]

# ─────────────────────────────────────────
#  RANDOM TIME PICKER  (00:00 – 11:59)
# ─────────────────────────────────────────
def pick_random_time():
    hour   = random.randint(0, 11)
    minute = random.randint(0, 59)
    return f"{hour:02d}:{minute:02d}"

# ─────────────────────────────────────────
#  HEARTBEAT STATE FILE
# ─────────────────────────────────────────
def save_heartbeat(next_time: str):
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    data = {
        "next_run_time": next_time,
        "next_run_date": tomorrow,
        "scheduled_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "platform":      platform.system()
    }
    with open(HEARTBEAT_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data

def load_heartbeat():
    if HEARTBEAT_FILE.exists():
        try:
            with open(HEARTBEAT_FILE) as f:
                return json.load(f)
        except Exception:
            return None
    return None

# ─────────────────────────────────────────
#  WINDOWS — Task Scheduler via schtasks
# ─────────────────────────────────────────
def schedule_windows(next_time: str):
    cmd    = _heartbeat_cmd()
    tr_arg = " ".join(f'"{c}"' for c in cmd)
    result = subprocess.run(
        ["schtasks", "/create", "/tn", TASK_NAME,
         "/tr", tr_arg, "/sc", "DAILY", "/st", next_time, "/f"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  ✅ Windows Task Scheduler: '{TASK_NAME}' set for {next_time} daily.")
    else:
        print(f"  ❌ schtasks error: {result.stderr.strip()}")
    return result.returncode == 0

def remove_windows():
    result = subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  ✅ Task '{TASK_NAME}' removed from Task Scheduler.")
    else:
        print(f"  ❌ {result.stderr.strip()}")

# ─────────────────────────────────────────
#  LINUX — crontab
# ─────────────────────────────────────────
def schedule_linux(next_time: str):
    cmd       = _heartbeat_cmd()
    cmd_str   = " ".join(cmd)
    hour, minute = next_time.split(":")
    cron_line = f"{minute} {hour} * * * {cmd_str} # {TASK_NAME}"

    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    lines    = [l for l in existing.stdout.splitlines()
                if TASK_NAME not in l and "system_info_notify" not in l]
    lines.append(cron_line)

    proc = subprocess.run(["crontab", "-"],
                          input="\n".join(lines) + "\n",
                          text=True, capture_output=True)
    if proc.returncode == 0:
        print(f"  ✅ Crontab updated: '{TASK_NAME}' set for {next_time} daily.")
    else:
        print(f"  ❌ crontab error: {proc.stderr.strip()}")
    return proc.returncode == 0

def remove_linux():
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    lines    = [l for l in existing.stdout.splitlines()
                if TASK_NAME not in l and "system_info_notify" not in l]
    subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True)
    print(f"  ✅ '{TASK_NAME}' removed from crontab.")

# ─────────────────────────────────────────
#  MAIN ENTRY — detect OS and schedule
# ─────────────────────────────────────────
def schedule_next():
    """Pick a random time and register with the OS scheduler. Returns the chosen time."""
    next_time = pick_random_time()
    os_name   = platform.system()

    print(f"  🕐 Next heartbeat scheduled: {next_time}")

    if os_name == "Windows":
        schedule_windows(next_time)
    elif os_name == "Linux":
        schedule_linux(next_time)
    else:
        print(f"  ⚠️  Unsupported platform: {os_name} — time chosen but not registered with OS.")

    save_heartbeat(next_time)
    return next_time

def remove_schedule():
    os_name = platform.system()
    if os_name == "Windows":
        remove_windows()
    elif os_name == "Linux":
        remove_linux()
    else:
        print(f"  ⚠️  Unsupported platform: {os_name}")
    if HEARTBEAT_FILE.exists():
        HEARTBEAT_FILE.unlink()
        print("  🗑️  heartbeat.json removed.")

# ─────────────────────────────────────────
#  STANDALONE / ENTRY POINT
# ─────────────────────────────────────────
def main():
    if "--status" in sys.argv:
        data = load_heartbeat()
        if data:
            print(f"  📅 Next run : {data['next_run_date']} at {data['next_run_time']}")
            print(f"  🖥️  Platform : {data['platform']}")
            print(f"  🕐 Scheduled: {data['scheduled_at']}")
        else:
            print("  ⚠️  No heartbeat scheduled yet. Run without --status to set one.")
    elif "--remove" in sys.argv:
        remove_schedule()
    else:
        print("🗓️  Scheduling next heartbeat...")
        schedule_next()

if __name__ == "__main__":
    main()
