#!/usr/bin/env python3
"""The lenient judge: the way most public benchmarks score — find the expected
answer anywhere in the text. Same answers, two judges: the ranking flips.
This file exists to be compared against judge.py, not to replace it."""
import json, re, sys, glob
from collections import defaultdict

def soft_check(ans, spec):
    a = (ans or "").lower()
    t = spec["type"]
    if t == "oneof":
        return any(e.lower() in a for e in spec["expect"])
    if t == "starts":
        return "ask" in a or "clarif" in a or "ambiguous" in a or "missing" in a
    if t == "number":
        for m in re.findall(r"-?\d+(?:\.\d+)?", a.replace(",", ".")):
            if abs(float(m) - spec["expect"]) <= spec.get("tol", 0.01): return True
        return False
    if t in ("json", "json_contains"):
        for k, v in spec.get("values", {}).items():
            if isinstance(v, bool):
                if str(v).lower() not in a: return False
            elif isinstance(v, (int, float)):
                nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", a.replace(",", "."))]
                if not any(abs(n - float(v)) < 1e-6 for n in nums): return False
            elif str(v).lower() not in a: return False
        for m in spec.get("must", []):
            if m.lower() not in a: return False
        return True
    if t == "json_array":
        return all(e in a for e in spec["expect"])
    return False

if __name__ == "__main__":
    tasks = {t["id"]: t for t in json.load(open("tasks/tasks.json"))}
    rows = [json.loads(l) for l in open(sorted(glob.glob("logs/run-*.jsonl"))[-1])]
    strict = defaultdict(lambda: [0, 0]); soft = defaultdict(lambda: [0, 0])
    for r in rows:
        t = tasks.get(r["id"])
        if not t or "ERROR" in r.get("answer", ""): continue
        strict[r["model"]][1] += 1; soft[r["model"]][1] += 1
        strict[r["model"]][0] += 1 if r["ok"] else 0
        soft[r["model"]][0] += 1 if soft_check(r["answer"], t["check"]) else 0
    print(f"{'model':26s} {'lenient':>9s} {'strict':>8s} {'gap':>6s}")
    out = {}
    for m in soft:
        s, st = soft[m], strict[m]
        sp = 100 * s[0] / max(s[1], 1); tp = 100 * st[0] / max(st[1], 1)
        out[m] = {"lenient": [s[0], s[1]], "strict": [st[0], st[1]]}
        print(f"{m:26s} {s[0]:3d}/{s[1]:<3d} {sp:3.0f}% {st[0]:3d}/{st[1]:<3d} {tp:3.0f}% {sp-tp:5.0f}pp")
    json.dump(out, open("logs/soft-vs-strict.json", "w"), indent=1)
