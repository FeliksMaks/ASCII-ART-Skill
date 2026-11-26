"""Totals for a post from ask.py's runs.jsonl: python -I stats.py work/runs.jsonl [names of the answers used, e.g. art1 v2_1]"""
import json, sys

runs = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
used = set(sys.argv[2:])


def total(rs, label):
    tok = sum(r.get("completion_tokens") or 0 for r in rs)
    sec = sum(r.get("seconds") or 0 for r in rs)
    think = [r.get("reasoning_tokens") for r in rs]
    th = f", thinking {sum(think)}" if all(x is not None for x in think) and rs else ""
    print(f"{label}: {len(rs)} answers, {tok:,} output tokens{th}, {sec:.0f} s, {tok / sec if sec else 0:.1f} tok/s")


for r in runs:
    print(f"  {r['name']:>8} {r['model']} seed {r['seed']} T={r['temperature']} reasoning={r['reasoning']}: "
          f"{r['completion_tokens']} tokens, {r['seconds']} s, {r['tok_s']} tok/s, {r['finish']}")
if used:
    total([r for r in runs if r["name"] in used], "used")
total(runs, "all samples")
