#!/usr/bin/env python3
"""Трасса сессии dsh по dir песочницы: шаги, вызовы, ошибки, usage. Аргумент: /tmp/rt-xxx/tN [--usage]"""
import sys,json,glob,os,zstandard
d=sys.argv[1]; slug='--'+d.strip('/').replace('/','-')+'--'
for s in sorted(glob.glob(os.path.expanduser(f'~/.dsh/sessions/{slug}/session-*/session.jsonl.zstd'))):
    raw=zstandard.ZstdDecompressor().stream_reader(open(s,'rb')).read().decode()
    L=[json.loads(l) for l in raw.splitlines() if l.strip()]
    for l in L:
        t=l['type']; x=l.get('data',{})
        if t=='tool/call': print(f"  call {x['name']:12s} {x['arguments'][:110]}")
        elif t=='tool/result':
            for p in x['message']['content']:
                if p.get('type')=='tool-result':
                    txt=' '.join(c.get('text','') for c in p.get('content',[]) if isinstance(c,dict)).replace('\n',' ⏎ ')
                    print(f"  {'ERR ' if p.get('isError') else 'res '} {txt[:110]}")
        elif t=='assistant/message' and '--usage' in sys.argv:
            m=x.get('message',{}); u=m.get('usage') or x.get('usage'); print('  usage', json.dumps(u)[:160] if u else json.dumps(x)[:200])
        elif t=='turn/end': print('  END', json.dumps(x))
