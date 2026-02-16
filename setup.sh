#!/bin/bash
# RetroTUI â€” Setup script for Ubuntu minimal
set -e

echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
echo "  RetroTUI v0.3.6 â€” Setup"
echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[!] Python3 not found. Installing..."
    sudo apt update && sudo apt install -y python3
else
    echo "[âœ“] Python3: $(python3 --version)"
fi

# Check ncurses
if python3 -c "import curses" 2>/dev/null; then
    echo "[âœ“] curses module available"
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
        echo "[âœ“] GPM is installed"
    else
        echo "[!] Installing GPM for console mouse support..."
        sudo apt install -y gpm
    fi
    if systemctl is-active --quiet gpm 2>/dev/null; then
        echo "[âœ“] GPM daemon is running"
    else
        echo "[!] Starting GPM daemon..."
        sudo systemctl enable --now gpm
        echo "[âœ“] GPM started"
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
    echo "[âœ“] UTF-8 locale detected â€” Unicode borders enabled"
else
    echo "[!] Non-UTF-8 locale â€” falling back to ASCII borders"
    echo "    To enable Unicode: sudo dpkg-reconfigure locales"
fi

echo ""
echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
echo "  Setup complete! Run with:"
echo "  python3 -m retrotui"
echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
