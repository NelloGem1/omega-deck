#!/usr/bin/env python3
"""SCENE FORGE — parallel on-demand cinematic renderer.
POST /render {"title":"...","scenes":[...],"duration":36,"dna":"<id>"}
GET  /status/<id> -> progress · GET /file/<id> -> mp4 · GET / -> gallery
Frames auto-archive into image_vault (dedup + webp + index)."""
import json, os, queue, threading, time, math, random, subprocess, uuid, sys, bisect, tempfile
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'renders'); os.makedirs(OUT, exist_ok=True)
DNA_DIR = os.path.join(HERE, 'dna')
JOBS = {}
Q = queue.Queue()
WORKERS = int(os.environ.get('RENDER_WORKERS', '4'))

def load_dna(ref):
    for cand in (ref if str(ref).endswith('.json') else ref + '.json',
                 os.path.join(DNA_DIR, str(ref) + '.json'),
                 os.path.join(DNA_DIR, os.path.basename(str(ref)) + '.json')):
        if os.path.exists(cand):
            return json.load(open(cand))
    return None

def hex2rgb(h):
    h = str(h).lstrip('#'); return tuple(int(h[i:i+2],16) for i in (0,2,4))

W, H, FPS = 960, 540, 24
LH = int(H * (1 - 1/2.39) / 2)
AY, AH = LH, H - 2*LH
GROUND = AY + AH - 8

try:
    FONT = ImageFont.truetype("consola.ttf", 30); FONT_S = ImageFont.truetype("consola.ttf", 16)
except Exception:
    FONT = FONT_S = ImageFont.load_default()

# ---------- precomputed assets ----------
def skyline(seed, base_y, col, win_col, antenna=False):
    rnd = random.Random(seed); img = Image.new('RGB', (W, AH), (0,0,0)); d = ImageDraw.Draw(img)
    x = -20
    while x < W + 40:
        bw = rnd.randint(26, 95); bh = rnd.randint(70, int(AH*0.92))
        d.rectangle([x, base_y-bh, x+bw, base_y+10], fill=col)
        # parapet + antenna
        d.rectangle([x-2, base_y-bh-4, x+bw+2, base_y-bh], fill=col)
        if antenna and rnd.random() < 0.3:
            ax = x + bw//2
            d.line([ax, base_y-bh-4, ax, base_y-bh-24], fill=col, width=2)
            d.ellipse([ax-2, base_y-bh-28, ax+2, base_y-bh-24], fill=(255,60,60))
        # windows grid with warm/cool variance
        for wy in range(base_y-bh+8, base_y-10, 15):
            for wx in range(x+5, x+bw-6, 11):
                if rnd.random() < 0.30:
                    warm = rnd.random()
                    c = win_col if warm > 0.4 else ((80,140,255) if warm > 0.15 else (60,30,30))
                    if rnd.random() < 0.05: c = (255,80,80)  # blinking red
                    d.rectangle([wx, wy, wx+4, wy+6], fill=c)
        x += bw + rnd.randint(3, 16)
    return img

def _mask(im): return im.convert('L').point(lambda v: 255 if v > 10 else 0)

FAR  = skyline(11, GROUND-140, (16,16,38), (255,214,96), antenna=True)
NEAR = skyline(23, GROUND,     (7,7,18),  (255,150,70))
FAR_M, NEAR_M = _mask(FAR), _mask(NEAR)

# starfield (static, twinkle via alpha at draw time)
STARS = [(random.Random(99).random()*W, random.Random(98).random()*AY*0.8,
          random.Random(97).random()*1.5+0.5) for _ in range(140)]
# re-seed properly
_r = random.Random(99); STARS = [(_r.random()*W, _r.random()*AY*0.8, _r.random()*1.6+0.4) for _ in range(140)]

def moon(d, x, y, r=28):
    d.ellipse([x-r, y-r, x+r, y+r], fill=(230,230,210))
    d.ellipse([x-r+6, y-r+4, x+r-10, y+r-8], fill=(200,200,185))
    # glow
    for i in range(3):
        rr = r + 8 + i*10
        d.ellipse([x-rr, y-rr, x+rr, y+rr], outline=(230,230,210), width=1)

