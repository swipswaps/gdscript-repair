#!/usr/bin/env bash
# install.sh – Pipe‑safe, resolves path to absolute before re‑exec
set -euo pipefail

# Detect pipe mode (no real script file)
if [[ ! -f "${BASH_SOURCE[0]}" ]]; then
    echo "[INFO] Detected pipe execution (curl | bash)."
    if [ $# -eq 0 ]; then
        echo "[ERROR] Please provide your Godot project directory as an argument."
        echo "Example: bash <(curl ...) /path/to/your/godot_project"
        exit 1
    fi
    # Resolve the first argument to an absolute path
    TARGET_DIR="$(cd "$1" 2>/dev/null && pwd || echo "$1")"
    if [ ! -f "$TARGET_DIR/project.godot" ]; then
        echo "[ERROR] '$TARGET_DIR' is not a valid Godot project (missing project.godot)."
        exit 1
    fi
    echo "[INFO] Cloning repository to temporary directory..."
    TEMP_DIR="$(mktemp -d)"
    git clone https://github.com/swipswaps/gdscript-repair.git "$TEMP_DIR"
    cd "$TEMP_DIR"
    # Re‑run with the absolute path
    exec bash install.sh "$TARGET_DIR"
fi

# Normal execution (from local file) – argument is already absolute (or we use pwd)
TARGET_DIR="${1:-$(pwd)}"
if [ ! -f "$TARGET_DIR/project.godot" ]; then
    echo "[ERROR] No project.godot found in $TARGET_DIR"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_SRC="$SCRIPT_DIR/gd_repair"
if [ ! -d "$PLUGIN_SRC" ]; then
    echo "[ERROR] Cannot find gd_repair folder at $PLUGIN_SRC"
    exit 1
fi

ADDONS_DIR="$TARGET_DIR/addons"
mkdir -p "$ADDONS_DIR"
if [ -d "$ADDONS_DIR/gd_repair" ]; then
    echo "[WARN] Removing existing gd_repair plugin"
    rm -rf "$ADDONS_DIR/gd_repair"
fi
cp -r "$PLUGIN_SRC" "$ADDONS_DIR/"
chmod +x "$ADDONS_DIR/gd_repair/repair_gdscript_v2.py"

if [ -f "$ADDONS_DIR/gd_repair/plugin.cfg" ] && \
   [ -f "$ADDONS_DIR/gd_repair/plugin.gd" ] && \
   [ -f "$ADDONS_DIR/gd_repair/repair_gdscript_v2.py" ]; then
    echo "[INFO] Installation successful!"
    echo "Next steps:"
    echo "1. Open your Godot project"
    echo "2. Go to Project → Project Settings → Plugins"
    echo "3. Enable 'GDScript Repair (Safe)'"
    echo "4. Open any GDScript file and click the '🔧 Repair Script' button"
else
    echo "[ERROR] Installation incomplete – missing required files."
    exit 1
fi