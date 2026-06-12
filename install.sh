#!/usr/bin/env bash
# PATH: install.sh
# PURPOSE: Safe, non‑breaking installation of GDScript Repair plugin.
#           Works both locally and via `curl | bash` when project path is provided.
# USAGE:
#   When run locally:   ./install.sh [/path/to/godot/project]
#   When run from pipe: bash <(curl ...) /path/to/godot/project
#   (If already in project root, use '.' as argument)
#
# CITATION: Bash script best practices – https://www.gnu.org/software/bash/manual/
# CITATION: Godot project structure – https://docs.godotengine.org/en/stable/tutorials/plugins/editor/index.html
# CITATION: Detect pipe execution – https://stackoverflow.com/questions/9112136/bash-check-if-script-is-being-run-through-a-pipe

set -euo pipefail

# ----------------------------------------------------------------------------
# DETECTOR: Check if running from a pipe (curl | bash) and if argument is missing
# ----------------------------------------------------------------------------
PIPE_MODE=false
if [[ ! -f "${BASH_SOURCE[0]}" ]]; then
    PIPE_MODE=true
    echo "[INFO] Detected pipe execution (curl | bash)."
    if [ $# -eq 0 ]; then
        echo "[ERROR] When using pipe execution, you must provide the Godot project path as an argument."
        echo "Example: bash <(curl -s https://raw.githubusercontent.com/swipswaps/gdscript-repair/master/install.sh) /path/to/your/godot_project"
        echo "If you are already inside your project root, use '.' as argument:"
        echo "  cd /path/to/your/godot_project && bash <(curl -s ...) ."
        exit 1
    fi
    # Clone repository to temporary directory and re-run with the same arguments
    echo "[INFO] Cloning repository to a temporary directory..."
    TEMP_DIR=$(mktemp -d)
    git clone https://github.com/swipswaps/gdscript-repair.git "$TEMP_DIR"
    cd "$TEMP_DIR"
    exec bash install.sh "$@"
    # exec replaces the process; never reaches here
fi

# ----------------------------------------------------------------------------
# GATE 0: Determine target directory (first argument or current directory)
# ----------------------------------------------------------------------------
TARGET_DIR="${1:-$(pwd)}"
if [ ! -f "$TARGET_DIR/project.godot" ]; then
    echo "[ERROR] No project.godot found in $TARGET_DIR"
    echo "Please provide a valid Godot project directory:"
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
    echo "Make sure you are running this script from the cloned repository root (or that the repository is intact)."
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