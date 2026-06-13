@tool
extends EditorScript

# ------------------------------------------------------------------
# Main entry point – executed when you press File → Run (Ctrl+Shift+X)
# ------------------------------------------------------------------
func _run():
    print("🛠️ GDScript Repair Tool (EditorScript version)")
    var script_path = "res://scripts/build_terrain.gd"
    var script_res: Script = load(script_path)
    if not script_res:
        printerr("ERROR: Could not load script at ", script_path)
        return

    var source_code = script_res.source_code
    var new_code = apply_fixes(source_code)
    if new_code == source_code:
        print("No fixes needed.")
        return

    # Show diff in Output panel (simplified)
    print("\n📝 Changes to apply:")
    var old_lines = source_code.split("\n")
    var new_lines = new_code.split("\n")
    for i in range(min(old_lines.size(), new_lines.size())):
        if old_lines[i] != new_lines[i]:
            print(f"Line {i+1}: - {old_lines[i]}")
            print(f"         + {new_lines[i]}")

    var editor = EditorInterface.get_singleton()
    editor.edit_script(script_res, -1, -1, false)
    script_res.source_code = new_code
    print("\n✅ Fixes applied successfully. Reopen the script to see changes.")

# ------------------------------------------------------------------
# Apply all safe fixes (same as Python version)
# ------------------------------------------------------------------
func apply_fixes(content: String) -> String:
    var changes = []

    # FIX-A
    if content.find('print("[VERBATIM] _hide_loading_screen()")') != -1:
        content = content.replace('print("[VERBATIM] _hide_loading_screen()")', '_hide_loading_screen()')
        changes.append("FIX-A")

    # FIX-B: scale
    if content.find('_canopy_instance.scale = Vector3(0.18, 0.12, 0.18)') != -1:
        content = content.replace('_canopy_instance.scale = Vector3(0.18, 0.12, 0.18)', '_canopy_instance.scale = Vector3(3.0, 2.0, 3.0)')
        changes.append("FIX-B (initial scale)")
    if content.find('_canopy_instance.scale = Vector3.ZERO') != -1:
        content = content.replace('_canopy_instance.scale = Vector3.ZERO', '_canopy_instance.scale = Vector3(3.0, 2.0, 3.0)')
        changes.append("FIX-B (deploy scale)")

    # Animation insertion
    if content.find('_game_state = GameState.OPENING_ANIM') != -1 and content.find('var t = 1.0 -') == -1:
        var anim = "\n\tvar t = 1.0 - (_deployment_timer / DEPLOY_TIME)\n\t_canopy_instance.scale = Vector3(3.0, 2.0, 3.0) * t\n"
        content = content.replace('_game_state = GameState.OPENING_ANIM', '_game_state = GameState.OPENING_ANIM' + anim)
        changes.append("FIX-B (animation)")

    # FIX-C: camera
    if content.find('.fov = 75.0') != -1:
        content = content.replace('.fov = 75.0', '.fov = 85.0')
        changes.append("FIX-C (FOV)")
    if content.find('.near = 0.1') != -1:
        content = content.replace('.near = 0.1', '.near = 0.05')
        changes.append("FIX-C (near plane)")
    if content.find('.far = 10000.0') != -1:
        content = content.replace('.far = 10000.0', '.far = 20000.0')
        changes.append("FIX-C (far plane)")
    if content.find('Vector3(0.0, 2.0, 3.0)') != -1:
        content = content.replace('Vector3(0.0, 2.0, 3.0)', 'Vector3(0.0, 4.0, 8.0)')
        changes.append("FIX-C (offset)")
    if content.find('y + 1.0') != -1:
        content = content.replace('y + 1.0', 'y + 3.0')
        changes.append("FIX-C (look‑at)")

    # FIX-D
    if content.find('Quaternion(Vector3.RIGHT, angle)') != -1:
        content = content.replace('Quaternion(Vector3.RIGHT, angle)', 'Quaternion(Vector3.FORWARD, angle)')
        changes.append("FIX-D (arm axis)")

    # FIX-F
    if content.find('if _frame_count == 2:') != -1:
        content = content.replace('if _frame_count == 2:', 'if false:  # disabled (audit_logs path may not exist)')
        changes.append("FIX-F (screenshot)")

    # FIX-E (HUD guard) – preserve tabs
    var regex = RegEx.new()
    regex.compile("(if\\s+_hud_layer:\\s*\\n\\s*)return")
    if regex.search(content):
        content = regex.sub(content, "$1# HUD guard disabled – HUD will be recreated if needed\\n\\tpass")
        changes.append("FIX-E (HUD guard)")

    if changes.is_empty():
        print("No fixes needed.")
    else:
        print("Applied fixes: " + ", ".join(changes))
    return content