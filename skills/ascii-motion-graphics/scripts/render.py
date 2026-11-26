"""Draw text frames (frames.py's JSON) to PNG stills or an MP4.
python -I render.py frames.json out.mp4 [--loops 2] [--still 0,90,180] [--caption TEXT] [--brand TEXT] [--font PATH]
                    [--size 1920x1080] [--fps 30] [--shade " .,-~:;=!*#$@"]"""
import argparse, json, os, shutil, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("frames")
ap.add_argument("out")
ap.add_argument("--loops", type=int, default=2)
ap.add_argument("--still", help="frame numbers: writes out_<n>.png and stops")
ap.add_argument("--caption", default="")
ap.add_argument("--brand", default="")
ap.add_argument("--font")
ap.add_argument("--size", default="1920x1080")
ap.add_argument("--fps", type=float, default=30)
ap.add_argument("--crf", type=int, default=17, help="H.264 quality: lower is better and bigger (12-18 for fine text)")
ap.add_argument("--audio", help="a video or audio file whose sound goes under the clip (video.py's source)")
ap.add_argument("--audio-start", type=float, default=0.0, help="seconds into --audio (video.py's --start)")
ap.add_argument("--shade", default=" .,-~:;=!*#$@", help="the dark-to-bright ramp the program used, for the colours")
a = ap.parse_args()

W, H = (int(x) for x in a.size.split("x"))
BG = (12, 14, 18)
LO, MID, HI = (70, 78, 94), (200, 205, 214), (255, 150, 96)   # cool grey into a warm highlight
CANDIDATES = [a.font] if a.font else [
    "C:/Windows/Fonts/CascadiaMono.ttf", "C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf", "/System/Library/Fonts/Menlo.ttc", "/Library/Fonts/Menlo.ttc"]
path = next((f for f in CANDIDATES if f and os.path.exists(f)), None)
if not path:
    sys.exit("no monospace font found: pass --font")
frames = json.load(open(a.frames))
# a frame is a list of rows, or {"t": rows, "c": rows of 6-hex-digit colours per character} (photo.py --color)
frames = [(f["t"], f.get("c"), f.get("b")) if isinstance(f, dict) else (f, None, None) for f in frames]   # (b: half blocks)
rows, cols = len(frames[0][0]), len(frames[0][0][0])
# the largest font size whose grid fits in 92% of the width and 86% of the height (room for the caption)
size = 120
while size > 6:
    F = ImageFont.truetype(path, size)
    cw, lh = F.getlength("M"), size * 1.05
    if cw * cols <= W * 0.92 and lh * rows <= H * 0.86:
        break
    size -= 1
CAP = ImageFont.truetype(path, max(12, size))
x0, y0 = (W - cw * cols) / 2, (H * 0.90 - lh * rows) / 2


def col(ch):
    i = a.shade.find(ch)
    if i < 0:
        return MID
    x = i / max(1, len(a.shade) - 1)
    if x < 0.6:
        k = x / 0.6
        return tuple(int(LO[j] + (MID[j] - LO[j]) * k) for j in range(3))
    k = (x - 0.6) / 0.4
    return tuple(int(MID[j] + (HI[j] - MID[j]) * k) for j in range(3))


COLS = {}


def hexrgb(h):
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def draw(frc, t):
    fr, hx, bg = frc
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    if bg:   # half blocks: each cell two exact rectangles, the upper colour over the lower one
        for r in range(len(fr)):
            y = y0 + r * lh
            for c in range(len(fr[r])):
                x = x0 + c * cw
                d.rectangle((x, y, x + cw, y + lh / 2), fill=hexrgb(hx[r][6 * c:6 * c + 6]))
                d.rectangle((x, y + lh / 2, x + cw, y + lh), fill=hexrgb(bg[r][6 * c:6 * c + 6]))
        fr = []
    for r, line in enumerate(fr):
        y = y0 + r * lh
        for c, ch in enumerate(line):
            if ch != " ":
                if hx:
                    h = hx[r][6 * c:6 * c + 6]
                    fill = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
                else:
                    if ch not in COLS:
                        COLS[ch] = col(ch)
                    fill = COLS[ch]
                d.text((x0 + c * cw, y), ch, font=F, fill=fill)
    k = min(1.0, t / 1.5)   # the caption fades in over 1.5 s
    cap = tuple(int(BG[j] + ((110, 118, 132)[j] - BG[j]) * k) for j in range(3))
    if a.caption:
        d.text((x0, H - H * 0.057), a.caption, font=CAP, fill=cap)
    if a.brand:
        d.text((W - x0, H - H * 0.057), a.brand, font=CAP, fill=cap, anchor="ra")
    return im


if a.still:
    base = os.path.splitext(a.out)[0]
    for s in a.still.split(","):
        draw(frames[int(s)], 5).save(f"{base}_{s}.png")
        print(f"{base}_{s}.png")
    sys.exit()
if not shutil.which("ffmpeg"):
    sys.exit("ffmpeg is not on PATH")
cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r",
       str(a.fps), "-i", "-"]
if a.audio:   # the source's sound, cut to the same span; a file without sound is fine ("1:a?")
    cmd += ["-ss", str(a.audio_start), "-i", a.audio, "-map", "0:v", "-map", "1:a?", "-c:a", "aac", "-b:a", "192k", "-shortest"]
cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", a.out]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
n = 0
for _ in range(a.loops):
    for fr in frames:
        p.stdin.write(draw(fr, n / a.fps).tobytes())
        n += 1
p.stdin.close()
p.wait()
print(a.out, n, "frames, exit", p.returncode)
