#!/usr/bin/env python3
"""SCENE RENDERER — applies SCENE_CRAFT.md principles, outputs MP4 via ffmpeg.
960x540 @ 24fps, 2.39:1 letterbox, ~36s."""
import math, random, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR = 960, 540, 24, 36
random.seed(7)
NF = FPS * DUR

try:
    FONT = ImageFont.truetype("consola.ttf", 26)
    FONT_S = ImageFont.truetype("consola.ttf", 15)
except Exception:
    FONT = FONT_S = ImageFont.load_default()

# letterbox: 2.39:1 active area
LH = int(H * (1 - 1/2.39) / 2)          # bar height ~56px
AY = LH                                # active top
AH = H - 2*LH                          # active height ~428

# pre-generate skyline (two parallax layers)
def skyline(seed, base_y, col, win_col):
    rnd = random.Random(seed); buildings = []
    x = -20
    while x < W + 40:
        bw = rnd.randint(30, 90); bh = rnd.randint(60, int(AH*0.9))
        buildings.append((x, base_y - bh, bw, bh)); x += bw + rnd.randint(4, 18)
    img = Image.new('RGB', (W, AH), (0,0,0))
    d = ImageDraw.Draw(img)
    for bx, by, bw, bh in buildings:
        d.rectangle([bx, by, bx+bw, base_y], fill=col)
        for wy in range(by+8, base_y-8, 14):
            for wx in range(bx+5, bx+bw-6, 12):
                if rnd.random() < 0.28:
                    flick = rnd.random()
                    c = win_col if flick > 0.06 else (60, 30, 30)
                    d.rectangle([wx, wy, wx+4, wy+6], fill=c)
    return img, buildings

far_layer, _ = skyline(11, AY + AH - 60, (14, 14, 34), (255, 214, 96))
near_layer, _ = skyline(23, AY + AH - 10, (6, 6, 16), (255, 140, 60))

def draw_person(d, x, y, s, col=(232,232,255), rim=None):
    """silhouette figure; s = height px"""
    head = s*0.14; torso = s*0.42; leg = s*0.44
    d.ellipse([x-head/2, y-s, x+head/2, y-s+head], fill=col)
    d.rectangle([x-s*0.11, y-s+head, x+s*0.11, y-s+head+torso], fill=col)
    d.rectangle([x-s*0.10, y-s+head+torso, x-s*0.015, y-leg*0.5], fill=col)
    d.rectangle([x+s*0.015, y-s+head+torso, x+s*0.10, y-leg*0.5], fill=col)
    d.rectangle([x-s*0.16, y-s+head+torso*0.7, x-s*0.09, y-s+head+torso*0.2], fill=col)
    d.rectangle([x+s*0.09, y-s+head+torso*0.7, x+s*0.16, y-s+head+torso*0.2], fill=col)
    if rim:  # warm rim light on one side
        d.line([x+head/2, y-s+2, x+head/2, y-s+head*0.5], fill=rim, width=2)

def grade(img, teal=0.0, warm=0.0):
    """cheap color grade: shift channels"""
    if teal == 0 and warm == 0: return img
    r, g, b = img.split()
    r = r.point(lambda v: max(0, min(255, v + int(warm*30))))
    b = b.point(lambda v: max(0, min(255, v + int(teal*40))))
    return Image.merge('RGB', (r, g, b))

