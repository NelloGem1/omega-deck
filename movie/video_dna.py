#!/usr/bin/env python3
"""VIDEO DNA → ACADEMY LESSON
Analyze a local video file -> extract craft metrics -> write a lesson
into fleet/learning/. Usage: python video_dna.py <video.mp4> [name]
Only analyze videos you have rights to."""
import json, os, re, subprocess, sys, tempfile
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
LEARN = os.path.join(HERE, '..', 'learning')
DNA_DIR = os.path.join(HERE, 'dna'); os.makedirs(DNA_DIR, exist_ok=True)

def probe(path):
    out = subprocess.run(['ffprobe','-v','quiet','-print_format','json','-show_format','-show_streams',path],
                         capture_output=True, text=True).stdout
    d = json.loads(out)
    v = next((s for s in d['streams'] if s['codec_type']=='video'), {})
    a = next((s for s in d['streams'] if s['codec_type']=='audio'), {})
    return {'duration': float(d['format'].get('duration',0)),
            'fps': eval(v.get('r_frame_rate','24/1').split('/')[0]+'/'+v.get('r_frame_rate','24/1').split('/')[1]) if '/' in v.get('r_frame_rate','24/1') else 24,
            'w': v.get('width'), 'h': v.get('height'),
            'has_audio': bool(a)}

def shots(path, thresh=0.35):
    """scene-change detection -> shot boundaries"""
    p = subprocess.run(['ffmpeg','-i',path,'-vf',f"select='gt(scene,{thresh})',showinfo",
                        '-f','null','-'], capture_output=True, text=True)
    times = [float(m) for m in re.findall(r'pts_time:([\d.]+)', p.stderr)]
    dur = probe(path)['duration']
    bounds = [0.0]+times+[dur]
    return [round(bounds[i+1]-bounds[i],2) for i in range(len(bounds)-1)]

def palette(path, n=10):
    """sample n frames evenly -> average color per frame"""
    dur = probe(path)['duration']
    colors = []
    with tempfile.TemporaryDirectory() as td:
        for i in range(n):
            t = dur*(i+0.5)/n
            fp = os.path.join(td, f'f{i}.jpg')
            subprocess.run(['ffmpeg','-y','-v','quiet','-ss',str(t),'-i',path,
                            '-frames:v','1','-vf','scale=64:36',fp], check=True)
            im = Image.open(fp).convert('RGB').resize((1,1))
            colors.append('#%02x%02x%02x' % im.getpixel((0,0)))
    return colors

def energy(path):
    p = subprocess.run(['ffmpeg','-i',path,'-af','volumedetect','-f','null','-'],
                       capture_output=True, text=True)
    m = re.search(r'mean_volume: ([-\d.]+)', p.stderr)
    return float(m.group(1)) if m else -90.0

def hex2rgb(h): return tuple(int(h[i:i+2],16) for i in (1,3,5))

def analyze(path):
    info = probe(path)
    sl = shots(path)
    pal = palette(path)
    en = energy(path)
    avg_shot = sum(sl)/len(sl) if sl else info['duration']
    # classify pacing
    if avg_shot < 2.5: pace = 'FRANTIC — action coverage, cuts land fast'
    elif avg_shot < 5: pace = 'BRISK — standard scene rhythm'
    else: pace = 'CONTEMPLATIVE — long holds, tension through stillness'
    # dominant palette mood
    rs = [hex2rgb(c)[0] for c in pal]; gs=[hex2rgb(c)[1] for c in pal]; bs=[hex2rgb(c)[2] for c in pal]
    if sum(rs)/len(rs) > sum(bs)/len(bs): mood = 'WARM — safety, nostalgia, heroism'
    else: mood = 'COOL — dread, technology, distance'
    return {'file': os.path.basename(path), 'probe': info, 'shot_lengths': sl,
            'palette': pal, 'mean_volume_db': en,
            'analysis': {'avg_shot_s': round(avg_shot,2), 'shot_count': len(sl),
                         'pacing': pace, 'palette_mood': mood}}

def write_lesson(dna, name):
    a = dna['analysis']; p = dna['probe']
    md = f"""# LESSON — VIDEO DNA: {name}
*Auto-generated craft analysis of `{dna['file']}` — OMEGA Academy*

## THE FILM AT A GLANCE
- Duration: {p['duration']:.1f}s · {p['w']}x{p['h']} · ~{p['fps']:.0f}fps · audio: {'yes' if p['has_audio'] else 'no'}
- Shots detected: **{a['shot_count']}** · avg length **{a['avg_shot_s']}s**
- Audio energy: {dna['mean_volume_db']:.1f} dB mean

## PACING — the heartbeat
{a['pacing']}
Shot lengths: {', '.join(map(str, dna['shot_lengths'][:20]))}{'…' if len(dna['shot_lengths'])>20 else ''}

> **Craft note:** shot length IS emotion. <2.5s = adrenaline, >5s = dread.
> Count the cuts in any scene you love — the rhythm is the message.

## PALETTE — the emotional filter
{a['palette_mood']}
Dominant sampled colors: {' '.join(dna['palette'])}

> **Craft note:** warm palettes say *home/safety*, cool say *danger/tech*.
> Directors grade toward one or the other — check any poster.

## TRY IT (lab exercise)
1. Pick a film you love. Scrub it and COUNT the shots in one scene.
2. Sample 10 paused frames — what colors dominate? Warm or cool?
3. Recreate the DNA: `python video_dna.py <your_clip.mp4>` then
   POST the DNA to the render farm (`/render` with matching scenes).
4. Compare your render's pacing against the original shot list.

## THE BIG IDEA — compressed computation
A video's entire *style* compresses to ~2KB of DNA (this JSON):
shot rhythm + palette + energy. The footage is disposable;
the pattern is the art. That is how style transfers at scale.
"""
    fn = os.path.join(LEARN, f"{name}.md")
    open(fn,'w',encoding='utf-8').write(md)
    hid = dna['file'].rsplit('.',1)[0].lower().replace(' ','_')[:24]
    json.dump(dna, open(os.path.join(DNA_DIR, hid+'.json'),'w'), indent=1)
    return fn, os.path.join(DNA_DIR, hid+'.json')

if __name__ == '__main__':
    path = sys.argv[1]
    name = sys.argv[2] if len(sys.argv)>2 else 'video-dna-'+os.path.basename(path).rsplit('.',1)[0][:20]
    print('analyzing', path, flush=True)
    dna = analyze(path)
    lf, df = write_lesson(dna, name)
    print('LESSON ->', lf)
    print('DNA    ->', df)
    print(json.dumps(dna['analysis'], indent=1))
