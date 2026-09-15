#!/usr/bin/env python3
"""Пересудить сохранённые прогоны (поле dir в jsonl) текущим судьёй: python3 rejudge.py logs/*.jsonl"""
import sys,json,os,tempfile,subprocess
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); from judge_repo import judge
clean=tempfile.mkdtemp(prefix="rt-clean-"); subprocess.run([sys.executable,os.path.join(HERE,"make.py"),clean],check=True,capture_output=True)
J=json.load(open(os.path.join(clean,"judge.json")))
for f in sys.argv[1:]:
    rows=[json.loads(l) for l in open(f)]; changed=0
    for r in rows:
        if not r.get('dir') or not os.path.isdir(r['dir']): continue
        ok,why=judge(r['id'],r['dir'],os.path.join(clean,r['id']),J[r['id']]['judge'],r.get('reply',''))
        if ok!=r['ok']: changed+=1
        r['ok'],r['why']=ok,"; ".join(why)
    open(f,'w').write("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in rows))
    print(f"{os.path.basename(f)}: {sum(r['ok'] for r in rows)}/{len(rows)} (изменилось {changed})")
