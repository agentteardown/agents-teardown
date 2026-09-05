#!/usr/bin/env python3
"""Факты EP02 — из сырых логов, ничего руками. Сценарий читает этот файл,
гейт чисел сверяет сценарий с ним. Чего здесь нет — того не было.

Источники (все 02.09.2026, починенный набор задач):
  logs/cc-20260902-1741.jsonl      Claude Code haiku + sonnet
  logs/run-20260902-1937.jsonl     prompt-builder 27B, ASK_TIMEOUT=600
  logs/run-20260902-2104.jsonl     qwen3.5 / ornith / distill
  logs/final-table.json            что показал EP01 (сломанный набор)
"""
import json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import glob
SRC = ["logs/cc-20260902-1741.jsonl", "logs/run-20260902-1937.jsonl", "logs/run-20260902-2104.jsonl"]
# повторные прогоны облака (03.09): разброс между прогонами — сам по себе факт
CC_RUNS = sorted(f for f in glob.glob("logs/cc-2026090*.jsonl") if f >= "logs/cc-20260902-1741.jsonl")
QWEN_CAP = sorted(glob.glob("logs/run-20260903-*.jsonl"))   # qwen с NUM_PREDICT=4000
tasks = {t["id"]: t for t in json.load(open("tasks/tasks.json"))}
last = {}
for f in SRC:
    for l in open(f):
        r = json.loads(l); last[(r["model"], r["id"])] = r

agg = defaultdict(lambda: {"strict": [0, 0], "cat": defaultdict(lambda: [0, 0]), "sec": [],
                           "cost": 0.0, "in_tok": [], "out_tok": [], "empty": 0, "tps": []})
for (m, i), r in last.items():
    a = agg[m]
    from judge import check as _chk
    r["ok"] = _chk(r["answer"], tasks[i]["check"])[0]        # факты — по ТЕКУЩЕМУ судье
    a["strict"][1] += 1; a["strict"][0] += 1 if r["ok"] else 0
    a["cat"][r["cat"]][1] += 1; a["cat"][r["cat"]][0] += 1 if r["ok"] else 0
    if r["sec"] > 0: a["sec"].append(r["sec"])
    a["cost"] += r.get("cost_usd", 0.0) or 0.0
    if r.get("in_tokens"): a["in_tok"].append(r["in_tokens"])
    if r.get("out_tokens"): a["out_tok"].append(r["out_tokens"])
    if r.get("tps"): a["tps"].append(r["tps"])
    if "NO ANSWER" in (r.get("answer") or ""): a["empty"] += 1

NAMES = {"claude-code/haiku": "haiku", "claude-code/sonnet": "sonnet", "qwen3.5:9b": "qwen",
         "ornith-agent:latest": "ornith", "distill-agent:latest": "distill", "prompt-builder:latest": "27b"}
facts = {"models": {}, "meta": {"tasks": len(tasks), "date": "2026-09-02"}, "examples": {}}
for m, a in agg.items():
    st = a["strict"]
    facts["models"][NAMES.get(m, m)] = {
        "id": m, "strict_n": st, "strict_pct": round(100 * st[0] / st[1]),
        "by_cat": dict(a["cat"]),
        "sec_per_task": round(sum(a["sec"]) / len(a["sec"]), 1) if a["sec"] else 0,   # только завершённые
        "sec_median": round(__import__("statistics").median(a["sec"]), 1) if a["sec"] else 0,
        "cost_usd": round(a["cost"], 2), "cost_usd_exact": round(a["cost"], 4),
        "in_tokens_avg": round(sum(a["in_tok"]) / len(a["in_tok"])) if a["in_tok"] else 0,
        "out_tokens_avg": round(sum(a["out_tok"]) / len(a["out_tok"]), 1) if a["out_tok"] else 0,
        "tok_per_s": round(sum(a["tps"]) / len(a["tps"]), 1) if a["tps"] else 0,
        "empty_answers": a["empty"]}

# размеры локальных моделей — из ollama /api/tags (снято 31.08)
sizes = {}
for mm in json.load(open("logs/ollama-models-20260831.json"))["models"]:
    sizes[mm["name"]] = {"params": mm["details"]["parameter_size"], "gib": round(mm["size"] / 2**30, 1)}
for k, f in facts["models"].items():
    if f["id"] in sizes: f.update(sizes[f["id"]])

