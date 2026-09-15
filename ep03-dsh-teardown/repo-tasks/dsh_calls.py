#!/usr/bin/env python3
"""Вызовы инструментов dsh по логам сессий. Аргументы: jsonl-файлы прогонов; сопоставление по полю dir → слаг сессии."""
import sys,json,glob,os,collections
import zstandard
def load(path):
    raw=zstandard.ZstdDecompressor().stream_reader(open(path,'rb')).read().decode()
    return [json.loads(l) for l in raw.splitlines() if l.strip()]
def stats(L):
    calls=[l for l in L if l['type']=='tool/call']; res=[l for l in L if l['type']=='tool/result']
    names=collections.Counter(c['data']['name'] for c in calls)
    err=0; kinds=collections.Counter(); byname={c['data']['callId']:c['data']['name'] for c in calls}; tool_err=collections.Counter()
    for r in res:
        for p in r['data']['message']['content']:
            if p.get('type')=='tool-result' and p.get('isError'):
                err+=1; tool_err[byname.get(p.get('toolCallId'),'?')]+=1; txt=' '.join(x.get('text','') for x in p.get('content',[]) if isinstance(x,dict))
                k='unknown tool' if 'unknown tool' in txt else 'invalid arguments' if 'invalid arguments' in txt else 'exec/other'
                kinds[k]+=1
    steps=sum(1 for l in L if l['type']=='step/start'); ends=[l['data'].get('reason',{}).get('kind') for l in L if l['type']=='turn/end']
    return dict(calls=len(calls),errors=err,err_kinds=dict(kinds),tools=dict(names),tool_err=dict(tool_err),steps=steps,end=ends)
out={}
for f in sys.argv[1:]:
    for l in open(f):
        d=json.loads(l)
        if d.get('harness')!='dsh': continue
        slug='--'+d['dir'].strip('/').replace('/','-')+'--'
        ss=sorted(glob.glob(os.path.expanduser(f'~/.dsh/sessions/{slug}/session-*/session.jsonl.zstd')))
        if not ss: print('нет сессии', d['id'], d['dir'], file=sys.stderr); continue
        L=[]; [L.extend(load(s)) for s in ss]
        out[d['dir']]=dict(id=d['id'],ok=d['ok'],sessions=len(ss),**stats(L))
json.dump(out,open('logs/dsh-calls.json','w'),ensure_ascii=False,indent=1)
tot=collections.Counter(); kinds=collections.Counter(); tools=collections.Counter()
for v in out.values(): tot['calls']+=v['calls']; tot['errors']+=v['errors']; tot['steps']+=v['steps']; kinds.update(v['err_kinds']); tools.update(v['tools'])
print(f"dsh: прогонов {len(out)}, шагов {tot['steps']}, вызовов {tot['calls']}, ошибок {tot['errors']} {dict(kinds)}; инструменты {dict(tools)}")
for k,v in sorted(out.items(), key=lambda kv: kv[1]['id']): print(f"  {v['id']} {'ok' if v['ok'] else 'FAIL'} вызовов {v['calls']:3d} ошибок {v['errors']:2d} {v['err_kinds']} конец {v['end']}")
