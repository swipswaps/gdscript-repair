# gdscript-repair

**Fully automatic repair tool for Godot GDScript** – specifically for the `build_terrain.gd` parachute game script.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

| Fix | Description |
|-----|-------------|
| **FIX‑A** | Grey loading screen → calls `_hide_loading_screen()` |
| **FIX‑B** | Canopy scale 18 cm → 3 m + **continuous opening animation** inside `_physics_process` (smooth growth) |
| **FIX‑C** | Camera offset (0,2,3)→(0,4,8), FOV 75→85, near 0.1→0.05, far 10000→20000 |
| **FIX‑D** | Arm rotation axis – automatically tested via headless Godot (FORWARD/UP/RIGHT) |
| **FIX‑E** | HUD guard early return removed (preserves indentation) |
| **FIX‑F** | Frame‑2 screenshot disabled (stalled the game) |
| **Dry‑run default** | Shows unified diff before any changes |
| **Automatic backup** | `.backup_auto` created before write |
| **gdformat integration** | Normalises indentation (tabs/spaces) |
| **gdparse verification** | Aborts and restores backup on syntax error |

## Usage

### Python version (recommended – fully automatic)

```bash
# From your Godot project root (where scripts/build_terrain.gd exists)
python gd_repair/repair_gdscript_v2.py          # dry run (shows diff)
python gd_repair/repair_gdscript_v2.py --apply  # apply after confirmation
python gd_repair/repair_gdscript_v2.py --apply --yes  # skip confirmation
python gd_repair/repair_gdscript_v2.py --skip-arm-test  # skip arm axis test

Requirements: Python 3.8+, optional gdtoolkit (for gdformat/gdparse):
bash

pip install gdtoolkit

EditorScript version (limited – not recommended)

A GDScript version (apply_safe_fixes.gd) is provided but does not include the continuous canopy animation – use the Python script for full fixes.
Repository Structure
text

gdscript-repair/
├── README.md
└── gd_repair/
    ├── repair_gdscript_v2.py      # Python repair script (fully automatic)
    └── apply_safe_fixes.gd        # EditorScript (limited)

How It Works

The Python script performs safe, idempotent regex replacements while preserving indentation. It:

    Shows a unified diff (dry‑run default).

    Tests arm axis by launching a headless Godot instance (with correct GDScript syntax).

    Inserts the canopy animation before the FREEFALL state handling so it runs every frame during OPENING_ANIM.

    Removes any previously inserted one‑time animation lines.

    Creates a timestamped log file with all output.

    Runs gdformat and gdparse after writing, restoring the backup if syntax fails.

Why This Exists

The original build_terrain.gd accumulated many small bugs from manual edits and LLM‑generated patches – a grey overlay, invisible canopy (scale 0.18), wrong arm axis, etc. This tool automates the fixes without introducing new errors.
License

MIT