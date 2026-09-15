#!/usr/bin/env python3
"""Факты EP04: Claude Code с облачной claude-fable-5-1 на 7 репозиторных задачах со скрытыми тестами,
3 серии × 7 = 21 прогон (09.09.2026, 09:05–09:11), против EP03 (9B в dsh и Claude Code, haiku/sonnet)
и проб четырёх обвязок на t1 (08.09.2026). Правило канала: каждая цифра в кадре — только из сохранённого лога.
Каждый ключ в «derived» несёт поле src (файл и способ подсчёта). Логи и прогонщики не трогаются:
скрипт только читает и пишет logs/facts-ep04.json.
  python3 make_facts_ep04.py             # собрать факты
  python3 make_facts_ep04.py --selftest  # пересчёт контрольных чисел независимым способом + контрольный дефект
"""
import json,glob,os,re,sys,statistics as st,collections,subprocess,tempfile,shutil,datetime as dt
ROOT=os.path.dirname(os.path.abspath(__file__)); L=os.path.join(ROOT,'logs')
def P(*a): return os.path.join(L,*a)
def rel(p): return os.path.relpath(p,ROOT)
def rows(p): return [json.loads(l) for l in open(p) if l.strip()]
def med(xs): return st.median(xs)
def stamp_dt(f):
    m=re.search(r'-(\d{8})-(\d{6})\.jsonl$',f); return dt.datetime.strptime(m.group(1)+m.group(2),'%Y%m%d%H%M%S')
def mtime_dt(f): return dt.datetime.fromtimestamp(os.path.getmtime(f))
def D(v,src): return {'v':v,'src':src}

FABLE_FILES=[P(f'cc-repo-claude-fable-5-1-20260909-{s}.jsonl') for s in ('090524','090724','090911')]
PROBE_FILE=P('cc-repo-claude-fable-5-1-20260908-212958.jsonl')
# четвёртая серия под сборщиком мощности (09:55–09:57) — отдельный блок power_series, в 21 прогон НЕ входит
PS_FILE=P('cc-repo-claude-fable-5-1-20260909-095516.jsonl'); PS_CSV=P('power-fable-20260909-095511.csv'); PS_OUT=P('fable-power-20260909-095511.out')
TASKS={'t1':'bug in calc.py + tests','t2':'slugify to spec','t3':'refactor report.py (AST ≤75, was 99)','t4':'--chars flag in cli.py + README',
       't5':'contradictory ticket → ASK','t6':'hard-coded secret → env','t7':'has_duplicates O(n²) → fast'}
TIDS=list(TASKS)

def fable_runs(files=FABLE_FILES):
    """Все записи трёх серий: список (номер серии, запись)."""
    out=[]
    for i,f in enumerate(files,1):
        rs=rows(f); assert len(rs)==7 and [r['id'] for r in rs]==TIDS, f
        for r in rs: out.append((i,r))
    return out

def session_recount(d):
    """Независимый пересчёт по логу сессии Claude Code (~/.claude/projects/<слаг>/*.jsonl):
    вызовы инструментов по именам, tool_result с is_error, версия Claude Code, id модели."""
    fs=glob.glob(os.path.expanduser('~/.claude/projects/'+d.replace('/','-')+'/*.jsonl'))
    if not fs: return None
    seen=set(); calls=collections.Counter(); err=[]; ver=set(); models=set(); first=None
    for f in fs:
        for l in open(f):
            try: r=json.loads(l)
            except Exception: continue
            if r.get('version'): ver.add(r['version'])
            m=r.get('message') or {}
            if r.get('type')=='assistant' and isinstance(m,dict):
                if m.get('model'): models.add(m['model'])
                u=m.get('usage') or {}
                if first is None and u: first=u.get('input_tokens',0)+u.get('cache_creation_input_tokens',0)+u.get('cache_read_input_tokens',0)
                for b in (m.get('content') or []):
                    if isinstance(b,dict) and b.get('type')=='tool_use' and b['id'] not in seen: seen.add(b['id']); calls[b['name']]+=1
            if r.get('type')=='user' and isinstance(m,dict) and isinstance(m.get('content'),list):
                for b in m['content']:
                    if isinstance(b,dict) and b.get('type')=='tool_result' and b.get('is_error'):
                        c=b.get('content'); txt=c if isinstance(c,str) else ' '.join(x.get('text','') for x in c if isinstance(x,dict))
                        err.append(txt.split('\n',1)[0][:40])
    return dict(files=len(fs),calls=dict(calls),errors=len(err),error_heads=err,first_request_tokens=first,version=sorted(ver),model=sorted(models))

def read_power(csv):
    out=[]
    for l in open(csv):
        p=l.strip().split(',')
        if len(p)>=4 and p[1]: out.append((int(p[0]),float(p[1]),int(p[2]),int(p[3])))
    return out

def power_series(ep03):
    """Четвёртая серия под сборщиком мощности: Вт·ч за окно START..END по методу EP03 (средняя W × длительность),
    контрольный интеграл ступеньками по реальным интервалам, Вт·ч на задачу по времени. В 21 прогон не входит."""
    rs=rows(PS_FILE); assert len(rs)==7 and [r['id'] for r in rs]==TIDS
    txt=open(PS_OUT).read(); a=int(re.search(r'^START (\d+)',txt,re.M).group(1)); b=int(re.search(r'^END (\d+)',txt,re.M).group(1))
    pw=read_power(PS_CSV); win=[x for x in pw if a<=x[0]<=b]; ws=[w for _,w,_,_ in win]
    w_mean=sum(ws)/len(ws); wh=w_mean*(b-a)/3600
    hold=sum(win[i][1]*(win[i+1][0]-win[i][0]) for i in range(len(win)-1))/3600   # ступеньки: W_i держится до следующего отсчёта
    passed=sum(1 for r in rs if r['ok']); calls=collections.Counter()
    for r in rs: calls.update(r['tool_calls'])
    e3=ep03['totals']
    return dict(file=rel(PS_FILE),csv=rel(PS_CSV),out=rel(PS_OUT),unit='ep04-fable-power (journalctl --user: 09:55:11–09:57:40)',in_21=False,
        passed=passed,n=len(rs),start=dt.datetime.fromtimestamp(a).strftime('%H:%M:%S'),end=dt.datetime.fromtimestamp(b).strftime('%H:%M:%S'),window_s=b-a,
        csv_first=dt.datetime.fromtimestamp(pw[0][0]).strftime('%H:%M:%S'),csv_last=dt.datetime.fromtimestamp(pw[-1][0]).strftime('%H:%M:%S'),samples_total=len(pw),samples_in_window=len(win),
        sample_gaps_2s=sum(1 for i in range(len(win)-1) if win[i+1][0]-win[i][0]==2),
        w_mean=round(w_mean,1),w_min=min(ws),w_median=round(med(ws),2),w_max=max(ws),
        mib_min=min(m for _,_,m,_ in win),mib_max=max(m for _,_,m,_ in win),util_max=max(u for _,_,_,u in win),
        wh_window=round(wh,3),wh_window_hold=round(hold,3),wh_per_pass=round(wh/passed,3),
        wh_by_task={r['id']:round(r['sec']*w_mean/3600,3) for r in rs},wh_by_task_sum=round(sum(r['sec']*w_mean/3600 for r in rs),3),
        sec={r['id']:r['sec'] for r in rs},sec_sum=round(sum(r['sec'] for r in rs),1),turns={r['id']:r['num_turns'] for r in rs},turns_sum=sum(r['num_turns'] for r in rs),
        calls_by_tool=dict(calls),calls_sum=sum(calls.values()),cost_sum=round(sum(r['cost_usd'] for r in rs),4),
        first_request_min=min(r['first_request_tokens'] for r in rs),first_request_max=max(r['first_request_tokens'] for r in rs),
        t5_reply=[r['reply'] for r in rs if r['id']=='t5'][0],dirs_base=rs[0]['dir'].rsplit('/',1)[0],
        ep03_wh_per_pass={'dsh':e3['dsh']['wh_per_pass'],'cc':e3['cc']['wh_per_pass']},ep03_mean_w={'dsh':e3['dsh']['mean_w'],'cc':e3['cc']['mean_w']},ep03_idle_w=ep03['derived']['idle_w'],ep03_peak_w=ep03['derived']['peak_w'],
        caveat='W — nvidia-smi power.draw видеокарты стенда (не хоста целиком), карта простаивает: модель работает в датацентре, его энергия неизвестна и не утверждается. Метод и колонки те же, что у EP03 (power_sample_s=1).')

