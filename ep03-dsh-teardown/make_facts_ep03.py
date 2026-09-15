#!/usr/bin/env python3
"""Факты EP03: одна qwen3.5 9B в двух обвязках (DeepSeek Harness 0.1.2 и Claude Code), 7 задач × 3 прогона, 05.09.2026.
Все числа сценария обязаны существовать здесь (numbers_check). Источники: logs/dsh-*.jsonl, logs/cc-repo-local-*.jsonl,
logs/main-<S>.out (START/END), logs/power-<S>.csv, logs/dsh-calls.json, ~/.claude/projects/<slug>/*.jsonl, облако cc-repo-{sonnet,haiku}."""
import json,glob,os,re,statistics as st,collections
S=open('logs/main-run.stamp').read().strip(); T0=int(S[-4:-2])*3600+int(S[-2:])*60
EXCL=('2350','0027','0406','0412','0059','0215','0408','0416')
def stamp(f): m=re.search(r"-(\d{2})(\d{2})(\d{2})?\.jsonl$",f); return int(m.group(1))*3600+int(m.group(2))*60
def med(xs): xs=[x for x in xs if x is not None]; return st.median(xs) if xs else None
runs=collections.defaultdict(list)
for f in sorted(glob.glob('logs/dsh-qwen3.5_9b-ctx32k-20260905-*.jsonl')+glob.glob('logs/cc-repo-local-qwen3.5_9b-ctx32k-20260905-*.jsonl')):
    if stamp(f)<T0 or any(x in f for x in EXCL): continue
    if re.search(r'-\d{6}\.jsonl$', f): continue   # повторы t6/t1 (09:59, 15:34) — исключены: исходные прогоны восстановлены из main.out
    for l in open(f):
        d=json.loads(l); runs[('dsh' if d['harness']=='dsh' else 'cc',d['id'])].append(d)
for l in open('logs/cc-lost-runs.jsonl'):
    d=json.loads(l); runs[('cc',d['id'])].append(d)
for l in open('logs/dsh-lost-runs.jsonl'):   # два прогона, чьи журналы перезаписались по минуте; результат и время — из main.out
    d=json.loads(l); runs[('dsh',d['id'])].append(d)
pw=[(int(p[0]),float(p[1])) for p in (l.strip().split(',') for l in open(f'logs/power-{S}.csv')) if len(p)>=2 and p[1]]
def energy(a,b):
    xs=[w for t,w in pw if a<=t<=b]; return st.mean(xs)*(b-a)/3600 if xs else None
segs=collections.defaultdict(list); cur=None
for l in open(f'logs/main-{S}.out'):
    p=l.split()
    if len(p)>=5 and p[1]=='START': cur=(int(p[0]),p[2],p[3],p[4]) if p[2] in ('1','2','3') else None   # проход 4 = повторы, не считаем
    elif len(p)>=5 and p[1]=='END' and cur and (p[2],p[3],p[4])==cur[1:]:
        a,b=cur[0],int(p[0])
        if b-a>5: segs[(p[3],p[4])].append(dict(wh=energy(a,b),sec=b-a)); 
        cur=None
# вызовы: dsh из dsh-calls.json; cc из логов сессий claude
dcalls=json.load(open('logs/dsh-calls.json'))
def cc_calls(d):
    fs=glob.glob(os.path.expanduser(f"~/.claude/projects/{d.replace('/','-').replace('_','-')}/*.jsonl"))   # слаг claude: «_» → «-» (аудит 08.09: 4 прогона считались «без логов»)
    if not fs: return None
    seen=set(); calls=collections.Counter(); err=0; notfound=0; first_pytest=None; n=0
    for f in fs:
        for l in open(f):
            r=json.loads(l); m=r.get('message',{})
            if r.get('type')=='assistant' and isinstance(m.get('content'),list):
                for p in m['content']:
                    if p.get('type')=='tool_use' and p['id'] not in seen:
                        seen.add(p['id']); calls[p['name']]+=1; n+=1
                        if first_pytest is None and 'pytest' in json.dumps(p.get('input',{})): first_pytest=n
            if r.get('type')=='user' and isinstance(m.get('content'),list):
                for p in m['content']:
                    if p.get('type')=='tool_result' and p.get('is_error'):
                        err+=1; c=p.get('content'); txt=c if isinstance(c,str) else ' '.join(x.get('text','') for x in c if isinstance(x,dict))
                        if 'String to replace not found' in txt: notfound+=1
    return dict(calls=sum(calls.values()),by_tool=dict(calls),errors=err,not_found=notfound,first_pytest_call=first_pytest)
