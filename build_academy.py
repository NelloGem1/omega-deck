#!/usr/bin/env python3
"""Generate OMEGA ACADEMY index from fleet/learning modules."""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
import os, re, html

DIR = r'C:\Users\neilh\fleet\learning'
files = sorted(f for f in os.listdir(DIR) if f.endswith('.html'))

def cat(f):
    n = f.lower()
    if n.startswith(('00','01','02','03')): return '🎓 Core'
    if re.match(r'0[4-9] -', n): return '⚔️ Security Ops'
    if re.match(r'1[0-8] -', n): return '🧪 Labs & Challenges'
    if n.startswith('19 -'): return '🛠️ CLI Toolkit'
    if re.match(r'2[0-3] -', n): return '🔐 Cryptography'
    if re.match(r'2[4-5] -', n): return '📜 Certificates'
    if re.match(r'(2[6-9]|3[0-5]) -', n): return '📖 Field Guides'
    if re.match(r'3[6-8] -', n): return '🗄️ Vault'
    if n.startswith('39 -'): return '🤖 ML & Data'
    if re.match(r'4[0-9] -', n): return '🗺️ Knowledge Maps'
    if re.match(r'5[0-3] -', n): return '🏅 Marshal Track'
    return '📦 Archive'

cats = {}
for f in files:
    cats.setdefault(cat(f), []).append(f)

def title(f):
    t = re.sub(r'^\d+ - ', '', f[:-5])
    return t.replace('-', ' ').strip().title()

sections = ''
for c, fs in cats.items():
    items = ''.join(
        f'<a class="mod" href="/learning/{html.escape(f)}"><span class="mt">{html.escape(title(f))}</span><span class="mf">{f.split(" - ")[0] if " - " in f else ""}</span></a>'
        for f in fs)
    sections += f'<div class="cat"><h3>{c} <span class="cnt">{len(fs)}</span></h3><div class="mods">{items}</div></div>'

PAGE = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>OMEGA ACADEMY</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#05070f;color:#e8ecf4;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}}
header{{text-align:center;padding:52px 24px 10px}}
h1{{font-size:40px;font-weight:800;letter-spacing:6px;
 background:linear-gradient(90deg,#34d399,#7dd3fc,#a78bfa,#34d399);background-size:300% 100%;
 -webkit-background-clip:text;background-clip:text;color:transparent;animation:fl 9s linear infinite}}
@keyframes fl{{to{{background-position:300% 0}}}}
.sub{{margin-top:10px;color:#7c8aa5;font-size:13px;letter-spacing:2px}}
#q{{display:block;width:min(520px,90vw);margin:26px auto 0;padding:14px 22px;border-radius:14px;
 border:1px solid rgba(125,211,252,.3);background:rgba(255,255,255,.05);color:#e8ecf4;
 font-size:15px;outline:none;backdrop-filter:blur(8px)}}
#q:focus{{border-color:#7dd3fc;box-shadow:0 0 24px -6px rgba(125,211,252,.5)}}
main{{max-width:1100px;margin:0 auto;padding:20px 24px 60px}}
.cat{{margin-bottom:26px;animation:rise .6s backwards}}
@keyframes rise{{from{{opacity:0;transform:translateY(18px)}}}}
.cat h3{{font-size:14px;letter-spacing:3px;color:#7c8aa5;text-transform:uppercase;margin-bottom:12px;
 border-bottom:1px solid rgba(255,255,255,.08);padding-bottom:8px}}
.cnt{{color:#34d399;font-size:11px}}
.mods{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}}
.mod{{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:13px 16px;
 border-radius:12px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.08);
 text-decoration:none;color:#dbe4f0;font-size:13.5px;transition:.25s}}
.mod:hover{{border-color:rgba(52,211,153,.5);transform:translateX(5px);background:rgba(52,211,153,.07)}}
.mf{{font-family:monospace;font-size:10px;color:#4a5568}}
.hide{{display:none}}
a.back{{display:inline-block;margin:24px;color:#7dd3fc;text-decoration:none;font-size:13px}}
</style></head><body>
<header>
 <h1>🎓 OMEGA ACADEMY</h1>
 <div class="sub">{len(files)} MODULES · {len(cats)} TRACKS · SELF-HOSTED</div>
 <input id="q" placeholder="search modules…" oninput="filt()">
</header>
<main>{sections}</main>
<a class="back" href="/">← back to fleet command</a>
<script>
function filt(){{const q=document.getElementById('q').value.toLowerCase();
 document.querySelectorAll('.mod').forEach(m=>{{m.classList.toggle('hide',!m.textContent.toLowerCase().includes(q))}});
 document.querySelectorAll('.cat').forEach(c=>{{const vis=[...c.querySelectorAll('.mod')].some(m=>!m.classList.contains('hide'));c.style.display=vis?'':'none'}})}}
</script></body></html>"""

open(os.path.join(DIR, 'INDEX.html'), 'w', encoding='utf-8').write(PAGE)
print(f'INDEX.html written — {len(files)} modules, {len(cats)} categories')
for c, fs in cats.items(): print(f'  {c}: {len(fs)}')
