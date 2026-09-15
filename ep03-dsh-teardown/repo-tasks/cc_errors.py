#!/usr/bin/env python3
"""Ошибки инструментов в логах сессий Claude Code: python3 cc_errors.py logs/cc-repo-*.jsonl
Берёт session_id из записей (поле dir → лог ~/.claude/projects/<slug>/<sid>.jsonl) и считает
tool_use / tool_result с is_error, вход/выход токенов (с кэшем) по ходам."""
import sys,json,glob,os,collections
for f in sys.argv[1:]:
    print("==",os.path.basename(f))
    for l in open(f):
        r=json.loads(l); d=r.get('dir')
        if not d: continue
        slug=d.replace('/','-')
        logs=glob.glob(os.path.expanduser(f"~/.claude/projects/{slug}/*.jsonl"))
        if not logs: print(f"  {r['id']}: нет лога"); continue
        calls=collections.Counter(); errs=0; tin=0; tout=0; turns=0; seen=set()
        for lg in logs:
            for x in open(lg):
                try: e=json.loads(x)
                except: continue
                m=e.get('message') or {}
                if e.get('type')=='assistant' and isinstance(m,dict):
                    # одно сообщение модели пишется в лог кусками с одним id: текст отдельно, tool_use отдельно —
                    # вызовы считаем по всем кускам, ходы и токены — по уникальному id
                    for b in m.get('content') or []:
                        if isinstance(b,dict) and b.get('type')=='tool_use': calls[b['name']]+=1
                    mid=m.get('id')
                    if mid in seen: continue
                    seen.add(mid); turns+=1
                    u=m.get('usage') or {}; tin+=u.get('input_tokens',0)+u.get('cache_read_input_tokens',0)+u.get('cache_creation_input_tokens',0); tout+=u.get('output_tokens',0)
                if e.get('type')=='user' and isinstance(m,dict):
                    for b in m.get('content') or []:
                        if isinstance(b,dict) and b.get('type')=='tool_result' and b.get('is_error'): errs+=1
        print(f"  {r['id']} {'ok  ' if r['ok'] else 'FAIL'} ходов {turns:2d} вызовов {sum(calls.values()):2d} ошибок {errs:2d} вход {tin:8,} выход {tout:6,}  {dict(calls)}")
