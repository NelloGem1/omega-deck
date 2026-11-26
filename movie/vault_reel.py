#!/usr/bin/env python3
"""VAULT REEL v2 — cinematic cut from vault photos.
Upgrades: procedural synthwave score, title cards, varied shot lengths,
mixed transitions, per-shot grade shifts, grain, letterbox.
Output: renders/vault_reel_v2_<ts>.mp4"""
import json, os, subprocess, time, random

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1280, 720, 24
OUTD = os.path.join(HERE, 'renders')
FONT = 'C\\:/Windows/Fonts/arialbd.ttf'

# shot list: (pick_index, duration) — transitions cycle from TRANS
SHOTS = [(0,2.4),(1,3.6),(2,1.9),(3,4.2),(4,2.6),(5,3.4),(6,2.2),(7,3.8)]
TRANS = ['fade','slideleft','smoothleft','circleopen','fade','wipeleft','fade','fade']

def pick_images(n):
    rows=[json.loads(l) for l in open(os.path.join(HERE,'vault','index.jsonl'),encoding='utf-8') if l.strip()]
    stock=[r for r in rows if r['tag'].startswith('stock:')]
    seen,picks=set(),[]
    for r in stock:
        if r['tag'] not in seen: seen.add(r['tag']); picks.append(r)
    for r in stock:
        if len(picks)>=n: break
        if r not in picks: picks.append(r)
    return picks[:n]

def build():
    picks = pick_images(len(SHOTS))
    n = len(picks)
    if not n: print('vault empty'); return
    # inputs: title card (color) + n images
    inputs = ['-f','lavfi','-i',f'color=c=0x0a0a14:s={W}x{H}:d=3:r={FPS}']
    for r in picks:
        inputs += ['-loop','1','-t','6','-i',r['file']]
    fc = []
    # title card: zoom slowly + text
    fc.append(f"[0:v]zoompan=z='1.0+0.12*on/72':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
              f"drawtext=fontfile='{FONT}':text='OMEGA':fontsize=110:fontcolor=0xff2d55:"
              f"x=(w-text_w)/2:y=(h-text_h)/2-40:alpha='if(lt(t\\,0.5)\\,(t/0.5)\\,if(gt(t\\,2.5)\\,(3-t)/0.5\\,1))',"
              f"drawtext=fontfile='{FONT}':text='VAULT REEL — REAL IMAGES, FORGED STYLE':fontsize=26:fontcolor=0xffb3c1:"
              f"x=(w-text_w)/2:y=(h+text_h)/2+20:alpha='if(lt(t\\,0.8)\\,(t-0.5)/0.5\\,if(gt(t\\,2.3)\\,(3-t)/0.5\\,1))',"
              f"eq=saturation=0.6[v0]")
    labels=['v0']
    # image shots with varied zoom direction + grade
    for i,(idx,dur) in enumerate(SHOTS):
        inp = i+1
        frames = int(dur*FPS)+30
        zoom_in = i%2==0
        zexpr = f"1.02+0.28*on/{frames}" if zoom_in else f"1.30-0.28*on/{frames}"
        panx = "(iw-iw/zoom)*on/%d" % frames if i%3==1 else "iw/2-(iw/zoom/2)"
        pany = "(ih-ih/zoom)*on/%d" % frames if i%3==2 else "ih/2-(ih/zoom/2)"
        # grade: alternate warm/cool per shot
        grade = "eq=saturation=1.25:contrast=1.1" if i%2==0 else "eq=saturation=0.9:contrast=1.15:brightness=-0.03,colorbalance=bs=0.08:rs=-0.03"
        fc.append(f"[{inp}:v]scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
                  f"zoompan=z='{zexpr}':x='{panx}':y='{pany}':d=1:s={W}x{H}:fps={FPS},"
                  f"{grade},setsar=1[v{i+1}]")
        labels.append(f'v{i+1}')
    # concat shots then xfade chain? simpler: concat with transitions needs xfade pairwise.
    # Build xfade chain across title+shots
    cur='v0'; offset=3.0
    ti=0
    for i,(idx,dur) in enumerate(SHOTS):
        nxt=f'v{i+1}'; out=f'x{i}'
        fc.append(f'[{cur}][{nxt}]xfade=transition={TRANS[ti%len(TRANS)]}:duration=0.7:offset={offset:.2f}[{out}]')
        cur=out; offset += dur; ti+=1
    total = offset + 0.7
    # letterbox + grain
    fc.append(f'[{cur}]drawbox=x=0:y=0:w=iw:h=52:color=black:t=fill,drawbox=x=0:y=ih-52:w=iw:h=52:color=black:t=fill,'
              f"noise=alls=8:allf=t+u[vout]")
    out = os.path.join(OUTD, f'vault_reel_v2_{int(time.time())}.mp4')
    # ---- synthwave audio: four-on-floor bass + pad + hats ----
    fc_a = []
    fc_a.append("[1:a]" if False else "")
    audio_src = (
        "aevalsrc=sin(2*PI*55*t)*gt(mod(t\\,0.42)\\,0.30)+sin(2*PI*110*t)*0.4*gt(mod(t\\,0.42)\\,0.30)"
        ":s=44100:d=%.1f[bass];"
        "aevalsrc=sin(2*PI*110*t)+sin(2*PI*164.8*t)+sin(2*PI*220*t):s=44100:d=%.1f,volume=0.10,tremolo=f=4:d=0.6[pad];"
        "anoisesrc=color=white:amplitude=0.15:d=%.1f,highpass=f=6000,volume='gt(mod(t\\,0.21)\\,0.18)':eval=frame[hat];"
        "[bass][pad][hat]amix=inputs=3:normalize=0,acompressor=threshold=-18dB:ratio=4,alimiter=limit=0.9[aout]"
    ) % (total, total, total)
    cmd = ['ffmpeg','-y'] + inputs + \
          ['-f','lavfi','-i', f'aevalsrc=sin(2*PI*440*t)*0:d={total}:s=44100'] + \
          ['-filter_complex',';'.join(fc)+';'+audio_src,
           '-map','[vout]','-map','[aout]','-c:v','libx264','-pix_fmt','yuv420p','-crf','20',
           '-c:a','aac','-b:a','160k','-shortest', out]
    print('rendering v2:', n, 'shots + score, ~%.0fs' % total, flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
    else:
        print('DONE ->', out)

if __name__ == '__main__':
    build()
