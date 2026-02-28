#!/usr/bin/env bash
# install.sh — Ubuntu/Linux installer for Plex API Manager
# Run this from inside the cloned repo directory:
#   git clone https://<token>@github.com/trickdaddy24/plex-api-manager.git
#   cd plex-api-manager
#   bash install.sh
set -e

CONFIG_DIR="$HOME/.plex-manager"

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

# ── pip check ────────────────────────────────────────────────
if ! command -v pip3 &>/dev/null; then
    echo "📦 Installing pip3..."
    sudo apt-get update -qq
    sudo apt-get install -y python3-pip
fi

# ── Install from local clone ─────────────────────────────────
if [ ! -f "pyproject.toml" ]; then
    echo "❌ pyproject.toml not found."
    echo "   Run this script from inside the cloned repo directory."
    exit 1
fi

echo "📦 Installing plex-api-manager..."
pip3 install --user --upgrade .

# ── Ensure PATH includes ~/.local/bin ────────────────────────
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo ""
    echo "⚠️  Adding ~/.local/bin to PATH in ~/.bashrc"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    export PATH="$HOME/.local/bin:$PATH"
fi

# ── Config directory ─────────────────────────────────────────
mkdir -p "$CONFIG_DIR"
echo "✅ Config dir: $CONFIG_DIR"

# ── Server config template ────────────────────────────────────
if [ ! -f "$CONFIG_DIR/plex_servers.json" ]; then
    if [ -f "plex_servers.example.json" ]; then
        cp plex_servers.example.json "$CONFIG_DIR/plex_servers.json"
        echo "✅ Server config template copied to $CONFIG_DIR/plex_servers.json"
        echo "   ⚠️  Edit it with your Plex server URL and token before running."
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
echo "First-time setup:"
echo "  1. Edit $CONFIG_DIR/plex_servers.json with your Plex URL and token"
echo "  2. Run: plex-manager"
echo "  3. Go to option 7 to configure your Discord webhook"
echo "  4. Run: plex-scheduler  (to set up the daily heartbeat)"
echo ""
