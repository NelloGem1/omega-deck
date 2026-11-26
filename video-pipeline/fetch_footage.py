#!/usr/bin/env python3
"""FETCH FOOTAGE — pull public-domain/CC video clips from archive.org.
Search -> pick smallest usable mp4 -> download to footage/.
Usage: python fetch_footage.py "query" [count]"""
import json, os, sys, urllib.request, urllib.parse, time

HERE = os.path.dirname(os.path.abspath(__file__))
FOOT = os.path.join(HERE, 'footage'); os.makedirs(FOOT, exist_ok=True)
HDRS = {'User-Agent': 'scene-forge-vault/1.0'}

def search(query, rows=12):
    q = urllib.parse.quote(f'mediatype:movies AND ({query})')
    url = f'https://archive.org/advancedsearch.php?q={q}&fl[]=identifier&fl[]=title&rows={rows}&output=json'
    d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=20).read())
    return d['response']['docs']

def files_of(ident):
    d = json.loads(urllib.request.urlopen(
        urllib.request.Request(f'https://archive.org/metadata/{ident}', headers=HDRS), timeout=20).read())
    out = []
    for f in d.get('files', []):
        n = f['name']
        if n.endswith(('.mp4', '.webm')) and int(f.get('size', 0) or 0) < 400_000_000:
            out.append((n, int(f.get('size', 0))))
    return sorted(out, key=lambda x: x[1])

def fetch(query, count=3):
    got = 0
    for doc in search(query):
        if got >= count: break
        ident = doc['identifier']
        cands = files_of(ident)
        if not cands: continue
        name, size = cands[0]
        dest = os.path.join(FOOT, f"{ident[:30]}_{name[:40]}")
        if os.path.exists(dest): got += 1; continue
        url = f'https://archive.org/download/{ident}/{urllib.parse.quote(name)}'
        try:
            print(f'  pulling {name} ({size//1_000_000}MB) from {ident[:40]}', flush=True)
            urllib.request.urlretrieve(url, dest)
            got += 1
        except Exception as e:
            print('  fail:', e)
        time.sleep(0.5)
    print(f'"{query}": {got} clips in footage/')

if __name__ == '__main__':
    q = sys.argv[1] if len(sys.argv) > 1 else 'timelapse'
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    fetch(q, n)
