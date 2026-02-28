"""
movie_db_scan.py
Standalone script — enriches the local Movie Database with TMDB + OMDB metadata.
Designed to be run on a schedule (Windows Task Scheduler / crontab) so that
the 1000-call/day TMDB quota is never exceeded in a single session.

Usage:
  python movie_db_scan.py          # run scan (continues where it left off)
  python movie_db_scan.py --status # show current scan progress
  python movie_db_scan.py --remove # remove the scheduled task

  # or when installed via pip:
  plex-movie-scan
  plex-movie-scan --status
  plex-movie-scan --remove
"""

import json
import logging
import os
import platform
import random
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Base directory ────────────────────────────────────────────────────────────
_script_dir = Path(__file__).parent
if (_script_dir / "versions.json").exists():
    BASE_DIR = _script_dir
else:
    BASE_DIR = Path(os.environ.get("PLEX_MANAGER_HOME", Path.home() / ".plex-manager"))
    BASE_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR            = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
MOVIE_DB_LOG_DIR   = LOG_DIR / "movie_db"
MOVIE_DB_LOG_DIR.mkdir(exist_ok=True)

SERVERS_FILE       = BASE_DIR / "plex_servers.json"
DISCORD_FILE       = BASE_DIR / "discord_creds.json"
API_KEYS_FILE      = BASE_DIR / "api_keys.json"
MOVIE_DB_FILE      = BASE_DIR / "movie_db.json"
MOVIE_DB_PROG_FILE = BASE_DIR / "movie_db_progress.json"
MOVIE_DB_TASK_NAME = "PlexMovieDBScan"
TMDB_DAILY_LIMIT   = 1000

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(MOVIE_DB_LOG_DIR / "movie_db_scan.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("movie_db_scan")

# ── Third-party imports (auto-install if missing) ─────────────────────────────
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# ── JSON helpers ──────────────────────────────────────────────────────────────
def _load_json(path, default):
    if Path(path).exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"Could not read {path}: {e}")
    return default

def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ── Config loaders ────────────────────────────────────────────────────────────
def _get_active_server():
    servers = _load_json(SERVERS_FILE, [])
    for s in servers:
        if s.get("active"):
            return s
    return servers[0] if servers else None

def _get_api_keys():
    return _load_json(API_KEYS_FILE, {})

def _get_discord_webhook():
    return _load_json(DISCORD_FILE, {}).get("webhook_url", "").strip()

def _load_movie_db():
    return _load_json(MOVIE_DB_FILE, {})

def _load_progress():
    return _load_json(MOVIE_DB_PROG_FILE, {})

# ── Discord notification ──────────────────────────────────────────────────────
def _notify_discord(message, title="Movie DB Scan", color=0x00b0f4):
    webhook = _get_discord_webhook()
    if not webhook:
        return
    payload = {
        "embeds": [{
            "title":       title,
            "description": message,
            "color":       color,
            "timestamp":   datetime.utcnow().isoformat(),
            "footer":      {"text": f"Plex Movie DB Scan — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"},
        }]
    }
    try:
        requests.post(webhook, json=payload, timeout=5)
    except Exception as e:
        log.warning(f"Discord notify failed: {e}")

# ── Quota helpers ─────────────────────────────────────────────────────────────
def _quota_check(prog):
    today = datetime.now().strftime("%Y-%m-%d")
    if prog.get("quota_date") != today:
        prog["quota_date"] = today
        prog["quota_used"] = 0
    return prog