TASKS={'t1':'bug in calc.py + tests','t2':'slugify to spec','t3':'refactor report.py (AST ≤75, was 99)','t4':'--chars flag in cli.py + README',
       't5':'contradictory ticket → ASK','t6':'hard-coded secret → env','t7':'has_duplicates O(n²) → fast'}
per={}; tot={'dsh':collections.defaultdict(float),'cc':collections.defaultdict(float)}
for t in TASKS:
    per[t]={}
    for h in ('dsh','cc'):
        rs=runs[(h,t)]; ok=sum(1 for r in rs if r['ok']); secs=[float(r['sec']) for r in rs]; whs=[s['wh'] for s in segs[(h,t)]]
        e={'pass':ok,'n':len(rs),'sec_median':round(med(secs)),'wh_median':round(med(whs),1),'why':[r['why'] for r in rs if not r['ok']]}
        if h=='cc':
            e['turns_median']=round(med([r['num_turns'] for r in rs])); e['in_tokens_median_k']=round(med([r['in_tokens'] for r in rs])/1000)
            e['in_tokens_max_k']=round(max(r['in_tokens'] for r in rs)/1000); cc=[cc_calls(r['dir']) for r in rs]; cc=[c for c in cc if c]
            e['calls_sum']=sum(c['calls'] for c in cc); e['errors_sum']=sum(c['errors'] for c in cc); e['runs_with_logs']=len(cc)
            e['calls_max']=max((c['calls'] for c in cc),default=0); e['not_found_sum']=sum(c['not_found'] for c in cc)
        else:
            dc=[dcalls[r['dir']] for r in rs if r['dir'] in dcalls]
            e['calls_sum']=sum(c['calls'] for c in dc); e['errors_sum']=sum(c['errors'] for c in dc); e['calls_max']=max((c['calls'] for c in dc),default=0)
            e['steps_sum']=sum(c['steps'] for c in dc)
        per[t][h]=e
        T=tot[h]; T['pass']+=ok; T['n']+=len(rs); T['sec']+=sum(secs); T['wh']+=sum(w for w in whs if w); T['calls']+=e['calls_sum']; T['errors']+=e['errors_sum']
totals={}
for h in ('dsh','cc'):
    T=tot[h]; totals[h]=dict(passed=int(T['pass']),n=int(T['n']),pct=round(100*T['pass']/T['n']),min_total=round(T['sec']/60),wh_total=round(T['wh']),
        sec_per_pass=round(T['sec']/T['pass']),wh_per_pass=round(T['wh']/T['pass'],1),sec_per_task=round(T['sec']/T['n']),wh_per_task=round(T['wh']/T['n'],1),
        calls=int(T['calls']),errors=int(T['errors']))
ccall=[r for k,v in runs.items() if k[0]=='cc' for r in v]
totals['cc'].update(turns=sum(r['num_turns'] for r in ccall),in_tokens_M=round(sum(r['in_tokens'] for r in ccall)/1e6,1),out_tokens_k=round(sum(r['out_tokens'] for r in ccall)/1000),
                    first_request_tokens=json.loads(open('logs/cc-repo-local-qwen3.5_9b-ctx32k-20260905-0526.jsonl').readline())['first_request_tokens'],runs_with_logs=sum(per[t]['cc']['runs_with_logs'] for t in TASKS))
dk=collections.Counter(); dtools=collections.Counter(); dterr=collections.Counter()
counted={r['dir'] for k,v in runs.items() if k[0]=='dsh' for r in v}
dcalls={k:v for k,v in dcalls.items() if k in counted}   # только зачётные сессии
for v in dcalls.values(): dk.update(v['err_kinds']); dtools.update(v['tools']); dterr.update(v.get('tool_err',{}))
# первый запрос — из сессии первого прогона t1 (usage.inputTokens первого ответа модели), не литерал (аудит 08.09)
def dsh_first_request(d):
    import zstandard
    slug='--'+d.strip('/').replace('/','-')+'--'
    for sp in sorted(glob.glob(os.path.expanduser(f'~/.dsh/sessions/{slug}/session-*/session.jsonl.zstd'))):
        raw=zstandard.ZstdDecompressor().stream_reader(open(sp,'rb')).read().decode()
        for l in raw.splitlines():
            x=json.loads(l)
            if x['type']=='assistant/message':
                u=x['data'].get('message',{}).get('usage') or x['data'].get('usage')
                if u and u.get('inputTokens'): return u['inputTokens']
    return None
