# gdscript-repair

A Godot 4 editor plugin that surgically repairs GDScript parse errors using
assert-gated, anchor-based fixes. Safe by design: every fix is idempotent,
every change is backed up with a timestamp, and nothing is written to disk
unless gdparse exits 0.

Built to repair build_terrain.gd in the parachute-cfd-game project after
multiple LLM-introduced indentation and duplication errors broke the file.


## What it fixes

**FIX-1 — Orphaned indent block (missing state guard)**

Detects a double-tab block with no opening statement at single-tab depth
inside _physics_process. Inserts the missing
`if _game_state == GameState.FREEFALL:` guard that was accidentally removed
by a prior automated patch.

    Root cause confirmed by gdparse:
        Unexpected token Token('_INDENT', '\t\t') at line 1436


**FIX-2 — Duplicate screenshot timer**

Removes the third copy of the screenshot-timer block — the one calling
`_save_flight_screenshot()` (a superseded private method) rather than the
ScreenshotLibrary approach used by the other two copies.


**FIX-3 — Duplicate function definitions at bottom of file**

Removes two extra copies of `_unhandled_input` and one extra `toggle_pause`
that accumulated at the bottom of the file via repeated LLM patches.
GDScript does not permit duplicate function names.


**FIX-4 — General duplicate function scanner**

Scans the entire file for any remaining duplicate function definitions and
removes subsequent occurrences, keeping the first. Catches duplicates
introduced by future patches that FIX-3 does not cover.


## Safety guarantees

- Timestamped backup created before any mutation (`file.gd.backup_YYYYMMDD_HHMMSS`)
- Each fix checks its anchor string appears exactly once before replacing.
  Zero or multiple occurrences raise AssertionError and abort with no write.
- gdparse syntax verification runs on the candidate content before write.
  If gdparse exits non-zero, the failed content is written to `.gd.failed`
  for inspection and the original file is left untouched.
- All fixes are idempotent. Running on an already-repaired file skips every
  fix and exits 0.


## Installation

**One-line install (pipe to bash):**

    bash <(curl -fsSL https://raw.githubusercontent.com/swipswaps/gdscript-repair/main/install.sh) /path/to/your/godot_project

**Manual install:**

    git clone https://github.com/swipswaps/gdscript-repair.git
    cd gdscript-repair
    bash install.sh /path/to/your/godot_project

The installer copies `gd_repair/` into your project's `addons/` directory
and sets the execute bit on `repair_gdscript_v2.py`.


## Enable in Godot

    1. Open your project in Godot 4
    2. Project -> Project Settings -> Plugins
    3. Enable "GDScript Repair (Safe)"
    4. A "Repair Script" button appears in the script editor toolbar


## Command-line usage (no Godot required)

    python3 addons/gd_repair/repair_gdscript_v2.py scripts/build_terrain.gd

Expected output on a broken file:

    [INFO] Input: scripts/build_terrain.gd (75681 bytes, 1893 lines)
    [INFO] Backup created: scripts/build_terrain.gd.backup_20260612_170233
    [INFO] FIX-1 applied: inserted if _game_state == GameState.FREEFALL: guard
    [INFO] FIX-2 applied: removed duplicate screenshot timer (_save_flight_screenshot copy)
    [INFO] FIX-3 applied: removed 2x duplicate _unhandled_input + 1x duplicate toggle_pause
    [INFO] FIX-4 skip: no remaining duplicate functions found
    [INFO] Fixes applied: FIX-1, FIX-2, FIX-3
    [INFO] Running gdparse syntax verification...
    [OK]   Written: scripts/build_terrain.gd
    [OK]   SYNTAX OK -- gdparse exit 0

Expected output when run on an already-repaired file:

    [INFO] No fixes needed -- file already clean.
    [OK]   SYNTAX OK -- gdparse exit 0


## Requirements

- Python 3.8+
- gdtoolkit 4.x (`pip install 'gdtoolkit==4.*'`) — auto-installed if missing
- Godot 4.x project with a `project.godot` file


## Repository layout

    gd_repair/
        plugin.cfg              Editor plugin manifest
        plugin.gd               EditorPlugin: adds toolbar button, calls repair script
        repair_gdscript_v2.py   Repair engine (also usable standalone from CLI)
    install.sh                  Installer: copies gd_repair/ into target project addons/
    README.md                   This file


## How the repair engine works

The engine does not rewrite indentation globally. It applies three targeted
fixes using literal string anchors, then runs a general duplicate-function
scanner as a catch-all.

Each anchor fix follows this pattern:

    1. Check whether the anchor string is present. If absent, skip (idempotent).
    2. Assert the anchor appears exactly once (assert_unique_replace guard).
    3. Replace the anchor with the corrected string.
    4. Continue to next fix.

After all fixes, gdparse verifies the candidate content. Only if gdparse
exits 0 is the file written to disk.

This approach was chosen because global indentation rewrites (the previous
strategy) destroyed if/else/elif block structure. Flattening all lines inside
_physics_process to 4 spaces placed the `else:` tokens at the same depth as
the `if:` body lines, making them unparseable.

Citation: Godot GDScript basics, Indentation section
https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html#indentation

Citation: gdtoolkit (gdparse, gdformat)
https://github.com/Scony/godot-gdscript-toolkit


## Verified on

- Fedora 41/43, Python 3.12, gdtoolkit 4.5.0, Godot 4.6.2 stable
- build_terrain.gd: 75681 bytes, 1893 lines, tab-indented
- All three fixes applied in < 1 second; gdparse exit 0 confirmed on real machine


## License

MIT