# ── TMDB helpers ──────────────────────────────────────────────────────────────
def _tmdb_details(tmdb_id, tmdb_key):
    try:
        res = requests.get(
            f"https://api.themoviedb.org/3/movie/{tmdb_id}",
            params={"api_key": tmdb_key, "language": "en-US", "append_to_response": "release_dates"},
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()
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
        log.warning(f"TMDB details error tmdb={tmdb_id}: {e}")
        return None

def _omdb_ratings(imdb_id, omdb_key):
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
        log.warning(f"OMDB ratings error imdb={imdb_id}: {e}")
        return {"imdb_rating": "N/A", "rt_rating": "N/A"}

def _extract_guids(item):
    tmdb_id = None
    imdb_id = None
    for g in item.get("Guid", []):
        gid = g.get("id", "")
        if gid.startswith("tmdb://"):
            tmdb_id = gid.split("tmdb://")[-1]
        elif gid.startswith("imdb://"):
            imdb_id = gid.split("imdb://")[-1]
    return tmdb_id, imdb_id

# ── Plex helpers ──────────────────────────────────────────────────────────────
def _plex_headers(token):
    return {"X-Plex-Token": token, "Accept": "application/json"}

def _fetch_plex_movies(server):
    url   = server["url"]
    token = server["token"]
    hdrs  = _plex_headers(token)
    all_movies = []
    try:
        r = requests.get(f"{url}/library/sections", headers=hdrs, timeout=10)
        r.raise_for_status()
        sections   = r.json()["MediaContainer"].get("Directory", [])
        movie_libs = [s for s in sections if s.get("type") == "movie"]
        for lib in movie_libs:
            lib_key   = lib.get("key")
            lib_title = lib.get("title", "?")
            res = requests.get(
                f"{url}/library/sections/{lib_key}/all",
                headers=hdrs,
                params={"includeGuids": 1},
                timeout=30,
            )
            res.raise_for_status()
            items = res.json()["MediaContainer"].get("Metadata", [])
            for item in items:
                item["_plex_library"] = lib_title
            all_movies.extend(items)
            log.info(f"Fetched {len(items)} movies from '{lib_title}'")
    except Exception as e:
        log.error(f"Plex fetch error: {e}")
    return all_movies

def _fetch_full_item(url, token, rating_key):
    try:
        r = requests.get(
            f"{url}/library/metadata/{rating_key}",
            headers=_plex_headers(token),
            timeout=10,
        )
        r.raise_for_status()
        items = r.json()["MediaContainer"].get("Metadata", [])
        return items[0] if items else {}
    except Exception:
        return {}

# ── Scheduler ─────────────────────────────────────────────────────────────────
def _schedule_next(prog):
    h, m     = random.randint(0, 5), random.randint(0, 59)
    run_time = f"{h:02d}:{m:02d}"
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    ep  = shutil.which("plex-movie-scan")
    cmd = ep if ep else f"{sys.executable} \"{Path(__file__).resolve()}\""

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

    next_run = f"{tomorrow} {run_time}"
    log.info(f"Next scan scheduled: {next_run}")
    return next_run

def _remove_schedule():
    if platform.system() == "Windows":
        subprocess.run(["schtasks", "/delete", "/tn", MOVIE_DB_TASK_NAME, "/f"], capture_output=True)
        print(f"Removed Windows scheduled task: {MOVIE_DB_TASK_NAME}")
    else:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
        lines    = [l for l in existing.splitlines() if MOVIE_DB_TASK_NAME not in l]
        subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True)
        print(f"Removed crontab entry: {MOVIE_DB_TASK_NAME}")

# ── Status display ────────────────────────────────────────────────────────────
def _show_status():
    prog  = _load_progress()
    db    = _load_movie_db()
    today = datetime.now().strftime("%Y-%m-%d")
    if prog.get("quota_date") != today:
        q_used = 0
    else:
        q_used = prog.get("quota_used", 0)
    print("=" * 52)
    print("  MOVIE DB SCAN STATUS")
    print("=" * 52)
    print(f"  Status:            {prog.get('status','idle')}")
    print(f"  Scan started:      {prog.get('scan_started_at','N/A')}")
    print(f"  Total Plex movies: {prog.get('total_plex_movies',0)}")
    print(f"  Processed:         {prog.get('processed_count',0)}")
    print(f"  Failed/skipped:    {prog.get('failed_count',0)}")
    print(f"  Pending:           {len(prog.get('pending_rating_keys',[]))}")
    print(f"  In database:       {len(db)}")
    print(f"  TMDB calls today:  {q_used} / {TMDB_DAILY_LIMIT}  ({today})")
    print(f"  Next scheduled:    {prog.get('next_scheduled_run','Not scheduled')}")
    print(f"  Log folder:        {MOVIE_DB_LOG_DIR}")
    print("=" * 52)

