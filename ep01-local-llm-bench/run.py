#!/usr/bin/env python3
"""Run the task set against local models through Ollama. Deterministic
(temperature 0), every raw answer saved to logs/run-*.jsonl — the number in the
video must be traceable to a line in a file."""
import json, os, sys, time, urllib.request, subprocess

HOST = os.environ.get("OLLAMA_HOST") or ("http://" + subprocess.run(
    "ip route show default | awk '{print $3}'", shell=True, capture_output=True,
    text=True).stdout.strip() + ":11434")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from judge import check

def ask(model, prompt, timeout=int(os.environ.get("ASK_TIMEOUT", "180"))):
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0, "seed": 7, "num_predict": 1500}}).encode()
    req = urllib.request.Request(HOST + "/api/generate", body,
                                 {"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    dt = time.time() - t0
    tok = d.get("eval_count", 0)
    rate = tok / (d.get("eval_duration", 1) / 1e9) if d.get("eval_duration") else 0
    ans = (d.get("response") or "").strip()
    think = (d.get("thinking") or "")
    # reasoning-модель может истратить весь бюджет на размышления и вернуть пустоту —
    # в агентной обвязке это провал, а не «почти ответ»
    if not ans and think:
        ans = "<NO ANSWER: thinking only, %d tokens, %s>" % (tok, d.get("done_reason"))
    return ans, dt, rate, tok, len(think)

def main():
    models = sys.argv[1:] or ["qwen3.5:9b", "ornith-agent:latest", "distill-agent:latest", "prompt-builder:latest"]
    tasks = json.load(open(os.path.join(ROOT, "tasks", "tasks.json")))
    stamp = time.strftime("%Y%m%d-%H%M")
    log = open(os.path.join(ROOT, "logs", f"run-{stamp}.jsonl"), "w")
    summary = {}
    for m in models:
        got = {"format": [0, 0], "tool": [0, 0], "ambiguity": [0, 0], "data": [0, 0]}
        tps = []; secs = []; toks = []
        print(f"\n=== {m}", flush=True)
        for t in tasks:
            try:
                ans, dt, rate, ntok, nthink = ask(m, t["prompt"])
            except Exception as e:
                ans, dt, rate, ntok, nthink = f"<ERROR {e}>", 0.0, 0.0, 0, 0
            ok, why = check(ans, t["check"])
            got[t["cat"]][1] += 1
            got[t["cat"]][0] += 1 if ok else 0
            if rate: tps.append(rate)
            secs.append(dt); toks.append(ntok)
            log.write(json.dumps({"model": m, "id": t["id"], "cat": t["cat"], "ok": ok,
                                  "why": why, "sec": round(dt, 2), "tps": round(rate, 1),
                                  "tokens": ntok, "think_chars": nthink,
                                  "answer": ans[:2000]}, ensure_ascii=False) + "\n")
            log.flush()
            print(f"  {t['id']:8s} {'ok ' if ok else 'FAIL'} {dt:5.1f}s  {why[:52]}", flush=True)
        tot = sum(v[0] for v in got.values()), sum(v[1] for v in got.values())
        summary[m] = {"by_cat": got, "total": tot,
                      "tps": round(sum(tps) / len(tps), 1) if tps else 0,
                      "sec_avg": round(sum(secs) / len(secs), 1),
                      "tok_avg": round(sum(toks) / len(toks))}
        print(f"  → {tot[0]}/{tot[1]}  {summary[m]['tps']} tok/s  avg {summary[m]['sec_avg']}s", flush=True)
    log.close()
    with open(os.path.join(ROOT, "logs", f"summary-{stamp}.json"), "w") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    print("\n=== SUMMARY")
    print(f"{'model':28s} {'total':>7s} {'format':>7s} {'tool':>6s} {'ambig':>6s} {'data':>5s} {'tok/s':>7s}")
    for m, s in summary.items():
        c = s["by_cat"]
        print(f"{m:28s} {s['total'][0]:3d}/{s['total'][1]:<3d} "
              f"{c['format'][0]:3d}/5  {c['tool'][0]:2d}/5  {c['ambiguity'][0]:2d}/5  {c['data'][0]:2d}/5 {s['tps']:7.1f}")

if __name__ == "__main__":
    main()
