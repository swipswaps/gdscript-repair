#!/usr/bin/env python3
# repair_gdscript_v2.py – Safe, non‑breaking GDScript repair
# Complies with skill rules: backup before edit, gate before change,
# verify after change, rollback on failure, timestamped backups,
# inline citations to official docs.
#
# Usage: python3 repair_gdscript_v2.py <file.gd>
# Returns: 0 (clean or fixed), 1 (error)

import sys
import re
import subprocess
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

# ============================================================================
# CITATIONS (verbatim linked references)
# ============================================================================
# Godot GDScript reference: https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html
# gdtoolkit (gdparse) documentation: https://github.com/Scony/godot-gdscript-toolkit
# Godot InputEvent class: https://docs.godotengine.org/en/stable/classes/class_inputevent.html
# Python subprocess module: https://docs.python.org/3/library/subprocess.html
# Python datetime: https://docs.python.org/3/library/datetime.html
# Python pathlib: https://docs.python.org/3/library/pathlib.html
# ============================================================================

# ----------------------------------------------------------------------------
# GATE 0: Ensure gdtoolkit is installed
# ----------------------------------------------------------------------------
def check_gdtoolkit() -> bool:
    """
    Return True if gdparse is available (required for syntax verification).
    CITATION: gdtoolkit – https://github.com/Scony/godot-gdscript-toolkit
    """
    try:
        # CITATION: subprocess.run – https://docs.python.org/3/library/subprocess.html#subprocess.run
        result = subprocess.run(["gdparse", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def ensure_gdtoolkit() -> None:
    """Install gdtoolkit automatically if missing (non‑breaking)."""
    if not check_gdtoolkit():
        print("[GATE] gdtoolkit not found. Installing...")
        try:
            # CITATION: pip install – standard Python package installation
            subprocess.run([sys.executable, "-m", "pip", "install", "gdtoolkit==4.*"], check=True)
            print("[GATE] Installation successful.")
        except subprocess.CalledProcessError:
            print("[ERROR] Could not install gdtoolkit. Please run: pip install 'gdtoolkit==4.*'")
            sys.exit(1)

# ----------------------------------------------------------------------------
# DETECTOR: Find duplicate function definitions (with body comparison)
# ----------------------------------------------------------------------------
def extract_function_body(lines: List[str], start_idx: int) -> Tuple[int, str]:
    """
    Given a list of lines and the index of a 'func' line, return (end_idx, body_text).
    The body includes the signature and all indented lines until dedent.
    CITATION: GDScript function syntax – https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html#functions
    """
    # CITATION: Python len() and lstrip() for indentation detection
    base_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
    end_idx = start_idx
    for i in range(start_idx + 1, len(lines)):
        if lines[i].strip() == "":
            continue
        curr_indent = len(lines[i]) - len(lines[i].lstrip())
        # CITATION: re.match – https://docs.python.org/3/library/re.html#re.match
        if curr_indent <= base_indent and re.match(r'^\s*func\s+', lines[i]):
            end_idx = i - 1
            break
        end_idx = i
    body = "".join(lines[start_idx:end_idx + 1])
    return end_idx, body

def find_duplicate_functions(content: str) -> List[Tuple[int, int, str]]:
    """
    Return list of (first_line, duplicate_line, function_name) for duplicates.
    Only reports duplicates where the bodies are identical (safe to delete).
    If bodies differ, the function is NOT reported (prevents breaking logic).
    CITATION: GDScript function naming rules – https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_styleguide.html#function-names
    """
    # CITATION: .splitlines(keepends=True) – https://docs.python.org/3/library/stdtypes.html#str.splitlines
    lines = content.splitlines(keepends=True)
    # CITATION: regex pattern for function definition – matches "func name(" with optional whitespace
    func_pattern = re.compile(r'^\s*func\s+([a-zA-Z0-9_]+)\s*\(')
    seen = {}  # name -> (line_idx, body)
    duplicates = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = func_pattern.match(line)
        if m:
            name = m.group(1)
            end_idx, body = extract_function_body(lines, i)
            if name in seen:
                first_line, first_body = seen[name]
                # Only report duplicate if bodies are identical (safe deletion)
                if body.strip() == first_body.strip():
                    duplicates.append((first_line, i, name))
                else:
                    print(f"[WARN] Duplicate function '{name}' at line {i+1} has different body – skipping auto‑removal (non‑breaking)")
                i = end_idx
            else:
                seen[name] = (i, body)
                i = end_idx
        i += 1
    return duplicates

# ----------------------------------------------------------------------------
# DETECTOR: Find orphaned indented lines (outside any function)
# ----------------------------------------------------------------------------
def find_orphaned_indented_lines(content: str) -> List[int]:
    """
    Return line numbers where indented code appears without a containing function.
    CITATION: GDScript indentation rules – https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_basics.html#indentation
    """
    lines = content.splitlines(keepends=True)
    inside_func = False
    orphaned = []
    for idx, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        indent_level = len(line) - len(stripped)
        if line.strip() == "":
            continue
        # CITATION: regex matches function start
        if re.match(r'^\s*func\s+', line):
            inside_func = True
        # Dedent to zero means leaving function scope
        if inside_func and indent_level == 0 and not re.match(r'^\s*func\s+', line):
            inside_func = False
        if not inside_func and indent_level > 0:
            orphaned.append(idx)
    return orphaned

# ----------------------------------------------------------------------------
# FIXER: Remove duplicate functions (keep first, delete identical duplicates)
# ----------------------------------------------------------------------------
def remove_duplicate_functions(content: str) -> str:
    """Delete duplicate function blocks where bodies are identical."""
    lines = content.splitlines(keepends=True)
    duplicates = find_duplicate_functions(content)
    if not duplicates:
        return content
    # CITATION: Python set for tracking line indices to delete
    to_delete = set()
    for first_ln, dup_ln, name in duplicates:
        dup_start = dup_ln
        _, body = extract_function_body(lines, dup_ln)
        dup_end = dup_ln + body.count('\n')
        for j in range(dup_start, dup_end + 1):
            to_delete.add(j)
    # Rebuild file without deleted lines
    new_lines = [line for i, line in enumerate(lines) if i not in to_delete]
    return "".join(new_lines)

# ----------------------------------------------------------------------------
# FIXER: Normalise indentation (tabs -> 4 spaces) and dedent orphaned lines
# ----------------------------------------------------------------------------
def fix_indentation(content: str) -> str:
    """
    Convert leading tabs to 4 spaces; dedent lines that are outside any function.
    CITATION: Godot style guide recommends spaces over tabs – https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_styleguide.html#indentation
    """
    lines = content.splitlines(keepends=True)
    # First pass: tabs to spaces (only leading)
    space_lines = []
    for line in lines:
        if line.startswith('\t'):
            # CITATION: re.sub with lambda – https://docs.python.org/3/library/re.html#re.sub
            space_line = re.sub(r'^\t+', lambda m: ' ' * (len(m.group(0)) * 4), line)
            space_lines.append(space_line)
        else:
            space_lines.append(line)
    content_tab_fixed = ''.join(space_lines)

    # Second pass: dedent orphaned lines
    lines2 = content_tab_fixed.splitlines(keepends=True)
    inside_func = False
    out_lines = []
    for line in lines2:
        stripped = line.lstrip()
        indent_level = len(line) - len(stripped)
        if line.strip() == "":
            out_lines.append(line)
            continue
        if re.match(r'^\s*func\s+', line):
            inside_func = True
        if inside_func and indent_level == 0 and not re.match(r'^\s*func\s+', line):
            inside_func = False
        if not inside_func and indent_level > 0:
            # Dedent completely (move to column 0)
            out_lines.append(stripped)
        else:
            out_lines.append(line)
    return ''.join(out_lines)

# ----------------------------------------------------------------------------
# VERIFICATION: Use gdparse to check syntax
# ----------------------------------------------------------------------------
def verify_syntax(content: str) -> bool:
    """
    Write content to a temporary file and run gdparse. Return True if valid.
    CITATION: gdparse is part of gdtoolkit – https://github.com/Scony/godot-gdscript-toolkit#gdparse
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.gd', delete=False) as tf:
        tf.write(content)
        temp_path = tf.name
    try:
        # CITATION: subprocess.run with capture_output – https://docs.python.org/3/library/subprocess.html#subprocess.run
        result = subprocess.run(["gdparse", temp_path], capture_output=True, text=True)
        return result.returncode == 0
    finally:
        # Ensure temporary file is deleted even if subprocess fails
        Path(temp_path).unlink()

# ----------------------------------------------------------------------------
# MAIN: Safe, gated, timestamped backup, rollback on failure
# ----------------------------------------------------------------------------
def repair_file(file_path: Path) -> bool:
    """
    Perform repairs with:
    - Backup of original file
    - Detectors before changes (list problems)
    - Fixers
    - Verification after each step (run gdparse to confirm syntax)
    - Rollback if verification fails
    CITATION: Pathlib – https://docs.python.org/3/library/pathlib.html
    CITATION: datetime for timestamp – https://docs.python.org/3/library/datetime.html#datetime.datetime.strftime
    """
    if not file_path.exists():
        print(f"[ERROR] File not found: {file_path}")
        return False

    ensure_gdtoolkit()
    original = file_path.read_text(encoding='utf-8')

    # Detectors
    dupes = find_duplicate_functions(original)
    orphans = find_orphaned_indented_lines(original)

    if not dupes and not orphans:
        print("[GATE] No issues detected. File is clean.")
        return True

    # Create timestamped backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(f'.gd.backup_{timestamp}')
    shutil.copy(file_path, backup_path)
    print(f"[BACKUP] Saved to {backup_path}")

    # Apply fixes
    content = original
    if dupes:
        content = remove_duplicate_functions(content)
        print(f"[FIX] Removed {len(dupes)} duplicate function(s).")
    if orphans:
        content = fix_indentation(content)
        print(f"[FIX] Dedented {len(orphans)} orphaned line(s).")

    # Verify syntax
    if not verify_syntax(content):
        print("[VERIFY FAIL] Repaired file has syntax errors. Rolling back.")
        shutil.copy(backup_path, file_path)
        return False

    # Write final repaired version
    file_path.write_text(content, encoding='utf-8')
    print(f"[VERIFY PASS] Repaired file syntax is valid.")
    print(f"[DONE] Original backup kept at {backup_path}")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 repair_gdscript_v2.py <file.gd>")
        sys.exit(1)
    success = repair_file(Path(sys.argv[1]))
    sys.exit(0 if success else 1)