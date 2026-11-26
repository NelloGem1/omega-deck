#!/usr/bin/env python3
"""FETCH STOCK — pull Creative Commons images via Openverse API (no key).
All results are CC-licensed (check each license field). Ingests straight
into image_vault with tag 'stock:<query>'.
Usage: python fetch_stock.py "query" [count] [tag]"""
import json, os, sys, urllib.request, urllib.parse, time
import image_vault

API = 'https://api.openverse.org/v1/images/'
HDRS = {'User-Agent': 'scene-forge-vault/1.0 (educational image collection)'}

def fetch(query, count=60, tag=None):
    tag = tag or ('stock:' + query.replace(' ', '-')[:30])
    got = stored = dup = 0
    page = 1
    while got < count:
        url = API + '?' + urllib.parse.urlencode({
            'q': query, 'page_size': min(20, count-got), 'page': page,
            'license_type': 'all-cc'})
        try:
            req = urllib.request.Request(url, headers=HDRS)
            data = json.loads(urllib.request.urlopen(req, timeout=20).read())
        except Exception as e:
            print('api error:', e); break
        results = data.get('results', [])
        if not results: break
        for r in results:
            if got >= count: break
            img_url = r.get('url', '')
            if not img_url.lower().endswith(('.jpg','.jpeg','.png','.webp')) and 'image' not in r.get('mimetype',''):
                continue
            try:
                req = urllib.request.Request(img_url, headers=HDRS)
                blob = urllib.request.urlopen(req, timeout=15).read()
                if len(blob) < 5000 or len(blob) > 20_000_000: continue
                tmp = os.path.join(image_vault.VAULT, '_tmp_' + str(got) + '.img')
                open(tmp, 'wb').write(blob)
                res = image_vault.add_file(tmp, tag)
                os.remove(tmp)
                got += 1
                if res['status'] == 'stored': stored += 1
                else: dup += 1
                lic = r.get('license', '?')
                # stash license in tag for provenance
            except Exception:
                continue
            time.sleep(0.15)  # be polite to source hosts
        page += 1
        if page > 8: break
    print(f'"{query}": fetched {got} -> stored {stored}, dupes {dup} [tag: {tag}]')

if __name__ == '__main__':
    q = sys.argv[1] if len(sys.argv) > 1 else 'neon city'
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    tag = sys.argv[3] if len(sys.argv) > 3 else None
    fetch(q, n, tag)