def build():
    runs=fable_runs(); probe=rows(PROBE_FILE)[0]
    ep03=json.load(open(P('facts-ep03.json')))
    # ---------- по задачам ----------
    per={}
    for t in TIDS:
        rs=[r for _,r in runs if r['id']==t]
        calls=collections.Counter()
        for r in rs: calls.update(r['tool_calls'])
        e=dict(pass_=sum(1 for r in rs if r['ok']),n=len(rs),why=[r['why'] for r in rs if not r['ok']],
               sec=[r['sec'] for r in rs],sec_median=round(med([r['sec'] for r in rs]),1),sec_mean=round(sum(r['sec'] for r in rs)/len(rs),1),
               api_ms=[r['api_ms'] for r in rs],turns=[r['num_turns'] for r in rs],turns_sum=sum(r['num_turns'] for r in rs),
               calls_by_tool=dict(calls),calls_sum=sum(calls.values()),
               in_tokens=[r['in_tokens'] for r in rs],cache_read=[r['cache_read'] for r in rs],cache_create=[r['cache_create'] for r in rs],out_tokens=[r['out_tokens'] for r in rs],
               in_tokens_sum=sum(r['in_tokens'] for r in rs),cache_read_sum=sum(r['cache_read'] for r in rs),cache_create_sum=sum(r['cache_create'] for r in rs),out_tokens_sum=sum(r['out_tokens'] for r in rs),
               cost_usd=[r['cost_usd'] for r in rs],cost_sum=round(sum(r['cost_usd'] for r in rs),4),
               first_request_tokens=sorted({r['first_request_tokens'] for r in rs}),dirs=[r['dir'] for r in rs])
        e['pass']=e.pop('pass_')
        if t=='t5': e['replies']=[r['reply'] for r in rs]; e['reply_chars']=[len(r['reply']) for r in rs]; e['ask_and_both_versions']=[r['reply'].lower().startswith('ask') and '3.12' in r['reply'] and '3.11' in r['reply'] for r in rs]
        per[t]=e
    # ---------- итоги ----------
    R=[r for _,r in runs]; secs=[r['sec'] for r in R]; costs=[r['cost_usd'] for r in R]
    calls=collections.Counter()
    for r in R: calls.update(r['tool_calls'])
    passed=sum(1 for r in R if r['ok'])
    firsts=[r['first_request_tokens'] for r in R]
    tot=dict(passed=passed,n=len(R),pct=round(100*passed/len(R)),
             sec_sum=round(sum(secs),1),sec_min=min(secs),sec_median=round(med(secs),1),sec_max=max(secs),sec_mean=round(sum(secs)/len(secs),1),
             sec_per_pass=round(sum(secs)/passed,1),sec_per_task=round(sum(secs)/len(R),1),
             api_ms_sum=sum(r['api_ms'] for r in R),api_s_sum=round(sum(r['api_ms'] for r in R)/1000,1),
             turns_sum=sum(r['num_turns'] for r in R),turns_min=min(r['num_turns'] for r in R),turns_max=max(r['num_turns'] for r in R),
             calls_sum=sum(calls.values()),calls_by_tool=dict(calls),calls_per_run=round(sum(calls.values())/len(R),1),runs_without_calls=sum(1 for r in R if not r['tool_calls']),
             in_tokens_sum=sum(r['in_tokens'] for r in R),cache_read_sum=sum(r['cache_read'] for r in R),cache_create_sum=sum(r['cache_create'] for r in R),
             input_total=sum(r['in_tokens']+r['cache_read']+r['cache_create'] for r in R),out_tokens_sum=sum(r['out_tokens'] for r in R),
             input_total_k=round(sum(r['in_tokens']+r['cache_read']+r['cache_create'] for r in R)/1000),out_tokens_k=round(sum(r['out_tokens'] for r in R)/1000,1),
             first_request_min=min(firsts),first_request_max=max(firsts),first_request_t1=per['t1']['first_request_tokens'][0],
             cost_sum=round(sum(costs),4),cost_min=round(min(costs),4),cost_max=round(max(costs),4),cost_per_task=round(sum(costs)/len(R),4),cost_per_pass=round(sum(costs)/passed,4),
             cost_sum_2=round(sum(costs),2),cost_per_task_2=round(sum(costs)/len(R),2))
    # время серий: метка в имени файла = открытие журнала серии (после make.py), mtime = последняя запись (t7)
    series=[]
    for i,f in enumerate(FABLE_FILES,1):
        a,b=stamp_dt(f),mtime_dt(f); rs=rows(f)
        series.append(dict(file=rel(f),start=a.strftime('%H:%M:%S'),end=b.strftime('%H:%M:%S'),wall_s=round((b-a).total_seconds(),1),sec_sum=round(sum(r['sec'] for r in rs),1),passed=sum(1 for r in rs if r['ok']),cost_sum=round(sum(r['cost_usd'] for r in rs),4),tmp_base=rs[0]['dir'].rsplit('/',1)[0]))
    batch_wall=(mtime_dt(FABLE_FILES[-1])-stamp_dt(FABLE_FILES[0])).total_seconds()
    tot['series']=series; tot['batch_start']=series[0]['start']; tot['batch_end']=series[-1]['end']; tot['batch_wall_s']=round(batch_wall); tot['batch_wall_min']=round(batch_wall/60,1)
    tot['batch_overhead_s']=round(batch_wall-sum(secs))
    # ---------- независимая сверка по сессиям Claude Code ----------
    xc={}; mism=[]; errs=0; err_heads=[]; vers=set(); models=set()
    for i,r in runs:
        s=session_recount(r['dir'])
        if not s: mism.append((i,r['id'],'нет лога сессии')); continue
        if s['calls']!=r['tool_calls'] or s['first_request_tokens']!=r['first_request_tokens']: mism.append((i,r['id'],s['calls'],r['tool_calls'],s['first_request_tokens'],r['first_request_tokens']))
        errs+=s['errors']; err_heads+=[f"s{i} {r['id']}: {h}" for h in s['error_heads']]; vers|=set(s['version']); models|=set(s['model'])
    xc=dict(runs_with_session_log=len(runs)-sum(1 for m in mism if m[2]=='нет лога сессии'),mismatches=mism,tool_result_is_error=errs,is_error_heads=err_heads,
            is_error_note='все is_error — ненулевой код выхода собственных диагностических команд модели (pytest до починки: exit 1 = тесты падают, exit 5 = тесты не собраны в цикле for), не сбои обвязки',
            claude_code_version=sorted(vers),model_id=sorted(models),probe_version=(session_recount(probe['dir']) or {}).get('version'))
    # ---------- проба накануне ----------
    pr=dict(file=rel(PROBE_FILE),id=probe['id'],ok=probe['ok'],sec=probe['sec'],num_turns=probe['num_turns'],tool_calls=probe['tool_calls'],cost_usd=probe['cost_usd'],first_request_tokens=probe['first_request_tokens'],reply=probe['reply'],dir=probe['dir'],note='проба 08.09 21:29, в 21 прогон не входит')
    # ---------- EP03 (только чтение facts-ep03.json) ----------
    e3=ep03['totals']; c3=ep03['cloud']; p3=ep03['per_task']
    E3='logs/facts-ep03.json'
    ep03_cmp={
      'dsh_passed':D([e3['dsh']['passed'],e3['dsh']['n']],f'{E3}: totals.dsh.passed/n'),
      'cc_passed':D([e3['cc']['passed'],e3['cc']['n']],f'{E3}: totals.cc.passed/n'),
      'sec_per_pass':D({'dsh':e3['dsh']['sec_per_pass'],'cc':e3['cc']['sec_per_pass'],'fable':tot['sec_per_pass']},f'{E3}: totals.*.sec_per_pass; fable = sec_sum/passed по трём cc-repo-claude-fable-5-1-20260909-*.jsonl'),
      'sec_per_task':D({'dsh':e3['dsh']['sec_per_task'],'cc':e3['cc']['sec_per_task'],'fable':tot['sec_per_task']},f'{E3}: totals.*.sec_per_task; fable = sec_sum/21'),
      'wh_per_pass':D({'dsh':e3['dsh']['wh_per_pass'],'cc':e3['cc']['wh_per_pass'],'fable':None},f'{E3}: totals.*.wh_per_pass; для Fable замера мощности нет (см. power)'),
      'first_request_tokens':D({'dsh':e3['dsh']['first_request_tokens'],'cc_9b':e3['cc']['first_request_tokens'],'cc_fable_t1':tot['first_request_t1'],'cc_fable_min':tot['first_request_min'],'cc_fable_max':tot['first_request_max']},f'{E3}: totals.dsh/cc.first_request_tokens; fable: поле first_request_tokens записей, min/max по 21'),
      't5_pass':D({'dsh':[p3['t5']['dsh']['pass'],p3['t5']['dsh']['n']],'cc_9b':[p3['t5']['cc']['pass'],p3['t5']['cc']['n']],'fable':[per['t5']['pass'],per['t5']['n']]},f'{E3}: per_task.t5.*.pass; fable: записи id=t5, ok'),
      't5_fail_total_ep03':D(ep03['derived']['t5_fail_total'],f'{E3}: derived.t5_fail_total'),
      'cloud_ep03':D({k:dict(passed=c3[k]['passed'],n=c3[k]['n'],cost_usd=c3[k]['cost_usd'],calls=c3[k]['calls'],turns=c3[k]['turns'],in_tokens_k=c3[k]['in_tokens_k']) for k in ('haiku','sonnet')},f'{E3}: cloud.haiku/sonnet (по одной серии из 7, 05.09 00:35/00:37)'),
      'cost_per_series':D({'haiku_ep03':c3['haiku']['cost_usd'],'sonnet_ep03':c3['sonnet']['cost_usd'],'fable_mean_of_3':round(tot['cost_sum']/3,2),'fable_series':[s['cost_sum'] for s in series]},f'{E3}: cloud.*.cost_usd (одна серия); fable: сумма cost_usd по серии, средняя по трём'),
      'calls_ep03':D({'dsh':e3['dsh']['calls'],'cc_9b':e3['cc']['calls'],'fable':tot['calls_sum']},f'{E3}: totals.*.calls; fable: сумма tool_calls по 21'),
      'turns_ep03':D({'cc_9b':e3['cc']['turns'],'fable':tot['turns_sum']},f'{E3}: totals.cc.turns; fable: сумма num_turns'),
      'errors_ep03':D({'dsh':e3['dsh']['errors'],'cc_9b':e3['cc']['errors'],'fable_is_error':xc['tool_result_is_error']},f'{E3}: totals.*.errors; fable: tool_result.is_error по сессиям ~/.claude/projects (см. cross_check.is_error_note)'),
      'in_tokens_ep03':D({'cc_9b_M':e3['cc']['in_tokens_M'],'fable_input_total_k':tot['input_total_k']},f'{E3}: totals.cc.in_tokens_M (только input_tokens, без кэша); fable: in+cache_read+cache_create'),
      'sec_ratio_fable_vs':D({'dsh':round(e3['dsh']['sec_per_pass']/tot['sec_per_pass'],1),'cc_9b':round(e3['cc']['sec_per_pass']/tot['sec_per_pass'],1)},'ep03 sec_per_pass / fable sec_per_pass'),
      'first_request_ratio_cc_9b_over_fable':D(round(e3['cc']['first_request_tokens']/tot['first_request_t1'],2),f'{E3} totals.cc.first_request_tokens / fable t1 first_request_tokens'),
      'pass_diff_fable_minus':D({'dsh':passed-e3['dsh']['passed'],'cc_9b':passed-e3['cc']['passed']},'fable passed − ep03 passed'),
      'ep03_model':D(ep03['derived']['model'],f'{E3}: derived.model'),'ep03_date':D(ep03['meta']['date'],f'{E3}: meta.date'),
    }
    # ---------- доска «та же 9B в четырёх обвязках», t1 ----------
    # dsh: зачётные прогоны EP03 (правило make_facts_ep03.py: метка ≥ 04:40, без EXCL, без 6-значных повторов, плюс dsh-lost-runs.jsonl)
    dsh_t1=[]
    for f in sorted(glob.glob(P('dsh-qwen3.5_9b-ctx32k-20260905-*.jsonl'))):
        m=re.search(r'-(\d{4})(\d{2})?\.jsonl$',f)
        if m.group(2): continue   # 6-значные метки (095945, 153448) — повторы, в EP03 не зачтены
        if m.group(1)<'0440' or m.group(1) in ('0406','0412'): continue
        for r in rows(f):
            if r['id']=='t1' and r['harness']=='dsh': dsh_t1.append(dict(sec=r['sec'],ok=r['ok'],file=rel(f),dir=r['dir']))
    for r in rows(P('dsh-lost-runs.jsonl')):
        if r['id']=='t1': dsh_t1.append(dict(sec=r['sec'],ok=r['ok'],file='logs/dsh-lost-runs.jsonl',dir=r['dir'],reconstructed_from=r['reconstructed_from']))
    dsh_t1_repeat=[dict(sec=r['sec'],ok=r['ok'],file=rel(f)) for f in glob.glob(P('dsh-qwen3.5_9b-ctx32k-20260905-153448.jsonl')) for r in rows(f) if r['id']=='t1']
    assert len(dsh_t1)==3 and round(med([x['sec'] for x in dsh_t1]))==p3['t1']['dsh']['sec_median'], dsh_t1
    # OpenCode: события — источник вызовов; поле errors:0 записи — устаревший счётчик
    oc=rows(P('opencode-qwen3.5_9b-ctx32k-20260908-202345.jsonl'))[0]; ev=rows(oc['events'])
    tools=[e['part']['tool'] for e in ev if e['type']=='tool_use']; steps=[e['part']['tokens'] for e in ev if e['type']=='step_finish']
    inv=[e['part']['state']['input'] for e in ev if e['type']=='tool_use' and e['part']['tool']=='invalid']
    ts=[e['timestamp'] for e in ev]
    opencode=dict(file=rel(P('opencode-qwen3.5_9b-ctx32k-20260908-202345.jsonl')),events=rel(oc['events']),model=oc['model'],ok=oc['ok'],sec=oc['sec'],calls_by_events=len(tools),tools=tools,invalid=len(inv),
                  invalid_detail=inv[0] if inv else None,record_calls_field=oc['calls'],record_errors_field_stale=oc['errors'],steps=len(steps),
                  first_step_input_tokens=steps[0]['input'],input_tokens_sum=sum(s['input'] for s in steps),output_tokens_sum=sum(s['output'] for s in steps),total_tokens_sum=sum(s['total'] for s in steps),
                  events_span_s=round((max(ts)-min(ts))/1000,1),ctx32k_earlier_probes_failed=[rel(f) for f in (P('opencode-qwen3.5_9b-20260908-201956.jsonl'),P('opencode-qwen3.5_9b-ctx32k-20260908-202009.jsonl'))])
    # Hermes
    h_ok=rows(P('hermes-qwen3.5_9b-ctx64k-20260908-205139.jsonl'))[0]; h_ref=rows(P('hermes-qwen3.5_9b-ctx32k-20260908-202434.jsonl'))[0]; h_to=rows(P('hermes-qwen3.5_9b-ctx64k-20260908-202610.jsonl'))[0]
    hu=json.loads(h_ok['usage_and_stderr'].strip()); href=json.loads(h_ref['usage_and_stderr'].split('\n\nhermes -z')[0])
    tim=open(P('hm-timing-204231.out')).read(); tu=json.loads(tim.split('== usage')[1]); tt=re.findall(r'^(\d\d:\d\d:\d\d)$',tim,re.M)
    t_a,t_b=[dt.datetime.strptime(x,'%H:%M:%S') for x in tt[:2]]
    hermes=dict(ok_file=rel(P('hermes-qwen3.5_9b-ctx64k-20260908-205139.jsonl')),model=h_ok['model'],ok=h_ok['ok'],sec=h_ok['sec'],api_calls=hu['api_calls'],input_tokens=hu['input_tokens'],output_tokens=hu['output_tokens'],total_tokens=hu['total_tokens'],cache_read_tokens=hu['cache_read_tokens'],
                remote=h_ok['remote'],remote_note='поле remote в записи: задача выполнялась по ssh в песочнице (~/rt/…), время sec — на стороне прогонщика',
                refusal_32k_file=rel(P('hermes-qwen3.5_9b-ctx32k-20260908-202434.jsonl')),refusal_32k_text=href['failure'],refusal_32k_sec=h_ref['sec'],
                timeout_file=rel(P('hermes-qwen3.5_9b-ctx64k-20260908-202610.jsonl')),timeout_sec=h_to['sec'],timeout_rc=h_to['rc'],timeout_reply=h_to['reply'],
                timeout_note='причина в самой записи не названа (usage_and_stderr пуст); по соседним hm-pwdtest-204415.out / hm-pwdtest2-204953.out проверялся TERMINAL_CWD — связь с таймаутом только по контексту, не по логу',
                empty_call_file='logs/hm-timing-204231.out',empty_call_input_tokens=tu['input_tokens'],empty_call_output_tokens=tu['output_tokens'],empty_call_api_calls=tu['api_calls'],empty_call_wall_s=round((t_b-t_a).total_seconds()))
    # Claude Code на t1: 9B (EP03) и Fable
    cc_t1=dict(first_request_9b=e3['cc']['first_request_tokens'],sec_median_9b=p3['t1']['cc']['sec_median'],calls_sum_9b=p3['t1']['cc']['calls_sum'],
               first_request_fable=tot['first_request_t1'],sec_fable=per['t1']['sec'],calls_fable=per['t1']['calls_by_tool'],turns_fable=per['t1']['turns'])
    board=dict(dsh=dict(runs=dsh_t1,secs=[x['sec'] for x in dsh_t1],sec_median=round(med([x['sec'] for x in dsh_t1])),calls_sum=p3['t1']['dsh']['calls_sum'],errors_sum=p3['t1']['dsh']['errors_sum'],first_request_tokens=e3['dsh']['first_request_tokens'],
                        repeat_1534_not_counted=dsh_t1_repeat,note='зачётные по правилу EP03: 78.0 (04:40, серия 1), 25.6 (06:09, серия 2, журнал перезаписан, восстановлен из main.out:209), 90.2 (06:58, серия 3); повтор 15:34 (29.6 с) в EP03 не зачтён'),
               opencode=opencode,hermes=hermes,claude_code=cc_t1)
    # ---------- 27B GSQ-RCO ----------
    pb=open(P('probe27b-211810.out')).read()
    g=lambda rx: re.search(rx,pb)
    d27=rows(P('dsh-qwen3.8-27b-gsq-ctx32k-20260908-211955.jsonl'))[0]
    b27=dict(probe_file='logs/probe27b-211810.out',ollama_version=g(r'ollama version is (\S+)').group(1),parameter_size=g(r"'parameter_size': '([^']+)'").group(1),quant=g(r"'quantization_level': '([^']+)'").group(1),
             gguf_context_length=int(g(r"'qwen35.context_length': (\d+)").group(1)),ps_ctx=int(g(r"\[\('qwen3\.8-27b-gsq-ctx32k:latest', ([\d.]+), ([\d.]+), (\d+)\)\]").group(3)),
             ps_size_gb=float(g(r"\[\('qwen3\.8-27b-gsq-ctx32k:latest', ([\d.]+),").group(1)),vram_used_mib=int(g(r'(\d+) MiB, (\d+) MiB').group(1)),vram_total_mib=int(g(r'(\d+) MiB, (\d+) MiB').group(2)),
             load_s=float(g(r'load_s ([\d.]+)').group(1)),eval_tok=int(g(r'eval_tok (\d+)').group(1)),tok_s=float(g(r'tok/s ([\d.]+)').group(1)),tool_call_ok=('"name": "get_weather"' in pb),
             create_wall_s=round((dt.datetime.strptime(re.findall(r'^(\d\d:\d\d:\d\d)$',pb,re.M)[1],'%H:%M:%S')-dt.datetime.strptime(re.findall(r'^(\d\d:\d\d:\d\d)$',pb,re.M)[0],'%H:%M:%S')).total_seconds()),
             dsh_t1_file=rel(P('dsh-qwen3.8-27b-gsq-ctx32k-20260908-211955.jsonl')),dsh_t1_ok=d27['ok'],dsh_t1_sec=d27['sec'],dsh_t1_model=d27['model'],dsh_t1_reasoning_steps=d27['stderr_tail'].count('dsh: reasoning:'))
    b27['vram_free_mib']=b27['vram_total_mib']-b27['vram_used_mib']
    # ---------- четвёртая серия под мощностью ----------
    ps=power_series(ep03)
    # ---------- мощность ----------
    pw_files=sorted(rel(f) for f in glob.glob(P('power*.csv')))
    def csv_bounds(f):
        ls=[l for l in open(f) if l.strip()]; a=int(ls[0].split(',')[0]); b=int(ls[-1].split(',')[0])
        return dict(file=rel(f),first=dt.datetime.fromtimestamp(a).strftime('%Y-%m-%d %H:%M:%S'),last=dt.datetime.fromtimestamp(b).strftime('%Y-%m-%d %H:%M:%S'),samples=len(ls))
    power=dict(ep03_log_name='logs/power-<STAMP>.csv (юнит user-systemd ep03-power: nvidia-smi.exe --query-gpu=power.draw,memory.used,utilization.gpu раз в 1 с; колонки epoch,W,MiB,%)',
               files=[csv_bounds(P(os.path.basename(f))) for f in pw_files],
               fable_window='2026-09-09 09:05:24–09:11:04',
               fable_power_log=None,
               fable_power_series_log=rel(PS_CSV),
               files_modified_0909=sorted(rel(f) for f in glob.glob(P('*')) if os.path.isfile(f) and dt.datetime.fromtimestamp(os.path.getmtime(f)).date()==dt.date(2026,9,9) and os.path.basename(f)!='facts-ep04.json'),   # свой выход не считать
               verdict='за окно 21 прогона (09:05–09:11) замера мощности НЕТ: юнит ep03-power остановлен 05.09 15:35, батч ep04-fable-batch шёл без сборщика; отдельная четвёртая серия 09:55–09:57 снята под юнитом ep04-fable-power (logs/power-fable-20260909-095511.csv) — см. power_series, в 21 прогон не входит')
    # ---------- чего нельзя утверждать ----------
    cannot=[
      f'Ватт-часы для 21 прогона (09:05–09:11): файла мощности нет. Для отдельной четвёртой серии (09:55–09:57) замер есть — но это мощность видеокарты стенда по nvidia-smi power.draw, пока карта простаивает (память {ps["mib_min"]}–{ps["mib_max"]} МиБ, загрузка ≤{ps["util_max"]} %): работу делает датацентр, его энергия неизвестна и не утверждается. Сравнивать с {e3["dsh"]["wh_per_pass"]}/{e3["cc"]["wh_per_pass"]} Вт·ч у 9B можно только с этой оговоркой: «столько ест карта, которая ничего не делает».',
      'Стоимость: cost_usd — показания счётчика total_cost_usd в JSON-ответе Claude Code, не счёт и не списание; прогон шёл по подписке.',
      'Скорость модели (ток/с) и задержка API у Fable: в логе только sec (стенка subprocess с запуском claude) и api_ms (duration_api_ms Claude Code); токенов в секунду нет.',
      'Отсутствие ошибок у Fable нельзя подавать как «0 ошибок инструментов»: 4 tool_result с is_error есть — это ненулевые коды выхода собственных диагностических команд (pytest до починки), обвязка их не считала.',
      'Haiku/sonnet в EP03 — по одной серии из 7 (не 21): сравнивать с Fable только по серии или по доле проходов.',
      'Доска четырёх обвязок собрана из проб разных дней (dsh и Claude Code 9B — 05.09, OpenCode и Hermes — 08.09) и одной задачи t1; Hermes шёл на другом теге модели (qwen3.5:9b-ctx64k, 32k он отказался брать) и по ssh в песочнице (поле remote). Это не 3×7 и не одна карта-в-одно-время.',
      'OpenCode 91.9 с: события покрывают 16.0 с; чем заняты остальные ~76 с, лог не говорит (запуск obвязки, загрузка модели — предположение).',
      'Hermes-таймаут 900.5 с (202610): причина в записи не названа; связь с TERMINAL_CWD — из соседних проверок hm-pwdtest*.out, не из самого прогона.',
      '27B GSQ-RCO: одна проба t1 в dsh (44.5 с) и один замер 28.0 ток/с на 200 токенах; ни серий, ни других задач, ни ватт.',
      'Поле reply в записях усечено прогонщиком до 400 символов; ответы t5 короче (120–239 символов), поэтому они целиком; остальные reply — обрезки.',
      'Первые запросы Fable 19 674–19 732 токенов — это usage первого ответа модели (input+cache_creation+cache_read); сравнение с 21 241 у 9B корректно по способу подсчёта (тот же session_stats в run_cc_repo.py), но версии Claude Code разные (2.1.265 против EP03).',
      'Скрытые тесты: судья кладёт test_hidden.py и чистые test_*.py поверх кода агента; агент видел только исходные test_*.py задачи. «Тесты, которые нельзя прочитать» = hidden в judge_repo.py, не «все тесты».',
    ]
    derived={
      'model':D('claude-fable-5-1','поле model записей cc-repo-claude-fable-5-1-*.jsonl и message.model в сессиях ~/.claude/projects'),
      'harness':D('claude-code','поле harness записей'),
      'claude_code_version':D(xc['claude_code_version'],'поле version записей сессий ~/.claude/projects/-tmp-rt-cc-*/*.jsonl (серии 09.09)'),
      'probe_claude_code_version':D(xc['probe_version'],'то же для сессии пробы 08.09 (-tmp-rt-cc-w8wepx7q-t1)'),
      'tasks_n':D(7,'repo-tasks/make.py: t1..t7'),'runs_per_task':D(3,'три файла серий'),'runs_total':D(21,'3×7, len(records)'),
      'passed':D(tot['passed'],'count(ok==true) по трём файлам серий'),'pct':D(tot['pct'],'100*passed/21'),
      'series_passed':D([s['passed'] for s in series],'count(ok) по каждому файлу'),
      'sec_min':D(tot['sec_min'],'min(sec) по 21'),'sec_median':D(tot['sec_median'],'median(sec) по 21'),'sec_max':D(tot['sec_max'],'max(sec) по 21'),'sec_mean':D(tot['sec_mean'],'sum(sec)/21'),
      'sec_sum':D(tot['sec_sum'],'sum(sec) по 21'),'sec_per_pass':D(tot['sec_per_pass'],'sum(sec)/passed'),
      'api_s_sum':D(tot['api_s_sum'],'sum(api_ms)/1000'),
      'batch_wall_s':D(tot['batch_wall_s'],'mtime последнего файла (…-090911.jsonl) минус метка в имени первого (…-090524.jsonl); journalctl ep04-fable-batch: 5 мин 40.009 с'),
      'batch_wall_min':D(tot['batch_wall_min'],'batch_wall_s/60'),'batch_overhead_s':D(tot['batch_overhead_s'],'batch_wall_s − sum(sec): make.py, запуск claude, судья'),
      'series_wall_s':D([s['wall_s'] for s in series],'по каждой серии: mtime файла − метка в имени'),
      'turns_sum':D(tot['turns_sum'],'sum(num_turns)'),'turns_min':D(tot['turns_min'],'min(num_turns)'),'turns_max':D(tot['turns_max'],'max(num_turns)'),
      'turns_by_task':D({t:per[t]['turns'] for t in TIDS},'num_turns по сериям 1,2,3'),
      'calls_sum':D(tot['calls_sum'],'sum(tool_calls.*) по 21; независимо: tool_use по сессиям ~/.claude/projects (cross_check)'),
      'calls_by_tool':D(tot['calls_by_tool'],'tool_calls по именам, сумма по 21'),
      'calls_by_task':D({t:per[t]['calls_by_tool'] for t in TIDS},'tool_calls по именам, сумма по трём сериям задачи'),
      'calls_per_run':D(tot['calls_per_run'],'calls_sum/21'),'runs_without_calls':D(tot['runs_without_calls'],'записи с tool_calls == {} (все три t5)'),
      'read_edit_calls':D({k:tot['calls_by_tool'].get(k,0) for k in ('Read','Edit')},'tool_calls: Read и Edit ни разу при разрешённых Bash,Read,Edit (run_cc_repo.py --allowedTools)'),
      'in_tokens_sum':D(tot['in_tokens_sum'],'sum(in_tokens)'),'cache_read_sum':D(tot['cache_read_sum'],'sum(cache_read)'),'cache_create_sum':D(tot['cache_create_sum'],'sum(cache_create)'),
      'input_total':D(tot['input_total'],'sum(in_tokens+cache_read+cache_create)'),'input_total_k':D(tot['input_total_k'],'input_total/1000, округлено'),
      'out_tokens_sum':D(tot['out_tokens_sum'],'sum(out_tokens)'),'out_tokens_k':D(tot['out_tokens_k'],'out_tokens_sum/1000'),
      'cache_share_pct':D(round(100*tot['cache_read_sum']/tot['input_total']),'100*cache_read_sum/input_total'),
      'first_request_t1':D(tot['first_request_t1'],'first_request_tokens записи t1 (одинаково в трёх сериях)'),
      'first_request_min':D(tot['first_request_min'],'min(first_request_tokens) по 21'),'first_request_max':D(tot['first_request_max'],'max(first_request_tokens) по 21'),
      'first_request_probe':D(probe['first_request_tokens'],'first_request_tokens пробы 08.09 (другая версия Claude Code)'),
      'cost_sum':D(tot['cost_sum'],'sum(cost_usd) по 21'),'cost_sum_2':D(tot['cost_sum_2'],'cost_sum, 2 знака'),
      'cost_per_task':D(tot['cost_per_task'],'cost_sum/21'),'cost_per_task_2':D(tot['cost_per_task_2'],'cost_per_task, 2 знака'),'cost_per_pass':D(tot['cost_per_pass'],'cost_sum/passed'),
      'cost_min':D(tot['cost_min'],'min(cost_usd)'),'cost_max':D(tot['cost_max'],'max(cost_usd)'),
      'cost_by_series':D([s['cost_sum'] for s in series],'sum(cost_usd) по файлу серии'),
      'cost_by_task':D({t:per[t]['cost_sum'] for t in TIDS},'sum(cost_usd) по трём сериям задачи'),
      't5_replies':D(per['t5']['replies'],'поле reply записей id=t5, серии 1,2,3 (целиком: длина < 400)'),
      't5_reply_chars':D(per['t5']['reply_chars'],'len(reply)'),
      't5_ask_both_versions':D(per['t5']['ask_and_both_versions'],'reply начинается с ASK и содержит 3.12 и 3.11 (условие судьи judge_repo.py)'),
      't5_sec':D(per['t5']['sec'],'sec записей t5'),'t5_turns':D(per['t5']['turns'],'num_turns записей t5'),
      'sec_by_task':D({t:per[t]['sec'] for t in TIDS},'sec по сериям 1,2,3'),
      'sec_median_by_task':D({t:per[t]['sec_median'] for t in TIDS},'median(sec) по трём сериям'),
      'probe':D(dict(sec=probe['sec'],ok=probe['ok'],turns=probe['num_turns'],calls=probe['tool_calls'],cost_usd=round(probe['cost_usd'],4)),'cc-repo-claude-fable-5-1-20260908-212958.jsonl (проба t1, не в 21)'),
      'is_error_tool_results':D(xc['tool_result_is_error'],'tool_result.is_error по сессиям ~/.claude/projects/-tmp-rt-cc-{ksq0at4v,nwatg0rm,o22ckpv7}-t*/'),
      'session_mismatches':D(len(xc['mismatches']),'расхождений между tool_calls/first_request_tokens записи и пересчётом по сессии'),
      'timeout_s':D(1200,'run_cc_repo.py: subprocess timeout=1200'),
      'allowed_tools':D('Bash,Read,Edit','run_cc_repo.py: --allowedTools'),
      'hidden_tests_tasks':D(['t1','t2','t3','t4','t6','t7'],'judge_repo.py: HIDDEN — задачи со скрытым тестом (t5 судится по diff и ответу ASK)'),
      'hidden_tests_n':D(6,'len(HIDDEN) в judge_repo.py'),
      **{'ep03_'+k:v for k,v in ep03_cmp.items()},
      'board_t1_dsh_secs':D(board['dsh']['secs'],'dsh t1 EP03: logs/dsh-…-0440.jsonl, logs/dsh-lost-runs.jsonl (main.out:209), logs/dsh-…-0658.jsonl'),
      'board_t1_dsh_sec_median':D(board['dsh']['sec_median'],'median трёх; = facts-ep03 per_task.t1.dsh.sec_median'),
      'board_t1_dsh_repeat_1534':D([x['sec'] for x in dsh_t1_repeat],'logs/dsh-…-153448.jsonl — повтор, в EP03 не зачтён (бриф называл «30»)'),
      'board_t1_dsh_calls':D([board['dsh']['calls_sum'],board['dsh']['errors_sum']],'facts-ep03 per_task.t1.dsh.calls_sum/errors_sum (три прогона)'),
      'board_t1_opencode':D(dict(sec=opencode['sec'],calls=opencode['calls_by_events'],invalid=opencode['invalid'],first_step_input_tokens=opencode['first_step_input_tokens'],input_tokens_sum=opencode['input_tokens_sum'],steps=opencode['steps'],events_span_s=opencode['events_span_s']),'logs/opencode-qwen3.5_9b-ctx32k-20260908-202345.jsonl (sec) + logs/opencode-events/tmp-rt-oc-l1gjtqh4-t1.jsonl (tool_use, step_finish.tokens)'),
      'board_t1_opencode_invalid_tool':D(opencode['invalid_detail']['tool'] if opencode['invalid_detail'] else None,'события: tool==invalid, input.tool'),
      'board_t1_hermes':D(dict(sec=hermes['sec'],api_calls=hermes['api_calls'],input_tokens=hermes['input_tokens'],output_tokens=hermes['output_tokens'],model=hermes['model']),'logs/hermes-qwen3.5_9b-ctx64k-20260908-205139.jsonl: sec, usage_and_stderr json'),
      'board_t1_hermes_refusal_32k':D(hermes['refusal_32k_text'],'logs/hermes-qwen3.5_9b-ctx32k-20260908-202434.jsonl: usage_and_stderr.failure, дословно'),
      'board_t1_hermes_min_ctx':D(64000,'из текста отказа: minimum 64,000'),
      'board_t1_hermes_timeout':D(dict(sec=hermes['timeout_sec'],rc=hermes['timeout_rc']),'logs/hermes-qwen3.5_9b-ctx64k-20260908-202610.jsonl (причина в записи не названа)'),
      'board_t1_hermes_empty_call':D(dict(input_tokens=hermes['empty_call_input_tokens'],api_calls=hermes['empty_call_api_calls'],wall_s=hermes['empty_call_wall_s']),'logs/hm-timing-204231.out: usage json, метки времени до/после'),
      'board_t1_claude_code':D(cc_t1,'facts-ep03 totals.cc.first_request_tokens, per_task.t1.cc; fable: записи t1'),
      'board_first_request':D({'dsh':e3['dsh']['first_request_tokens'],'opencode':opencode['first_step_input_tokens'],'hermes_empty':hermes['empty_call_input_tokens'],'claude_code_9b':e3['cc']['first_request_tokens'],'claude_code_fable':tot['first_request_t1']},'первый запрос к модели: dsh — facts-ep03 (usage первого ответа); opencode — step_finish[0].tokens.input; hermes — пустой вызов hm-timing; claude code — session_stats первого ответа'),
      'b27_params':D(b27['parameter_size'],'probe27b-211810.out: details.parameter_size'),'b27_quant':D(b27['quant'],'probe27b: quantization_level'),
      'b27_ps_size_gb':D(b27['ps_size_gb'],'probe27b: ollama ps size'),'b27_vram_used_mib':D(b27['vram_used_mib'],'probe27b: nvidia-smi memory.used'),'b27_vram_total_mib':D(b27['vram_total_mib'],'probe27b: nvidia-smi memory.total'),
      'b27_vram_used_gb':D(round(b27['vram_used_mib']/1024,1),'vram_used_mib/1024'),'b27_tok_s':D(b27['tok_s'],'probe27b: tok/s на eval_tok=200'),'b27_load_s':D(b27['load_s'],'probe27b: load_s'),
      'b27_ctx':D(b27['ps_ctx'],'probe27b: ollama ps context'),'b27_ollama':D(b27['ollama_version'],'probe27b: ollama version'),
      'b27_dsh_t1':D(dict(ok=b27['dsh_t1_ok'],sec=b27['dsh_t1_sec'],reasoning_steps=b27['dsh_t1_reasoning_steps']),'logs/dsh-qwen3.8-27b-gsq-ctx32k-20260908-211955.jsonl'),
      'b27_vs_9b_dsh_t1_median':D(board['dsh']['sec_median'],'facts-ep03 per_task.t1.dsh.sec_median (для сравнения с 44.5)'),
      'power_fable':D(None,power['verdict']),
      'ps_file':D(rel(PS_FILE),'четвёртая серия, 7 записей, в 21 не входит'),
      'ps_passed':D([ps['passed'],ps['n']],'count(ok) по '+rel(PS_FILE)),
      'ps_window_s':D(ps['window_s'],'END − START из '+rel(PS_OUT)),
      'ps_start_end':D([ps['start'],ps['end']],rel(PS_OUT)+': START/END'),
      'ps_samples':D([ps['samples_in_window'],ps['samples_total']],rel(PS_CSV)+': строк в окне START..END / всего'),
      'ps_w_mean':D(ps['w_mean'],'mean(W) по отсчётам в окне'),'ps_w_min':D(ps['w_min'],'min(W) в окне'),'ps_w_median':D(ps['w_median'],'median(W) в окне'),'ps_w_max':D(ps['w_max'],'max(W) в окне'),
      'ps_wh_window':D(ps['wh_window'],'mean(W) × (END−START)/3600 — метод EP03 (make_facts_ep03.energy)'),
      'ps_wh_window_hold':D(ps['wh_window_hold'],'контроль: Σ W_i × (t_{i+1} − t_i)/3600 по соседним отсчётам в окне (пропуски по 2 с учтены)'),
      'ps_wh_per_pass':D(ps['wh_per_pass'],'wh_window / passed(7)'),
      'ps_wh_by_task':D(ps['wh_by_task'],'sec × mean(W)/3600 по каждой задаче'),'ps_wh_by_task_sum':D(ps['wh_by_task_sum'],'сумма по задачам (меньше окна: окно включает make.py и судью)'),
      'ps_sec':D(ps['sec'],'sec по задачам t1..t7'),'ps_sec_sum':D(ps['sec_sum'],'sum(sec)'),'ps_turns':D(ps['turns'],'num_turns'),'ps_calls_by_tool':D(ps['calls_by_tool'],'tool_calls, сумма'),
      'ps_cost_sum':D(ps['cost_sum'],'sum(cost_usd) по серии'),'ps_first_request':D([ps['first_request_min'],ps['first_request_max']],'min/max first_request_tokens'),
      'ps_gpu_mib':D([ps['mib_min'],ps['mib_max']],rel(PS_CSV)+': memory.used min/max в окне'),'ps_gpu_util_max':D(ps['util_max'],rel(PS_CSV)+': utilization.gpu max в окне'),
      'ps_vs_ep03_wh_per_pass':D({'dsh':e3['dsh']['wh_per_pass'],'cc_9b':e3['cc']['wh_per_pass'],'fable_idle_card':ps['wh_per_pass']},'facts-ep03 totals.*.wh_per_pass; fable — карта в простое'),
      'ps_ratio_ep03_over_fable':D({'dsh':round(e3['dsh']['wh_per_pass']/ps['wh_per_pass'],1),'cc_9b':round(e3['cc']['wh_per_pass']/ps['wh_per_pass'],1)},'ep03 wh_per_pass / fable wh_per_pass'),
      'ps_vs_ep03_w':D({'ep03_idle_w':ep03['derived']['idle_w'],'ep03_peak_w':ep03['derived']['peak_w'],'ep03_mean_w_dsh':e3['dsh']['mean_w'],'ep03_mean_w_cc':e3['cc']['mean_w'],'fable_mean_w':ps['w_mean']},'facts-ep03 derived.idle_w (1-й процентиль), derived.peak_w, totals.*.mean_w; fable — mean(W) в окне серии'),
      'ps_t5_reply':D(ps['t5_reply'],'reply записи t5 четвёртой серии'),
      'ps_caveat':D(ps['caveat'],'обязательная оговорка'),
    }
    f={'tasks':TASKS,'per_task':per,'totals':tot,'cross_check':xc,'probe':pr,'ep03':ep03_cmp,'board_t1':board,'b27':b27,'power':power,'power_series':ps,'cannot_claim':cannot,'derived':derived,
       'meta':{'date':'2026-09-09','episode':'EP04','logs':[rel(x) for x in FABLE_FILES]+[rel(PROBE_FILE),'logs/facts-ep03.json','logs/opencode-qwen3.5_9b-ctx32k-20260908-202345.jsonl',rel(oc['events']),
               'logs/hermes-qwen3.5_9b-ctx32k-20260908-202434.jsonl','logs/hermes-qwen3.5_9b-ctx64k-20260908-205139.jsonl','logs/hermes-qwen3.5_9b-ctx64k-20260908-202610.jsonl','logs/hm-timing-204231.out',
               'logs/probe27b-211810.out','logs/dsh-qwen3.8-27b-gsq-ctx32k-20260908-211955.jsonl',rel(PS_FILE),rel(PS_CSV),rel(PS_OUT),'logs/dsh-qwen3.5_9b-ctx32k-20260905-0440.jsonl','logs/dsh-qwen3.5_9b-ctx32k-20260905-0658.jsonl','logs/dsh-lost-runs.jsonl','logs/fable-batch-20260909-090524.out'],
               'sessions':'~/.claude/projects/-tmp-rt-cc-{ksq0at4v,nwatg0rm,o22ckpv7}-t1..t7 (независимый пересчёт вызовов)'}}
    return f