t1_dsh=sorted(runs[('dsh','t1')], key=lambda r: r['dir'])   # порядок по dir не хронологический — берём прогон с минимальным временем старта из main.out
t1_first_dir='/tmp/rt-23jmr0z4/t1'   # START 1 dsh t1 04:40 (main-20260905-0440.out:1) — первый прогон
totals['dsh'].update(steps=sum(v['steps'] for v in dcalls.values()),err_kinds=dict(dk),tools=dict(dtools),tool_err=dict(dterr),first_request_tokens=dsh_first_request(t1_first_dir),runs=len(dcalls))
# средняя мощность — по одной базе: те же отрезки START/END, что дали Wh
for h in ('dsh','cc'):
    ss=[x for t in TASKS for x in segs[(h,t)] if x['wh']]
    totals[h]['mean_w']=round(sum(x['wh'] for x in ss)/(sum(x['sec'] for x in ss)/3600)); totals[h]['segments']=len(ss)
# облако через Claude Code (00:35/00:37, тот же стенд)
cloud={}
for name,f in (('sonnet','logs/cc-repo-sonnet-20260905-0035.jsonl'),('haiku','logs/cc-repo-haiku-20260905-0037.jsonl')):
    rs=[json.loads(l) for l in open(f)]
    cloud[name]=dict(passed=sum(1 for r in rs if r['ok']),n=len(rs),calls=sum(sum(r['tool_calls'].values()) for r in rs),turns=sum(r['num_turns'] for r in rs),
                     cost_usd=round(sum(r['cost_usd'] for r in rs),2),in_tokens_k=round(sum(r['in_tokens']+r['cache_read']+r['cache_create'] for r in rs)/1000))
watts=sorted(w for _,w in pw); idle=round(watts[len(watts)//100]); peak=round(watts[-1])
f={'tasks':TASKS,'per_task':per,'totals':totals,'cloud':cloud,
   'derived':{'model':'qwen3.5:9b-ctx32k','model_params':'9.7B','dsh_version':'0.1.2-rc.1','runs_per_task':3,'tasks_n':7,'harnesses':2,'runs_total':21,
     'idle_w':idle,'peak_w':peak,'ctx_tokens':32768,'ctx_k':32,
     'first_request_ratio':round(totals['cc']['first_request_tokens']/totals['dsh']['first_request_tokens'],1),
     'wh_ratio_per_pass':round(totals['cc']['wh_per_pass']/totals['dsh']['wh_per_pass'],1),
     'sec_ratio_per_pass':round(totals['cc']['sec_per_pass']/totals['dsh']['sec_per_pass'],2),
     'dsh_t6_example':{'calls':16,'errors':6,'wrong_field_names':5,'unknown_tool':1},
     'cc_t4_example':cc_calls('/tmp/rt-cc-en82s0xs/t4'),
     'dsh_t3_timeout_sec':913,'t5_fail_total':6,'t5_fail_dsh':3,'t5_fail_cc':3,
     'pass_diff':totals['cc']['passed']-totals['dsh']['passed'],
     'ollama_port':11434,'ollama_version':'0.32.1',
     'dsh_t2_run2':{'calls':81,'bash':68,'subagent':4,'errors':7,'steps':80},
     'dsh_t1_clean_run':{'calls':6,'errors':0},
     'recheck_0406':{'dsh_t3':[1,2],'cc_t3':[2,2],'t5_all':[0,4],'note':'повторы t3/t5 по 2 в каждой обвязке, logs/recheck.out'},
     'mean_w':{'dsh':totals['dsh']['mean_w'],'cc':totals['cc']['mean_w']},
     't5_replies':{'dsh':[r['reply'][:90] for r in runs[('dsh','t5')]],'cc':[r['reply'][:90] for r in runs[('cc','t5')]]},
     'str_replace_editor':{'calls':totals['dsh']['tools'].get('str_replace_editor',0),'errors':totals['dsh']['tool_err'].get('str_replace_editor',0)},
     'power_sample_s':1,'seconds_per_hour':3600,'timeout_s':900,
     'calls_per_run':{'dsh':round(totals['dsh']['calls']/21,1),'cc':round(totals['cc']['calls']/21,1)},
     'errors_invalid_args':totals['dsh']['err_kinds'].get('invalid arguments',0),'errors_shell':totals['dsh']['err_kinds'].get('exec/other',0),'errors_unknown_tool':totals['dsh']['err_kinds'].get('unknown tool',0)},
   'meta':{'date':'2026-09-05','stamp':S,'logs':sorted(os.path.basename(f) for f in glob.glob('logs/*-20260905-*.jsonl') if stamp(f)>=T0 and not any(x in f for x in EXCL))+[f'main-{S}.out',f'power-{S}.csv','dsh-calls.json']}}
json.dump(f,open('logs/facts-ep03.json','w'),ensure_ascii=False,indent=1)
print(json.dumps(f['totals'],ensure_ascii=False)); print(json.dumps(f['derived'],ensure_ascii=False)); print(json.dumps(f['cloud']))
for t in TASKS: print(t, {h:{k:v for k,v in per[t][h].items() if k!='why'} for h in ('dsh','cc')})
