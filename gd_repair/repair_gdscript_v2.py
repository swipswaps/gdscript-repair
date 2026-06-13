#!/usr/bin/env python3
"""
GDScript Repair Tool for Godot Parachute Game
Applies safe fixes: camera, canopy scale/animation, arm axis, HUD guard, screenshot disable.
Dry‑run default; use --apply to write changes.
"""

import re
import subprocess
import shutil
import sys
import difflib
from pathlib import Path
from datetime import datetime

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
GD_FILE = Path("scripts/build_terrain.gd")
BACKUP_SUFFIX = ".backup_auto"
LOG_FILE = Path(f"repair_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# ----------------------------------------------------------------------
# Helper: log to console and file
# ----------------------------------------------------------------------
def log(msg: str, also_print: bool = True):
    if also_print:
        print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# ----------------------------------------------------------------------
# Helper: run gdformat (check or write)
# ----------------------------------------------------------------------
def run_gdformat(file_path: Path, apply: bool) -> bool:
    if shutil.which("gdformat") is None:
        log("⚠️  gdformat not installed – skipping indentation normalization.")
        log("   Install with: pip install gdtoolkit")
        return True  # not fatal
    cmd = ["gdformat", "--write" if apply else "--check", str(file_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log(f"gdformat {'would reformat' if not apply else 'error'}:\n{result.stderr}")
            return False
        if not apply and "would be reformatted" in result.stdout:
            log("📝 gdformat would reformat the file. Run with --apply to fix.")
        return True
    except Exception as e:
        log(f"gdformat failed: {e}")
        return False

# ----------------------------------------------------------------------
# Apply all fixes (returns new content and list of applied fixes with details)
# ----------------------------------------------------------------------
def apply_fixes(content: str) -> tuple[str, list[dict]]:
    fixes = []
    original = content

    # 1. Camera FOV
    new_content, count = re.subn(r'(\.fov\s*=\s*)\d+(\.?\d*)', r'\g<1>85.0', content)
    if count:
        fixes.append({"name": "Camera FOV 85", "pattern": r'\.fov\s*=\s*\d+'})
        content = new_content
    # 2. Camera near
    new_content, count = re.subn(r'(\.near\s*=\s*)\d+(\.?\d*)', r'\g<1>0.05', content)
    if count:
        fixes.append({"name": "Camera near 0.05", "pattern": r'\.near\s*=\s*\d+'})
        content = new_content
    # 3. Camera far
    new_content, count = re.subn(r'(\.far\s*=\s*)\d+(\.?\d*)', r'\g<1>20000.0', content)
    if count:
        fixes.append({"name": "Camera far 20000", "pattern": r'\.far\s*=\s*\d+'})
        content = new_content
    # 4. Canopy initial scale
    new_content, count = re.subn(r'Vector3\s*\(\s*0\.18\s*,\s*0\.12\s*,\s*0\.18\s*\)', 'Vector3(3.0, 2.0, 3.0)', content)
    if count:
        fixes.append({"name": "Canopy scale (initial)", "pattern": r'Vector3\(0\.18, 0\.12, 0\.18\)'})
        content = new_content
    # 5. Canopy deployment scale (ZERO -> 3.0)
    new_content, count = re.subn(r'_canopy_instance\.scale\s*=\s*Vector3\.ZERO', '_canopy_instance.scale = Vector3(3.0, 2.0, 3.0)', content)
    if count:
        fixes.append({"name": "Canopy scale (deploy)", "pattern": r'_canopy_instance\.scale\s*=\s*Vector3\.ZERO'})
        content = new_content
    # 6. Insert animation after OPENING_ANIM
    if re.search(r'_game_state\s*=\s*GameState\.OPENING_ANIM', content) and 'var t = 1.0 -' not in content:
        anim = '\n\tvar t = 1.0 - (_deployment_timer / DEPLOY_TIME)\n\t_canopy_instance.scale = Vector3(3.0, 2.0, 3.0) * t\n'
        new_content = re.sub(r'(_game_state\s*=\s*GameState\.OPENING_ANIM)', r'\1' + anim, content)
        if new_content != content:
            fixes.append({"name": "Canopy animation inserted", "pattern": r'_game_state\s*=\s*GameState\.OPENING_ANIM'})
            content = new_content
    # 7. Arm axis RIGHT -> FORWARD
    new_content, count = re.subn(r'Quaternion\s*\(\s*Vector3\.RIGHT\s*,\s*angle\s*\)', 'Quaternion(Vector3.FORWARD, angle)', content)
    if count:
        fixes.append({"name": "Arm axis RIGHT→FORWARD", "pattern": r'Quaternion\(Vector3\.RIGHT, angle\)'})
        content = new_content
    # 8. Disable frame‑2 screenshot
    new_content, count = re.subn(r'if\s+_frame_count\s*==\s*2:', 'if false:  # disabled (audit_logs path may not exist)', content)
    if count:
        fixes.append({"name": "Frame‑2 screenshot disabled", "pattern": r'if\s+_frame_count\s*==\s*2:'})
        content = new_content
    # 9. HUD guard – remove early return (preserve indentation)
    pattern = r'(if\s+_hud_layer:\s*\n\s*)return'
    replacement = r'\1# HUD guard disabled – HUD will be recreated if needed\n\tpass'
    new_content, count = re.subn(pattern, replacement, content)
    if count:
        fixes.append({"name": "HUD guard early return removed", "pattern": r'if\s+_hud_layer:\s*\n\s*return'})
        content = new_content
    else:
        new_content = re.sub(r'if\s+_hud_layer:\s*\n\s*return', '# HUD guard removed (was early return)', content)
        if new_content != content:
            fixes.append({"name": "HUD guard early return removed (fallback)", "pattern": r'if\s+_hud_layer:\s*\n\s*return'})
            content = new_content

    return content, fixes

# ----------------------------------------------------------------------
# Show unified diff
# ----------------------------------------------------------------------
def show_diff(original: str, modified: str):
    diff = difflib.unified_diff(original.splitlines(keepends=True), modified.splitlines(keepends=True),
                                fromfile='original', tofile='modified', lineterm='')
    diff_lines = list(diff)
    if not diff_lines:
        log("No changes detected.")
        return
    log("\n📝 Detailed changes (unified diff):")
    for line in diff_lines:
        log(line.rstrip())

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Apply safe fixes to build_terrain.gd")
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default dry‑run)")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    if not GD_FILE.exists():
        log(f"❌ {GD_FILE} not found. Run from godot_project directory.")
        sys.exit(1)

    log("\n🎮 GDScript Repair Tool\n")
    if not args.apply:
        log("🔍 DRY RUN MODE – use --apply to write changes\n")

    original = GD_FILE.read_text(encoding='utf-8')
    new_content, fixes = apply_fixes(original)

    if not fixes:
        log("✅ No fixes needed.")
        return

    show_diff(original, new_content)
    log("\n📋 Fixes to apply:")
    for f in fixes:
        log(f"   - {f['name']} (pattern: {f['pattern']})")

    if not args.apply:
        log("\n🎮 Dry run completed. To apply, run: python repair_gdscript_v2.py --apply")
        log(f"📄 Full log saved to: {LOG_FILE}")
        return

    if not args.yes:
        confirm = input("\n⚠️  Do you want to apply these changes? (y/N): ").strip().lower()
        if confirm != 'y':
            log("Aborted by user.")
            return

    backup = GD_FILE.with_suffix(GD_FILE.suffix + BACKUP_SUFFIX)
    if not backup.exists():
        shutil.copy(GD_FILE, backup)
        log(f"📦 Backup saved: {backup}")

    GD_FILE.write_text(new_content, encoding='utf-8')
    log("✅ Applied fixes: " + ", ".join([f['name'] for f in fixes]))

    log("\n🔄 Running gdformat to normalise indentation...")
    if run_gdformat(GD_FILE, apply=True):
        log("✅ Indentation normalised.")
    else:
        log("⚠️  gdformat failed – you may need to run it manually later.")

    if shutil.which("gdparse"):
        result = subprocess.run(["gdparse", str(GD_FILE)], capture_output=True, text=True)
        if result.returncode == 0:
            log("✅ Syntax check passed.")
        else:
            log(f"❌ Syntax error after fixes:\n{result.stderr}")
            log("Restoring backup...")
            shutil.copy(backup, GD_FILE)
            sys.exit(1)
    else:
        log("⚠️  gdparse not installed – skipping syntax verification.")

    log(f"\n🎉 All fixes applied successfully! Full log saved to: {LOG_FILE}")

if __name__ == "__main__":
    main()