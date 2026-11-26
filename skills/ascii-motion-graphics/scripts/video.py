"""A video to ASCII art: frames for render.py (and the first frame as text), optionally in the video's colours.

python -I video.py IN.mp4 OUT [--cols 140] [--fps 30] [--start 0] [--duration 20] [--ramp classic|fine|blocks|simple|"..."]
                   [--color] [--true-color] [--edges 0.0-1.0] [--gamma 1.0] [--contrast 1.0] [--invert] [--max-seconds 60]
Writes OUT.json (frames), OUT.txt (the first frame) and OUT.meta.json (fps, start, duration, source: for the sound).
Then: python -I render.py OUT.json OUT.mp4 --loops 1 --fps 30 --audio IN.mp4 --audio-start 0
Needs ffmpeg and ffprobe on PATH, and Pillow.  The video is only decoded to pixels: nothing in it is run."""
import argparse, json, os, shutil, subprocess, sys
from PIL import Image, ImageFilter, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import halfblock   # noqa: E402  (this folder's shared code)

RAMPS = {   # dark -> bright, for a dark background
    "classic": " .,-~:;=!*#$@",
    "fine": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "blocks": " ░▒▓█",
    "simple": " .:-=+*#%@",
}
ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("out")
ap.add_argument("--cols", type=int, default=200, help="more columns, more detail (200-240 at 1080p; up to ~400 for --size 3840x2160)")
ap.add_argument("--rows", type=int, help="default: from the video's shape (a character is about twice as tall as wide)")
ap.add_argument("--fps", type=float, default=30)
ap.add_argument("--start", type=float, default=0.0, help="seconds into the video")
ap.add_argument("--duration", type=float, help="seconds (default: to the end, at most --max-seconds)")
ap.add_argument("--max-seconds", type=float, default=60, help="a guard: frames are kept in memory and in the JSON")
ap.add_argument("--ramp", default="fine", help="fine (70 levels, the default for video), classic, blocks, simple or your own")
ap.add_argument("--color", action="store_true")
ap.add_argument("--true-color", action="store_true")
ap.add_argument("--edges", type=float, default=0.0)
ap.add_argument("--gamma", type=float, default=1.0)
ap.add_argument("--contrast", type=float, default=1.0)
ap.add_argument("--invert", action="store_true")
ap.add_argument("--aspect", type=float, default=0.5, help="character width / height")
ap.add_argument("--mode", default="ascii", choices=["ascii", "halfblock"],
                help="halfblock: two coloured pixels a cell (upper and lower half), not ASCII but twice the detail")
a = ap.parse_args()
for tool in ("ffmpeg", "ffprobe"):
    if not shutil.which(tool):
        sys.exit(f"{tool} is not on PATH")

ramp = RAMPS.get(a.ramp, a.ramp)
pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=width,height:stream_side_data=rotation:format=duration", "-of", "json", a.src],
                               capture_output=True, text=True, check=True).stdout)
st = pr["streams"][0]
W0, H0 = int(st["width"]), int(st["height"])
rot = 0
for sd in st.get("side_data_list", []) or []:
    rot = int(sd.get("rotation", 0) or 0)
if rot % 180:   # a phone video recorded upright: ffmpeg turns it, so the shape is swapped
    W0, H0 = H0, W0
total = float(pr.get("format", {}).get("duration", 0) or 0)
dur = a.duration if a.duration else max(0.0, total - a.start)
dur = min(dur, a.max_seconds)
if dur <= 0:
    sys.exit("nothing to convert: check --start and --duration")
cols = a.cols
rows = a.rows or max(1, round(cols * H0 / W0 * a.aspect))
# decode at 4 x the grid (outlines need the detail; the grid is averaged from it)
sw, sh = cols * 4, rows * 4


def decode(w, h, fmt):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(a.start), "-t", str(dur), "-i", a.src, "-vf",
           f"fps={a.fps},scale={w}:{h}:flags=area", "-f", "rawvideo", "-pix_fmt", fmt, "-"]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE)


# pass 1: one brightness range for the whole clip (a per-frame stretch would flicker)
hist = [0] * 256
p = decode(cols, rows, "gray")
n1 = cols * rows
while True:
    b = p.stdout.read(n1)
    if len(b) < n1:
        break
    for v in b:
        hist[v] += 1
p.wait()
tot = sum(hist) or 1
acc, lo, hi = 0, 0, 255
for i, h in enumerate(hist):
    acc += h
    if acc >= tot * 0.01:
        lo = i
        break
acc = 0
for i in range(255, -1, -1):
    acc += hist[i]
    if acc >= tot * 0.01:
        hi = i
        break
span = max(1, hi - lo)
n = len(ramp) - 1


def lift_levels(rgb):   # the true colours through the clip's levels (half blocks)
    return tuple(min(255, max(0, int((x - lo) * 255 / span))) for x in rgb)


def pixels(im):
    return list(im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata())


def to_cells(im):
    if a.mode == "halfblock":
        fg, bg = halfblock.halfblock_cells(im, cols, rows, lift_levels)
        return ["▀" * cols for _ in range(rows)], fg, bg
    small = im.resize((cols, rows), Image.BOX)
    L = pixels(small.convert("L"))
    if a.edges > 0:
        e = im.convert("L").filter(ImageFilter.FIND_EDGES).resize((cols, rows), Image.BOX)
        E = pixels(ImageOps.autocontrast(e))
    C = pixels(small) if a.color else None
    text, hexes = [], []
    for r in range(rows):
        line, hx = [], []
        for c in range(cols):
            i = r * cols + c
            v = min(1.0, max(0.0, (L[i] - lo) / span))
            if a.edges > 0:
                v = (1 - a.edges) * v + a.edges * E[i] / 255.0
            v = min(1.0, max(0.0, (v - 0.5) * a.contrast + 0.5)) ** a.gamma
            if a.invert:
                v = 1.0 - v
            line.append(ramp[int(v * n + 0.5)])
            if C:
                rgb = C[i]
                if not a.true_color:   # the hue kept, the brightness from the character's level (readable on dark)
                    mx = max(rgb) or 1
                    k = (0.45 + 0.55 * v) * 255 / mx
                    rgb = tuple(min(255, int(x * k)) for x in rgb)
                hx.append("%02x%02x%02x" % rgb)
        text.append("".join(line))
        hexes.append("".join(hx))
    return text, hexes, None


# pass 2: the frames
frames = []
p = decode(sw, sh, "rgb24")
nb = sw * sh * 3
while True:
    b = p.stdout.read(nb)
    if len(b) < nb:
        break
    text, hx, bg = to_cells(Image.frombytes("RGB", (sw, sh), b))
    frames.append({"t": text, "c": hx, "b": bg} if bg else {"t": text, "c": hx} if a.color else text)
p.wait()
if not frames:
    sys.exit("no frames decoded")
first = frames[0]["t"] if isinstance(frames[0], dict) else frames[0]
open(a.out + ".txt", "w", encoding="utf-8").write("\n".join(first) + "\n")
json.dump(frames, open(a.out + ".json", "w"))
json.dump({"fps": a.fps, "start": a.start, "duration": len(frames) / a.fps, "source": a.src, "cols": cols, "rows": rows},
          open(a.out + ".meta.json", "w"))
print(f"{a.out}.json: {len(frames)} frames ({len(frames) / a.fps:.1f} s at {a.fps:g} fps), {cols} x {rows}, "
      f"levels {lo}-{hi}{', colours' if a.color else ''}")
