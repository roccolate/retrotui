#!/bin/bash
# RetroTUI Smoke Test Battery
# Usage: bash tools/smoke_test.sh [--create-data]
#
# Run with --create-data to create the test data directory first.
# Then launch RetroTUI and follow the manual checklist in tools/TESTING.md.

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

DATA_DIR="$HOME/.retrotui-test-data"

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }

# ─── Environment Check ────────────────────────────────────────
echo "═══════════════════════════════════════════════"
echo " RetroTUI Smoke Test"
echo "═══════════════════════════════════════════════"
echo ""
echo "── Environment ──"

echo -n "  TERM=$TERM → "
case "$TERM" in
    xterm*|screen*|tmux*|linux|rxvt*|alacritty|kitty) ok "supported" ;;
    *) warn "unknown ($TERM), may have issues" ;;
esac

COLORS=$(tput colors 2>/dev/null || echo 0)
echo -n "  Colors: $COLORS → "
if [ "$COLORS" -ge 256 ]; then ok "256-color (best)"
elif [ "$COLORS" -ge 8 ]; then warn "8-color (basic themes only)"
else fail "no color support"; fi

COLS=$(tput cols 2>/dev/null || echo 0)
LINES=$(tput lines 2>/dev/null || echo 0)
echo -n "  Terminal size: ${COLS}x${LINES} → "
if [ "$COLS" -ge 80 ] && [ "$LINES" -ge 24 ]; then ok "OK"
elif [ "$COLS" -ge 60 ]; then warn "small, some windows may not fit"
else fail "too small (min 80x24)"; fi

echo -n "  Unicode rendering: ╔═╗║╚╝ ░▒▓ → "
ok "check visually above"

# Detect Python command
# We search for a functional python interpreter in this order:
# 1. python3 (standard on Linux/macOS)
# 2. python (standard on Windows if added to PATH)
# 3. Common Windows installation paths (for Git Bash where PATH might not be inherited perfectly)

find_python() {
    # Check standard commands first
    for cmd in python3 python py; do
        if command -v "$cmd" &>/dev/null; then
            if "$cmd" --version &>/dev/null; then
                echo "$cmd"
                return 0
            fi
        fi
    done

    # Check common Windows paths (accessed via Git Bash /c/...)
    # We look for the latest version first (sort -r)
    for path in /c/Program\ Files/Python3*/python.exe /c/Python3*/python.exe; do
        if [ -f "$path" ]; then
             echo "$path"
             return 0
        fi
    done

    return 1
}

PYTHON_CMD=$(find_python)

echo -n "  Python: "
if [ -n "$PYTHON_CMD" ]; then
    VER=$($PYTHON_CMD --version 2>&1 | head -n 1)
    ok "found ($VER at $PYTHON_CMD)"
else
    fail "python3/python not found (checked PATH and standard Windows locations)"
    echo "    Host OS seems to be Windows. Ensure Python is installed and added to PATH."
fi

echo -n "  curses: "
if [ -n "$PYTHON_CMD" ]; then
    if $PYTHON_CMD -c "import curses; print('OK')" 2>/dev/null | grep -q "OK"; then
        ok "available"
    else
        fail "not available (install windows-curses with: pip install windows-curses)"
    fi
else
    fail "skipped"
fi

echo -n "  retrotui: "
if [ -n "$PYTHON_CMD" ]; then
    if $PYTHON_CMD -c "import retrotui" 2>/dev/null; then
        ok "importable"
    else
        warn "not installed (running from source?)"
    fi
else
    fail "skipped"
fi

# ─── External tools ──────────────────────────────────────────
echo ""
echo "── External Tools (optional) ──"

for tool in chafa timg catimg mpv nmcli dosbox; do
    echo -n "  $tool: "
    if command -v $tool &>/dev/null; then ok "$(command -v $tool)"
    else warn "not found (feature will be disabled)"; fi
done

# ─── Create Test Data ────────────────────────────────────────
if [ "$1" = "--create-data" ]; then
    echo ""
    echo "── Creating Test Data in $DATA_DIR ──"
    mkdir -p "$DATA_DIR"

    # Plain text files
    mkdir -p "$DATA_DIR/documents"
    echo "Hello World. This is a simple text file for testing." > "$DATA_DIR/documents/simple.txt"
    echo "Línea en español con acentos: á é í ó ú ñ ¿¡" > "$DATA_DIR/documents/spanish.txt"
    echo "日本語テスト: こんにちは世界" > "$DATA_DIR/documents/japanese.txt"
    echo "Emoji test: 🎉 🖥️ 📁 🐍 💣 🃏 🎨" > "$DATA_DIR/documents/emoji.txt"

    # Long file for scroll testing
    seq 1 500 | while read n; do echo "Line $n: $(head -c 20 /dev/urandom | base64)"; done > "$DATA_DIR/documents/long_file.txt"

    # Wide lines for horizontal scroll
    $PYTHON_CMD -c "print('A' * 300)" > "$DATA_DIR/documents/wide_lines.txt"
    $PYTHON_CMD -c "
for i in range(50):
    print(f'Row {i:03d}: ' + ''.join(f'Col{j:02d} ' for j in range(40)))
" >> "$DATA_DIR/documents/wide_lines.txt"

    # Empty file
    touch "$DATA_DIR/documents/empty.txt"

    # File with no extension
    echo "No extension file content" > "$DATA_DIR/documents/noextension"

    # File with special characters in name
    echo "spaces in name" > "$DATA_DIR/documents/file with spaces.txt"
    echo "special chars" > "$DATA_DIR/documents/file-with-dashes_and_underscores.txt"

    # Config-like files
    mkdir -p "$DATA_DIR/configs"
    cat > "$DATA_DIR/configs/sample.toml" << 'EOF'
