#!/bin/sh
# ─────────────────────────────────────────
#  Plex API Manager — Docker Entrypoint
#
#  Runs before the main command on every container start.
#  Seeds /data with default files on first run, then executes CMD.
# ─────────────────────────────────────────

set -e

DATA_DIR="${PLEX_MANAGER_HOME:-/data}"

# Create required subdirectories if they don't exist
mkdir -p \
  "${DATA_DIR}/logs/movie_db" \
  "${DATA_DIR}/library_cache" \
  "${DATA_DIR}/watchlist_exports" \
  "${DATA_DIR}/old"

# Seed versions.json on first run (source of truth for app version)
if [ ! -f "${DATA_DIR}/versions.json" ]; then
  echo "  [entrypoint] First run — seeding ${DATA_DIR}/versions.json"
  cp /app/versions_default.json "${DATA_DIR}/versions.json"
fi

# Seed plex_servers.json example on first run so the user has a template
if [ ! -f "${DATA_DIR}/plex_servers.json" ] && [ -f /app/plex_servers.example.json ]; then
  echo "  [entrypoint] Seeding example plex_servers.json — edit with your URL and token"
  cp /app/plex_servers.example.json "${DATA_DIR}/plex_servers.json"
fi

exec "$@"
