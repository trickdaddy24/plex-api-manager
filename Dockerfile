# ─────────────────────────────────────────
#  Plex API Manager — Dockerfile
#  Interactive CLI container
#
#  Build:  docker compose build
#  Run:    docker compose run --rm plex-manager
# ─────────────────────────────────────────

FROM python:3.12-slim

LABEL maintainer="trickdaddy24"
LABEL description="Plex API Manager — colorized CLI for managing Plex Media Server"
LABEL org.opencontainers.image.source="https://github.com/trickdaddy24/plex-api-manager"

WORKDIR /app

# Install Python dependencies up front so they are cached as a separate layer
RUN pip install --no-cache-dir requests colorama

# Copy application scripts
COPY plex_menu.py \
     movie_db_scan.py \
     heartbeat_scheduler.py \
     system_info_notify.py \
     ./

# Copy versions.json as the default seed — NOT as versions.json in /app so that
# the PLEX_MANAGER_HOME path-detection logic in plex_menu.py triggers correctly.
# The entrypoint will copy this to /data/versions.json on first run.
COPY versions.json /app/versions_default.json

# Copy and enable entrypoint
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# /data is the persistent data volume — all user config and generated files live here
VOLUME /data

# Tell plex_menu.py / all scripts to use /data as the base directory
ENV PLEX_MANAGER_HOME=/data

ENTRYPOINT ["/entrypoint.sh"]

# Default command — interactive CLI
CMD ["python", "plex_menu.py"]
