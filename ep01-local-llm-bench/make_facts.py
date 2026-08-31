#!/usr/bin/env python3
"""Facts of the episode, computed from the raw logs — never typed by hand.
The script that writes numbers into the video reads this file; the numbers gate
checks the script against it. If a number is not here, it did not happen."""
import json, glob, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from soft_judge import soft_check
from collections import defaultdict

tasks = {t["id"]: t for t in json.load(open("tasks/tasks.json"))}
rows = []
for f in sorted(glob.glob("logs/run-*.jsonl")): rows += [json.loads(l) for l in open(f)]
last = {}
for r in rows: last[(r["model"], r["id"])] = r

agg = defaultdict(lambda: {"strict": [0, 0], "soft": [0, 0], "cat": defaultdict(lambda: [0, 0]),
                           "tps": [], "sec": [], "empty": 0,
                           "think": [], "cap": 0})
for (m, i), r in last.items():
    t = tasks.get(i)
    if not t: continue
    a = agg[m]
    a["strict"][1] += 1; a["strict"][0] += 1 if r["ok"] else 0
    a["soft"][1] += 1; a["soft"][0] += 1 if soft_check(r.get("answer", ""), t["check"]) else 0
    a["cat"][r["cat"]][1] += 1; a["cat"][r["cat"]][0] += 1 if r["ok"] else 0
    if r.get("tps"): a["tps"].append(r["tps"])
    if r["sec"] > 0: a["sec"].append(r["sec"])
    if "NO ANSWER" in r.get("answer", ""): a["empty"] += 1
    if r.get("think_chars"): a["think"].append(r["think_chars"])
    if "length" in r.get("answer", ""): a["cap"] = max(a["cap"], r.get("tokens") or 0)

facts = {"models": {}, "meta": {}}
for m, a in agg.items():
    sp = round(100 * a["soft"][0] / max(a["soft"][1], 1))
    st = round(100 * a["strict"][0] / max(a["strict"][1], 1))
    facts["models"][m] = {
        "strict_pct": st, "lenient_pct": sp, "gap_pp": sp - st,
        "strict_n": a["strict"], "lenient_n": a["soft"],
        "by_cat": {k: v for k, v in a["cat"].items()},
        "tok_per_s": round(sum(a["tps"]) / len(a["tps"]), 1) if a["tps"] else 0,
        "sec_per_task": round(sum(a["sec"]) / len(a["sec"]), 1) if a["sec"] else 0,
        "empty_answers": a["empty"],
        "think_chars_max": max(a["think"]) if a["think"] else 0,
        "token_cap_hits": a["cap"]}
# размеры моделей — из ollama /api/tags, снято 31.08.2026: подписи «9B/27B» и
# вывод «не влезает в 16 ГБ» держались ни на чём (опровергатель 31.08)
sizes = {}
if os.path.exists("logs/ollama-models-20260831.json"):
    for m in json.load(open("logs/ollama-models-20260831.json"))["models"]:
        sizes[m["name"]] = {"params": m["details"]["parameter_size"],
                            "gib": round(m["size"] / 2**30, 1),
                            "quant": m["details"]["quantization_level"]}
for m, f in facts["models"].items():
    if m in sizes: f.update(sizes[m])
stab = json.load(open("logs/stability.json")) if os.path.exists("logs/stability.json") else {}
facts["meta"] = {"tasks": len(tasks), "models": len(agg),
                 "judge_controls": 13,
                 "stability_runs": len(stab) * 3,
                 "stability_verdict_changes": sum(1 for v in stab.values() if len(set(v["verdicts"])) > 1),
                 "stability_text_drift": sum(1 for v in stab.values() if not v["identical_text"])}
# улики конкретных примеров, которые показывает ролик: их числа тоже обязаны
# приходить из логов, а не считаться на глаз (опровергатель 31.08)
ex = {}
r = last.get(("distill-agent:latest", "tool-01"))
if r and "run_shell(" in (r.get("answer") or ""):
    ex["tool01_words_before_call"] = len(r["answer"][:r["answer"].find("run_shell(")].split())
# база мягкого судьи: сколько задач проходит один лишь текст задания
ex["lenient_echo_pass"] = sum(1 for t in tasks.values() if soft_check(t["prompt"], t["check"]))
# кратность по времени на задачу: её показывает гонка в кадре, значит она факт
# отношение ИМЕННО ТОЙ пары, что показывает гонка в кадре: качели «самый
# быстрый против самого медленного» дали бы 50.3 против ornith, а на экране
# сравниваются qwen3.5 и prompt-builder (31.08)
a = facts["models"].get("qwen3.5:9b", {}).get("sec_per_task")
b = facts["models"].get("prompt-builder:latest", {}).get("sec_per_task")
if a and b:
    ex["qwen_vs_27b_sec_ratio"] = round(b / a, 1)
facts["examples"] = ex
json.dump(facts, open("logs/facts.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(facts["meta"], ensure_ascii=False))
for m, f in sorted(facts["models"].items(), key=lambda kv: -kv[1]["strict_pct"]):
    print(f"{m:26s} strict {f['strict_pct']:3d}%  lenient {f['lenient_pct']:3d}%  "
          f"gap {f['gap_pp']:3d}pp  {f['tok_per_s']:5.1f} tok/s  {f['sec_per_task']:6.1f}s  "
          f"empty {f['empty_answers']}")
