"""Run a checked art program's frame(t) in a child process and save the frames as JSON.
python -I frames.py art.py frames.json [--fps 30] [--seconds 12] [--rows 45] [--cols 140] [--frame-timeout 10]"""
import argparse, json, queue, subprocess, sys, threading, time

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("out")
ap.add_argument("--fps", type=float, default=30)
ap.add_argument("--seconds", type=float, default=12)
ap.add_argument("--rows", type=int, default=45)
ap.add_argument("--cols", type=int, default=140)
ap.add_argument("--frame-timeout", type=float, default=10, help="seconds a frame may take")
a = ap.parse_args()

# the child: only `math` can be imported, a short list of builtins, nothing for files or the network
CHILD = r'''
import builtins, json, math, sys
def imp(n, *x, **y):
    if n != "math":
        raise ImportError(n)
    return math
B = {k: getattr(builtins, k) for k in ("range len int float abs min max round list tuple str enumerate zip sum sorted "
     "reversed bool dict set isinstance map filter any all divmod pow chr ord ValueError ZeroDivisionError IndexError "
     "Exception").split()}
B["__import__"] = imp
ns = {"__builtins__": B}
exec(compile(open(sys.argv[1], encoding="utf-8").read(), sys.argv[1], "exec"), ns)
for line in sys.stdin:
    sys.stdout.write(json.dumps(ns["frame"](float(line))) + "\n")
    sys.stdout.flush()
'''
p = subprocess.Popen([sys.executable, "-I", "-c", CHILD, a.src], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
q = queue.Queue()


def reader():
    for x in iter(p.stdout.readline, ""):
        q.put(x)
    q.put("")


threading.Thread(target=reader, daemon=True).start()
frames, t0 = [], time.time()
try:
    for i in range(int(a.fps * a.seconds)):
        p.stdin.write(f"{i / a.fps}\n")
        p.stdin.flush()
        try:
            line = q.get(timeout=a.frame_timeout)
        except queue.Empty:
            sys.exit(f"frame {i} took more than {a.frame_timeout} s")
        if not line:
            sys.exit(f"the program stopped at frame {i}")
        f = json.loads(line)
        ok = isinstance(f, list) and len(f) == a.rows and all(isinstance(r, str) and len(r) == a.cols for r in f)
        if not ok:
            got = f"{len(f)} rows, lengths {[len(r) for r in f][:4]}" if isinstance(f, list) else type(f).__name__
            sys.exit(f"frame {i}: want {a.rows} strings of {a.cols} characters, got {got}")
        frames.append(f)
finally:
    p.kill()
json.dump(frames, open(a.out, "w"))
print(a.src, len(frames), "frames in", round(time.time() - t0, 1), "s")
