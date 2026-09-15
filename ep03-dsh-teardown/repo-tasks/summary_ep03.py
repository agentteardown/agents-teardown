#!/usr/bin/env python3
"""Итог основного замера EP03: 3 прогона × 7 задач × 2 обвязки. Читает jsonl после отметки, main-*.out (START/END) и power-*.csv."""
import json,glob,sys,statistics as st,collections
S=sys.argv[1] if len(sys.argv)>1 else open('logs/main-run.stamp').read().strip()
T0=int(S[-4:-2])*3600+int(S[-2:])*60
def stamp(f):
    import re; m=re.search(r"-(\d{2})(\d{2})(\d{2})?\.jsonl$",f); return int(m.group(1))*3600+int(m.group(2))*60
runs=collections.defaultdict(list)   # (h,t) -> [dict]
for f in sorted(glob.glob('logs/dsh-qwen3.5_9b-ctx32k-*.jsonl')+glob.glob('logs/cc-repo-local-qwen3.5_9b-ctx32k-*.jsonl')):
    if stamp(f)<T0: continue
    for l in open(f):
        d=json.loads(l); h='dsh' if d['harness']=='dsh' else 'cc'; runs[(h,d['id'])].append(d)
# энергия: пары START/END в main.out, длительность >5 с
pw=[]
for l in open(f'logs/power-{S}.csv'):
    p=l.strip().split(',')
    if len(p)>=2 and p[1]: pw.append((int(p[0]),float(p[1])))
def energy(a,b):
    xs=[w for t,w in pw if a<=t<=b]; return (st.mean(xs)*(b-a)/3600, len(xs)) if xs else (None,0)
segs=collections.defaultdict(list); cur=None
for l in open(f'logs/main-{S}.out'):
    p=l.split()
    if len(p)>=5 and p[1]=='START': cur=(int(p[0]),p[2],p[3],p[4])
    elif len(p)>=5 and p[1]=='END' and cur and (p[2],p[3],p[4])==cur[1:]:
        a,b=cur[0],int(p[0])
        if b-a>5: segs[(p[3],p[4])].append(energy(a,b)+(b-a,))
        cur=None
def med(xs): xs=[x for x in xs if x is not None]; return st.median(xs) if xs else float('nan')
print(f"# Основной замер EP03 — {S[:8]} ({S[9:11]}:{S[11:]}), qwen3.5:9b-ctx32k, по 3 прогона\n")
print("| задача | dsh пройдено | dsh с, медиана | dsh Вт·ч | CC пройдено | CC с, медиана | CC Вт·ч | CC ходов | CC токенов входа |")
print("|---|---|---|---|---|---|---|---|---|")
tot={'dsh':[0,0,0.0,0.0],'cc':[0,0,0.0,0.0]}
for t in ['t1','t2','t3','t4','t5','t6','t7']:
    row=[t]
    for h in ['dsh','cc']:
        rs=runs[(h,t)]; ok=sum(1 for r in rs if r['ok']); n=len(rs)
        e=[s[0] for s in segs[(h,t)]]; sec=[float(r['sec']) for r in rs]
        tot[h][0]+=ok; tot[h][1]+=n; tot[h][2]+=sum(sec); tot[h][3]+=sum(x for x in e if x)
        row+= [f"{ok}/{n}", f"{med(sec):.0f}", f"{med(e):.2f}"]
        if h=='cc': row+=[f"{med([r['num_turns'] for r in rs]):.0f}", f"{med([r['in_tokens'] for r in rs])/1000:.0f}k"]
    print("| "+" | ".join(row)+" |")
for h in ['dsh','cc']:
    o,n,s,e=tot[h]; print(f"\n**{h}**: пройдено {o}/{n} ({100*o/n:.0f}%), суммарно {s/60:.0f} мин, {e:.1f} Вт·ч, среднее на задачу {s/n:.0f} с и {e/n:.2f} Вт·ч; на одну пройденную задачу {s/o:.0f} с и {e/o:.2f} Вт·ч")
cc=[r for k,v in runs.items() if k[0]=='cc' for r in v]
print(f"\nCC суммарно: ходов {sum(r['num_turns'] for r in cc)}, токенов входа {sum(r['in_tokens'] for r in cc)/1e6:.2f} M, выхода {sum(r['out_tokens'] for r in cc)/1000:.0f} k")
print("\nПричины провалов:")
for (h,t),rs in sorted(runs.items()):
    for r in rs:
        if not r['ok']: print(f"- {h} {t}: {r['why'][:90]}")
segn=sum(len(v) for v in segs.values()); print(f"\nОтрезков мощности: {segn} из {sum(len(v) for v in runs.values())} прогонов; точек в журнале мощности {len(pw)}")