ex = facts["examples"]
# что показал EP01 и что дал починенный набор
ep01 = json.load(open("logs/final-table.json"))
ex["ep01_strict"] = {NAMES[m]: v["strict"] for m, v in ep01.items()}
ex["fixed_strict"] = {k: v["strict_n"] for k, v in facts["models"].items() if k in ("qwen", "ornith", "distill", "27b")}
ex["scores_moved"] = sum(1 for k in ex["fixed_strict"] if ex["fixed_strict"][k][0] != ex["ep01_strict"][k][0])
ex["qwen_ep01_pct"] = round(100 * ex["ep01_strict"]["qwen"][0] / 20)
ex["qwen_fixed_pct"] = facts["models"]["qwen"]["strict_pct"]
# цена: полный прогон и «во сколько раз»
h, s = facts["models"]["haiku"], facts["models"]["sonnet"]
ex["sonnet_vs_haiku_cost_ratio"] = round(s["cost_usd_exact"] / h["cost_usd_exact"], 1)
ex["system_prompt_tokens"] = h["in_tokens_avg"]          # почти весь вход — системный промт, задача ~100 токенов
ex["cost_per_task_min"] = round(min(r["cost_usd"] for (m, i), r in last.items() if m == "claude-code/haiku" and r.get("cost_usd")), 4)
# скорость: 27B против лучшей 9B
ex["qwen_vs_27b_sec_ratio"] = round(facts["models"]["27b"]["sec_per_task"] / facts["models"]["qwen"]["sec_per_task"], 1)
# улики: ответы sonnet и haiku на data-05, ответ модели на сломанную data-03 в EP01
ex["sonnet_data05"] = last[("claude-code/sonnet", "data-05")]["answer"]
ex["haiku_data05"] = last[("claude-code/haiku", "data-05")]["answer"]
ex["data05_expected"] = tasks["data-05"]["check"]["expect"]
ex["data05_prompt_tail"] = tasks["data-05"]["prompt"].splitlines()[-1]
ex["ornith_data03_ep01"] = next(json.loads(l)["answer"][:120] for l in open("logs/run-20260830-1731.jsonl")
                                if json.loads(l)["id"] == "data-03" and json.loads(l)["model"].startswith("ornith"))
ex["broken_tasks"] = ["data-03", "data-04"]
ex["bench_bug_found_by"] = "both sides failed the same task with the same complaint"
# доля задач, которые лучшая локальная модель прошла вровень с облаком, по категориям
ex["local_matches_cloud_cats"] = [c for c, v in facts["models"]["qwen"]["by_cat"].items()
                                  if v[0] == facts["models"]["haiku"]["by_cat"][c][0]]
# разброс облака по прогонам: сколько раз haiku >= sonnet, и счёт каждого прогона
runs = []
for f in CC_RUNS:
    sc = {}
    for l in open(f):
        r = json.loads(l); sc.setdefault(r["model"], [0, 0]); sc[r["model"]][1] += 1; sc[r["model"]][0] += r["ok"]
    if "claude-code/haiku" in sc and "claude-code/sonnet" in sc:
        runs.append({"file": os.path.basename(f), "haiku": sc["claude-code/haiku"], "sonnet": sc["claude-code/sonnet"]})
ex["cloud_runs"] = runs
ex["cloud_runs_n"] = len(runs)
ex["haiku_ge_sonnet_runs"] = sum(1 for r in runs if r["haiku"][0] >= r["sonnet"][0])
ex["haiku_scores"] = [r["haiku"][0] for r in runs]; ex["sonnet_scores"] = [r["sonnet"][0] for r in runs]
# промахи qwen на починенном наборе: сколько из них — пустой ответ (лимит генерации)
qm = [r for (m, i), r in last.items() if m == "qwen3.5:9b" and not r["ok"]]
ex["qwen_misses"] = len(qm); ex["qwen_misses_no_answer"] = sum(1 for r in qm if "NO ANSWER" in r["answer"])
ex["num_predict_default"] = 1500
# qwen с поднятым лимитом
if QWEN_CAP:
    q = {}
    for l in open(QWEN_CAP[-1]):
        r = json.loads(l)
        if r["model"] == "qwen3.5:9b": q[r["id"]] = r
    if q:
        ex["qwen_cap4000_strict"] = [sum(1 for r in q.values() if r["ok"]), len(q)]
        ex["qwen_cap4000_no_answer"] = sum(1 for r in q.values() if "NO ANSWER" in r["answer"])
        ex["qwen_cap4000_sec"] = round(sum(r["sec"] for r in q.values() if r["sec"] > 0) / max(1, sum(1 for r in q.values() if r["sec"] > 0)), 1)
        ex["qwen_cap4000_by_cat"] = {}
        for r in q.values():
            c = ex["qwen_cap4000_by_cat"].setdefault(r["cat"], [0, 0]); c[1] += 1; c[0] += r["ok"]
# haiku: все форматные ответы в ```json-заборе; судья забор срезает
hf = [r for (m, i), r in last.items() if m == "claude-code/haiku" and r["cat"] == "format"]
ex["haiku_format_fenced"] = sum(1 for r in hf if r["answer"].lstrip().startswith("```"))
qf = [r for (m, i), r in last.items() if m == "qwen3.5:9b" and r["cat"] == "format" and r["ok"]]
ex["qwen_format_bare"] = sum(1 for r in qf if not r["answer"].lstrip().startswith("```"))
# мягкий судья на починенном наборе
from soft_judge import soft_check
ex["lenient_fixed"] = {}
for (m, i), r in last.items():
    if m.startswith("claude"): continue
    c = ex["lenient_fixed"].setdefault(NAMES.get(m, m), [0, 0]); c[1] += 1; c[0] += soft_check(r["answer"], tasks[i]["check"])
