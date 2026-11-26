#!/usr/bin/env python3
"""OMEGA GATEWAY — single entry point for ALL apps on this machine.
One port (8088). Dashboard shows every app with live status.
/go/<app> redirects to the real service. No more scattered links."""
import json, socket, time, os, subprocess, threading, hashlib
try:
    import psutil
except Exception:
    psutil = None
try:
    import sentry
except Exception:
    sentry = None
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
SWEEP_INTERVAL = 6 * 3600  # auto-update every 6 hours

_keyfile = os.path.join(HERE, 'marshal.key')
if not os.path.exists(_keyfile):
    import secrets
    open(_keyfile, 'w').write(secrets.token_hex(24))
MARSHAL_KEY = open(_keyfile).read().strip()

PORT = 8088

APPS = {
    'whiteboard': {'port': 8901, 'name': 'Live Whiteboard', 'desc': 'Type shapes — they draw live on canvas', 'icon': '🎨'},
    'dvwa':       {'port': 4280,  'name': 'DVWA',          'desc': 'Exploit lab — SQLi, XSS, command injection', 'icon': '💣'},
    'juice':      {'port': 3000,  'name': 'Juice Shop',    'desc': 'Modern web vulnerability app', 'icon': '🧃'},
    'webgoat':    {'port': 18081, 'name': 'WebGoat',       'desc': 'OWASP security lessons', 'icon': '🐐'},
    'os_encyclopedia': {'port': 0, 'name': 'OS Encyclopedia', 'desc': '632-entry world OS catalog (file)', 'icon': '🖥️', 'file': r'C:\Users\neilh\Downloads\OS_WORLD_ENCYCLOPEDIA.html'},
    'cyber':      {'port': 0, 'name': 'Cyber Knowledge',   'desc': '177-topic security encyclopedia (file)', 'icon': '🛡️', 'file': r'C:\Users\neilh\Downloads\CYBER_KNOWLEDGE.html'},
}

REALAPPS = {
    'burp':      {'name':'Burp Suite','desc':'Community web attack proxy','icon':'🥊','exe':r'C:\Users\neilh\AppData\Local\Programs\BurpSuiteCommunity\BurpSuiteCommunity.exe'},
    'zap':       {'name':'OWASP ZAP','desc':'Dynamic web app scanner','icon':'🛡️','exe':r'C:\Program Files\ZAP\Zed Attack Proxy\ZAP.exe'},
    'keepass':   {'name':'KeePassXC','desc':'Local password vault','icon':'🗝️','exe':r'C:\Program Files\KeePassXC\KeePassXC.exe'},
    'veracrypt': {'name':'VeraCrypt','desc':'On-the-fly disk encryption','icon':'🔐','exe':r'C:\Program Files\VeraCrypt\VeraCrypt.exe'},
    'cryptomator':{'name':'Cryptomator','desc':'Client-side cloud encryption','icon':'🗄️','exe':r'C:\Program Files\Cryptomator\Cryptomator.exe'},
    'vlc':       {'name':'VLC','desc':'Media player','icon':'🎞️','exe':r'C:\Program Files\VideoLAN\VLC\vlc.exe'},
    'chrome':    {'name':'Chrome','desc':'Browser','icon':'🌐','exe':r'C:\Program Files\Google\Chrome\Application\chrome.exe'},
    'vscode':    {'name':'VS Code','desc':'Code editor','icon':'💻','exe':r'C:\Users\neilh\AppData\Local\Programs\Microsoft VS Code\Code.exe'},
    'devin':     {'name':'Devin','desc':'AI software engineer','icon':'🧠','exe':r'C:\Users\neilh\AppData\Local\Programs\Devin\Devin.exe'},
    'deepseek':  {'name':'DeepSeek Harness','desc':'AI assistant suite','icon':'🐋','exe':r'C:\Users\neilh\AppData\Local\Programs\DeepSeek Harness\DeepSeek Harness.exe'},
    'telegram':  {'name':'Telegram','desc':'Messenger','icon':'✈️','exe':r'C:\Users\neilh\AppData\Roaming\Telegram Desktop\Telegram.exe'},
    'gitbash':   {'name':'Git Bash','desc':'Unix shell for Windows','icon':'🌿','exe':r'C:\Program Files\Git\git-bash.exe'},
    'kleopatra': {'name':'Kleopatra','desc':'GPG certificate manager','icon':'🔏','exe':r'C:\Program Files\Gpg4win\bin\kleopatra.exe'},
    'diskinfo':  {'name':'CrystalDiskInfo','desc':'Drive health monitor','icon':'💽','exe':r'C:\Program Files\CrystalDiskInfo\DiskInfo64.exe'},
    'winword':   {'name':'Word','desc':'Office document editor','icon':'📄','exe':r'C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE'},
    'sensors':   {'name':'LibreHardwareMonitor','desc':'CPU/GPU temp sensors','icon':'🌡️','exe':r'C:\Users\neilh\AppData\Local\Microsoft\WinGet\Packages\LibreHardwareMonitor.LibreHardwareMonitor_Microsoft.Winget.Source_8wekyb3d8bbwe\LibreHardwareMonitor.exe'},
}

