#!/usr/bin/env python3
"""Прогон задач через OpenCode (безголовый `opencode run`) с локальной моделью Ollama.
  python3 run_opencode.py <модель Ollama> [t1 t2 ...]  → logs/opencode-<модель>-<время>.jsonl
Провайдер задаётся конфигом уровня проекта (opencode.json в песочнице задачи): глобальный конфиг не трогаем.
События `--format json` пишутся целиком в logs/opencode-events/<dir>.jsonl — по ним считаются вызовы и ошибки.
Судья тот же, что у dsh и Claude Code (judge_repo.judge)."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from judge_repo import judge as judge_repo  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
model = sys.argv[1]; only = sys.argv[2:]
TIMEOUT = int(os.environ.get("OC_TIMEOUT", "1200"))
oc = os.path.expanduser("~/.opencode/bin/opencode")
host = subprocess.run("ip route show default | awk '{print $3}'", shell=True, capture_output=True, text=True, check=False).stdout.strip()
env = {**os.environ, "PATH": os.path.dirname(oc) + ":" + os.environ["PATH"]}
env.pop("http_proxy", None); env.pop("https_proxy", None); env.pop("HTTP_PROXY", None); env.pop("HTTPS_PROXY", None)   # локальная Ollama, прокси не нужен

base = tempfile.mkdtemp(prefix="rt-oc-"); subprocess.run([sys.executable, os.path.join(HERE, "make.py"), base], check=True, capture_output=True)
clean = tempfile.mkdtemp(prefix="rt-clean-"); subprocess.run([sys.executable, os.path.join(HERE, "make.py"), clean], check=True, capture_output=True)
J = json.load(open(os.path.join(base, "judge.json")))
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
stamp = time.strftime("%Y%m%d-%H%M%S")
os.makedirs(os.path.join(ROOT, "logs", "opencode-events"), exist_ok=True)
tag = model.replace(":", "_").replace("/", "_")
log = open(os.path.join(ROOT, "logs", f"opencode-{tag}-{stamp}.jsonl"), "w")
cfg = {"$schema": "https://opencode.ai/config.json",
       "provider": {"ollama": {"npm": "@ai-sdk/openai-compatible", "name": "Ollama",
                               "options": {"baseURL": f"http://{host}:11434/v1"},
                               "models": {model: {"name": model}}}},
       "model": f"ollama/{model}", "small_model": f"ollama/{model}",
       "compaction": {"auto": True, "prune": True}}
tot = 0
for tid, t in J.items():
    if only and tid not in only: continue
    d = os.path.join(base, tid)
    json.dump(cfg, open(os.path.join(d, "opencode.json"), "w"))
    if "opencode.json" not in t["judge"].get("unchanged", []): pass   # конфиг — служебный файл, судья его не трогает
    t0 = time.time(); events_path = os.path.join(ROOT, "logs", "opencode-events", d.strip("/").replace("/", "-") + ".jsonl")
    try:
        # --dir и PWD обязательны: без них OpenCode открывает сессию в каталоге из окружения (проба 08.09: 2,6 с, «Unexpected server error»)
        r = subprocess.run([oc, "run", "--dir", d, "--model", f"ollama/{model}", "--format", "json", "--pure", t["prompt"]],
                           cwd=d, env={**env, "PWD": d}, capture_output=True, text=True, timeout=TIMEOUT, check=False)
        open(events_path, "w").write(r.stdout); err = r.stderr[-2000:]; rc = r.returncode
        # итоговый текст ответа — последние текстовые события
        reply = ""; calls = 0; errors = 0
        for line in r.stdout.splitlines():
            try: ev = json.loads(line)
            except json.JSONDecodeError: continue
            et = ev.get("type", ""); p = ev.get("part") or ev.get("properties", {}).get("part") or {}
            pt = p.get("type") if isinstance(p, dict) else None
            if pt == "text" and p.get("text"): reply = p["text"]
            if pt == "tool":
                calls += 1
                # ошибка вызова: статус error либо инструмент «invalid» (OpenCode так помечает вызов несуществующего инструмента / битые аргументы)
                if (p.get("state") or {}).get("status") == "error" or p.get("tool") == "invalid": errors += 1
            if et == "text" and ev.get("text"): reply = ev["text"]
        reply = reply.strip()
    except subprocess.TimeoutExpired:
        reply = f"<TIMEOUT {TIMEOUT}s>"; err = ""; rc = -1; calls = errors = None
    dt = time.time() - t0
    ok, why = judge_repo(tid, d, os.path.join(clean, tid), t["judge"], reply)
    tot += ok
    rec = dict(model=model, harness="opencode", id=tid, ok=ok, why="; ".join(why), sec=round(dt, 1), rc=rc, reply=reply[:400],
               stderr_tail=err[-600:], dir=d, events=events_path, calls=calls, errors=errors)
    log.write(json.dumps(rec, ensure_ascii=False) + "\n"); log.flush()
    print(f"  {tid}  {'ok ' if ok else 'FAIL'} {dt:6.1f}s calls {calls} err {errors}  {('; '.join(why) or reply[:60])!r}", flush=True)
print(f"→ {tot}/{len(only) or len(J)}  opencode {model}  {log.name}")
