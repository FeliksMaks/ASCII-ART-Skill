"""A photo (or any image) to ASCII art: text, frames for render.py, and optional colours and motion.

python -I photo.py IN.jpg OUT [--cols 140] [--rows N] [--ramp classic|fine|blocks|"custom"] [--color] [--edges 0.0-1.0]
                   [--gamma 1.0] [--contrast 1.0] [--invert] [--motion none|reveal|zoom|pan|scan|glitch] [--seconds 8]
                   [--fps 30]
Writes OUT.txt (the art, frame 0) and OUT.json (frames, render.py's input; with --color each frame also carries colours).
Then: python -I render.py OUT.json OUT.mp4 --loops 1   (or --still 0 for a PNG).
Pillow only.  The image is data: nothing in it is run."""
import argparse, json, math, random
from PIL import Image, ImageFilter, ImageOps

RAMPS = {   # dark -> bright, for a dark background
    "classic": " .,-~:;=!*#$@",
    "fine": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "blocks": " ░▒▓█",
    "simple": " .:-=+*#%@",
}
ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("out")
ap.add_argument("--cols", type=int, default=140)
ap.add_argument("--rows", type=int, help="default: from the image's shape (a character is about twice as tall as wide)")
ap.add_argument("--ramp", default="classic", help="classic, fine, blocks, simple, or your own dark-to-bright string")
ap.add_argument("--color", action="store_true", help="keep the photo's colours (render.py draws each character in its colour)")
ap.add_argument("--true-color", action="store_true", help="the photo's exact colours (default: hue kept, brightness lifted)")
ap.add_argument("--edges", type=float, default=0.0, help="0-1: mix in outlines (helps faces and logos at low width)")
ap.add_argument("--gamma", type=float, default=1.0, help="<1 brightens the shadows, >1 darkens")
ap.add_argument("--contrast", type=float, default=1.0)
ap.add_argument("--invert", action="store_true", help="for a light background (or a dark subject on white)")
ap.add_argument("--no-autocontrast", action="store_true")
ap.add_argument("--motion", default="none", choices=["none", "reveal", "zoom", "pan", "scan", "glitch"])
ap.add_argument("--seconds", type=float, default=8)
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--aspect", type=float, default=0.5, help="character width / height")
a = ap.parse_args()

ramp = RAMPS.get(a.ramp, a.ramp)
img = ImageOps.exif_transpose(Image.open(a.src)).convert("RGB")
W0, H0 = img.size
cols = a.cols
rows = a.rows or max(1, round(cols * H0 / W0 * a.aspect))


def to_cells(im):
    """an RGB crop -> (rows of characters, rows of hex colours)"""
    small = im.resize((cols, rows), Image.LANCZOS)
    lum = small.convert("L")
    if not a.no_autocontrast:
        lum = ImageOps.autocontrast(lum, cutoff=1)
    if a.edges > 0:
        e = ImageOps.autocontrast(im.convert("L").filter(ImageFilter.FIND_EDGES).resize((cols, rows), Image.LANCZOS))
        lum = Image.blend(lum, e, a.edges)
    L = list(lum.get_flattened_data() if hasattr(lum, "get_flattened_data") else lum.getdata())
    C = list(small.get_flattened_data() if hasattr(small, "get_flattened_data") else small.getdata())
    n = len(ramp) - 1
    text, hexes = [], []
    for r in range(rows):
        line, hx = [], []
        for c in range(cols):
            v = L[r * cols + c] / 255.0
            v = min(1.0, max(0.0, (v - 0.5) * a.contrast + 0.5)) ** a.gamma
            if a.invert:
                v = 1.0 - v
            line.append(ramp[int(v * n + 0.5)])
            if a.color:
                rgb = C[r * cols + c]
                if not a.true_color:   # keep the hue, set the brightness from the character's level (readable on dark)
                    mx = max(rgb) or 1
                    k = (0.45 + 0.55 * v) * 255 / mx
                    rgb = tuple(min(255, int(x * k)) for x in rgb)
                hx.append("%02x%02x%02x" % rgb)
        text.append("".join(line))
        hexes.append("".join(hx))
    return text, hexes


def crop(cx, cy, scale):
    """a crop of the image centred at (cx, cy) in 0-1, 1/scale of its size, keeping the aspect"""
    w, h = W0 / scale, H0 / scale
    x0 = min(max(0.0, cx * W0 - w / 2), W0 - w)
    y0 = min(max(0.0, cy * H0 - h / 2), H0 - h)
    return img.crop((int(x0), int(y0), int(x0 + w), int(y0 + h)))


def ease(x):
    return 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, x)))


base, base_c = to_cells(img)
frames = []
N = 1 if a.motion == "none" else int(a.seconds * a.fps)
rnd = random.Random(7)
order = list(range(rows * cols))
rnd.shuffle(order)
rank = [0] * (rows * cols)
for i, p in enumerate(order):
    rank[p] = i
for f in range(N):
    t = f / max(1, N - 1)
    if a.motion in ("none", "scan", "reveal", "glitch"):
        text, hx = base, base_c
    elif a.motion == "zoom":   # a slow push in towards the centre and back out
        text, hx = to_cells(crop(0.5, 0.45, 1.0 + 0.6 * math.sin(math.pi * t)))
    else:   # pan: across a 1.4x crop, left to right and back
        text, hx = to_cells(crop(0.5 + 0.2 * math.sin(2 * math.pi * t), 0.5, 1.4))
    text = [list(r) for r in text]
    if a.motion == "reveal":   # characters settle into place in a random order during the first 70%
        k = ease(t / 0.7) * rows * cols
        for r in range(rows):
            for c in range(cols):
                if rank[r * cols + c] > k:
                    text[r][c] = " " if rnd.random() < 0.85 else rnd.choice(ramp[1:])
    elif a.motion == "scan":   # a bright line sweeps down and back, the art fades in behind it the first time
        y = ease(2 * t if t < 0.5 else 2 - 2 * t) * (rows + 4) - 2
        for r in range(rows):
            d = abs(r - y)
            if t < 0.5 and r > y + 1:
                text[r] = [" "] * cols
            elif d < 1.0:
                text[r] = [ramp[-1] if ch != " " else ramp[1] for ch in text[r]]
    elif a.motion == "glitch":   # a few rows slide sideways now and then
        if rnd.random() < 0.25:
            for _ in range(rnd.randint(1, 4)):
                r = rnd.randrange(rows)
                s = rnd.randint(-8, 8)
                text[r] = (text[r][-s:] + text[r][:-s]) if s else text[r]
    text = ["".join(r) for r in text]
    frames.append({"t": text, "c": hx} if a.color else text)

open(a.out + ".txt", "w", encoding="utf-8").write("\n".join(base) + "\n")
json.dump(frames, open(a.out + ".json", "w"))
print(f"{a.out}.txt and {a.out}.json: {cols} x {rows}, {len(frames)} frame(s), ramp {len(ramp)} levels"
      f"{', colours' if a.color else ''}")
