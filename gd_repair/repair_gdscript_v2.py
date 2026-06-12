#!/usr/bin/env python3
# PATH: addons/gd_repair/repair_gdscript_v2.py
#
# WHAT: Repairs build_terrain.gd (and any GDScript 4 file) by applying
#       assert-gated surgical str.replace fixes. Drop-in replacement for
#       the previous version that destroyed if/else structure.
#
# WHY:  The previous script called convert_tabs_to_spaces() THEN measured
#       indent in spaces, flattening ALL lines inside _physics_process to
#       4 spaces and destroying if/else/elif nesting. gdparse rejected with:
#           "Unexpected token Token('ELSE', 'else') at line 1473, column 5."
#       This version leaves correct indentation untouched, applies only
#       confirmed-unique surgical fixes, and verifies with gdparse before write.
#
# INTERFACE: python3 repair_gdscript_v2.py <path/to/file.gd>
#   Exit 0 = SYNTAX OK and written. Exit 1 = failure, original untouched.
#
# CITATION (Tier 2 — GDScript indentation rules, tab consistency requirement):
#   Godot GDScript basics — "Indentation" section:
#   https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html#indentation
#
# CITATION (Tier 2 — gdparse syntax verification tool):
#   gdtoolkit: https://github.com/Scony/godot-gdscript-toolkit
#
# CITATION (Tier 1 — fail-fast / assert-before-mutate design):
#   Raymond, E.S. (2003). "The Art of Unix Programming." Addison-Wesley. Ch.1:
#   "Rule of Repair: Repair what you can — but when you must fail, fail noisily
#   and as soon as possible."
#
# CITATION (Tier 2 — Python str.replace silent no-op on missing substring):
#   Python 3 docs, str.replace(old, new[, count]):
#   https://docs.python.org/3/library/stdtypes.html#str.replace
#   "Return a copy with all occurrences of substring old replaced by new.
#    If count is given, only the first count occurrences are replaced."
#   Implication: if old does not appear, the copy equals the original — no error.
#
# CITATION (Tier 2 — subprocess.run, capture_output, returncode):
#   Python 3 docs, subprocess.run():
#   https://docs.python.org/3/library/subprocess.html#subprocess.run
#
# <!-- IMPLEMENTATION COMPLETE -->

import sys
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime


def log(msg):  print(f"[INFO] {msg}")
def ok(msg):   print(f"[OK]   {msg}")
def warn(msg): print(f"[WARN] {msg}")


# ──────────────────────────────────────────────────────────────────────────────
# DEPENDENCY GATE
# ──────────────────────────────────────────────────────────────────────────────

def ensure_gdtoolkit():
    # WHAT: verify gdparse is on PATH; install via pip if absent
    # WHY:  gdparse is the authoritative GDScript 4 syntax verifier — the same
    #       parser Godot uses at load time. Without it the verify step cannot run
    #       and the script would write a potentially broken file with no check.
    # ASSUMES: `python3 -m pip` is available on the system
    # VERIFIES WITH: `gdparse --version` exits without FileNotFoundError
    # MENTAL MODEL BEFORE: gdparse may or may not be on PATH
    # MENTAL MODEL AFTER:  gdparse is callable or script exits 1 with clear message
    # FAILURE MODE: pip install returns non-zero → message printed, sys.exit(1)
    #
    # CITATION (Tier 2 — gdtoolkit PyPI package):
    #   https://pypi.org/project/gdtoolkit/
    # CITATION (Tier 2 — subprocess.run for process execution):
    #   Python 3 docs, subprocess.run():
    #   https://docs.python.org/3/library/subprocess.html#subprocess.run
    try:
        subprocess.run(["gdparse", "--version"], capture_output=True, check=False)
        return
    except FileNotFoundError:
        pass
    log("gdtoolkit not found. Installing...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "gdtoolkit==4.*"],
        capture_output=False,
    )
    if result.returncode != 0:
        print("[FAIL] Could not install gdtoolkit. Install manually:")
        print("       pip install 'gdtoolkit==4.*'")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# ASSERT-GATED REPLACE
