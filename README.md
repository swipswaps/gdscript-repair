# GDScript Repair (Safe) – Godot Editor Plugin

A non‑breaking, safe plugin for Godot 4 that automatically fixes:
- **Duplicate function definitions** (identical bodies only)
- **Orphaned indented lines** (code outside any function)
- **Mixed indentation** (tabs → 4 spaces)

It creates timestamped backups and verifies syntax with gdparse before overwriting.  
Rolls back automatically on any failure.

## Features
- ✅ One‑click repair from the script editor toolbar
- ✅ Detects duplicates only if bodies are identical (safe)
- ✅ Fixes indentation while preserving logic
- ✅ Uses gdtoolkit (gdparse) for syntax verification
- ✅ Timestamped backups (e.g., file.gd.backup_20260612_143021)
- ✅ Rolls back if verification fails

## Installation

### Automatic (recommended)

Run this command **inside your Godot project root** (where project.godot is located):

bash <(curl -s https://raw.githubusercontent.com/swipswaps/gdscript-repair/master/install.sh) .

### Manual (fallback)

1. Download the gd_repair folder from this repository.
2. Create an addons/ folder in your Godot project root if it doesn't exist.
3. Copy the gd_repair folder into addons/.
4. Enable the plugin in Project → Project Settings → Plugins.

## Requirements

- Python 3.8+ with pip installed.
- The plugin will automatically install gdtoolkit if missing (pip install gdtoolkit==4.*).

## Usage

1. Open any GDScript file in the Godot script editor.
2. Click the 🔧 Repair Script button in the top toolbar.
3. The script is repaired, verified, and saved. A backup is created in the same folder.

## Manual command line (without plugin)

    python3 repair_gdscript_v2.py path/to/script.gd

## How it works

- **Detector** scans for duplicate functions and orphaned indentation.
- **Backup** is created with a timestamp.
- **Fixer** removes identical duplicates and dedents orphaned lines.
- **Verifier** runs gdparse on the repaired code.
- **Rollback** restores the backup if verification fails.

## License

MIT – use freely, modify, share.