[server]
host = "localhost"
port = 8080
debug = true

[database]
url = "sqlite:///data.db"
pool_size = 5
EOF

    cat > "$DATA_DIR/configs/sample.json" << 'EOF'
{
  "name": "RetroTUI",
  "version": "0.9.0",
  "features": ["filemanager", "notepad", "terminal"],
  "settings": {
    "theme": "win31",
    "mouse": true
  }
}
EOF

    cat > "$DATA_DIR/configs/sample.yaml" << 'EOF'
application:
  name: RetroTUI
  version: 0.9.0
  components:
    - filemanager
    - notepad
    - terminal
    - calculator
EOF

    # Source code files
    mkdir -p "$DATA_DIR/code"
    cat > "$DATA_DIR/code/hello.py" << 'EOF'
#!/usr/bin/env python3
"""Hello World in Python."""

def greet(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(greet("RetroTUI"))
EOF

    cat > "$DATA_DIR/code/hello.c" << 'EOF'
#include <stdio.h>

int main() {
    printf("Hello from C!\n");
    return 0;
}
EOF

    cat > "$DATA_DIR/code/hello.sh" << 'EOF'
#!/bin/bash
echo "Hello from shell!"
for i in 1 2 3; do
    echo "  Count: $i"
done
EOF

    # Binary files for Hex Viewer
    mkdir -p "$DATA_DIR/binary"
    printf '\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' > "$DATA_DIR/binary/fake_header.png"
    head -c 256 /dev/urandom > "$DATA_DIR/binary/random_256b.bin"
    head -c 4096 /dev/urandom > "$DATA_DIR/binary/random_4k.bin"
    head -c 65536 /dev/urandom > "$DATA_DIR/binary/random_64k.bin"
    printf 'MZ\x90\x00' > "$DATA_DIR/binary/fake_exe.bin"
    printf '\x7fELF' > "$DATA_DIR/binary/fake_elf.bin"

    # Images (if ImageMagick available)
    mkdir -p "$DATA_DIR/images"
    if command -v convert &>/dev/null; then
        convert -size 100x100 xc:red "$DATA_DIR/images/red_square.png" 2>/dev/null && ok "red_square.png" || warn "ImageMagick failed"
        convert -size 200x100 xc:blue "$DATA_DIR/images/blue_rect.png" 2>/dev/null && ok "blue_rect.png" || true
        convert -size 50x50 gradient:yellow-green "$DATA_DIR/images/gradient.png" 2>/dev/null && ok "gradient.png" || true
    else
        warn "ImageMagick not found — creating placeholder images with Python"
        (cd "$DATA_DIR/images" && $PYTHON_CMD -c "
import struct, zlib
def make_png(path, w, h, r, g, b):
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
    raw = b''
    for y in range(h):
        raw += b'\x00' + bytes([r, g, b]) * w
    return (b'\x89PNG\r\n\x1a\n' +
            chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw)) +
            chunk(b'IEND', b''))
for name, w, h, r, g, b in [('red_square.png',100,100,255,0,0),('blue_rect.png',200,100,0,0,255),('gradient.png',50,50,255,255,0)]:
    with open(name, 'wb') as f:
        f.write(make_png(f.name, w, h, r, g, b))
print('Created PNG test images')
") 2>/dev/null || warn "Could not create test images"
    fi

    # Directory structure for navigation testing
    mkdir -p "$DATA_DIR/deep/level1/level2/level3/level4"
    echo "deepest file" > "$DATA_DIR/deep/level1/level2/level3/level4/deep.txt"

    # Many files directory for performance testing
    mkdir -p "$DATA_DIR/many_files"
    for i in $(seq -w 1 200); do
        echo "File content $i" > "$DATA_DIR/many_files/file_$i.txt"
    done
    ok "Created 200 files in many_files/"

    # Hidden files
    echo "hidden content" > "$DATA_DIR/.hidden_file"
    mkdir -p "$DATA_DIR/.hidden_dir"
    echo "inside hidden dir" > "$DATA_DIR/.hidden_dir/visible.txt"

    # Symlinks
    ln -sf "$DATA_DIR/documents/simple.txt" "$DATA_DIR/documents/link_to_simple.txt" 2>/dev/null || warn "Symlinks not supported"
    ln -sf "$DATA_DIR/deep" "$DATA_DIR/link_to_deep" 2>/dev/null || true

    # Read-only file
    rm -f "$DATA_DIR/documents/readonly.txt"
    echo "read only content" > "$DATA_DIR/documents/readonly.txt"
    chmod 444 "$DATA_DIR/documents/readonly.txt" 2>/dev/null || true

    # Large text file
    (cd "$DATA_DIR/documents" && $PYTHON_CMD -c "
import string, random
random.seed(42)
with open('large_10k_lines.txt', 'w') as f:
    for i in range(10000):
        f.write(f'Line {i:05d}: {\".\".join(random.choices(string.ascii_lowercase, k=8))}\n')
print('Created 10k line file')
")

    echo ""
    ok "Test data created at $DATA_DIR"
    echo ""
    echo "  Contents:"
    find "$DATA_DIR" -maxdepth 1 -mindepth 1 | sort | while read d; do
        count=$(find "$d" -type f 2>/dev/null | wc -l)
        echo "    $(basename $d)/ — $count files"
    done
fi

echo ""
echo "═══════════════════════════════════════════════"
echo " Now launch RetroTUI and follow tools/TESTING.md"
echo "═══════════════════════════════════════════════"