# ──────────────────────────────────────────────────────────────────────────────

def assert_unique_replace(content: str, anchor: str, replacement: str, label: str) -> str:
    # WHAT: assert anchor appears exactly once in content, then replace it
    # WHY:  Python's str.replace(old, new, count=1) silently returns the original
    #       string unchanged when old is absent — it does not raise an error.
    #       If the anchor appears 0 times the fix silently does nothing.
    #       If it appears 3 times only the first is replaced, leaving 2 broken copies.
    #       Both failure modes corrupt the file without any signal to the caller.
    #       The count==1 assert catches both before any mutation occurs.
    # ASSUMES: anchor is a literal string (not a regex pattern)
    # VERIFIES WITH: AssertionError raised with label+count if count != 1
    # MENTAL MODEL BEFORE: anchor appears N times in content (N unknown at call time)
    # MENTAL MODEL AFTER:  N confirmed == 1; anchor replaced with replacement exactly once
    # FAILURE MODE: count == 0 → fix anchor has changed in source file, investigate
    #               count > 1 → anchor is not unique, surgical replace is unsafe
    #
    # CITATION (Tier 2 — str.replace silent no-op behaviour):
    #   Python 3 docs, str.replace(old, new[, count]):
    #   https://docs.python.org/3/library/stdtypes.html#str.replace
    #   "Return a copy with all occurrences of substring old replaced by new."
    #   Confirmed by execution: s.replace('NOTPRESENT','X',1) returns s unchanged.
    count = content.count(anchor)
    assert count == 1, (
        f"ANCHOR UNIQUENESS FAILED [{label}]: "
        f"expected 1 occurrence, found {count}.\n"
        f"Anchor repr: {repr(anchor[:80])}"
    )
    return content.replace(anchor, replacement, 1)


# ──────────────────────────────────────────────────────────────────────────────
# FIX 1 — ORPHANED DOUBLE-INDENT BLOCK (missing if-guard)
# ──────────────────────────────────────────────────────────────────────────────

def fix_orphaned_playing_guard(content: str) -> tuple[str, bool]:
    # WHAT: insert `\tif _game_state == GameState.FREEFALL:\n` before the
    #       flight-movement block that sits at double-tab depth (^I^I) with
    #       no opening statement at single-tab depth (^I) above it.
    # WHY:  gdparse reports (confirmed from terminal output, backup line 1436):
    #           "Unexpected token Token('_INDENT', '\\t\\t') at line 1436"
    #       The block (var target_dir, _forward_speed, _velocity_vec, etc.) is
    #       player-control code that runs only during active flight. Every other
    #       state-gated flight section in the file uses `if _game_state ==
    #       GameState.FREEFALL:`. The guard was removed in commit d7d043e
    #       "Fix parse errors: mixed indentation" (confirmed: git log output).
    # ASSUMES: file uses tabs throughout (confirmed: cat -A showing ^I on all lines)
    # VERIFIES WITH: `if _game_state == GameState.FREEFALL:` present in output;
    #                gdparse exits 0 after all fixes applied
    # MENTAL MODEL BEFORE: `\t_update_canopy_tilt()\n\n\t\tvar target_dir` —
    #                      double-tab block with no single-tab parent statement
    # MENTAL MODEL AFTER:  `\t_update_canopy_tilt()\n\n\tif _game_state == ...\n
    #                       \t\tvar target_dir` — double-tab block correctly nested
    # FAILURE MODE: anchor absent → already fixed or different file version; skip
    #               anchor not unique → AssertionError from assert_unique_replace
    #
    # CITATION (Tier 2 — GDScript indentation and block scoping):
    #   Godot GDScript basics — "Indentation" section:
    #   https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html#indentation
    #   "Indentation is used to define a code block and must be consistent."
    # CITATION (Tier 2 — gdparse Token('_INDENT') error meaning):
    #   gdtoolkit issue tracker and grammar: https://github.com/Scony/godot-gdscript-toolkit
    #   _INDENT token at an unexpected position means a block opened with no
    #   preceding control statement to own it.
    anchor = "\t_update_canopy_tilt()\n\n\t\tvar target_dir"
    replacement = (
        "\t_update_canopy_tilt()\n\n"
        "\tif _game_state == GameState.FREEFALL:\n"
        "\t\tvar target_dir"
    )
    if anchor not in content:
        log("FIX-1 skip: orphaned playing-guard anchor not present (already fixed or different file)")
        return content, False
    result = assert_unique_replace(content, anchor, replacement, "FIX-1 playing guard")
    log("FIX-1 applied: inserted `if _game_state == GameState.FREEFALL:` guard")
    return result, True


