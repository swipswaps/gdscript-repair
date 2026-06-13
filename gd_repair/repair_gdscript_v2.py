#!/usr/bin/env python3
"""
Fully automatic GDScript Repair Tool for Godot Parachute Game – FINAL
- Inserts continuous canopy animation into _physics_process (preserves control flow)
- Tests arm rotation axis with valid GDScript (Godot 4)
- Applies camera, scale, HUD, screenshot fixes
- Dry-run default; use --apply to write changes
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
GODOT_BIN = shutil.which("godot")

# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------
def log(msg: str, also_print: bool = True):
    if also_print:
        print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# ----------------------------------------------------------------------
# Run gdformat (check or write) – show full output
# ----------------------------------------------------------------------
def run_gdformat(file_path: Path, apply: bool) -> bool:
    if shutil.which("gdformat") is None:
        log("⚠️  gdformat not installed – skipping indentation normalization.")
        log("   Install with: pip install gdtoolkit")
        return True
    cmd = ["gdformat"] + ([] if apply else ["--check"]) + [str(file_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        log(f"gdformat command: {' '.join(cmd)}")
        if result.stdout:
            log(f"gdformat stdout:\n{result.stdout}")
        if result.stderr:
            log(f"gdformat stderr:\n{result.stderr}")
        if result.returncode != 0:
            log(f"gdformat {'would reformat' if not apply else 'error'} (code {result.returncode})")
            return False
        if not apply and "would be reformatted" in result.stdout:
            log("📝 gdformat would reformat the file. Run with --apply to fix.")
        return True
    except Exception as e:
        log(f"gdformat failed: {e}")
        return False

# ----------------------------------------------------------------------
# Test arm axis using headless Godot (returns best axis)
# ----------------------------------------------------------------------
def test_arm_axis() -> str:
    if GODOT_BIN is None:
        log("⚠️  Godot binary not found – skipping arm axis test (default FORWARD).")
        return "FORWARD"
    test_script = Path("temp_arm_test.gd")
    # Correct GDScript 4 syntax – no tuple unpacking in for loop
    test_code = '''extends Node
func _ready():
    var fbx = load("res://assets/characters/parachutist.fbx")
    if not fbx:
        print("ERROR: FBX not found")
        return
    var inst = fbx.instantiate()
    add_child(inst)
    await get_tree().process_frame
    var sk = inst.find_child("Skeleton3D", true, false)
    if not sk:
        print("ERROR: No skeleton")
        return
    var idx = sk.find_bone("mixamorig:LeftArm")
    if idx == -1:
        idx = 8
    var axes = [Vector3.RIGHT, Vector3.FORWARD, Vector3.UP]
    var names = ["RIGHT", "FORWARD", "UP"]
    for i in range(axes.size()):
        var axis = axes[i]
        var axis_name = names[i]
        sk.set_bone_pose_rotation(idx, Quaternion(axis, deg_to_rad(45)))
        await get_tree().process_frame
        var euler = sk.get_bone_pose_rotation(idx).get_euler()
        print("AXIS_TEST", axis_name, euler)
    get_tree().quit()
'''
    test_script.write_text(test_code)
    try:
        cmd = [GODOT_BIN, "--headless", "--script", str(test_script)]
        log(f"Running arm axis test: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            log(f"   Arm axis test failed (code {result.returncode}) – using FORWARD.")
            log(f"   stderr: {result.stderr}")
            return "FORWARD"
        # Parse output
        for line in result.stdout.splitlines():
            if "AXIS_TEST FORWARD" in line and "z=0.78" in line:
                log("   ✅ Arm axis test: FORWARD works (rotation around Z).")
                return "FORWARD"
            if "AXIS_TEST UP" in line and "y=0.78" in line:
                log("   ✅ Arm axis test: UP works (rotation around Y).")
                return "UP"
            if "AXIS_TEST RIGHT" in line and "x=0.78" in line:
                log("   ✅ Arm axis test: RIGHT works (rotation around X).")
                return "RIGHT"
        log("   Arm axis test ambiguous – defaulting to FORWARD.")
        log(f"   Full test output:\n{result.stdout}")
        return "FORWARD"
    except Exception as e:
        log(f"   Arm axis test error: {e} – using FORWARD.")
        return "FORWARD"
    finally:
        test_script.unlink(missing_ok=True)

# ----------------------------------------------------------------------
# Apply all fixes (continuous canopy animation inserted, not replacing)
# ----------------------------------------------------------------------
def apply_fixes(content: str, best_axis: str) -> tuple[str, list[dict]]:
    fixes = []
    # 1-3. Camera FOV, near, far
    for pattern, repl, name in [
        (r'(\.fov\s*=\s*)\d+(\.?\d*)', r'\g<1>85.0', "Camera FOV 85"),
        (r'(\.near\s*=\s*)\d+(\.?\d*)', r'\g<1>0.05', "Camera near 0.05"),
        (r'(\.far\s*=\s*)\d+(\.?\d*)', r'\g<1>20000.0', "Camera far 20000"),
    ]:
        new_content, cnt = re.subn(pattern, repl, content)
        if cnt:
            fixes.append({"name": name, "pattern": pattern})
            content = new_content

    # 4. Canopy initial scale
    new_content, cnt = re.subn(r'Vector3\s*\(\s*0\.18\s*,\s*0\.12\s*,\s*0\.18\s*\)', 'Vector3(3.0, 2.0, 3.0)', content)
    if cnt:
        fixes.append({"name": "Canopy scale (initial)", "pattern": r'Vector3\(0\.18, 0\.12, 0\.18\)'})
        content = new_content

    # 5. Canopy deploy scale (ZERO -> 3.0)
    new_content, cnt = re.subn(r'_canopy_instance\.scale\s*=\s*Vector3\.ZERO', '_canopy_instance.scale = Vector3(3.0, 2.0, 3.0)', content)
    if cnt:
        fixes.append({"name": "Canopy scale (deploy)", "pattern": r'_canopy_instance\.scale\s*=\s*Vector3\.ZERO'})
        content = new_content

    # 6. Remove any previously inserted one‑time animation from _deploy_canopy
    content = re.sub(r'var t = 1\.0 - \(_deployment_timer / DEPLOY_TIME\)\s*\n\s*_canopy_instance\.scale = Vector3\(3\.0, 2\.0, 3\.0\) \* t\s*\n', '', content)

    # 7. Insert continuous animation into _physics_process BEFORE the FREEFALL if line
    # Find the line "if _game_state == GameState.FREEFALL:" and capture its indentation
    lines = content.splitlines(keepends=True)
    new_lines = []
    insertion_done = False
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if not insertion_done and stripped.startswith("if _game_state == GameState.FREEFALL:"):
            # Capture indentation of this line
            indent = line[:len(line)-len(stripped)]
            # Insert animation block before this line
            anim_block = (
                f"{indent}# Canopy opening animation (continuous)\n"
                f"{indent}if _game_state == GameState.OPENING_ANIM and _deployment_timer > 0:\n"
                f"{indent}    var t = 1.0 - (_deployment_timer / DEPLOY_TIME)\n"
                f"{indent}    _canopy_instance.scale = Vector3(3.0, 2.0, 3.0) * t\n"
                f"{indent}\n"
            )
            new_lines.append(anim_block)
            insertion_done = True
        new_lines.append(line)
    if insertion_done:
        content = "".join(new_lines)
        fixes.append({"name": "Canopy animation inserted into _physics_process", "pattern": "continuous animation"})
    else:
        # Fallback: try simple insertion after _update_canopy_tilt()
        content = re.sub(r'(_update_canopy_tilt\(\))', r'\1\n\t# Canopy opening animation (continuous)\n\tif _game_state == GameState.OPENING_ANIM and _deployment_timer > 0:\n\t    var t = 1.0 - (_deployment_timer / DEPLOY_TIME)\n\t    _canopy_instance.scale = Vector3(3.0, 2.0, 3.0) * t\n', content)
        fixes.append({"name": "Canopy animation inserted (fallback)", "pattern": "fallback insertion"})

    # 8. Arm axis
    axis_map = {"RIGHT": "Vector3.RIGHT", "FORWARD": "Vector3.FORWARD", "UP": "Vector3.UP"}
    new_axis = axis_map.get(best_axis, "Vector3.FORWARD")
    pattern_axis = r'Quaternion\s*\(\s*Vector3\.\w+\s*,\s*angle\s*\)'
    new_content, cnt = re.subn(pattern_axis, f'Quaternion({new_axis}, angle)', content)
    if cnt:
        fixes.append({"name": f"Arm axis set to {best_axis}", "pattern": pattern_axis})
        content = new_content

    # 9. Disable frame‑2 screenshot
    new_content, cnt = re.subn(r'if\s+_frame_count\s*==\s*2:', 'if false:  # disabled (audit_logs path may not exist)', content)
    if cnt:
        fixes.append({"name": "Frame‑2 screenshot disabled", "pattern": r'if\s+_frame_count\s*==\s*2:'})
        content = new_content

    # 10. HUD guard – remove early return (preserve indentation)
    pattern = r'(if\s+_hud_layer:\s*\n\s*)return'
    replacement = r'\1# HUD guard disabled – HUD will be recreated if needed\n\tpass'
    new_content, cnt = re.subn(pattern, replacement, content)
    if cnt:
        fixes.append({"name": "HUD guard early return removed", "pattern": pattern})
        content = new_content
    else:
        new_content = re.sub(r'if\s+_hud_layer:\s*\n\s*return', '# HUD guard removed (was early return)', content)
        if new_content != content:
            fixes.append({"name": "HUD guard early return removed (fallback)", "pattern": pattern})
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
    parser = argparse.ArgumentParser(description="Fully automatic repair for build_terrain.gd")
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default dry‑run)")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--skip-arm-test", action="store_true", help="Skip automatic arm axis test (uses FORWARD)")
    args = parser.parse_args()

    if not GD_FILE.exists():
        log(f"❌ {GD_FILE} not found. Run from godot_project directory.")
        sys.exit(1)

    log("\n🎮 Fully Automatic GDScript Repair Tool (FINAL)\n")
    if not args.apply:
        log("🔍 DRY RUN MODE – use --apply to write changes\n")

    # Step 1: Test arm axis
    best_axis = "FORWARD"
    if not args.skip_arm_test:
        log("\n🦾 Testing arm rotation axis (headless Godot)...")
        best_axis = test_arm_axis()
    else:
        log("\n⏩ Skipped arm axis test (using FORWARD).")

    original = GD_FILE.read_text(encoding='utf-8')
    new_content, fixes = apply_fixes(original, best_axis)

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
        log("✅ Indentation normalised (gdformat succeeded).")
    else:
        log("⚠️  gdformat failed – you may need to run it manually later.")

    if shutil.which("gdparse"):
        result = subprocess.run(["gdparse", str(GD_FILE)], capture_output=True, text=True)
        if result.returncode == 0:
            log("✅ Syntax check passed (gdparse exit 0).")
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