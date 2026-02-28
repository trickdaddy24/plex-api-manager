#!/usr/bin/env bash
# install.sh — Ubuntu/Linux installer for Plex API Manager
set -e

REPO="https://github.com/trickdaddy24/plex-api-manager.git"
CONFIG_DIR="$HOME/.plex-manager"
EXAMPLE_URL="https://raw.githubusercontent.com/trickdaddy24/plex-api-manager/main/plex_servers.example.json"

echo ""
echo "🎬 Plex API Manager — Installer"
echo "================================"
echo ""

# ── Python check ─────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "❌ python3 not found. Install it with: sudo apt install python3"
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python $PY_VER found"

# ── pipx install (handles PEP 668 / Ubuntu 24.04+) ───────────
# pipx installs CLI tools into isolated venvs — the correct
# approach for modern Ubuntu which blocks pip install --user.
if ! command -v pipx &>/dev/null; then
    echo "📦 Installing pipx..."
    sudo apt-get update -qq
    sudo apt-get install -y pipx
fi

echo "📦 Installing plex-api-manager via pipx..."
pipx install "git+$REPO" --force

# ── Ensure pipx bin dir is in PATH ────────────────────────────
pipx ensurepath --quiet
export PATH="$HOME/.local/bin:$PATH"

# ── Config directory ─────────────────────────────────────────
mkdir -p "$CONFIG_DIR"
echo "✅ Config dir: $CONFIG_DIR"

# ── Server config template ────────────────────────────────────
if [ ! -f "$CONFIG_DIR/plex_servers.json" ]; then
    if command -v curl &>/dev/null; then
        curl -sL "$EXAMPLE_URL" -o "$CONFIG_DIR/plex_servers.json"
        echo "✅ Server config template copied to $CONFIG_DIR/plex_servers.json"
        echo "   ⚠️  Edit it with your Plex server URL and token before running."
    else
        echo "⚠️  curl not found — copy plex_servers.example.json to $CONFIG_DIR/plex_servers.json manually."
    fi
else
    echo "✅ Existing server config found — not overwritten."
fi

# ── Done ─────────────────────────────────────────────────────
echo ""
echo "✅ Installation complete!"
echo ""
echo "Commands available:"
echo "  plex-manager    — launch the interactive menu"
echo "  plex-heartbeat  — send system info to Discord now"
echo "  plex-scheduler  — manage the daily heartbeat schedule"
echo ""
echo "Config directory: $CONFIG_DIR"
echo ""
echo "⚠️  If commands are not found, run: source ~/.bashrc"
echo ""
echo "First-time setup:"
echo "  1. Edit $CONFIG_DIR/plex_servers.json with your Plex URL and token"
echo "  2. Run: plex-manager"
echo "  3. Go to option 7 to configure your Discord webhook"
echo "  4. Run: plex-scheduler  (to set up the daily heartbeat)"
echo ""
