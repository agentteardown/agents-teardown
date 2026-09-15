#!/usr/bin/env python3
"""Прогон задач в репозитории через DeepSeek Harness (безголовый) с локальной моделью Ollama.
  python3 run_dsh.py <модель Ollama> [t1 t2 ...]  → logs/dsh-<модель>-<время>.jsonl
Судья: pytest (таймаут 120 с) + неизменённые файлы (sha256) + предел строк + начало ответа."""
import os,sys,json,time,hashlib,shutil,subprocess,tempfile
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); from judge_repo import judge as judge_repo
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
model=sys.argv[1]; only=sys.argv[2:]
node=os.path.expanduser("~/.nvm/versions/node"); nb=os.path.join(node,sorted(os.listdir(node))[-1],"bin")
env={**os.environ,"PATH":nb+":"+os.environ["PATH"],"OLLAMA_API_KEY":"ollama"}
host=subprocess.run("ip route show default | awk '{print $3}'",shell=True,capture_output=True,text=True).stdout.strip()
patch=os.path.join(HERE,f"ollama-{model.replace(':','_').replace('/','_')}.yml")
open(patch,"w").write(f"""- id: llm-pi-ai
  name: '@deepseek-ai/dsh-llm-pi-ai'
  config:
    providers:
      ollama:
        displayName: Ollama
        apiKeyEnv: OLLAMA_API_KEY
        api: openai-completions
        baseURL: http://{host}:11434/v1
        models:
          - id: {model}
            contextWindow: 32768
- id: agent-default-model
  config:
    provider: ollama
    model: {model}
""")
base=tempfile.mkdtemp(prefix="rt-"); subprocess.run([sys.executable,os.path.join(HERE,"make.py"),base],check=True,capture_output=True)
clean=tempfile.mkdtemp(prefix="rt-clean-"); subprocess.run([sys.executable,os.path.join(HERE,"make.py"),clean],check=True,capture_output=True)
J=json.load(open(os.path.join(base,"judge.json")))
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
stamp=time.strftime("%Y%m%d-%H%M%S"); os.makedirs(os.path.join(ROOT,"logs"),exist_ok=True)
log=open(os.path.join(ROOT,"logs",f"dsh-{model.replace(':','_').replace('/','_')}-{stamp}.jsonl"),"w")
tot=0
for tid,t in J.items():
    if only and tid not in only: continue
    d=os.path.join(base,tid); before={f:sha(os.path.join(d,f)) for f in t["judge"].get("unchanged",[])}
    t0=time.time()
    try:
        r=subprocess.run(["dsh","--profile","headless","--patch",patch,t["prompt"]],cwd=d,env=env,capture_output=True,text=True,timeout=900)
        reply=r.stdout.strip(); err=r.stderr[-2000:]; rc=r.returncode
    except subprocess.TimeoutExpired:
        reply="<TIMEOUT 900s>"; err=""; rc=-1
    dt=time.time()-t0
    ok,why=judge_repo(tid,d,os.path.join(clean,tid),t["judge"],reply)
    tot+=ok
    rec=dict(model=model,harness="dsh",id=tid,ok=ok,why="; ".join(why),sec=round(dt,1),rc=rc,reply=reply[:400],stderr_tail=err[-600:],dir=d)
    log.write(json.dumps(rec,ensure_ascii=False)+"\n"); log.flush()
    print(f"  {tid}  {'ok ' if ok else 'FAIL'} {dt:6.1f}s  {('; '.join(why) or reply[:60])!r}",flush=True)
print(f"→ {tot}/{len(only) or len(J)}  {model}  {log.name}")
