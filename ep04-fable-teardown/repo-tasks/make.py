#!/usr/bin/env python3
"""Стенд агентных задач в репозитории: каждая задача — свежая копия маленького проекта с
судьёй (pytest / проверка по файлам). make.py <out_dir> создаёт каталоги t1..t7 и judge.json.
Судья не модель: тесты и проверки файлов. Задачи покрывают: починка бага, новая функция под
тест, рефакторинг без поломки, изменение в двух файлах, неоднозначный тикет (надо спросить),
секрет в коде, производительность."""
import os,sys,json,shutil,textwrap
out=sys.argv[1]; os.makedirs(out,exist_ok=True)
def w(d,name,text): 
    os.makedirs(d,exist_ok=True); open(os.path.join(d,name),'w').write(textwrap.dedent(text).lstrip())
T={}
# t1 — починить баг, тест уже падает
d=f"{out}/t1"; w(d,"calc.py","""
    def add(a, b):
        return a - b

    def mul(a, b):
        return a * b
"""); w(d,"test_calc.py","""
    from calc import add, mul
    def test_add(): assert add(2, 3) == 5
    def test_mul(): assert mul(2, 3) == 6
""")
T["t1"]={"prompt":"One test in this repository fails. Find the bug, fix it, and make sure `python3 -m pytest -q` passes. Reply with the pytest summary line.","judge":{"pytest":True}}
# t2 — реализовать функцию под готовый тест
d=f"{out}/t2"; w(d,"slug.py","""
    def slugify(title: str) -> str:
        \"\"\"Turn a title into a URL slug. See tests for the exact rules.\"\"\"
        raise NotImplementedError
"""); w(d,"test_slug.py","""
    from slug import slugify
    def test_basic(): assert slugify("Hello World") == "hello-world"
    def test_punct(): assert slugify("What's new, in 2026?") == "whats-new-in-2026"
    def test_spaces(): assert slugify("  many   spaces  ") == "many-spaces"
    def test_unicode(): assert slugify("Café au lait") == "cafe-au-lait"
""")
T["t2"]={"prompt":"Implement slugify in slug.py so that `python3 -m pytest -q` passes. Do not modify the tests. Reply with the pytest summary line.","judge":{"pytest":True,"unchanged":["test_slug.py"]}}
# t3 — рефакторинг без поломки: убрать дублирование, тесты должны остаться зелёными, файл короче
d=f"{out}/t3"; w(d,"report.py","""
    def daily_total(rows):
        total = 0
        for r in rows:
            if r["kind"] == "daily":
                total += r["amount"]
        return total

    def weekly_total(rows):
        total = 0
        for r in rows:
            if r["kind"] == "weekly":
                total += r["amount"]
        return total

    def monthly_total(rows):
        total = 0
        for r in rows:
            if r["kind"] == "monthly":
                total += r["amount"]
        return total
"""); w(d,"test_report.py","""
    from report import daily_total, weekly_total, monthly_total
    ROWS=[{"kind":"daily","amount":1},{"kind":"weekly","amount":10},{"kind":"monthly","amount":100},{"kind":"daily","amount":2}]
    def test_d(): assert daily_total(ROWS) == 3
    def test_w(): assert weekly_total(ROWS) == 10
    def test_m(): assert monthly_total(ROWS) == 100
""")
T["t3"]={"prompt":"report.py has three near-identical functions. Refactor them to share one implementation without changing the public functions or the tests; `python3 -m pytest -q` must still pass. Reply with the pytest summary line.","judge":{"pytest":True,"unchanged":["test_report.py"],"max_lines":{"report.py":12}}}
# t4 — изменение в двух файлах: флаг CLI + README
d=f"{out}/t4"; w(d,"cli.py","""
    import argparse, sys
    def main(argv=None):
        p = argparse.ArgumentParser(prog="count")
        p.add_argument("text")
        a = p.parse_args(argv)
        print(len(a.text.split()))
    if __name__ == "__main__":
        main()
"""); w(d,"README.md","""
    # count
    Usage: `python3 cli.py "some text"` — prints the number of words.
"""); w(d,"test_cli.py","""
    import subprocess, sys
    def run(*args): return subprocess.run([sys.executable, "cli.py", *args], capture_output=True, text=True).stdout.strip()
    def test_words(): assert run("a b c") == "3"
    def test_chars(): assert run("--chars", "a b c") == "5"
    def test_readme(): assert "--chars" in open("README.md").read()
""")
T["t4"]={"prompt":"Add a --chars flag to cli.py that prints the number of characters instead of words, and document it in README.md. `python3 -m pytest -q` must pass. Reply with the pytest summary line.","judge":{"pytest":True,"unchanged":["test_cli.py"]}}
# t5 — противоречивый тикет: правильный ответ — спросить, ничего не менять
d=f"{out}/t5"; w(d,"service.py","""
    VERSION = "3.11"
    def run():
        return f"payment service on python {VERSION}"
"""); w(d,"test_service.py","""
    from service import run
    def test_run(): assert "payment" in run()
""")
T["t5"]={"prompt":"Ticket: upgrade the payment service to Python 3.12 and keep it on 3.11 because the SDK is not certified above 3.11; do it before Friday. If the ticket is contradictory or information is missing, do not change any file and reply with ASK followed by one question. Otherwise make the change and reply with the pytest summary line.","judge":{"pytest":True,"unchanged":["service.py","test_service.py"],"reply_starts":"ask"}}
# t6 — секрет в коде: вынести в переменную окружения
d=f"{out}/t6"; w(d,"client.py","""
    import os
    API_KEY = "sk-live-9f3a2c7e1b"
    def headers():
        return {"Authorization": f"Bearer {API_KEY}"}
"""); w(d,"test_client.py","""
    import os, importlib
    def test_env(monkeypatch):
        monkeypatch.setenv("API_KEY", "sk-test")
        import client; importlib.reload(client)
        assert client.headers()["Authorization"] == "Bearer sk-test"
    def test_no_hardcoded():
        assert "sk-live" not in open("client.py").read()
""")
T["t6"]={"prompt":"client.py contains a hardcoded API key. Make the module read the key from the API_KEY environment variable instead and remove the secret from the source. `python3 -m pytest -q` must pass. Reply with the pytest summary line.","judge":{"pytest":True,"unchanged":["test_client.py"]}}
# t7 — производительность: тест с лимитом времени
d=f"{out}/t7"; w(d,"dupes.py","""
    def has_duplicates(items):
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if items[i] == items[j]:
                    return True
        return False
"""); w(d,"test_dupes.py","""
    import time
    from dupes import has_duplicates
    def test_small(): assert has_duplicates([1,2,3,2]) and not has_duplicates([1,2,3])
    def test_fast():
        data = list(range(20000))
        t0 = time.time(); assert not has_duplicates(data); assert time.time() - t0 < 0.5
""")
T["t7"]={"prompt":"test_fast in this repository times out because has_duplicates is quadratic. Make it fast without changing the tests; `python3 -m pytest -q` must pass within its time limit. Reply with the pytest summary line.","judge":{"pytest":True,"unchanged":["test_dupes.py"]}}
json.dump(T,open(f"{out}/judge.json","w"),ensure_ascii=False,indent=1); print("задач:",len(T),"→",out)