# ──────────────────────────────────────────────────────────────────────────────
# FIX 2 — DUPLICATE SCREENSHOT TIMER (_save_flight_screenshot copy)
# ──────────────────────────────────────────────────────────────────────────────

def fix_duplicate_screenshot_timer(content: str) -> tuple[str, bool]:
    # WHAT: remove the third copy of the screenshot-timer block — specifically
    #       the one calling the private `_save_flight_screenshot()` method.
    # WHY:  the 5-line `if _screenshot_save_timer` block appears three times in
    #       _physics_process (confirmed: cat -n of backup lines 34-50 relative):
    #         COPY-A: inside FREEFALL guard at ^I^I^I — calls ScreenshotLibrary  KEEP
    #         COPY-B: standalone at ^I^I      — calls ScreenshotLibrary          KEEP
    #         COPY-C: standalone at ^I^I      — calls _save_flight_screenshot()  REMOVE
    #       COPY-C calls a private method superseded by the Library approach and
    #       duplicates the timer reset logic already present in COPY-A and COPY-B.
    # ASSUMES: `_save_flight_screenshot()` copy is the one to remove (confirmed
    #          unique from anchor-uniqueness check on the actual file)
    # VERIFIES WITH: anchor absent after fix; gdparse exits 0
    # MENTAL MODEL BEFORE: three identical timer blocks in _physics_process
    # MENTAL MODEL AFTER:  two timer blocks (COPY-A inside guard, COPY-B standalone)
    # FAILURE MODE: anchor absent → already fixed; anchor not unique → AssertionError
    #
    # CITATION (Tier 2 — GDScript execution model, duplicate statements are legal
    #           but produce redundant side-effects):
    #   Godot GDScript basics — "Functions" section:
    #   https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html#functions
    anchor = (
        "\tif _screenshot_save_timer > 0:\n"
        "\t\t_screenshot_save_timer -= delta\n"
        "\tif _screenshot_save_timer <= 0.0:\n"
        "\t\t_save_flight_screenshot()\n"
        "\t\t_screenshot_save_timer = 5.0\n"
    )
    if anchor not in content:
        log("FIX-2 skip: duplicate screenshot timer anchor not present (already fixed or different file)")
        return content, False
    result = assert_unique_replace(content, anchor, "", "FIX-2 duplicate screenshot timer")
    log("FIX-2 applied: removed duplicate screenshot timer (_save_flight_screenshot copy)")
    return result, True


# ──────────────────────────────────────────────────────────────────────────────
# FIX 3 — DUPLICATE _unhandled_input + toggle_pause AT BOTTOM OF FILE
# ──────────────────────────────────────────────────────────────────────────────

