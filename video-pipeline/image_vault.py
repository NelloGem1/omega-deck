#!/usr/bin/env python3
"""IMAGE VAULT — compressed, deduplicated image storage for generator training.
Ingest -> perceptual-hash dedup -> WebP compress -> JSONL index.
Usage:
  python image_vault.py add <file-or-dir> [tag]
  python image_vault.py list [tag]
  python image_vault.py stats
Store: vault/  (webp files + index.jsonl)"""
import json, os, sys, time, hashlib
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.join(HERE, 'vault'); os.makedirs(VAULT, exist_ok=True)
INDEX = os.path.join(VAULT, 'index.jsonl')

def ahash(im, size=16):
    """average perceptual hash -> 256-bit int (no deps)"""
    g = im.convert('L').resize((size, size))
    px = list(g.getdata()); avg = sum(px)/len(px)
    bits = 0
    for v in px: bits = (bits << 1) | (v > avg)
    return bits

def hamming(a, b): return bin(a ^ b).count('1')

def load_index():
    if not os.path.exists(INDEX): return []
    return [json.loads(l) for l in open(INDEX, encoding='utf-8') if l.strip()]

def save_index(rows):
    with open(INDEX, 'w', encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r) + '\n')

def add_file(path, tag=''):
    rows = load_index()
    im = Image.open(path).convert('RGB')
    h = ahash(im)
    # dedup: near-identical if hamming <= 12/256
    for r in rows:
        if hamming(h, int(r['hash'])) <= 12:
            return {'status': 'duplicate', 'of': r['id'], 'file': path}
    vid = hashlib.sha1(f"{h}{time.time()}".encode()).hexdigest()[:12]
    w, hh = im.size
    # cap training resolution at 1024 to keep vault lean
    if max(w, hh) > 1024:
        im.thumbnail((1024, 1024), Image.LANCZOS)
    out = os.path.join(VAULT, vid + '.webp')
    im.save(out, 'WEBP', quality=85, method=4)
    row = {'id': vid, 'file': out, 'src': os.path.basename(path), 'tag': tag,
           'w': im.size[0], 'h': im.size[1], 'bytes': os.path.getsize(out),
           'hash': str(h), 'ts': time.time()}
    rows.append(row)
    # append-only: safe under concurrent writers (no read-modify-write race)
    with open(INDEX, 'a', encoding='utf-8') as f:
        f.write(json.dumps(row) + '\n')
    return {'status': 'stored', **{k: row[k] for k in ('id','w','h','bytes','tag')}}

def add_path(path, tag=''):
    results = []
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for fn in files:
                if fn.lower().endswith(('.png','.jpg','.jpeg','.bmp','.gif','.webp','.tiff')):
                    results.append(add_file(os.path.join(root, fn), tag or os.path.basename(root)))
    else:
        results.append(add_file(path, tag))
    return results

def cmd_list(tag=None):
    rows = load_index()
    if tag: rows = [r for r in rows if r['tag'] == tag]
    for r in rows[-50:]:
        print(f"{r['id']}  {r['w']}x{r['h']}  {r['bytes']//1024}KB  [{r['tag']}]  {r['src']}")
    print(f"-- {len(rows)} total")

def cmd_reindex():
    """recover orphan .webp files missing from index.jsonl"""
    rows = load_index(); known = {r['id'] for r in rows}
    added = 0
    for fn in os.listdir(VAULT):
        if not fn.endswith('.webp') or fn.startswith('_tmp'): continue
        vid = fn[:-5]
        if vid in known: continue
        fp = os.path.join(VAULT, fn)
        try:
            im = Image.open(fp); h = ahash(im)
            row = {'id': vid, 'file': fp, 'src': 'recovered', 'tag': 'recovered',
                   'w': im.size[0], 'h': im.size[1], 'bytes': os.path.getsize(fp),
                   'hash': str(h), 'ts': time.time()}
            rows.append(row); added += 1
            with open(INDEX, 'a', encoding='utf-8') as f:
                f.write(json.dumps(row) + '\n')
        except Exception as e:
            print('skip', fn, e)
    print(f'reindexed: {added} orphans recovered')

def cmd_stats():
    rows = load_index()
    total = sum(r['bytes'] for r in rows)
    tags = {}
    for r in rows: tags[r['tag']] = tags.get(r['tag'], 0) + 1
    print(f"images: {len(rows)}  storage: {total/1e6:.1f}MB  tags: {tags}")

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'stats'
    if cmd == 'add':
        tag = sys.argv[3] if len(sys.argv) > 3 else ''
        res = add_path(sys.argv[2], tag)
        stored = sum(1 for r in res if r['status'] == 'stored')
        dup = sum(1 for r in res if r['status'] == 'duplicate')
        print(f"stored: {stored}  duplicates skipped: {dup}")
        for r in res[:10]: print(' ', r)
    elif cmd == 'list':
        cmd_list(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == 'reindex':
        cmd_reindex()
    else:
        cmd_stats()