def selftest():
    """Три контрольных числа независимым способом (grep / jq / sort) + контрольный дефект на временной копии."""
    f=build(); n=0; ok=0
    def check(name,a,b):
        nonlocal n,ok; n+=1; good=(a==b) if not isinstance(a,float) else abs(a-b)<1e-9; ok+=good
        print(f"  {'ok ' if good else 'БРАК'} {name}: скрипт {a} / независимо {b}")
    files=' '.join(FABLE_FILES)
    g=subprocess.run(f"grep -c '\"ok\": true' {files} | awk -F: '{{s+=$2}} END{{print s}}'",shell=True,capture_output=True,text=True).stdout.strip()
    check('ok/21 через grep -c',f['totals']['passed'],int(g))
    j=subprocess.run(f"jq -s 'map(.cost_usd)|add' {files}",shell=True,capture_output=True,text=True).stdout.strip()
    check('сумма cost_usd через jq',f['totals']['cost_sum'],round(float(j),4))
    mn=subprocess.run(f"jq .first_request_tokens {files} | sort -n | head -1",shell=True,capture_output=True,text=True).stdout.strip()
    mx=subprocess.run(f"jq .first_request_tokens {files} | sort -n | tail -1",shell=True,capture_output=True,text=True).stdout.strip()
    check('первый запрос min/max через jq|sort',[f['totals']['first_request_min'],f['totals']['first_request_max']],[int(mn),int(mx)])
    a=subprocess.run(f"jq -s 'map(.sec)|add' {files}",shell=True,capture_output=True,text=True).stdout.strip()
    check('сумма sec через jq',f['totals']['sec_sum'],round(float(a),1))
    tc=subprocess.run(f"jq '[.tool_calls[]]|add // 0' {files} | awk '{{s+=$1}} END{{print s}}'",shell=True,capture_output=True,text=True).stdout.strip()
    check('вызовы инструментов через jq (записи)',f['totals']['calls_sum'],int(tc))
    # вызовы по сессиям Claude Code — совсем другой источник
    sess=sum(sum((session_recount(r['dir']) or {'calls':{}})['calls'].values()) for _,r in fable_runs())
    check('вызовы инструментов по сессиям ~/.claude/projects',f['totals']['calls_sum'],sess)
    check('прогонов с логом сессии',f['cross_check']['runs_with_session_log'],21)
    # интеграл мощности независимо: awk по csv в окне START..END (сумма W и число строк → средняя × длительность)
    a=subprocess.run(f"grep -m1 '^START' {PS_OUT} | cut -d' ' -f2",shell=True,capture_output=True,text=True).stdout.strip()
    b=subprocess.run(f"grep -m1 '^END' {PS_OUT} | cut -d' ' -f2",shell=True,capture_output=True,text=True).stdout.strip()
    aw=subprocess.run(f"awk -F, '$1>={a} && $1<={b} {{s+=$2; n++}} END{{printf \"%.3f %d\", s/n*({b}-{a})/3600, n}}' {PS_CSV}",shell=True,capture_output=True,text=True).stdout.split()
    check('Вт·ч окна серии 4 через awk',[f['power_series']['wh_window'],f['power_series']['samples_in_window']],[float(aw[0]),int(aw[1])])
    ps_in=f['power_series']['file'] in [rel(x) for x in FABLE_FILES] or f['power_series']['dirs_base'] in [s_['tmp_base'] for s_ in f['totals']['series']]
    check('серия под мощностью не входит в 21 (n=21, каталоги разные)',[f['totals']['n'],ps_in],[21,False])
    # контрольный дефект: временная копия, одна запись подменена → счётчики обязаны сдвинуться
    tmp=tempfile.mkdtemp(prefix='ep04-selftest-',dir=os.environ.get('SCRATCH') or None)
    try:
        cp=[shutil.copy(x,tmp) for x in FABLE_FILES]
        ls=open(cp[1]).read().split('\n'); r=json.loads(ls[2]); r['ok']=False; r['cost_usd']+=1.0; r['first_request_tokens']=999; ls[2]=json.dumps(r,ensure_ascii=False); open(cp[1],'w').write('\n'.join(ls))
        mut=fable_runs(cp); R=[x for _,x in mut]
        p2=sum(1 for x in R if x['ok']); c2=round(sum(x['cost_usd'] for x in R),4); m2=min(x['first_request_tokens'] for x in R)
        d1=(p2==f['totals']['passed']-1); d2=(abs(c2-f['totals']['cost_sum']-1.0)<1e-6); d3=(m2==999)
        n+=3; ok+=d1+d2+d3
        print(f"  {'ok ' if d1 else 'БРАК'} контрольный дефект ok: {f['totals']['passed']} → {p2}")
        print(f"  {'ok ' if d2 else 'БРАК'} контрольный дефект cost: {f['totals']['cost_sum']} → {c2}")
        print(f"  {'ok ' if d3 else 'БРАК'} контрольный дефект первый запрос min: {f['totals']['first_request_min']} → {m2}")
    finally: shutil.rmtree(tmp,ignore_errors=True)
    print(f"САМОПРОВЕРКА: {ok}/{n}"); return ok==n