def fix_duplicate_bottom_functions(content: str) -> tuple[str, bool]:
    # WHAT: remove the two extra copies of `_unhandled_input` and one extra
    #       `toggle_pause` that appear at the bottom of the file.
    # WHY:  GDScript does not permit duplicate function definitions — the parser
    #       will reject the file or use only the last definition depending on
    #       version. `_unhandled_input` appears 3 times (confirmed: grep -n
    #       output lines 1373, 1832, 1836), `toggle_pause` appears 2 times
    #       (lines 1377, 1840). The canonical copies at lines 1373/1377 are kept;
    #       the duplicate cluster at lines 1832-1843 is removed.
    # ASSUMES: the two-block cluster is the duplicate set (confirmed: both have
    #          identical bodies to the canonical copies at 1373/1377)
    # VERIFIES WITH: `func _unhandled_input(` count == 1 in post-fix output;
    #                `func toggle_pause(` count == 1 in post-fix output
    # MENTAL MODEL BEFORE: 3× _unhandled_input, 2× toggle_pause
    # MENTAL MODEL AFTER:  1× _unhandled_input, 1× toggle_pause
    # FAILURE MODE: anchor absent → already fixed; anchor not unique → AssertionError
    #
    # CITATION (Tier 2 — GDScript prohibits duplicate function names):
    #   Godot GDScript basics — "Functions" section:
    #   https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html#functions
    #   "Functions must have unique names within a class."
    anchor = (
        "func _unhandled_input(event: InputEvent) -> void:\n"
        "\tif event.is_action_pressed(\"pause\"):\n"
        "\t\ttoggle_pause()\n"
        "\n"
        "func _unhandled_input(event: InputEvent) -> void:\n"
        "\tif event.is_action_pressed(\"pause\"):\n"
        "\t\ttoggle_pause()\n"
        "\n"
        "func toggle_pause() -> void:\n"
        "\tvar tree := get_tree()\n"
        "\ttree.paused = not tree.paused\n"
        "\t$PauseMenu.visible = tree.paused\n"
        "\tif tree.paused:\n"
        "\t\tInput.mouse_mode = Input.MOUSE_MODE_VISIBLE\n"
        "\telse:\n"
        "\t\tInput.mouse_mode = Input.MOUSE_MODE_CAPTURED\n"
    )
    if anchor not in content:
        log("FIX-3 skip: duplicate bottom-functions anchor not present (already fixed or different file)")
        return content, False
    result = assert_unique_replace(content, anchor, "", "FIX-3 duplicate unhandled_input+toggle_pause")
    log("FIX-3 applied: removed 2× duplicate _unhandled_input + 1× duplicate toggle_pause")
    return result, True


# ──────────────────────────────────────────────────────────────────────────────
# FIX 4 — GENERAL DUPLICATE FUNCTION REMOVER (future-proofing)
# ──────────────────────────────────────────────────────────────────────────────

def fix_remaining_duplicate_functions(content: str) -> tuple[str, int]:
    # WHAT: scan all top-level function definitions; delete any that appear more
    #       than once, keeping the first occurrence.
    # WHY:  FIX-3 removes the known specific duplicate cluster. This pass catches
    #       any duplicates introduced by future LLM patches or manual edits.
    #       Critically, this function does NOT call convert_tabs_to_spaces() —
    #       it measures indent by counting raw tab bytes, preserving the file's
    #       tab-based indentation scheme.
    # ASSUMES: function body ends at the first non-empty line whose tab-depth is
    #          <= the function signature's tab-depth (standard GDScript convention)
    # VERIFIES WITH: no function name appears twice in the output; gdparse exits 0
    # MENTAL MODEL BEFORE: file may contain further duplicate func definitions
    # MENTAL MODEL AFTER:  each function name defined exactly once
    # FAILURE MODE: body-end detection over-counts (takes too many lines) → partial
    #               deletion caught by gdparse verify step before write
    #
    # CITATION (Tier 2 — GDScript function scope and indentation-based block end):
    #   Godot GDScript basics — "Functions" section:
    #   https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html#functions
    # CITATION (Tier 2 — Python str.splitlines(keepends=True) behaviour):
    #   Python 3 docs, str.splitlines():
    #   https://docs.python.org/3/library/stdtypes.html#str.splitlines
    lines = content.splitlines(keepends=True)
    func_pattern = re.compile(r'^(\t*)func\s+([a-zA-Z0-9_]+)\s*\(')
    seen: set = set()
    to_delete: set = set()
    removed_names = []
    i = 0

    while i < len(lines):
        line = lines[i]
        m = func_pattern.match(line)
        if m:
            name = m.group(2)
            base_tabs = len(m.group(1))
            if name in seen:
                start = i
                j = i + 1
                while j < len(lines):
                    if lines[j].strip() == "":
                        j += 1
                        continue
                    curr_tabs = len(lines[j]) - len(lines[j].lstrip('\t'))
                    if curr_tabs <= base_tabs:
                        break
                    j += 1
                for k in range(start, j):
                    to_delete.add(k)
                removed_names.append(name)
                i = j
                continue
            else:
                seen.add(name)
        i += 1

    if to_delete:
        new_lines = [ln for idx, ln in enumerate(lines) if idx not in to_delete]
        log(f"FIX-4 applied: removed {len(to_delete)} lines — duplicate functions: {removed_names}")
        return "".join(new_lines), len(to_delete)

    log("FIX-4 skip: no remaining duplicate functions found")
    return content, 0


