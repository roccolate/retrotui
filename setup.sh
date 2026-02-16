#!/bin/bash
# RetroTUI — Setup script for Ubuntu minimal
set -e

echo "═══════════════════════════════════════════"
echo "  RetroTUI v0.6.0 — Setup"
echo "═══════════════════════════════════════════"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[!] Python3 not found. Installing..."
    sudo apt update && sudo apt install -y python3
else
    echo "[✓] Python3: $(python3 --version)"
fi

# Check ncurses
if python3 -c "import curses" 2>/dev/null; then
    echo "[✓] curses module available"
else
    echo "[!] Installing ncurses..."
    sudo apt install -y libncursesw5-dev python3-dev
fi

# Check if running in TTY (not terminal emulator)
if [[ "$(tty)" == /dev/tty* ]]; then
    echo ""
    echo "[i] Running in Linux virtual console (TTY)"
    echo "    GPM is REQUIRED for mouse support."
    echo ""
    if command -v gpm &>/dev/null; then
        echo "[✓] GPM is installed"
    else
        echo "[!] Installing GPM for console mouse support..."
        sudo apt install -y gpm
    fi
    if systemctl is-active --quiet gpm 2>/dev/null; then
        echo "[✓] GPM daemon is running"
    else
        echo "[!] Starting GPM daemon..."
        sudo systemctl enable --now gpm
        echo "[✓] GPM started"
    fi
else
    echo ""
    echo "[i] Running in terminal emulator: $(tty)"
    echo "    Mouse will use xterm protocol (no GPM needed)."
fi

# Check terminal capabilities
echo ""
echo "[i] Terminal: $TERM"
echo "[i] Colors:   $(tput colors 2>/dev/null || echo 'unknown')"
echo "[i] Size:     $(tput cols)x$(tput lines)"

# Check locale/UTF-8
if locale | grep -qi 'utf-8\|utf8'; then
    echo "[✓] UTF-8 locale detected — Unicode borders enabled"
else
    echo "[!] Non-UTF-8 locale — falling back to ASCII borders"
    echo "    To enable Unicode: sudo dpkg-reconfigure locales"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "  Setup complete! Run with:"
echo "  python3 -m retrotui"
echo "═══════════════════════════════════════════"
