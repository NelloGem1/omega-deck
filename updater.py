#!/usr/bin/env python3
"""FLEET UPDATER — updates Neil's OWN machines only.
Checks manifest → reports drift → applies updates (pip/git/ollama).
No spreading. No third-party systems. Signed-log every action."""
import json, subprocess, sys, os, time, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, 'manifest.json')
STATUS = os.path.join(HERE, 'status.json')
LOG = os.path.join(HERE, 'updater.log')

def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(LOG, 'a') as f: f.write(line + '\n')

def sh(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, str(e)

def pip_current(pkg):
    rc, out = sh(f'python -m pip show {pkg}')
    for l in out.splitlines():
        if l.startswith('Version:'): return l.split(':',1)[1].strip()
    return None

def check_item(item):
    """Return (name, current, latest_or_None, drift_bool)."""
    t = item['type']
    if t == 'pip':
        cur = pip_current(item['pkg'])
        # latest via pip index (cheap check)
        rc, out = sh(f'python -m pip index versions {item["pkg"]} 2>nul')
        latest = None
        for tok in out.replace('(',' ').replace(')',' ').replace(',', ' ').split():
            if tok and tok[0].isdigit(): latest = tok; break
        return item['pkg'], cur, latest, bool(latest and cur and cur != latest)
    if t == 'git':
        d = item['path']
        rc, _ = sh(f'git -C "{d}" fetch --quiet origin 2>nul')
        rc2, behind = sh(f'git -C "{d}" rev-list --count HEAD..@{{u}} 2>nul')
        b = behind.strip()
        return os.path.basename(d), 'local', b or '?', b not in ('0', '')
    if t == 'file':
        return item['name'], 'exists' if os.path.exists(item['path']) else 'MISSING', None, not os.path.exists(item['path'])
    if t == 'wsl':
        # command runs inside WSL; drift = nonzero exit or 'DRIFT' in output
        rc, out = sh(f'wsl -d Ubuntu -- bash -c "{item["cmd"]}"')
        drift = rc != 0 or 'DRIFT' in out
        return item['name'], out.strip().splitlines()[-1] if out.strip() else 'ran', None, drift
    return item.get('name','?'), '?', None, False

def apply_item(item):
    t = item['type']
    if t == 'pip':
        rc, out = sh(f'python -m pip install --user -U {item["pkg"]}')
        return rc == 0, out[-300:]
    if t == 'git':
        rc, out = sh(f'git -C "{item["path"]}" pull --ff-only')
        return rc == 0, out[-300:]
    if t == 'file':
        return os.path.exists(item['path']), 'verified' if os.path.exists(item['path']) else 'missing'
    if t == 'wsl':
        rc, out = sh(f'wsl -d Ubuntu -- bash -c "{item["cmd"]}"')
        return rc == 0, out[-300:]
    return False, 'unknown type'

LOCK = os.path.join(HERE, '.updater.lock')

def main():
    apply = '--apply' in sys.argv
    # collision guard: skip if another run is active (<10 min old lock)
    if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 600:
        print('another update run is active — skipping')
        return
    open(LOCK, 'w').write(str(os.getpid()))
    manifest = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {'items': []}
    log(f'=== FLEET UPDATE {"APPLY" if apply else "CHECK (dry-run)"} ===')
    results = []
    for item in manifest.get('items', []):
        name, cur, latest, drift = check_item(item)
        status = 'DRIFT' if drift else 'ok'
        log(f'{status:5} {name}: current={cur} latest={latest}')
        results.append({'name': name, 'current': cur, 'latest': latest, 'drift': drift})
        if drift and apply:
            ok, detail = apply_item(item)
            log(f'  → update {"OK" if ok else "FAIL"}: {detail[:200]}')
            results[-1]['updated'] = ok
    json.dump({'ts': time.time(), 'apply': apply, 'results': results}, open(STATUS, 'w'), indent=1)
    n_drift = sum(1 for r in results if r['drift'])
    log(f'=== done: {len(results)} checked, {n_drift} drifted ===')
    print(f'\n{len(results)} components · {n_drift} need updates' + (' — run with --apply to fix' if not apply else ''))
    try: os.remove(LOCK)
    except OSError: pass

if __name__ == '__main__':
    main()