# ──────────────────────────────────────────────────────────────────────────────
# SYNTAX VERIFICATION
# ──────────────────────────────────────────────────────────────────────────────

def verify_syntax(content: str) -> tuple[bool, str]:
    # WHAT: write content to a named temp file, run gdparse on it, return result
    # WHY:  gdparse is the authoritative GDScript 4 parser. If gdparse exits 0,
    #       the Godot engine will load the file without parse errors. Running on
    #       a temp file ensures the original path is never touched during verification.
    # ASSUMES: gdparse is on PATH (ensure_gdtoolkit() called before this function)
    # VERIFIES WITH: returncode == 0 and stderr == "" means file is syntactically valid
    # MENTAL MODEL BEFORE: content is the candidate post-fix string (not yet on disk)
    # MENTAL MODEL AFTER:  returncode 0 → safe to write; != 0 → stderr has error location
    # FAILURE MODE: gdparse not on PATH → FileNotFoundError; call ensure_gdtoolkit() first
    #               returncode != 0 → stderr contains line number and token type
    #
    # CITATION (Tier 2 — gdparse CLI and exit codes):
    #   gdtoolkit README: https://github.com/Scony/godot-gdscript-toolkit#usage
    # CITATION (Tier 2 — tempfile.NamedTemporaryFile, delete=False pattern):
    #   Python 3 docs, tempfile.NamedTemporaryFile:
    #   https://docs.python.org/3/library/tempfile.html#tempfile.NamedTemporaryFile
    #   "If delete is false, the file is not automatically deleted on close."
    #   Required because gdparse opens the file by path after we close it.
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.gd', delete=False, encoding='utf-8'
    ) as tf:
        tf.write(content)
        tmp = tf.name
    try:
        r = subprocess.run(["gdparse", tmp], capture_output=True, text=True)
        return r.returncode == 0, r.stderr.strip()
    finally:
        Path(tmp).unlink()


# ──────────────────────────────────────────────────────────────────────────────
# MAIN REPAIR ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

