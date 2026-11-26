"""Ask a chat model (OpenAI-compatible API) for an ASCII-art program; save each answer, its code and its usage.

python -I ask.py --base URL --model NAME --prompt prompt.txt --seeds 1 2 3 [--code prev.py] [--tag v2_] [--out work]
                 [--temperature T] [--max-tokens N] [--reasoning low|medium|high] [--key-env VAR]
The code is saved, never run.  Usage and timing go to <out>/runs.jsonl."""
import argparse, json, os, re, time, urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--base", required=True, help="server root, e.g. http://127.0.0.1:8080 (with or without /v1)")
ap.add_argument("--model", required=True)
ap.add_argument("--prompt", required=True, help="a text file")
ap.add_argument("--seeds", type=int, nargs="+", default=[1])
ap.add_argument("--code", help="the previous program, appended to the prompt in a python block (feedback round)")
ap.add_argument("--tag", default="art", help="file name prefix")
ap.add_argument("--out", default="work")
ap.add_argument("--temperature", type=float, default=0.7)
ap.add_argument("--max-tokens", type=int, default=8192)
ap.add_argument("--reasoning", help="reasoning_effort for thinking models; leave out for others")
ap.add_argument("--key-env", help="name of an environment variable holding the API key")
ap.add_argument("--timeout", type=int, default=1200)
a = ap.parse_args()

out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
prompt = Path(a.prompt).read_text(encoding="utf-8").rstrip("\n")
if a.code:
    prompt += "\n\n```python\n" + Path(a.code).read_text(encoding="utf-8").rstrip("\n") + "\n```"
base = a.base.rstrip("/")
url = base + ("/chat/completions" if base.endswith("/v1") else "/v1/chat/completions")
headers = {"Content-Type": "application/json"}
if a.key_env:
    headers["Authorization"] = "Bearer " + os.environ[a.key_env]

for seed in a.seeds:
    body = {"model": a.model, "messages": [{"role": "user", "content": prompt}], "temperature": a.temperature,
            "seed": seed, "max_tokens": a.max_tokens}
    if a.reasoning:
        body["reasoning_effort"] = a.reasoning
    t0 = time.time()
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    d = json.load(urllib.request.urlopen(req, timeout=a.timeout))
    dt = time.time() - t0
    msg = d["choices"][0]["message"]
    text = msg.get("content") or ""
    blocks = re.findall(r"```python\s*\n(.*?)```", text, re.S)
    code = blocks[-1] if blocks else ""
    name = f"{a.tag}{seed}"
    (out / f"{name}.md").write_text(text, encoding="utf-8")
    (out / f"{name}.py").write_text(code, encoding="utf-8")
    u = d.get("usage") or {}
    ct = u.get("completion_tokens")
    rec = {"name": name, "model": a.model, "seed": seed, "temperature": a.temperature, "reasoning": a.reasoning,
           "max_tokens": a.max_tokens, "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": ct,
           "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
           "seconds": round(dt, 1), "tok_s": round(ct / dt, 1) if ct else None,
           "finish": d["choices"][0].get("finish_reason"), "code_lines": code.count("\n")}
    with open(out / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    last = text.strip().splitlines()[-1][:160] if text.strip() else "EMPTY"
    print(f"{name}: {ct} tokens in {dt:.0f} s ({rec['tok_s']} tok/s, with the prompt), {rec['code_lines']} lines | {last}",
          flush=True)