def person(d, x, y, s, col=(15,15,25), rim=(255,190,90), phase=0.0, cape=False):
    """animated silhouette: walk cycle via phase, rim-lit edge"""
    head = s*0.13; torso = s*0.40; leg = s*0.47
    sw = math.sin(phase) * s*0.10          # leg swing
    bob = abs(math.sin(phase)) * s*0.02    # body bob
    y -= bob
    # legs (two-segment feel via offset rects)
    d.line([x, y-s*0.55, x-sw*0.4, y-leg*0.55], fill=col, width=max(2,int(s*0.045)))
    d.line([x, y-s*0.55, x+sw*0.4, y-leg*0.55], fill=col, width=max(2,int(s*0.045)))
    # torso
    d.rectangle([x-s*0.10, y-s*0.98, x+s*0.10, y-s*0.55], fill=col)
    # arms swing opposite
    d.line([x-s*0.10, y-s*0.92, x-s*0.16-sw*0.3, y-s*0.60], fill=col, width=max(2,int(s*0.035)))
    d.line([x+s*0.10, y-s*0.92, x+s*0.16+sw*0.3, y-s*0.60], fill=col, width=max(2,int(s*0.035)))
    # head + rim light
    d.ellipse([x-head/2, y-s-head*0.4, x+head/2, y-s+head*0.6], fill=col)
    d.arc([x-head/2, y-s-head*0.4, x+head/2, y-s+head*0.6], 200, 340, fill=rim, width=2)
    if cape:  # fluttering cape
        fl = math.sin(phase*1.3)*s*0.06
        d.polygon([(x-s*0.08, y-s*0.95),(x-s*0.30-fl, y-s*0.45),
                   (x-s*0.05, y-s*0.50)], fill=(40,10,20))

def muzzle(d, x, y, t):
    if t < 0.12:
        r = 26*(1-t/0.12)
        d.ellipse([x-r,y-r,x+r,y+r], fill=(255,230,120))
        d.ellipse([x-r*0.5,y-r*0.5,x+r*0.5,y+r*0.5], fill=(255,255,255))

def embers(d, n, t, seed=3):
    r = random.Random(int(t*10)+seed)
    for _ in range(n):
        x = r.random()*W; y = GROUND - r.random()*AH*0.7 - (t*30 % 200)
        a = max(0, 1 - ((GROUND-y)/AH))
        d.ellipse([x-1.5,y-1.5,x+1.5,y+1.5], fill=(255,120+int(80*a),40))

def rain(d, t, n=90):
    r = random.Random(int(t*24))
    for _ in range(n):
        x = r.random()*W; y = (r.random()*H + t*900) % H
        d.line([x, y, x-4, y+14], fill=(80,100,140), width=1)

def letterbox(d):
    d.rectangle([0,0,W,LH], fill=(0,0,0)); d.rectangle([0,H-LH,W,H], fill=(0,0,0))

