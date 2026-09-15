#!/usr/bin/env python3
"""Прогон задач через Hermes Agent в песочнице agent-lab (Hyper-V), модель — та же Ollama на хосте.
  python3 run_hermes.py <модель Ollama> [t1 t2 ...]  → logs/hermes-<модель>-<время>.jsonl
Песочница задачи упаковывается в tar+base64, уезжает в ВМ по vmssh.sh, hermes -z работает там,
каталог возвращается tar+base64 и судится локально тем же judge_repo. Оговорка для ролика:
`-z` (одиночный режим) подменяет инструмент clarify и снимает подтверждения (см. память
oneshot-mode-swaps-tools) — это свойство обвязки, оно и измеряется."""
import base64
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from judge_repo import judge as judge_repo

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
VMSSH = os.path.expanduser("~/agent-lab/vmssh.sh")
model = sys.argv[1]; only = sys.argv[2:]
TIMEOUT = int(os.environ.get("HERMES_TIMEOUT", "1200"))

def vm(cmd, timeout=TIMEOUT + 60):
    return subprocess.run(["bash", VMSSH, cmd], capture_output=True, text=True, timeout=timeout, check=False)

def push_dir(local, remote):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf: tf.add(local, arcname=".")
    b64 = base64.b64encode(buf.getvalue()).decode()
    r = vm(f"rm -rf {remote} && mkdir -p {remote} && echo {b64} | base64 -d | tar xzf - -C {remote}", timeout=120)
    if r.returncode != 0: raise RuntimeError("push: " + r.stderr[-300:])

def pull_dir(remote, local):
    r = vm(f"tar czf - -C {remote} . | base64 -w0", timeout=120)
    if r.returncode != 0: raise RuntimeError("pull: " + r.stderr[-300:])
    data = base64.b64decode(r.stdout.strip().split()[-1])
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf: tf.extractall(local)

base = tempfile.mkdtemp(prefix="rt-hm-"); subprocess.run([sys.executable, os.path.join(HERE, "make.py"), base], check=True, capture_output=True)
clean = tempfile.mkdtemp(prefix="rt-clean-"); subprocess.run([sys.executable, os.path.join(HERE, "make.py"), clean], check=True, capture_output=True)
J = json.load(open(os.path.join(base, "judge.json")))
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
stamp = time.strftime("%Y%m%d-%H%M%S"); os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
tag = model.replace(":", "_").replace("/", "_")
log = open(os.path.join(ROOT, "logs", f"hermes-{tag}-{stamp}.jsonl"), "w")
run_id = os.path.basename(base)
tot = 0
for tid, t in J.items():
    if only and tid not in only: continue
    d = os.path.join(base, tid); remote = f"~/rt/{run_id}/{tid}"
    push_dir(d, remote)
    p64 = base64.b64encode(t["prompt"].encode()).decode()
    t0 = time.time()
    # TERMINAL_CWD обязателен: ни cd, ни --in не задают каталог терминала в режиме -z — модель видит «cwd: <home>» (проба 08.09)
    abs_remote = remote.replace("~", "$HOME", 1)
    cmd = (f"cd {remote} && P=$(echo {p64} | base64 -d) && export PATH=$HOME/.local/bin:$PATH && export TERMINAL_CWD={abs_remote} && "
           f"timeout {TIMEOUT} hermes -z \"$P\" -m {model} --in {remote} --usage-file {remote}.usage.json --yolo 2> {remote}.stderr; "
           f"echo \"__RC=$?\"")
    try:
        r = vm(cmd); out = r.stdout
        rc = int(out.rsplit("__RC=", 1)[1].strip().split()[0]) if "__RC=" in out else r.returncode
        reply = out.rsplit("__RC=", 1)[0].strip()
        if rc == 124: reply = f"<TIMEOUT {TIMEOUT}s>"
    except subprocess.TimeoutExpired:
        reply = f"<TIMEOUT {TIMEOUT}s (ssh)>"; rc = -1
    dt = time.time() - t0
    back = os.path.join(base, tid + ".back"); os.makedirs(back, exist_ok=True)
    try: pull_dir(remote, back)
    except Exception as e: print("  pull failed:", e)
    usage = vm(f"cat {remote}.usage.json 2>/dev/null; echo; tail -c 600 {remote}.stderr 2>/dev/null", timeout=60).stdout
    ok, why = judge_repo(tid, back, os.path.join(clean, tid), t["judge"], reply)
    tot += ok
    rec = dict(model=model, harness="hermes", id=tid, ok=ok, why="; ".join(why), sec=round(dt, 1), rc=rc, reply=reply[:400],
               usage_and_stderr=usage[-1200:], dir=back, remote=remote)
    log.write(json.dumps(rec, ensure_ascii=False) + "\n"); log.flush()
    print(f"  {tid}  {'ok ' if ok else 'FAIL'} {dt:6.1f}s  {('; '.join(why) or reply[:60])!r}", flush=True)
print(f"→ {tot}/{len(only) or len(J)}  hermes {model}  {log.name}")