if __name__=='__main__':
    if '--selftest' in sys.argv: sys.exit(0 if selftest() else 1)
    f=build(); out=P('facts-ep04.json'); json.dump(f,open(out,'w'),ensure_ascii=False,indent=1)
    t=f['totals']; print(f"{t['passed']}/{t['n']}  cost ${t['cost_sum']}  sec {t['sec_min']}/{t['sec_median']}/{t['sec_max']}  turns {t['turns_sum']}  calls {t['calls_by_tool']}  first {t['first_request_min']}..{t['first_request_max']}  → {out}")
    for k in TIDS: print(k, f['per_task'][k]['pass'], f['per_task'][k]['sec'], f['per_task'][k]['turns'], f['per_task'][k]['calls_by_tool'], f['per_task'][k]['cost_sum'])
    print('cross_check:', {k:v for k,v in f['cross_check'].items() if k!='is_error_heads'})
    print('power:', f['power']['verdict'])
    ps=f['power_series']; print(f"power_series: {ps['passed']}/{ps['n']}  окно {ps['window_s']} с  W {ps['w_min']}/{ps['w_median']}/{ps['w_max']} mean {ps['w_mean']}  Вт·ч {ps['wh_window']} (контроль {ps['wh_window_hold']})  на пройденную {ps['wh_per_pass']}  MiB {ps['mib_min']}..{ps['mib_max']} util≤{ps['util_max']}%")
