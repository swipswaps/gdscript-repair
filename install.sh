#!/usr/bin/env bash
# PATH: install.sh
# PURPOSE: Safe, non‑breaking installation of GDScript Repair plugin.
#           Works both when run locally and via `curl | bash`.
# USAGE:   ./install.sh [/path/to/godot/project]
#          If no path given, uses current directory.
#
# CITATION: Bash script best practices – https://www.gnu.org/software/bash/manual/
# CITATION: Godot project structure – https://docs.godotengine.org/en/stable/tutorials/plugins/editor/index.html
# CITATION: Detect pipe execution – https://stackoverflow.com/questions/9112136/bash-check-if-script-is-being-run-through-a-pipe

set -euo pipefail

# ----------------------------------------------------------------------------
# DETECTOR: Check if running from a pipe (curl | bash)
# ----------------------------------------------------------------------------
# CITATION: ${BASH_SOURCE[0]} is empty or not a regular file when piped
if [[ ! -f "${BASH_SOURCE[0]}" ]]; then
    echo "[INFO] Detected pipe execution (curl | bash). Cloning repository to a temporary directory..."
    
    # Create a temporary directory
    TEMP_DIR=$(mktemp -d)
    # CITATION: git clone – https://git-scm.com/docs/git-clone
    git clone https://github.com/swipswaps/gdscript-repair.git "$TEMP_DIR"
    # Change to the temporary directory and re‑run this script (now from a real file)
    cd "$TEMP_DIR"
    exec bash install.sh
    # The exec replaces the current process; code after this line never runs in pipe mode.
fi

# ----------------------------------------------------------------------------
# GATE 0: Check that the target directory contains a Godot project
# ----------------------------------------------------------------------------
TARGET_DIR="${1:-$(pwd)}"
if [ ! -f "$TARGET_DIR/project.godot" ]; then
    echo "[ERROR] No project.godot found in $TARGET_DIR"
    echo "Please run this script from your Godot project root, or pass the path:"
    echo "  ./install.sh /path/to/your/godot_project"
    exit 1
fi

# ----------------------------------------------------------------------------
# GATE 1: Ensure the script is run from the repository root (gd_repair folder exists)
# ----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_SRC="$SCRIPT_DIR/gd_repair"
if [ ! -d "$PLUGIN_SRC" ]; then
    echo "[ERROR] Cannot find gd_repair folder at $PLUGIN_SRC"
    echo "Make sure you are running this script from the cloned repository root."
    exit 1
fi

# ----------------------------------------------------------------------------
# Create addons folder if missing
# ----------------------------------------------------------------------------
ADDONS_DIR="$TARGET_DIR/addons"
mkdir -p "$ADDONS_DIR"
echo "[INFO] Ensured addons folder exists: $ADDONS_DIR"

# ----------------------------------------------------------------------------
# Remove any previous installation (clean install)
# ----------------------------------------------------------------------------
if [ -d "$ADDONS_DIR/gd_repair" ]; then
    echo "[WARN] Removing existing gd_repair plugin"
    rm -rf "$ADDONS_DIR/gd_repair"
fi

# ----------------------------------------------------------------------------
# Copy plugin into addons/
# ----------------------------------------------------------------------------
cp -r "$PLUGIN_SRC" "$ADDONS_DIR/"
echo "[INFO] Copied gd_repair to $ADDONS_DIR/gd_repair"

# ----------------------------------------------------------------------------
# Make Python script executable
# ----------------------------------------------------------------------------
chmod +x "$ADDONS_DIR/gd_repair/repair_gdscript_v2.py"
echo "[INFO] Made repair_gdscript_v2.py executable"

# ----------------------------------------------------------------------------
# VERIFICATION: Check all required files are present
# ----------------------------------------------------------------------------
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