def scene_title(d, text, sub, alpha=255):
    d.rectangle([0, AY, W, AY+AH], fill=(0,0,0))
    d.text((W//2, AY+AH//2-30), text, font=FONT, fill=(255,45,85,alpha), anchor='mm')
    d.text((W//2, AY+AH//2+15), sub, font=FONT_S, fill=(255,179,193,alpha), anchor='mm')

ff = subprocess.Popen([
    'ffmpeg','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}',
    '-r',str(FPS),'-i','-','-c:v','libx264','-pix_fmt','yuv420p',
    '-crf','20','C:/Users/neilh/fleet/video-pipeline/scene_cut.mp4'
], stdin=subprocess.PIPE)

particles = []
for f in range(NF):
    t = f / FPS
    img = Image.new('RGB', (W, H), (0,0,0))
    d = ImageDraw.Draw(img)

    # letterbox bars
    d.rectangle([0,0,W,LH], fill=(0,0,0)); d.rectangle([0,H-LH,W,H], fill=(0,0,0))

    # sky gradient (teal->black, warm shift at climax)
    warmth = max(0.0, math.sin(t/36*math.pi)) * 0.8
    for y in range(AH):
        k = y/AH
        r = int(4 + warmth*30*k); g = int(6 + warmth*8*k); b = int(18 + warmth*6*(1-k))
        d.line([0, AY+y, W, AY+y], fill=(r,g,b))

    # ---- SCENE 1 (0-6s): ESTABLISHING — slow pan across city
    if t < 6:
        pan = int((t/6) * 120)
        img.paste(far_layer, (-pan, AY), far_layer)
        img.paste(near_layer, (-pan*1.6, AY), near_layer)
        d = ImageDraw.Draw(img)

    # ---- SCENE 2 (6-13s): MEDIUM — hero enters, rule-of-thirds left
    elif t < 13:
        img.paste(far_layer, (0, AY), far_layer); img.paste(near_layer, (0, AY), near_layer)
        lt = t - 6
        hx = W*0.33 - lt*30            # walks in from left third
        hy = AY + AH - 10
        walk = math.sin(lt*8)*6
        draw_person(d, hx, hy - walk, 150, rim=(255,180,90))
        # motivated practical: streetlamp cone
        lx = W*0.62
        for i in range(30):
            spread = 20 + i*3
            d.polygon([(lx, AY+AH-160), (lx-spread, AY+AH-10), (lx+spread, AY+AH-10)],
                      fill=(40, 30, 10, ))
        d.rectangle([lx-3, AY+AH-165, lx+3, AY+AH-150], fill=(255,190,80))
        d.ellipse([lx-8, AY+AH-172, lx+8, AY+AH-156], fill=(255,214,96))

    # ---- SCENE 3 (13-20s): CLOSE-UP feel — push in + heartbeat shake
    elif t < 20:
        img.paste(far_layer, (0, AY), far_layer); img.paste(near_layer, (0, AY), near_layer)
        lt = t - 13
        zoom = 1 + lt*0.10             # dolly-in
        hx = W*0.33; hy = AY + AH - 10
        ox = W*0.33; oy = hy - 80*zoom
        # draw scaled hero via temp layer
        hero = Image.new('RGBA', (W, AH), (0,0,0,0)); hd = ImageDraw.Draw(hero)
        draw_person(hd, ox, oy + 150*zoom*0.5, 150*zoom, rim=(255,180,90))
        shake_x = int(math.sin(lt*20)*1.5*lt)
        hero = hero.transform((W, AH), Image.AFFINE, (1,0,shake_x,0,1,0), resample=Image.BILINEAR)
        img.paste(hero, (0, AY), hero)
        # eyes glint
        ex, ey = ox, oy + 150*zoom*0.32
        d.ellipse([ex-4, ey-4, ex+4, ey+4], outline=(255,45,85), width=2)

    # ---- SCENE 4 (20-28s): THREAT REVEAL + IMPACT
    elif t < 28:
        lt = t - 20
        img.paste(far_layer, (0, AY), far_layer); img.paste(near_layer, (0, AY), near_layer)
        # red threat silhouette right third
        tx = W*0.72; ty = AY + AH - 10
        draw_person(d, tx, ty, 170, col=(60,5,15), rim=(255,45,85))
        # impact at t=23.5
        if t > 23.5:
            it = t - 23.5
            for i in range(60):
                ang = random.random()*math.pi*2; dist = it*140*(0.5+random.random())
                px = W*0.55 + math.cos(ang)*dist; py = (AY+AH-140) + math.sin(ang)*dist*0.6
                r = max(1, 8 - it*2)
                d.ellipse([px-r, py-r, px+r, py+r], fill=(255, 214-r*20, 60))
            flash = max(0, 1 - it*3)
            if flash > 0:
                d.rectangle([0, AY, W, AY+AH], fill=(255,255,240))
                img = Image.blend(img, Image.new('RGB',(W,H),(255,240,200)), flash*0.7)
                d = ImageDraw.Draw(img)
            # camera shake
            if it < 0.8:
                for _ in range(200):
                    px, py = random.randint(0,W), random.randint(AH, H)
                    d.point((px,py), fill=(255,255,255))

    # ---- SCENE 5 (28-36s): BUTTON — hero walks into light, fade
    else:
        lt = t - 28
        img.paste(far_layer, (0, AY), far_layer); img.paste(near_layer, (0, AY), near_layer)
        hx = W*0.33 + lt*25
        hy = AY + AH - 10
        draw_person(d, hx, hy - abs(math.sin(lt*7))*4, 150, rim=(255,190,90))
        # rising sun glow
        glow = max(0, 1 - lt/8)
        if glow > 0:
            d.ellipse([W*0.5-200*glow, AY+AH-180*glow, W*0.5+200*glow, AY+AH], fill=(80,40,20))
        # fade to black
        fade = min(1.0, lt/6)
        if fade > 0:
            d.rectangle([0,0,W,H], fill=(0,0,0))
            # re-draw scene then darken: simpler—overlay black alpha via blend
            black = Image.new('RGB',(W,H),(0,0,0))
            img = Image.blend(img, black, fade*0.9)
            d = ImageDraw.Draw(img)
            d.rectangle([0,0,W,LH], fill=(0,0,0)); d.rectangle([0,H-LH,W,H], fill=(0,0,0))

    # ---- finishing: grade, grain, vignette
    img = grade(img, teal=0.4, warm=warmth)
    px = img.load()
    for _ in range(900):  # film grain
        x, y = random.randint(0,W-1), random.randint(0,H-1)
        v = random.randint(-18, 18)
        r0,g0,b0 = px[x,y]
        px[x,y] = (max(0,min(255,r0+v)), max(0,min(255,g0+v)), max(0,min(255,b0+v)))
    # vignette
    vig = Image.new('L',(W,H),0); vd = ImageDraw.Draw(vig)
    vd.ellipse([-W*0.3,-H*0.4,W*1.3,H*1.4], fill=255)
    vig = vig.filter(__import__('PIL.ImageFilter',fromlist=['GaussianBlur']).GaussianBlur(120))
    black = Image.new('RGB',(W,H),(0,0,0))
    img = Image.composite(img, black, vig.point(lambda v: 255-v//3))

    # ---- title cards
    if 1.0 <= t < 4.0:
        scene_title(d, "OMEGA", "A SCENE IN FIVE SHOTS", int(255*(1-abs(t-2.5)/1.5)))
    elif 20.2 <= t < 22.5:
        scene_title(d, "THE HIT", "", 200)

    ff.stdin.write(img.tobytes())
    if f % (FPS*6) == 0:
        print(f"rendered {f}/{NF} frames ({t:.0f}s)", file=sys.stderr, flush=True)

ff.stdin.close(); ff.wait()
print("DONE -> scene_cut.mp4")
