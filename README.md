# gdscript-repair

Automated repair tools for Godot GDScript files – specifically for the `build_terrain.gd` parachute game script.

## Features

- Fixes grey loading screen (FIX‑A)
- Rescales canopy from 18 cm to 3 m and adds opening animation (FIX‑B)
- Adjusts camera offset, FOV, near/far planes (FIX‑C)
- Corrects arm rotation axis (FIX‑D)
- Removes early‑return HUD guard (FIX‑E)
- Disables frame‑2 screenshot that stalled the game (FIX‑F)
- Dry‑run default – shows exact changes before applying
- Automatic backup and syntax verification (`gdparse`)
- Optional `gdformat` integration for indentation cleanup

## Usage

### Python version (external, more verbose)

```bash
# From your Godot project root (where scripts/build_terrain.gd exists)
python gd_repair/repair_gdscript_v2.py          # dry run
python gd_repair/repair_gdscript_v2.py --apply  # apply after confirmation

Requires Python 3.8+ and optional gdtoolkit for gdformat/gdparse:
bash

pip install gdtoolkit

GDScript version (inside Godot editor)

    Copy gd_repair/apply_safe_fixes.gd into your project (e.g., res://addons/gd_repair/).

    Open the script in the Godot script editor.

    Press File → Run (or Ctrl+Shift+X).

    Check the Output panel (bottom of editor) for results.

No external dependencies – runs entirely inside Godot.
Repository Structure
text

gdscript-repair/
├── README.md
└── gd_repair/
    ├── repair_gdscript_v2.py      # Python repair script
    └── apply_safe_fixes.gd        # EditorScript version (GDScript)

How It Works

Both scripts perform the same safe, idempotent string replacements using regular expressions that tolerate whitespace variations. They:

    Show a unified diff of proposed changes.

    Create a .backup_auto file before writing.

    Run gdparse to verify syntax after changes (if available).

    Normalise indentation with gdformat (if installed).

Why This Exists

The original build_terrain.gd accumulated many small bugs from manual edits and LLM‑generated patches – a grey overlay, invisible canopy, wrong arm axis, etc. This tool automates the fixes without introducing new errors.
License

MIT