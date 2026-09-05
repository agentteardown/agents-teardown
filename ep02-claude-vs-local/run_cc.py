#!/usr/bin/env python3
"""Прогон того же набора задач через Claude Code (print-режим, без инструментов
и без контекста проекта) — вторая сторона сравнения для EP02. Судья тот же,
что и у локальных моделей: строгий check() из judge.py.

Каждый ответ, время и стоимость пишутся в logs/cc-*.jsonl — цифра в ролике
должна прослеживаться до строки в файле."""
import json, os, sys, time, subprocess, tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from judge import check

# пустой каталог: без CLAUDE.md, без кода вокруг — те же условия, что у локальной
# модели, которой достаётся только текст задачи
SANDBOX = tempfile.mkdtemp(prefix="cc-bench-")

def ask(model, prompt, timeout=300):
    cmd = ["claude", "-p", "--restricted", "--no-session-persistence",
           "--output-format", "json", "--model", model]
    t0 = time.time()
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                       timeout=timeout, cwd=SANDBOX)
    dt = time.time() - t0
    if r.returncode != 0:
        return f"<ERROR rc={r.returncode} {r.stderr[:200]}>", dt, 0.0, 0, 0
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        return f"<ERROR unparsable: {r.stdout[:200]}>", dt, 0.0, 0, 0
    ans = (d.get("result") or "").strip()
    cost = d.get("total_cost_usd") or 0.0
    u = d.get("usage") or {}
    # вход целиком: обычные + прочитанные из кэша + ЗАПИСАННЫЕ в кэш (03.09: без последнего
    # слагаемого вызовы без кэша показывали 11.5k, с кэшем 14.5k — среднее 12673 было
    # средним двух неполных способов учёта, а не размером входа)
    inp = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
    out = u.get("output_tokens", 0)
    return ans, dt, cost, inp, out

def main():
    models = sys.argv[1:] or ["haiku", "sonnet"]
    tasks = json.load(open(os.path.join(ROOT, "tasks", "tasks.json")))
    stamp = time.strftime("%Y%m%d-%H%M")
    log = open(os.path.join(ROOT, "logs", f"cc-{stamp}.jsonl"), "w")
    summary = {}
    for m in models:
        got = {"format": [0, 0], "tool": [0, 0], "ambiguity": [0, 0], "data": [0, 0]}
        secs = []; costs = []; outs = []
        print(f"\n=== {m}", flush=True)
        for t in tasks:
            try:
                ans, dt, cost, inp, out = ask(m, t["prompt"])
            except subprocess.TimeoutExpired:
                ans, dt, cost, inp, out = "<ERROR timeout>", 300.0, 0.0, 0, 0
            ok, why = check(ans, t["check"])
            got[t["cat"]][1] += 1
            got[t["cat"]][0] += 1 if ok else 0
            secs.append(dt); costs.append(cost); outs.append(out)
            log.write(json.dumps({"model": "claude-code/" + m, "id": t["id"],
                                  "cat": t["cat"], "ok": ok, "why": why,
                                  "sec": round(dt, 2), "cost_usd": cost,
                                  "in_tokens": inp, "out_tokens": out,
                                  "answer": ans[:2000]}, ensure_ascii=False) + "\n")
            log.flush()
            print(f"  {t['id']:8s} {'ok ' if ok else 'FAIL'} {dt:5.1f}s  ${cost:.4f}  {why[:44]}", flush=True)
        tot = (sum(v[0] for v in got.values()), sum(v[1] for v in got.values()))
        summary[m] = {"by_cat": got, "total": tot,
                      "sec_per_task": round(sum(secs)/len(secs), 2),
                      "cost_total_usd": round(sum(costs), 4),
                      "out_tokens_avg": round(sum(outs)/len(outs), 1)}
        print(f"  ИТОГО {tot[0]}/{tot[1]}  {summary[m]['sec_per_task']}с/задачу  ${summary[m]['cost_total_usd']}", flush=True)
    json.dump(summary, open(os.path.join(ROOT, "logs", f"cc-summary-{stamp}.json"), "w"),
              ensure_ascii=False, indent=2)
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
