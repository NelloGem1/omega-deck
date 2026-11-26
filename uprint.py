#!/usr/bin/env python3
"""UPRINT — Unicode-safe print. Never crashes on emoji/symbols.
Usage: from uprint import uprint; uprint('hello 🎓')"""
import sys

def uprint(*args, sep=' ', end='\n', file=None, flush=False):
    """Print that survives cp1252 consoles — emoji degrade gracefully."""
    target = file or sys.stdout
    try:
        # try strict first (works if console/utf-8 mode)
        text = sep.join(str(a) for a in args) + end
        target.write(text)
        if flush: target.flush()
    except UnicodeEncodeError:
        # fallback: replace unencodable chars with ?-style escapes
        enc = getattr(target, 'encoding', None) or 'utf-8'
        safe = []
        for a in args:
            s = str(a)
            try:
                s.encode(enc)
            except UnicodeEncodeError:
                s = s.encode(enc, errors='backslashreplace').decode(enc, errors='replace')
            safe.append(s)
        target.write(sep.join(safe) + end)
        if flush: target.flush()

# one-call fix: reconfigure THIS process's stdout to utf-8 w/ replace
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
except Exception:
    pass