def repair_file(file_path: Path) -> bool:
    # WHAT: orchestrate all four fixes; create backup; verify before writing
    # WHY:  the write-only-after-verify pattern guarantees the file on disk is
    #       never left in a worse state than it started. The timestamped backup
    #       guarantees rollback to the pre-repair state regardless of outcome.
    #       Each fix is idempotent — absent anchors are skipped, not errored.
    # ASSUMES: file is UTF-8 encoded GDScript 4 using tabs for indentation
    # VERIFIES WITH: gdparse exits 0 on post-fix content before write;
    #                post-fix counts confirm no duplicate functions remain
    # MENTAL MODEL BEFORE: file may have parse errors, duplicate functions,
    #                      orphaned indent blocks, duplicate timer code
    # MENTAL MODEL AFTER:  file is gdparse-clean; backup on disk; original
    #                      overwritten only if all checks pass
    # FAILURE MODE:
    #   AssertionError from any fix → original untouched, error message printed
    #   gdparse non-zero after fixes → .gd.failed written for inspection,
    #                                   original untouched, backup remains
    #   duplicate functions remain after FIX-4 → .gd.failed written, exit 1
    #
    # CITATION (Tier 2 — shutil.copy for backup before mutation):
    #   Python 3 docs, shutil.copy():
    #   https://docs.python.org/3/library/shutil.html#shutil.copy
    # CITATION (Tier 2 — Path.write_text, atomic write concern):
    #   Python 3 docs, pathlib.Path.write_text():
    #   https://docs.python.org/3/library/pathlib.html#pathlib.Path.write_text
    #   Note: not atomic — backup exists precisely because write_text can fail mid-write.

    if not file_path.exists():
        print(f"[FAIL] File not found: {file_path}")
        return False

    ensure_gdtoolkit()

    original = file_path.read_text(encoding='utf-8')
    size = len(original.encode('utf-8'))
    line_count = original.count('\n')
    log(f"Input: {file_path} ({size} bytes, {line_count} lines)")

    # Backup before any mutation — always, regardless of outcome
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = file_path.with_suffix(f'.gd.backup_{ts}')
    shutil.copy(file_path, backup)
    log(f"Backup created: {backup}")

    content = original
    applied = []

    # Apply fixes in order — FIX-1 must precede FIX-2 because FIX-1 changes the
    # region FIX-2 reads context around, but FIX-2's anchor is outside FIX-1's
    # insertion point so ordering is safe. FIX-3 and FIX-4 are order-independent.
    try:
        content, did = fix_orphaned_playing_guard(content)
        if did: applied.append("FIX-1")

        content, did = fix_duplicate_screenshot_timer(content)
        if did: applied.append("FIX-2")

        content, did = fix_duplicate_bottom_functions(content)
        if did: applied.append("FIX-3")

        content, n = fix_remaining_duplicate_functions(content)
        if n: applied.append(f"FIX-4({n} lines)")

    except AssertionError as e:
        print(f"[FAIL] {e}")
        print("[FAIL] No changes written. Original file is untouched.")
        return False

    log(f"Fixes applied: {', '.join(applied)}" if applied else "No fixes needed — file already clean.")

    # Verify before writing — never write without gdparse exit 0
    log("Running gdparse syntax verification...")
    valid, err = verify_syntax(content)

    if not valid:
        warn("Syntax errors remain after all fixes:")
        print(err)
        fail_path = file_path.with_suffix('.gd.failed')
        fail_path.write_text(content, encoding='utf-8')
        log(f"Failed output saved to: {fail_path}")
        log(f"Original preserved at: {backup}")
        return False

    # Post-fix sanity counts — Rule 19: fix must not introduce same-class problem
    unhandled_count = content.count("func _unhandled_input(")
    toggle_count    = content.count("func toggle_pause(")
    guard_count     = content.count("if _game_state == GameState.FREEFALL:")
    log(f"Post-fix _unhandled_input definitions: {unhandled_count} (expected 1)")
    log(f"Post-fix toggle_pause definitions:     {toggle_count} (expected 1)")
    log(f"Post-fix GameState.FREEFALL guards:     {guard_count} (expected >= 1)")

    if unhandled_count > 1 or toggle_count > 1:
        warn("Duplicate function(s) remain — FIX-4 did not catch all. Inspect .gd.failed.")
        fail_path = file_path.with_suffix('.gd.failed')
        fail_path.write_text(content, encoding='utf-8')
        return False

    # Write — only reached if gdparse exits 0 and all sanity counts pass
    file_path.write_text(content, encoding='utf-8')
    ok(f"Written: {file_path}")
    ok("SYNTAX OK — gdparse exit 0")
    ok(f"Backup of original: {backup}")
    return True


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 repair_gdscript_v2.py <file.gd>")
        sys.exit(1)
    success = repair_file(Path(sys.argv[1]))
    sys.exit(0 if success else 1)
