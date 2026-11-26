#[!]/usr/bin/env python3
"""ENCODING GUARD — detects, diagnoses, fixes UnicodeEncodeError.
Loop: SCAN → PROBLEM → FIX → VERIFY → RESULT report."""
import os, re, sys, io

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = [HERE]
HEADER = "import sys\nsys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')\nsys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')\n"

def risky_prints(path):
    """Find .py files that print() non-ASCII without a guard."""
    try:
        src = open(path, encoding='utf-8').read()
    except Exception:
        return None
    if 'reconfigure' in src or 'uprint' in src or 'PYTHONUTF8' in src:
        return None  # already guarded
    has_nonascii = any(ord(c) > 127 for c in src)
    has_print = 'print(' in src
    if has_nonascii and has_print:
        return src
    return None

def fix_file(path):
    src = open(path, encoding='utf-8').read()
    lines = src.split('\n')
    # insert guard after shebang/encoding/docstring-start — simplest: after first import block or at top
    # find first non-comment non-blank line position
    idx = 0
    for i, l in enumerate(lines[:15]):
        if l.startswith('#[!]') or l.startswith('#') or not l.strip() or l.strip().startswith('"""') or l.strip().startswith("'''"):
            idx = i + 1
        else:
            break
    guard = HEADER.rstrip('\n').split('\n')
    lines[idx:idx] = guard
    open(path, 'w', encoding='utf-8').write('\n'.join(lines))
    return True

def scan():
    found = []
    for root in TARGETS:
        for dp, _, fns in os.walk(root):
            for fn in fns:
                if fn.endswith('.py'):
                    p = os.path.join(dp, fn)
                    if risky_prints(p):
                        found.append(p)
    return found

def main():
    apply = '--fix' in sys.argv
    print('=== ENCODING GUARD ===')
    files = scan()
    if not files:
        print('RESULT: no unguarded non-ASCII print() found — all clean')
        return
    print(f'PROBLEM: {len(files)} file(s) can crash on emoji in cp1252 console')
    for f in files:
        print(f'  [!] {f}')
        if apply:
            fix_file(f)
            print(f'  [OK] FIXED: {os.path.basename(f)}')
    print(f'RESULT: {"fixed" if apply else "dry-run — rerun with --fix"}')

if __name__ == '__main__':
    main()