def is_up(port):
    if not port: return False
    try:
        s = socket.create_connection(('127.0.0.1', port), timeout=1)
        s.close(); return True
    except Exception:
        return False

_NET = {'t': 0, 's': 0, 'r': 0}
def vitals():
    """Live hardware telemetry for the Mission Control deck."""
    if not psutil: return {'ok': False}
    now = time.time()
    net = psutil.net_io_counters()
    dt = now - _NET['t'] if _NET['t'] else 0
    up = (net.bytes_sent - _NET['s']) / dt / 1024 if dt else 0
    dn = (net.bytes_recv - _NET['r']) / dt / 1024 if dt else 0
    _NET.update(t=now, s=net.bytes_sent, r=net.bytes_recv)
    ram = psutil.virtual_memory()
    drive = os.environ.get('SystemDrive', 'C:') + '/'
    disk = psutil.disk_usage(drive)
    bat = psutil.sensors_battery()
    return {'ok': True,
            'cpu': round(psutil.cpu_percent(interval=None), 1),
            'ram': round(ram.percent, 1),
            'ram_gb': round(ram.used / 2**30, 1), 'ram_tot': round(ram.total / 2**30, 1),
            'disk': round(disk.percent, 1), 'disk_free': round(disk.free / 2**30, 1),
            'net_up': round(up, 1), 'net_dn': round(dn, 1),
            'uptime_h': round((now - psutil.boot_time()) / 3600, 1),
            'battery': round(bat.percent, 0) if bat else None}

_VERSION_CACHE = {'t': 0, 'v': 0}
def fleet_version():
    """Fingerprint of every fleet file — world/, learning/, whiteboard/, corps, agents.
    Auto-reload triggers on ANY fleet change, not just gateway.py edits."""
    now = time.time()
    if now - _VERSION_CACHE['t'] < 2: return _VERSION_CACHE['v']
    h = hashlib.sha1()
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fn in sorted(files):
            if fn.endswith('.log') or fn == '.updater.lock': continue
            try:
                st = os.stat(os.path.join(root, fn))
                h.update(f"{fn}|{st.st_size}|{st.st_mtime_ns}".encode())
            except OSError: pass
    _VERSION_CACHE['t'] = now
    _VERSION_CACHE['v'] = int(h.hexdigest()[:12], 16)
    return _VERSION_CACHE['v']

