#!/usr/bin/env python3
import sys, re, subprocess, shutil, tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

def log(msg): print(f"[DEBUG] {msg}")

def check_gdtoolkit() -> bool:
    try:
        subprocess.run(["gdparse", "--version"], capture_output=True, text=True, check=False)
        return True
    except FileNotFoundError:
        return False

def ensure_gdtoolkit():
    if not check_gdtoolkit():
        subprocess.run([sys.executable, "-m", "pip", "install", "gdtoolkit==4.*"], check=True)

def extract_function_body(lines, start_idx):
    base_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
    end_idx = start_idx
    for i in range(start_idx+1, len(lines)):
        if lines[i].strip() == "": continue
        curr_indent = len(lines[i]) - len(lines[i].lstrip())
        if curr_indent <= base_indent and re.match(r'^\s*func\s+', lines[i]):
            end_idx = i-1; break
        end_idx = i
    return end_idx, "".join(lines[start_idx:end_idx+1])

def find_duplicate_functions(content):
    lines = content.splitlines(keepends=True)
    func_pattern = re.compile(r'^\s*func\s+([a-zA-Z0-9_]+)\s*\(')
    seen = {}
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
                if body.strip() == first_body.strip():
                    duplicates.append((first_line, i, name))
                else:
                    print(f"[WARN] Duplicate '{name}' at line {i+1} different body – skipping")
                i = end_idx
            else:
                seen[name] = (i, body)
                i = end_idx
        i += 1
    return duplicates

def remove_duplicate_functions(content):
    lines = content.splitlines(keepends=True)
    duplicates = find_duplicate_functions(content)
    if not duplicates:
        return content
    to_delete = set()
    for first_ln, dup_ln, name in duplicates:
        _, body = extract_function_body(lines, dup_ln)
        dup_end = dup_ln + body.count('\n')
        for j in range(dup_ln, dup_end+1):
            to_delete.add(j)
    new_lines = [line for i,line in enumerate(lines) if i not in to_delete]
    return "".join(new_lines)

def fix_physics_process_indentation(content):
    lines = content.splitlines(keepends=True)
    in_physics = False
    in_orphan_block = False
    base_indent = 0
    body_indent = 0
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if not in_physics and re.match(r'^\s*func\s+_physics_process\s*\(', line):
            in_physics = True
            base_indent = indent
            body_indent = base_indent + 4
            log(f"Found _physics_process at line {i+1}, body indent = {body_indent}")
            new_lines.append(line)
            i += 1
            continue
        if in_physics and not in_orphan_block and '_update_canopy_tilt()' in line:
            in_orphan_block = True
            log(f"Found '_update_canopy_tilt()' at line {i+1}")
            new_lines.append(line)
            i += 1
            continue
        if in_orphan_block:
            if line.strip() == "":
                new_lines.append(line)
                i += 1
                continue
            # Stop when we reach a line with indent <= 1 (the original indent of '_update_canopy_tilt()')
            if indent <= 1:
                in_orphan_block = False
                log(f"End of orphan block at line {i+1} (indent {indent} <= 1)")
                # This line will be added by the normal flow after the block ends
                # We don't add it here; we let the loop continue to the normal branch
                continue
            else:
                new_line = ' ' * body_indent + stripped
                log(f"Dedent line {i+1}: {indent} -> {body_indent}")
                new_lines.append(new_line)
                i += 1
                continue
        new_lines.append(line)
        i += 1
    return ''.join(new_lines)

def run_gdformat_on_file(file_path):
    try:
        from gdtoolkit.formatter import format_code
        with open(file_path, 'r', encoding='utf-8') as f:
            original = f.read()
        formatted = format_code(original, max_line_length=120)
        if formatted != original:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(formatted)
            print("[FORMAT] Applied gdformat.")
        return True
    except Exception as e:
        print(f"[FORMAT ERROR] {e}")
        return False

def repair_file(file_path):
    if not file_path.exists():
        print(f"[ERROR] File not found: {file_path}")
        return False

    ensure_gdtoolkit()
    original = file_path.read_text(encoding='utf-8')

    content = original
    dupes = find_duplicate_functions(original)
    if dupes:
        content = remove_duplicate_functions(content)
        print(f"[FIX] Removed {len(dupes)} duplicate function(s).")

    content = fix_physics_process_indentation(content)
    print("[FIX] Applied targeted _physics_process indentation fix.")

    inter_path = file_path.with_suffix('.gd.intermediate')
    inter_path.write_text(content, encoding='utf-8')
    print(f"[DEBUG] Intermediate file saved to {inter_path}")

    if not run_gdformat_on_file(inter_path):
        print("[ERROR] gdformat failed on intermediate file. Inspect manually.")
        return False

    content = inter_path.read_text(encoding='utf-8')
    inter_path.unlink()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.gd', delete=False) as tf:
        tf.write(content)
        temp_path = tf.name
    try:
        result = subprocess.run(["gdparse", temp_path], capture_output=True, text=True)
        if result.returncode != 0:
            print("[VERIFY FAIL] Syntax errors remain:")
            print(result.stderr)
            return False
    finally:
        Path(temp_path).unlink()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(f'.gd.backup_{timestamp}')
    shutil.copy(file_path, backup_path)
    print(f"[BACKUP] Saved original to {backup_path}")
    file_path.write_text(content, encoding='utf-8')
    print("[VERIFY PASS] Repaired file syntax is valid.")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 repair_gdscript_v2.py <file.gd>")
        sys.exit(1)
    success = repair_file(Path(sys.argv[1]))
    sys.exit(0 if success else 1)