# медиана 27B и размер задачи в словах
s27 = sorted(agg["prompt-builder:latest"]["sec"])
ex["timeout_27b_timeouts"] = sum(1 for (m, i), r in last.items() if m == "prompt-builder:latest" and "TIMEOUT" in r["answer"])
ex["task_words_max"] = max(len(t["prompt"].split()) for t in tasks.values())
ex["task_words_avg"] = round(sum(len(t["prompt"].split()) for t in tasks.values()) / len(tasks))
# токены входа — только из прогонов с полным учётом (после правки run_cc 03.09)
tok = {}
for f in CC_RUNS:
    if "20260903" not in f: continue
    for l in open(f):
        r = json.loads(l); tok.setdefault(r["model"], []).append(r["in_tokens"])
ex["haiku_in_tokens_fixed"] = round(sum(tok["claude-code/haiku"]) / len(tok["claude-code/haiku"])) if tok.get("claude-code/haiku") else None
ex["sonnet_in_tokens_fixed"] = round(sum(tok["claude-code/sonnet"]) / len(tok["claude-code/sonnet"])) if tok.get("claude-code/sonnet") else None
# цена за прогон, среднее по трём
cost = {}
for f in CC_RUNS:
    for l in open(f):
        r = json.loads(l); cost.setdefault((f, r["model"]), 0.0); cost[(f, r["model"])] += r.get("cost_usd") or 0.0
hc = [v for (f, m), v in cost.items() if m.endswith("haiku")]; sc = [v for (f, m), v in cost.items() if m.endswith("sonnet")]
ex["haiku_cost_runs"] = [round(x, 2) for x in hc]; ex["sonnet_cost_runs"] = [round(x, 2) for x in sc]
ex["haiku_cost_avg"] = round(sum(hc) / len(hc), 2); ex["sonnet_cost_avg"] = round(sum(sc) / len(sc), 2)
ex["sonnet_vs_haiku_cost_ratio_avg"] = round(sum(sc) / sum(hc), 1)
ex["haiku_wins"] = sum(1 for r in runs if r["haiku"][0] > r["sonnet"][0]); ex["ties"] = sum(1 for r in runs if r["haiku"][0] == r["sonnet"][0])
ex["haiku_out_tokens_avg"] = facts["models"]["haiku"]["out_tokens_avg"]
if QWEN_CAP and q:
    import statistics
    ex["qwen_cap4000_sec_median"] = round(statistics.median([r["sec"] for r in q.values() if r["sec"] > 0]), 1)
    ex["qwen_cap4000_vs_27b_median_ratio"] = round(facts["models"]["27b"]["sec_median"] / ex["qwen_cap4000_sec_median"], 1)
    ex["qwen_cap4000_max_tokens"] = max(r["tokens"] for r in q.values())
ex["27b_timeouts_600"] = sum(1 for (m, i), r in last.items() if m == "prompt-builder:latest" and "TIMEOUT" in r["answer"])
ex["num_predict_raised"] = 4000
ex["qwen_vs_27b_median_ratio"] = round(facts["models"]["27b"]["sec_median"] / facts["models"]["qwen"]["sec_median"], 1)
ex["cloud_vs_qwen_cap_sec_ratio"] = round(ex.get("qwen_cap4000_sec", 0) / facts["models"]["haiku"]["sec_per_task"], 1) if ex.get("qwen_cap4000_sec") else None
ex["sonnet_in_tokens_avg"] = facts["models"]["sonnet"]["in_tokens_avg"]
ex["27b_empty_answers"] = facts["models"]["27b"]["empty_answers"]
ex["rejudged_answers"] = len(last)                     # пересуд после правки судьи: все сохранённые ответы
ex["timeout_default_s"] = 180
ex["timeout_27b_median_s"] = round(sorted(agg["prompt-builder:latest"]["sec"])[len(agg["prompt-builder:latest"]["sec"]) // 2], 1)

json.dump(facts, open("logs/facts-ep02.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(ex, ensure_ascii=False, indent=1)[:1500])
for k, f in sorted(facts["models"].items(), key=lambda kv: -kv[1]["strict_pct"]):
    print(f"{k:8s} strict {f['strict_n'][0]:2d}/{f['strict_n'][1]} {f['strict_pct']:3d}%  {f['sec_per_task']:6.1f}s  ${f['cost_usd']:.2f}  in {f['in_tokens_avg']}  {f['by_cat']}")