INDEX = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>OMEGA</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#05070f;color:#e8ecf4;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;overflow-x:hidden}
#bg{position:fixed;inset:0;z-index:0}
header{position:relative;z-index:2;padding:48px 48px 8px;text-align:center}
h1{font-size:42px;font-weight:800;letter-spacing:6px;
 background:linear-gradient(90deg,#7dd3fc,#a78bfa,#f472b6,#7dd3fc);
 background-size:300% 100%;-webkit-background-clip:text;background-clip:text;color:transparent;
 animation:flow 8s linear infinite}
@keyframes flow{to{background-position:300% 0}}
.sub{margin-top:10px;color:#7c8aa5;font-size:14px;letter-spacing:1px}
.clock{position:absolute;top:48px;right:48px;font-family:monospace;font-size:13px;color:#7dd3fc;opacity:.8}
.stats{display:flex;justify-content:center;gap:14px;margin:26px 0 8px;flex-wrap:wrap}
.stat{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:12px 26px;backdrop-filter:blur(8px)}
.stat b{display:block;font-size:24px;background:linear-gradient(90deg,#7dd3fc,#a78bfa);-webkit-background-clip:text;background-clip:text;color:transparent}
.stat span{font-size:11px;color:#7c8aa5;letter-spacing:2px;text-transform:uppercase}
section{position:relative;z-index:2;padding:26px 48px}
h2{font-size:13px;letter-spacing:4px;color:#7c8aa5;text-transform:uppercase;margin-bottom:16px;display:flex;align-items:center;gap:10px}
h2::after{content:'';flex:1;height:1px;background:linear-gradient(90deg,rgba(125,211,252,.4),transparent)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px}
.card{position:relative;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.09);
 border-radius:18px;padding:24px;backdrop-filter:blur(12px);overflow:hidden;
 transition:transform .35s cubic-bezier(.2,.8,.3,1.2),border-color .3s,box-shadow .3s;
 animation:rise .7s cubic-bezier(.2,.8,.3,1) backwards}
.card:nth-child(2){animation-delay:.08s}.card:nth-child(3){animation-delay:.16s}
.card:nth-child(4){animation-delay:.24s}.card:nth-child(5){animation-delay:.32s}
.card:nth-child(6){animation-delay:.4s}.card:nth-child(7){animation-delay:.48s}
@keyframes rise{from{opacity:0;transform:translateY(26px) scale(.97)}}
.card::before{content:'';position:absolute;inset:0;background:radial-gradient(600px circle at var(--mx,50%) var(--my,50%),rgba(125,211,252,.09),transparent 45%);opacity:0;transition:opacity .3s}
.card:hover{transform:translateY(-6px);border-color:rgba(125,211,252,.45);box-shadow:0 18px 50px -18px rgba(125,211,252,.35)}
.card:hover::before{opacity:1}
.dot{position:absolute;top:20px;right:20px;width:11px;height:11px;border-radius:50%;background:#f87171;box-shadow:0 0 12px #f87171}
.dot.up{background:#34d399;box-shadow:0 0 12px #34d399;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.icon{font-size:38px;filter:drop-shadow(0 4px 12px rgba(0,0,0,.5))}
.name{font-size:18px;font-weight:700;margin:10px 0 4px;letter-spacing:.5px}
.desc{font-size:12.5px;color:#8b98ad;line-height:1.5;min-height:38px}
.meta{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.tag{font-size:10.5px;font-family:monospace;padding:4px 10px;border-radius:20px;background:rgba(125,211,252,.1);color:#7dd3fc;border:1px solid rgba(125,211,252,.2)}
.tag.file{background:rgba(167,139,250,.1);color:#a78bfa;border-color:rgba(167,139,250,.2)}
.go{display:inline-flex;align-items:center;gap:8px;margin-top:16px;padding:10px 22px;
 background:linear-gradient(90deg,rgba(125,211,252,.15),rgba(167,139,250,.15));
 border:1px solid rgba(125,211,252,.35);color:#e8ecf4;border-radius:12px;
 text-decoration:none;font-size:13px;font-weight:600;letter-spacing:.5px;transition:.25s}
.go:hover{background:linear-gradient(90deg,rgba(125,211,252,.3),rgba(167,139,250,.3));transform:translateX(4px);box-shadow:0 8px 24px -8px rgba(125,211,252,.5)}
footer{position:relative;z-index:2;text-align:center;padding:30px;color:#4a5568;font-size:11px;letter-spacing:1px}
.vital .vname{font-size:11px;letter-spacing:2px;color:#7c8aa5;text-transform:uppercase}
.vital .vbig{font-size:30px;font-weight:800;margin:4px 0 10px}
.vbar{height:7px;border-radius:5px;background:rgba(255,255,255,.07);overflow:hidden}
.vfill{height:100%;border-radius:5px;transition:width .8s cubic-bezier(.2,.8,.3,1)}
.vsub{font-size:11px;color:#5a6a80;font-family:monospace;margin-top:8px}
::-webkit-scrollbar{width:9px}::-webkit-scrollbar-thumb{background:#1e293b;border-radius:5px}
</style></head><body>
<canvas id="bg"></canvas>
<header>
 <h1>Ω OMEGA</h1>
 <div class="sub">ONE GATEWAY · EVERY WORLD · LIVE TELEMETRY</div>
 <div class="clock" id="clk"></div>
</header>
<div class="stats" id="stats"></div>
<section><h2>📡 Mission Control</h2><div class="grid" id="vit"></div></section>
<section><h2>▸ Active Systems</h2><div class="grid" id="g"></div></section>
<section><h2>🌍 Real World</h2><div class="grid" id="real"></div></section>
<section><h2>🌌 The World</h2><div class="grid" id="world"></div></section>
<section><h2>👥 Agent Corps</h2><div class="grid" id="agents"></div></section>
<section><h2>▸ Fleet Infrastructure</h2><div class="grid" id="sys"></div></section>
<section><h2>🛡️ Sentry Grid</h2><div class="grid" id="sentry"></div></section>
<script>
const APPS=__APPS__;
const cv=document.getElementById('bg'),cx2=cv.getContext('2d');
function size(){cv.width=innerWidth;cv.height=innerHeight}size();addEventListener('resize',size);
const P=Array.from({length:70},()=>({x:Math.random()*cv.width,y:Math.random()*cv.height,vx:(Math.random()-.5)*.3,vy:(Math.random()-.5)*.3}));
(function loop(){cx2.clearRect(0,0,cv.width,cv.height);
 for(const p of P){p.x+=p.vx;p.y+=p.vy;if(p.x<0||p.x>cv.width)p.vx*=-1;if(p.y<0||p.y>cv.height)p.vy*=-1}
 for(let i=0;i<P.length;i++)for(let j=i+1;j<P.length;j++){const a=P[i],b=P[j],d=Math.hypot(a.x-b.x,a.y-b.y);
  if(d<130){cx2.strokeStyle=`rgba(125,211,252,${(1-d/130)*.12})`;cx2.beginPath();cx2.moveTo(a.x,a.y);cx2.lineTo(b.x,b.y);cx2.stroke()}}
 for(const p of P){cx2.fillStyle='rgba(167,139,250,.5)';cx2.beginPath();cx2.arc(p.x,p.y,1.4,0,7);cx2.fill()}
 requestAnimationFrame(loop)})();
document.querySelectorAll('.card').forEach(()=>{});
document.addEventListener('mousemove',e=>{const c=e.target.closest('.card');if(!c)return;
 const r=c.getBoundingClientRect();c.style.setProperty('--mx',(e.clientX-r.left)+'px');c.style.setProperty('--my',(e.clientY-r.top)+'px')});
setInterval(()=>{document.getElementById('clk').textContent=new Date().toLocaleTimeString()},1000);
document.getElementById('clk').textContent=new Date().toLocaleTimeString();
async function load(){
 const st=await (await fetch('/status.json')).json();
 const ups=Object.keys(APPS).filter(k=>APPS[k].file||st[k]).length;
 document.getElementById('stats').innerHTML=
  `<div class="stat"><b>${ups}/${Object.keys(APPS).length}</b><span>systems online</span></div>
   <div class="stat"><b>:8088</b><span>gateway port</span></div>
   <div class="stat"><b id="up">—</b><span>uptime</span></div>`;
 document.getElementById('g').innerHTML=Object.entries(APPS).map(([k,a])=>{
  const up=a.file?true:st[k];
  const href=a.file?('file:///'+a.file.replace(/\\\\/g,'/')):('/go/'+k);
  return `<div class="card"><span class="dot ${up?'up':''}"></span>
   <div class="icon">${a.icon}</div><div class="name">${a.name}</div>
   <div class="desc">${a.desc}</div>
   <div class="meta"><span class="tag ${a.file?'file':''}">${a.port?'PORT '+a.port:'LOCAL FILE'}</span>
   <span class="tag">${up?'● ONLINE':'○ OFFLINE'}</span></div>
   <a class="go" href="${href}" target="_blank">LAUNCH ${up?'':'(offline)'} →</a></div>`}).join('')}
load();setInterval(load,2000);
async function sys(){
 try{
  const u=await (await fetch('/updater.json')).json();
  const drift=u.results?u.results.filter(r=>r.drift).length:0;
  const ts=u.ts?new Date(u.ts*1000).toLocaleString():'never';
  const n=u.results?u.results.length:0;
  document.getElementById('sys').innerHTML=`<div class="card">
   <span class="dot ${drift?'':'up'}"></span>
   <div class="icon">⚙️</div><div class="name">Fleet Updater</div>
   <div class="desc">${n} components tracked · ${drift} need updates · last scan ${ts}</div>
   <div class="meta"><span class="tag">MANIFEST manifest.json</span>
   <span class="tag">AUTO-SWEEP 6H</span>
   <span class="tag">${drift?'DRIFT DETECTED':'ALL NOMINAL'}</span></div>
   <a class="go" href="#" onclick="upd(this);return false">▶ RUN UPDATE SWEEP</a></div>`;
 }catch(e){}
}
async function agents(){
 try{
  const d=await (await fetch('/agents.json')).json();
  const rankColor={ 'FIELD MARSHAL':'#f472b6','MARSHAL':'#fbbf24','COMMANDER':'#7dd3fc','SPECIALIST':'#34d399','RECRUIT':'#8b98ad'};
  document.getElementById('agents').innerHTML=d.agents.map(a=>`
   <div class="card"><span class="dot up"></span>
    <div class="icon">${a.domain.includes('video')?'🎬':a.domain.includes('python')?'🐍':a.domain.includes('cyber')?'🛡️':a.domain.includes('visual')?'🎨':a.domain.includes('data')?'📊':'📡'}</div>
    <div class="name">${a.callsign} <span style="font-size:11px;color:${rankColor[a.rank]||'#8b98ad'}">${a.rank}</span></div>
    <div class="desc">${a.domain} · L${a.level} · ${a.xp}xp · ${a.tools.length} tools</div>
    <div class="desc" style="color:#5a6a80;font-size:11px">${a.last||''}</div>
    <div class="meta">${Object.entries(a.skills).slice(0,3).map(([k,v])=>`<span class="tag">${k}:${v}</span>`).join('')}</div>
   </div>`).join('');
 }catch(e){}
}
document.getElementById('world').innerHTML=`<div class="card" style="cursor:pointer" onclick="location.href='/world'">
   <span class="dot up"></span>
   <div class="icon">🌌</div><div class="name">OMEGA WORLD</div>
   <div class="desc">Parallel universe — every knowledge domain, agent, and creation as a living stimulated system. knowledge units flowing.</div>
   <div class="meta"><span class="tag">13 WORLDS</span><span class="tag">LIVE SIGNALS</span></div>
   <a class="go" href="/world">ENTER WORLD →</a></div>`;
agents();setInterval(agents,2000);
function vcard(icon,name,pct,sub,color){
 const c=color||'#7dd3fc';
 return `<div class="card vital"><div class="icon" style="font-size:26px">${icon}</div>
  <div class="vname" style="margin-top:8px">${name}</div>
  <div class="vbig" style="color:${c}">${pct==null?'—':pct+(name=='NET'?'/s':'%')}</div>
  <div class="vbar"><div class="vfill" style="width:${Math.min(100,pct||0)}%;background:linear-gradient(90deg,${c},#a78bfa)"></div></div>
  <div class="vsub">${sub||''}</div></div>`}
async function vit(){try{
 const v=await (await fetch('/vitals.json')).json();if(!v.ok)return;
 const heat=v.cpu>85?'#f87171':v.cpu>60?'#fbbf24':'#34d399';
 const rheat=v.ram>90?'#f87171':v.ram>75?'#fbbf24':'#7dd3fc';
 const dheat=v.disk>90?'#f87171':v.disk>75?'#fbbf24':'#a78bfa';
 document.getElementById('vit').innerHTML=
  vcard('🧠','CPU',v.cpu,`freq load · ${v.uptime_h}h uptime`,heat)+
  vcard('🧠','RAM',v.ram,`${v.ram_gb}/${v.ram_tot} GB`,rheat)+
  vcard('💽','DISK',v.disk,`${v.disk_free} GB free on system drive`,dheat)+
  vcard('📡','NET',Math.max(v.net_up,v.net_dn),`↑${v.net_up} KB/s ↓${v.net_dn} KB/s`,'#38bdf8')+
  (v.battery!=null?vcard('🔋','BATT',v.battery,'power cell','#34d399'):'');
}catch(e){}}
vit();setInterval(vit,2000);
async function real(){try{
 const d=await (await fetch('/realapps.json')).json();
 document.getElementById('real').innerHTML=Object.entries(d).map(([k,a])=>`
  <div class="card"><span class="dot up"></span>
   <div class="icon">${a.icon}</div><div class="name">${a.name}</div>
   <div class="desc">${a.desc}</div>
   <div class="meta"><span class="tag file">DESKTOP APP</span><span class="tag">${a.exe?'INSTALLED':'MISSING'}</span></div>
   <a class="go" href="/launch/${k}?key=${KEY}" target="_blank">▶ LAUNCH →</a></div>`).join('');
}catch(e){}}
real();setInterval(real,30000);
let VER=null;
async function ver(){try{const v=(await (await fetch('/version.json')).json()).v;
 if(VER===null){VER=v}else if(v!==VER){location.reload()}}catch(e){}}
ver();setInterval(ver,3000);
sys();setInterval(sys,3000);
async function sentryDeck(){try{const d=await (await fetch('/sentry.json')).json();
 const sevC={CRITICAL:'#ff2d55',HIGH:'#ff9f0a',MED:'#ffd60a',LOW:'#64d2ff'};
 document.getElementById('sentry').innerHTML=
  `<div class="card"><span class="dot ${(d.stats.total||0)>0?'down':'up'}"></span>
   <div class="icon">🛡️</div><div class="name">DETECTION GRID</div>
   <div class="desc">${d.stats.total||0} alerts · ${JSON.stringify(d.stats.by_sev||{})}</div>
   <div class="meta"><span class="tag">RULES:9</span><span class="tag">LIVE</span></div></div>`+
  d.alerts.slice(0,8).map(a=>`<div class="card"><span class="dot" style="background:${sevC[a.sev]||'#888'}"></span>
   <div class="icon">${a.sev==='CRITICAL'?'🔴':a.sev==='HIGH'?'🟠':'🟡'}</div>
   <div class="name">${a.rule} · ${a.name}</div>
   <div class="desc">${a.req}</div>
   <div class="meta"><span class="tag">${a.src}</span><span class="tag">${a.ts}</span></div></div>`).join('');
}catch(e){}}
sentryDeck();setInterval(sentryDeck,3000);
const KEY='__KEY__';
async function upd(el){el.textContent='⟳ SWEEPING FLEET…';
 await fetch('/update?key='+KEY,{method:'POST'});setTimeout(sys,3000)}
</script></body></html>""".replace('__APPS__', json.dumps(APPS)).replace('__KEY__', MARSHAL_KEY)

class H(BaseHTTPRequestHandler):
    server_version = ''
    sys_version = ''
    def log_message(self, *a): pass
    def _send(self, code, body, ctype='text/html', extra=None):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p = unquote(urlparse(self.path).path)
        if sentry:
            sentry.record(sentry.check('GET', self.path, authed=(MARSHAL_KEY in self.path)), 'GET', self.path)
        if p == '/':
            self._send(200, INDEX)
        elif p == '/status.json':
            self._send(200, json.dumps({k: is_up(a['port']) for k, a in APPS.items()}), 'application/json')
        elif p == '/healthz':
            self._send(200, '{"ok":true}', 'application/json')
        elif p == '/updater.json':
            try:
                self._send(200, open(os.path.join(HERE, 'status.json')).read(), 'application/json')
            except Exception:
                self._send(200, '{"results":[],"ts":0}', 'application/json')
        elif p == '/learning' or p.startswith('/learning/'):
            self._serve_learning(p)
        elif p == '/agents.json':
            try:
                self._send(200, open(os.path.join(HERE, 'agents_status.json')).read(), 'application/json')
            except Exception:
                self._send(200, '{"agents":[]}', 'application/json')
        elif p == '/version.json':
            self._send(200, json.dumps({'v': fleet_version()}), 'application/json')
        elif p == '/world' or p == '/world/':
            fp = os.path.join(HERE, 'world', 'index.html')
            self._send(200, open(fp, encoding='utf-8').read(), 'text/html; charset=utf-8')
        elif p == '/ainet' or p == '/ainet/':
            fp = os.path.join(HERE, 'ainet', 'index.html')
            self._send(200, open(fp, encoding='utf-8').read().replace('__KEY__', MARSHAL_KEY), 'text/html; charset=utf-8')
        elif p == '/ainet.json':
            try:
                props = json.load(open(os.path.join(HERE, 'ainet', 'proposals.json')))
                self._send(200, json.dumps({'proposals': props}), 'application/json')
            except Exception:
                self._send(200, '{"proposals":[]}', 'application/json')
        elif p == '/sentry.json':
            try:
                st = json.load(open(os.path.join(HERE, 'sentry_stats.json')))
            except Exception:
                st = {'total': 0, 'by_sev': {}}
            self._send(200, json.dumps({'stats': st, 'alerts': sentry.alerts(50) if sentry else []}), 'application/json')
        elif p == '/vitals.json':
            self._send(200, json.dumps(vitals()), 'application/json')
        elif p == '/realapps.json':
            self._send(200, json.dumps({k: {kk: vv for kk, vv in a.items() if kk != 'exe'} | {'exe': bool(a['exe'] and os.path.exists(a['exe']))} for k, a in REALAPPS.items()}), 'application/json')
        elif p.startswith('/launch/'):
            q = dict(x.split('=', 1) for x in urlparse(self.path).query.split('&') if '=' in x)
            if q.get('key') != MARSHAL_KEY:
                if sentry: sentry.record([('AUTH-02','unauth-launch','HIGH')], 'GET', self.path)
                self._send(403, 'marshal key required', 'text/plain'); return
            key = p[8:].strip('/')
            app = REALAPPS.get(key)
            if app and app['exe'] and os.path.exists(app['exe']):
                os.startfile(app['exe'])
                self._send(302, '', 'text/plain', {'Location': '/'})
            else:
                self._send(404, 'app not installed', 'text/plain')
        elif p.startswith('/go/'):
            key = p[4:].strip('/')
            app = APPS.get(key)
            if app and app['port']:
                self._send(302, '', 'text/plain', {'Location': f"http://localhost:{app['port']}/"})
            elif app and app.get('file'):
                self._send(302, '', 'text/plain', {'Location': 'file:///' + app['file'].replace('\\', '/')})
            else:
                self._send(404, 'unknown app', 'text/plain')
        else:
            self._send(404, 'not found', 'text/plain')

    def _serve_learning(self, path):
        root = os.path.join(HERE, 'learning')
        rel = path[len('/learning'):].lstrip('/') or 'INDEX.html'
        fp = os.path.normpath(os.path.join(root, rel))
        if not fp.startswith(root) or not os.path.isfile(fp):
            self._send(404, 'not found', 'text/plain'); return
        ext = os.path.splitext(fp)[1].lower()
        ctype = {'.html':'text/html','.css':'text/css','.js':'text/javascript',
                 '.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml'}.get(ext,'application/octet-stream')
        self._send(200, open(fp,'rb').read(), ctype + '; charset=utf-8' if ctype=='text/html' else ctype)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        if sentry:
            sentry.record(sentry.check('POST', self.path, authed=True), 'POST', self.path)
        if path == '/ainet/propose' or path == '/ainet/review':
            try:
                n = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(n) or b'{}')
                pf = os.path.join(HERE, 'ainet', 'proposals.json')
                props = json.load(open(pf)) if os.path.exists(pf) else []
                if path == '/ainet/review' and body.get('key') != MARSHAL_KEY:
                    if sentry: sentry.record([('AUTH-03','unauth-ainet-review','HIGH')], 'POST', path)
                    self._send(403, '{"ok":false,"err":"marshal key required"}', 'application/json'); return
                if path == '/ainet/propose':
                    props.append({'id': len(props) + 1,
                                  'author': str(body.get('author', '?'))[:24],
                                  'title': str(body.get('title', ''))[:120],
                                  'body': str(body.get('body', ''))[:4000],
                                  'status': 'pending',
                                  'ts': time.strftime('%Y-%m-%d %H:%M')})
                else:
                    pr = next((x for x in props if x['id'] == body.get('id')), None)
                    if pr and body.get('action') in ('approve', 'reject'):
                        pr['status'] = 'approved' if body['action'] == 'approve' else 'rejected'
                json.dump(props, open(pf, 'w'), indent=1)
                self._send(200, '{"ok":true}', 'application/json')
            except Exception as e:
                self._send(500, json.dumps({'ok': False, 'err': str(e)}), 'application/json')
        elif path == '/update':
            q = dict(x.split('=', 1) for x in urlparse(self.path).query.split('&') if '=' in x)
            if q.get('key') != MARSHAL_KEY:
                if sentry: sentry.record([('AUTH-01','unauth-update','CRITICAL')], 'POST', self.path)
                self._send(403, '{"ok":false,"err":"marshal key required"}', 'application/json')
                return
            subprocess.Popen(['python', os.path.join(HERE, 'updater.py'), '--apply'],
                             cwd=HERE, creationflags=subprocess.CREATE_NO_WINDOW)
            self._send(200, '{"ok":true,"started":true}', 'application/json')
        else:
            self._send(404, 'not found', 'text/plain')

def auto_update_loop():
    """Background daemon: sweep the fleet every SWEEP_INTERVAL seconds."""
    while True:
        time.sleep(SWEEP_INTERVAL)
        try:
            subprocess.Popen(['python', os.path.join(HERE, 'updater.py'), '--apply'],
                             cwd=HERE, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass

if __name__ == '__main__':
    print(f'OMEGA → http://localhost:{PORT}')
    threading.Thread(target=auto_update_loop, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', PORT), H).serve_forever()