def vignette(img):
    vig = Image.new('L',(W,H),0); vd = ImageDraw.Draw(vig)
    vd.ellipse([-W*0.25,-H*0.35,W*1.25,H*1.35], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(110))
    return Image.composite(img, Image.new('RGB',(W,H),(0,0,0)),
                           vig.point(lambda v: 255-v//3))

def grain(img, rnd, n=800):
    px = img.load()
    for _ in range(n):
        x,y = rnd.randint(0,W-1), rnd.randint(0,H-1); v = rnd.randint(-16,16)
        r0,g0,b0 = px[x,y]
        px[x,y] = (max(0,min(255,r0+v)), max(0,min(255,g0+v)), max(0,min(255,b0+v)))
    return img

def title(d, text, sub='', alpha=255):
    d.rectangle([0,AY,W,AY+AH], fill=(0,0,0))
    d.text((W//2,AY+AH//2-34), text, font=FONT, fill=(255,45,85,alpha), anchor='mm')
    if sub: d.text((W//2,AY+AH//2+12), sub, font=FONT_S, fill=(255,179,193,alpha), anchor='mm')

def sky_gradient(d, t, sc, warm):
    """precomputed per-frame gradient is slow — use 24 bands"""
    bands = 24
    for i in range(bands):
        k = i/bands
        r = int(4 + warm*46*k); g = int(6 + warm*9*k); b = int(18 + warm*5*(1-k))
        if sc == 'finale': b = int(b*0.6)
        d.rectangle([0, AY+i*AH//bands, W, AY+(i+1)*AH//bands], fill=(r,g,b))

SCENES = ['city','hero','chase','fight','finale','button']

def render(job):
    jid, spec = job['id'], job['spec']
    scenes = [s for s in spec.get('scenes', SCENES) if s in SCENES] or SCENES
    dna = load_dna(spec['dna']) if spec.get('dna') else None
    accent = (255,190,90); warm = 0.15; energy = 1.0; rain_on = False
    if dna:
        if dna.get('palette'): accent = hex2rgb(dna['palette'][0])
        mood = dna.get('analysis',{}).get('palette_mood','')
        warm = 0.6 if 'WARM' in mood else 0.12
        try: energy = max(0.4, min(2.5, 10 ** (dna.get('mean_volume_db',-30)/50)))
        except Exception: energy = 1.0
        shots = [max(0.5, s) for s in dna.get('shot_lengths',[])]
    else:
        shots = []
    if spec.get('rain'): rain_on = True
    total = max(4, int(spec.get('duration') or (dna['probe']['duration'] if dna else 36)))
    if shots:
        scale = total / sum(shots)
        segs = [(scenes[i % len(scenes)], s*scale) for i, s in enumerate(shots)]
    else:
        per = max(3, total // len(scenes))
        segs = [(s, float(per)) for s in scenes]
        total = int(sum(d for _, d in segs))
    bounds = [0.0]
    for _, dd in segs: bounds.append(bounds[-1] + dd)
    nf = int(total * FPS)
    out = os.path.join(OUT, jid + '.mp4')
    ff = subprocess.Popen(['ffmpeg','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}',
        '-r',str(FPS),'-i','-','-c:v','libx264','-pix_fmt','yuv420p','-crf','20',out],
        stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    rnd = random.Random(hash(jid) & 0xffff)
    try:
        for f in range(nf):
            t = f/FPS
            idx = min(max(0, bisect.bisect_right(bounds, t) - 1), len(segs)-1)
            sc, seg_dur = segs[idx]; lt = t - bounds[idx]; ph = lt*7
            img = Image.new('RGB',(W,H),(0,0,0)); d = ImageDraw.Draw(img)

            # sky + celestial
            sky_gradient(d, t, sc, warm)
            tw = 0.5 + 0.5*math.sin(t*3)
            for sx, sy, sr in STARS:
                d.point((sx, sy), fill=(255,255,255) if int(t*2+sx)%3 else (120,120,140))
            moon(d, W*0.78, AY+70, 26)

            # city parallax
            if sc == 'city':
                pan = int((lt/seg_dur)*140)
                img.paste(FAR, (int(-pan*0.5), AY), FAR_M)
                img.paste(NEAR, (int(-pan), AY), NEAR_M)
            else:
                shake = int(math.sin(t*13)*2) if sc=='fight' and lt<1.2 else 0
                img.paste(FAR, (shake, AY), FAR_M)
                img.paste(NEAR, (shake*2, AY), NEAR_M)
            d = ImageDraw.Draw(img)

            # ground haze
            d.rectangle([0, GROUND, W, AY+AH], fill=(10,8,14))

            if rain_on or sc=='chase': rain(d, t)

            # ---- scene actors ----
            if sc in ('hero','chase','button'):
                if sc=='hero': hx = W*0.30 - lt*26; hy = GROUND
                elif sc=='chase': hx = W*0.5 + math.sin(lt*4)*W*0.12; hy = GROUND
                else: hx = W*0.30 + lt*22; hy = GROUND
                lean = 0.18 if sc=='chase' else 0.05
                # streetlamp practical
                lx = W*0.62
                for i in range(26):
                    sp = 14 + i*3.2
                    shade = max(8, 60 - i*2)
                    d.polygon([(lx, GROUND-150), (lx-sp, GROUND-8), (lx+sp, GROUND-8)],
                              fill=(shade, shade//2, 8))
                d.rectangle([lx-3, GROUND-155, lx+3, GROUND-140], fill=(255,190,80))
                d.ellipse([lx-9, GROUND-163, lx+9, GROUND-145], fill=(255,220,140))
                person(d, hx, hy, 165, col=(10,10,20), rim=accent, phase=ph, cape=(sc!='button'))

            if sc == 'fight':
                # hero left third firing right; enemy silhouette right
                hx = W*0.30; ex = W*0.70
                person(d, hx, GROUND, 160, col=(10,10,20), rim=accent, phase=ph)
                person(d, ex, GROUND, 175, col=(50,5,12), rim=(255,45,85), phase=ph+2)
                # gun + muzzle flashes on beat
                beat = lt % 0.9
                if beat < 0.12:
                    muzzle(d, hx+55, GROUND-105, beat)
                    # tracer
                    for i in range(8):
                        bx = hx+60+i*22; d.line([bx, GROUND-105, bx+10, GROUND-105], fill=(255,220,120), width=2)
                # impact sparks at enemy
                if beat > 0.3 and beat < 0.5:
                    for i in range(14):
                        a = rnd.random()*6.28; dd = rnd.random()*40
                        px = ex-30+math.cos(a)*dd; py = GROUND-110+math.sin(a)*dd*0.6
                        d.ellipse([px-2,py-2,px+2,py+2], fill=(255,180,60))
                embers(d, int(14*energy), t)

            if sc == 'finale':
                # power stance center — aura rings + rising energy
                cx, cy = W*0.5, GROUND-95
                aura = 90 + math.sin(lt*6)*18
                for i in range(4):
                    rr = aura + i*26
                    d.ellipse([cx-rr, cy-rr*1.3, cx+rr, cy+rr*1.3], outline=accent, width=2)
                for i in range(int(20*energy)):
                    a = rnd.random()*6.28; rr = rnd.random()*aura*1.4
                    px, py = cx+math.cos(a)*rr, cy+math.sin(a)*rr*0.7
                    d.ellipse([px-2,py-2,px+2,py+2], fill=accent)
                person(d, cx, GROUND, 190, col=(10,10,20), rim=accent, phase=0, cape=True)
                if lt < 0.5:  # entry flash
                    fl = 1 - lt*2
                    img = Image.blend(img, Image.new('RGB',(W,H),(255,235,190)), fl*0.5)
                    d = ImageDraw.Draw(img); letterbox(d)

            if sc == 'city':
                embers(d, int(6*energy), t, seed=5)

            # ---- finishing ----
            letterbox(d)
            img = vignette(img)
            img = grain(img, rnd)
            d = ImageDraw.Draw(img)
            if rain_on:  # cool grade shift
                pass
            if f == 0 and spec.get('title'):
                title(d, spec['title'], 'A SCENE FORGE CUT')
            if sc == 'fight' and 0.2 < lt < 1.6: title(d, 'THE HIT', '')
            if sc == 'finale' and lt < 1.4: title(d, 'OMEGA PROTOCOL', '', int(255*(1-lt/1.4)))
            if sc == 'button' and seg_dur-lt < 2.5:
                title(d, 'FIN', 'THE VILLAGE STANDS', int(255*(seg_dur-lt)/2.5))
            ff.stdin.write(img.tobytes())
            JOBS[jid]['progress'] = round(f/nf,3); JOBS[jid]['scene'] = sc; JOBS[jid]['pct'] = int(f/nf*100)
        ff.stdin.close(); ff.wait()
        JOBS[jid].update(status='done', file='/file/'+jid, pct=100)
        # auto-archive frames into image vault (best-effort)
        try:
            import image_vault
            with tempfile.TemporaryDirectory() as td:
                subprocess.run(['ffmpeg','-y','-v','quiet','-i',out,'-vf','fps=1',
                                os.path.join(td,'f%04d.jpg')], check=True)
                res = image_vault.add_path(td, 'render:' + str(spec.get('title','untitled'))[:30])
                JOBS[jid]['vault'] = {'stored': sum(1 for r in res if r['status']=='stored'),
                                      'dupes': sum(1 for r in res if r['status']=='duplicate')}
        except Exception as ve:
            JOBS[jid]['vault'] = {'error': str(ve)[:120]}
    except Exception as e:
        try: ff.stdin.close(); ff.kill()
        except Exception: pass
        JOBS[jid].update(status='error', error=str(e)[:200])

def worker():
    while True:
        job = Q.get(); render(job); Q.task_done()
for _ in range(WORKERS):
    threading.Thread(target=worker, daemon=True).start()
print(f'SCENE FORGE live -> http://localhost:8898 [{WORKERS} workers]', flush=True)

GALLERY = """<!doctype html><meta charset=utf-8><title>SCENE FORGE</title>
<body style="background:#0a0a14;color:#eee;font-family:monospace;padding:30px">
<h1 style="color:#ff2d55">🎬 SCENE FORGE</h1>
<p style="color:#888">POST /render {"title":"X","scenes":["city","hero","chase","fight","finale","button"],"duration":36,"dna":"id","rain":true}</p>
<hr style="border-color:#333">__JOBS__"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def _send(self,code,body,ct='text/html'):
        b=body.encode() if isinstance(body,str) else body
        self.send_response(code); self.send_header('Content-Type',ct)
        self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p=urlparse(self.path).path
        if p=='/':
            rows=''.join(f'<p><a style="color:#ffd60a" href="/file/{j}">{j}</a> — {JOBS[j].get("status","?")} {JOBS[j].get("pct","")}% {JOBS[j].get("title","")} {JOBS[j].get("vault","")}</p>'
                         for j in sorted(JOBS, key=lambda k:JOBS[k].get('ts',0), reverse=True))
            self._send(200,GALLERY.replace('__JOBS__',rows or '<p style=color:#666>no renders yet</p>'))
        elif p.startswith('/status/'):
            jid=p.split('/')[-1]; self._send(200,json.dumps(JOBS.get(jid,{'status':'unknown'})),'application/json')
        elif p.startswith('/file/'):
            jid=p.split('/')[-1]; fp=os.path.join(OUT,jid+'.mp4')
            if os.path.exists(fp):
                data=open(fp,'rb').read()
                self.send_response(200); self.send_header('Content-Type','video/mp4')
                self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
            else: self._send(404,'not ready')
        elif p.startswith('/renders/'):
            fp=os.path.join(OUT,os.path.basename(p))
            if os.path.exists(fp):
                data=open(fp,'rb').read()
                self.send_response(200); self.send_header('Content-Type','video/mp4')
                self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
            else: self._send(404,'not found')
        else: self._send(404,'nf')
    def do_POST(self):
        p=urlparse(self.path).path
        if p=='/render':
            n=int(self.headers.get('Content-Length',0)); raw=self.rfile.read(n)
            try: spec=json.loads(raw) if raw else {}
            except Exception:
                spec={k:(v[0] if isinstance(v,list) else v) for k,v in parse_qs(raw.decode()).items()}
            jid=uuid.uuid4().hex[:8]
            spec['title']=spec.get('title') or 'UNTITLED'
            JOBS[jid]={'id':jid,'spec':spec,'status':'queued','progress':0,'pct':0,'ts':time.time(),'title':spec['title']}
            Q.put({'id':jid,'spec':spec})
            self._send(200,json.dumps({'id':jid,'status':'queued','check':f'/status/{jid}','file':f'/file/{jid}'}),'application/json')
        else: self._send(404,'nf')

if __name__=='__main__':
    ThreadingHTTPServer(('127.0.0.1',8898),Handler).serve_forever()
