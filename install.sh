#!/usr/bin/env bash
# install.sh — macOS / Ubuntu / Linux installer for Plex API Manager
set -e

REPO="https://github.com/trickdaddy24/plex-api-manager.git"
CONFIG_DIR="$HOME/.plex-manager"
EXAMPLE_URL="https://raw.githubusercontent.com/trickdaddy24/plex-api-manager/main/plex_servers.example.json"

echo ""
echo "🎬 Plex API Manager — Installer"
echo "================================"
echo ""

OS_TYPE=$(uname -s)   # "Darwin" = macOS, "Linux" = Linux/Ubuntu

# ── macOS ──────────────────────────────────────────────────────
if [[ "$OS_TYPE" == "Darwin" ]]; then
    echo "🍎 Detected macOS"
    echo ""

    # Homebrew — required on Mac
    if ! command -v brew &>/dev/null; then
        echo "❌ Homebrew is not installed — it is required to set up Python and pipx on macOS."
        echo ""
        echo "   Install Homebrew first, then re-run this script:"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        echo ""
        exit 1
    fi
    echo "✅ Homebrew found"

    # Python 3
    if ! command -v python3 &>/dev/null; then
        echo "📦 Installing Python 3 via Homebrew..."
        brew install python
    fi
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "✅ Python $PY_VER found"

    # pipx
    if ! command -v pipx &>/dev/null; then
        echo "📦 Installing pipx via Homebrew..."
        brew install pipx
        pipx ensurepath
    fi
    echo "✅ pipx found"

# ── Ubuntu / Linux ─────────────────────────────────────────────
elif [[ "$OS_TYPE" == "Linux" ]]; then
    echo "🐧 Detected Linux"
    echo ""

    # Python 3
    if ! command -v python3 &>/dev/null; then
        echo "❌ python3 not found. Install it with: sudo apt install python3"
        exit 1
    fi
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "✅ Python $PY_VER found"

    # pipx — handles PEP 668 / Ubuntu 24.04+
    if ! command -v pipx &>/dev/null; then
        echo "📦 Installing pipx..."
        sudo apt-get update -qq
        sudo apt-get install -y pipx
    fi
    echo "✅ pipx found"

else
    echo "❌ Unsupported OS: $OS_TYPE"
    echo "   Supported: macOS (Darwin), Ubuntu/Linux"
    exit 1
fi

# ── Install from GitHub (same for all platforms) ───────────────
echo ""
echo "📦 Installing plex-api-manager via pipx..."
pipx install "git+$REPO" --force

# ── Ensure pipx bin dir is in PATH ────────────────────────────
pipx ensurepath --quiet
export PATH="$HOME/.local/bin:$PATH"

# ── Config directory ──────────────────────────────────────────
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

# ── Done ──────────────────────────────────────────────────────
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

if [[ "$OS_TYPE" == "Darwin" ]]; then
    echo "⚠️  If commands are not found, reload your shell config:"
    echo "   source ~/.zshrc        (default macOS shell)"
    echo "   source ~/.bash_profile  (if using bash)"
else
    echo "⚠️  If commands are not found, run: source ~/.bashrc"
fi

echo ""
echo "First-time setup:"
echo "  1. Edit $CONFIG_DIR/plex_servers.json with your Plex URL and token"
echo "  2. Run: plex-manager"
echo "  3. Go to option 7 to configure your Discord webhook"
echo "  4. Run: plex-scheduler  (to set up the daily heartbeat)"
echo ""