# ── Main scan loop ────────────────────────────────────────────────────────────
def run_scan():
    log.info("=== Movie DB Scan started ===")

    server = _get_active_server()
    if not server:
        log.error("No Plex server configured.")
        return

    api_keys = _get_api_keys()
    tmdb_key = api_keys.get("tmdb_key", "")
    omdb_key = api_keys.get("omdb_key", "")
    if not tmdb_key:
        log.error("TMDB API key not set in api_keys.json.")
        return

    db   = _load_movie_db()
    prog = _load_progress()
    prog = _quota_check(prog)

    quota_remaining = TMDB_DAILY_LIMIT - prog.get("quota_used", 0)
    if quota_remaining <= 0:
        log.info(f"Daily TMDB quota exhausted ({TMDB_DAILY_LIMIT}). Scheduling next run.")
        next_run = _schedule_next(prog)
        prog["next_scheduled_run"] = next_run
        prog["status"] = "paused"
        _save_json(MOVIE_DB_PROG_FILE, prog)
        _notify_discord(
            f"⏸️ **Quota Exhausted** — daily limit of {TMDB_DAILY_LIMIT} reached.\n"
            f"⏰ Next run scheduled: `{next_run}`",
            title="📀 Movie DB Scan — Paused", color=0xFEE75C,
        )
        return

    # Build or resume pending list
    pending_keys = prog.get("pending_rating_keys", [])
    if not pending_keys:
        log.info("Fetching all movies from Plex...")
        plex_movies = _fetch_plex_movies(server)
        if not plex_movies:
            log.error("No movies found in Plex libraries.")
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
        _save_json(MOVIE_DB_PROG_FILE, prog)
        log.info(f"Scan started — {len(pending_keys)} movies to process")
        _notify_discord(
            f"📀 **Movie DB Scan Started**\n\n"
            f"🎬 Total movies: `{len(pending_keys)}`\n"
            f"🔑 TMDB quota remaining: `{quota_remaining}`",
            title="📀 Movie DB Scan — Started", color=0x57F287,
        )
    else:
        log.info(f"Resuming scan — {len(pending_keys)} movies remaining")
        _notify_discord(
            f"▶️ **Movie DB Scan Resumed**\n\n"
            f"🎬 Remaining: `{len(pending_keys)}`\n"
            f"🔑 TMDB quota remaining: `{quota_remaining}`",
            title="📀 Movie DB Scan — Resumed", color=0xFEE75C,
        )

    processed_this_run = 0
    failed_this_run    = 0

    while pending_keys and (TMDB_DAILY_LIMIT - prog.get("quota_used", 0)) > 0:
        rating_key = pending_keys[0]
        plex_item  = _fetch_full_item(server["url"], server["token"], rating_key)
        if not plex_item:
            pending_keys.pop(0)
            failed_this_run += 1
            prog["failed_count"] = prog.get("failed_count", 0) + 1
            log.warning(f"Could not fetch Plex item ratingKey={rating_key}")
            continue

        tmdb_id, imdb_id = _extract_guids(plex_item)
        if not tmdb_id:
            pending_keys.pop(0)
            prog["processed_count"] = prog.get("processed_count", 0) + 1
            log.info(f"No TMDB ID — skipped: {plex_item.get('title','?')}")
            continue

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
            _save_json(MOVIE_DB_PROG_FILE, prog)
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
            "plex_server":    server.get("name", "Unknown"),
            "last_updated":   datetime.now().strftime("%Y-%m-%d"),
        }
        pending_keys.pop(0)
        prog["processed_count"] = prog.get("processed_count", 0) + 1
        processed_this_run += 1
        log.info(
            f"Enriched: {details['title']} ({details['year']}) "
            f"tmdb:{tmdb_id} imdb:{eff_imdb} "
            f"IMDB:{ratings['imdb_rating']} RT:{ratings['rt_rating']}"
        )

        if processed_this_run % 10 == 0:
            _save_json(MOVIE_DB_FILE, db)
            prog["pending_rating_keys"] = pending_keys
            _save_json(MOVIE_DB_PROG_FILE, prog)

    # Final save
    _save_json(MOVIE_DB_FILE, db)
    prog["pending_rating_keys"] = pending_keys
    _save_json(MOVIE_DB_PROG_FILE, prog)

    if not pending_keys:
        prog["status"] = "complete"
        prog["next_scheduled_run"] = None
        _save_json(MOVIE_DB_PROG_FILE, prog)
        log.info(f"Scan complete — processed:{processed_this_run} failed:{failed_this_run} db_size:{len(db)}")
        _notify_discord(
            f"✅ **Movie DB Scan Complete!**\n\n"
            f"🎬 This run: `{processed_this_run}` processed, `{failed_this_run}` failed\n"
            f"📀 Total in database: `{len(db)}`",
            title="📀 Movie DB Scan — Complete", color=0x57F287,
        )
    else:
        next_run = _schedule_next(prog)
        prog["status"] = "paused"
        prog["next_scheduled_run"] = next_run
        _save_json(MOVIE_DB_PROG_FILE, prog)
        log.info(f"Scan paused (quota) — processed:{processed_this_run} remaining:{len(pending_keys)} next:{next_run}")
        _notify_discord(
            f"⏸️ **Movie DB Scan Paused — Daily Quota Reached**\n\n"
            f"🎬 This run: `{processed_this_run}` processed\n"
            f"⏳ Remaining: `{len(pending_keys)}`\n"
            f"⏰ Next run scheduled: `{next_run}`",
            title="📀 Movie DB Scan — Paused", color=0xFEE75C,
        )

    log.info("=== Movie DB Scan ended ===")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    if "--status" in args:
        _show_status()
    elif "--remove" in args:
        _remove_schedule()
    else:
        run_scan()


if __name__ == "__main__":
    main()
