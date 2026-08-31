#!/usr/bin/env python3
"""Does the bench repeat itself? Same task, same seed, three runs.
A benchmark that cannot reproduce its own number has no business ranking models
(learned from the previous episode: the judge was less stable than the gap it measured)."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import ask
from judge import check

tasks = {t["id"]: t for t in json.load(open("tasks/tasks.json"))}
ids = ["fmt-01", "tool-01", "amb-01", "data-01", "data-04"]
models = sys.argv[1:] or ["qwen3.5:9b", "ornith-agent:latest"]
out = {}
for m in models:
    print(f"=== {m}", flush=True)
    for i in ids:
        t = tasks[i]; verdicts = []; answers = []
        for r in range(3):
            try: a, dt, rate, tok, th = ask(m, t["prompt"])
            except Exception as e: a = f"<ERROR {e}>"
            ok, _ = check(a, t["check"]); verdicts.append(ok); answers.append(a.strip()[:120])
        same_text = len(set(answers)) == 1
        same_verdict = len(set(verdicts)) == 1
        out[f"{m}/{i}"] = {"verdicts": verdicts, "identical_text": same_text}
        print(f"  {i:8s} вердикты {['ok' if v else 'FAIL' for v in verdicts]} "
              f"{'текст идентичен' if same_text else 'ТЕКСТ ГУЛЯЕТ'}"
              f"{'' if same_verdict else '  ← ВЕРДИКТ НЕСТАБИЛЕН'}", flush=True)
json.dump(out, open("logs/stability.json", "w"), indent=1, ensure_ascii=False)
flip = sum(1 for v in out.values() if len(set(v["verdicts"])) > 1)
drift = sum(1 for v in out.values() if not v["identical_text"])
print(f"\nиз {len(out)} проверок: вердикт менялся {flip}, текст гулял {drift}")
