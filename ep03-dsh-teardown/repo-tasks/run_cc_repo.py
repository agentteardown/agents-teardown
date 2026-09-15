#!/usr/bin/env python3
"""Те же задачи в репозитории через обвязку Claude Code (print-режим, инструменты Bash/Read/Edit).
  python3 run_cc_repo.py local:qwen3.5:9b-ctx32k [t1 ...]   # локальная модель через Ollama (Anthropic-совместимый /v1/messages)
  python3 run_cc_repo.py haiku|sonnet [t1 ...]              # облако по подписке
Судья тот же (judge_repo). Лог: logs/cc-repo-<модель>-<время>.jsonl; из ответа Claude Code берём
num_turns, usage (вход/выход/кэш), duration_api_ms, а из лога сессии — число вызовов инструментов."""
import os,sys,json,time,subprocess,tempfile,glob,collections
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
sys.path.insert(0,HERE); from judge_repo import judge as judge_repo
spec=sys.argv[1]; only=sys.argv[2:]
env=dict(os.environ)
if spec.startswith("local:"):
    model=spec[6:]; host=subprocess.run("ip route show default | awk '{print $3}'",shell=True,capture_output=True,text=True).stdout.strip()
    env.update({"ANTHROPIC_BASE_URL":f"http://{host}:11434","ANTHROPIC_AUTH_TOKEN":"ollama"}); tag="local-"+model
else: model=spec; tag=spec
base=tempfile.mkdtemp(prefix="rt-cc-"); subprocess.run([sys.executable,os.path.join(HERE,"make.py"),base],check=True,capture_output=True)
clean=tempfile.mkdtemp(prefix="rt-clean-"); subprocess.run([sys.executable,os.path.join(HERE,"make.py"),clean],check=True,capture_output=True)
J=json.load(open(os.path.join(base,"judge.json")))
stamp=time.strftime("%Y%m%d-%H%M%S"); os.makedirs(os.path.join(ROOT,"logs"),exist_ok=True)
log=open(os.path.join(ROOT,"logs",f"cc-repo-{tag.replace(':','_').replace('/','_')}-{stamp}.jsonl"),"w")
def session_stats(sid):
    for f in glob.glob(os.path.expanduser("~/.claude/projects/*/")+sid+".jsonl"):
        c=collections.Counter(); turns=0; first=None
        for l in open(f):
            try: r=json.loads(l)
            except: continue
            m=r.get('message') or {}
            if r.get('type')=='assistant' and isinstance(m,dict):
                tools=[b.get('name') for b in (m.get('content') or []) if isinstance(b,dict) and b.get('type')=='tool_use']
                if tools or not any(isinstance(b,dict) and b.get('type')=='tool_use' for b in (m.get('content') or [])): turns+=1
                for t in tools: c[t]+=1
                u=m.get('usage') or {}
                if first is None and u: first=u.get('input_tokens',0)+u.get('cache_creation_input_tokens',0)+u.get('cache_read_input_tokens',0)
        return dict(tool_calls=dict(c),first_request_tokens=first)
    return {}
tot=0
for tid,t in J.items():
    if only and tid not in only: continue
    d=os.path.join(base,tid); t0=time.time()
    cmd=["claude","-p","--model",model,"--allowedTools","Bash,Read,Edit","--output-format","json",t["prompt"]]
    try:
        r=subprocess.run(cmd,cwd=d,env=env,capture_output=True,text=True,timeout=1200); dt=time.time()-t0
        try: j=json.loads(r.stdout)
        except Exception: j={"result":r.stdout[:400],"error":r.stderr[-400:]}
    except subprocess.TimeoutExpired:
        dt=time.time()-t0; j={"result":"<TIMEOUT 1200s>"}
    reply=j.get("result","") or ""
    ok,why=judge_repo(tid,d,os.path.join(clean,tid),t["judge"],reply)
    st=session_stats(j.get("session_id","")) if j.get("session_id") else {}
    u=j.get("usage",{})
    rec=dict(model=tag,harness="claude-code",id=tid,ok=ok,why="; ".join(why),sec=round(dt,1),api_ms=j.get("duration_api_ms"),num_turns=j.get("num_turns"),
             in_tokens=u.get("input_tokens"),cache_read=u.get("cache_read_input_tokens"),cache_create=u.get("cache_creation_input_tokens"),out_tokens=u.get("output_tokens"),
             cost_usd=j.get("total_cost_usd"),reply=reply[:400],dir=d,**st)
    tot+=ok; log.write(json.dumps(rec,ensure_ascii=False)+"\n"); log.flush()
    print(f"  {tid}  {'ok ' if ok else 'FAIL'} {dt:6.1f}s turns {j.get('num_turns')} in {u.get('input_tokens')} {('; '.join(why) or reply[:60])!r}",flush=True)
print(f"→ {tot}/{len(only) or len(J)}  {tag}  {log.name}")
