#!/usr/bin/env python3
"""SENTRY - OMEGA detection grid. Rules + alert log for the fleet.
Every blocked/forbidden/suspicious request gets fingerprinted here."""
import json, os, time, re

HERE = os.path.dirname(os.path.abspath(__file__))
ALERTS = os.path.join(HERE, 'detections.jsonl')
STATS = os.path.join(HERE, 'sentry_stats.json')

RULES = [
    ('TRV-01', 'path-traversal',       'HIGH',     re.compile(r'\.\.|%2e%2e|\.\./', re.I)),
    ('AUTH-01', 'unauth-update',       'CRITICAL', re.compile(r'POST /update')),
    ('AUTH-02', 'unauth-launch',       'HIGH',     re.compile(r'GET /launch/')),
    ('AUTH-03', 'unauth-ainet-review', 'HIGH',     re.compile(r'POST /ainet/review')),
    ('AUTH-04', 'unauth-draw',         'MED',      re.compile(r'POST /api/draw')),
    ('INJ-01', 'sqli-pattern',         'HIGH',     re.compile(r"union\s+select|or\s+1=1|sleep\s*\(|benchmark\s*\(", re.I)),
    ('INJ-02', 'xss-pattern',          'MED',      re.compile(r'<script|javascript:|onerror=|onload=', re.I)),
    ('SCAN-01', 'admin-probe',         'LOW',      re.compile(r'/(admin|wp-admin|phpmyadmin|\.env|\.git)', re.I)),
    ('BRUTE-01', 'key-guessing',       'HIGH',     re.compile(r'key=(wrong|test|admin|123|key|marshal)', re.I)),
]

def check(method, path, authed=False):
    sig = method + ' ' + path
    hits = []
    for rid, name, sev, rx in RULES:
        if rx.search(sig):
            if rid.startswith('AUTH') and authed:
                continue
            hits.append((rid, name, sev))
    return hits

def record(hits, method, path, src='gateway'):
    if not hits:
        return
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(ALERTS, 'a', encoding='utf-8') as f:
        for rid, name, sev in hits:
            f.write(json.dumps({'ts': ts, 'src': src, 'sev': sev, 'rule': rid,
                                'name': name, 'req': (method + ' ' + path)[:200]}) + '\n')
    try:
        st = json.load(open(STATS)) if os.path.exists(STATS) else {'total': 0, 'by_sev': {}}
    except Exception:
        st = {'total': 0, 'by_sev': {}}
    st['total'] += len(hits)
    for _, _, sev in hits:
        st['by_sev'][sev] = st['by_sev'].get(sev, 0) + 1
    st['last'] = ts
    json.dump(st, open(STATS, 'w'))

def alerts(n=50):
    if not os.path.exists(ALERTS):
        return []
    lines = open(ALERTS, encoding='utf-8').read().strip().split('\n')
    return [json.loads(l) for l in lines[-n:] if l.strip()][::-1]
