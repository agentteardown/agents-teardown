#!/usr/bin/env python3
"""Сторож набора задач. Два дефекта 02.09.2026 прошли в опубликованный выпуск:
data-03 ссылалась на таблицу, которой не было в промте, а data-04 требовала
голое число, не сказав об этом. Обе проверки ниже краснеют на этих дефектах —
и на контрольных, вшитых в самопроверку.

Правила:
  R1  промт, ссылающийся на прежние данные ("same table", "the table above",
      "previous"), обязан содержать эти данные сам — задачи задаются
      независимыми вызовами, истории между ними нет;
  R2  задача, чей судья требует голое значение (number / oneof / starts),
      обязана явно сказать "only" — иначе форма спрашивается молча;
  R3  ожидаемый ответ обязан выводиться из текста промта.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
# starts проверяет только начало ответа — текст после ключевого слова там
# предусмотрен самой задачей ("ASK followed by one question"), это не голое значение
BARE = ("number", "oneof")
REFERS = re.compile(r"\b(same table|the table above|previous (table|answer|question)|as above)\b", re.I)
# строка данных: две и более группы, разделённые пробелами, хотя бы одно число
# внутри строки — пробелы, но НЕ перевод строки: иначе выражение съедает
# весь промт целиком и видит в нём одну строку
DATAROW = re.compile(r"^[^\S\n]*\S+(?:[^\S\n]+\S+)+[^\S\n]*$", re.M)

def rules(t):
    bad = []
    p, c = t["prompt"], t["check"]
    if REFERS.search(p):
        # ссылается на прежние данные — значит они должны быть тут же
        digits = sum(ch.isdigit() for ch in p)
        if digits < 8 or len(DATAROW.findall(p)) < 2:
            bad.append("R1 ссылается на прежние данные, но их нет в промте")
    if c["type"] in BARE and "only" not in p.lower():
        bad.append(f"R2 судья {c['type']} требует голое значение, но 'only' в промте нет")
    if c["type"] == "number":
        nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", p.replace(",", "."))]
        if not nums:
            bad.append("R3 числовой ответ, но в промте нет ни одного числа")
    # R4: промт запрещает markdown-забор → судья обязан это проверять (иначе забор
    # молча прощается одной модели и не прощается другой — 03.09.2026)
    if re.search(r"no (markdown |code )?fence", p, re.I) and not c.get("no_fence"):
        bad.append("R4 промт запрещает забор, а у судьи нет флага no_fence")
    return bad

SELFTEST = [
    # (задача, должен ли сторож найти дефект)
    ({"prompt": "Same table. Which engine is best? Answer with the name only.",
      "check": {"type": "oneof", "expect": ["kokoro"]}}, True),   # контрольный дефект R1
    ({"prompt": "Log:\n  a 1\n  b 2\nGive the ratio.",
      "check": {"type": "number", "expect": 2}}, True),           # контрольный дефект R2
    ({"prompt": "Return ONLY JSON. No prose, no markdown fence.",
      "check": {"type": "json", "keys": ["a"]}}, True),           # контрольный дефект R4
    ({"prompt": "From this table pick the lowest. Answer with the name only.\n"
                "engine  WER\nkokoro  0.0066\nindex   0.0199",
      "check": {"type": "oneof", "expect": ["kokoro"]}}, False),  # контрольный образец
    ({"prompt": "Same table. Which engine is best? Answer with the name only.\n"
                "engine  WER\nkokoro  0.0066\nindex   0.0199",
      "check": {"type": "oneof", "expect": ["kokoro"]}}, False),  # ссылается, но данные тут же
    ({"prompt": "If the task is unambiguous, answer with the command. If information is "
                "missing, answer with the single word ASK followed by one question.",
      "check": {"type": "starts", "expect": "ask"}}, False),      # starts — не голое значение
]

def main():
    if "--selftest" in sys.argv:
        bad = 0
        for i, (t, want) in enumerate(SELFTEST, 1):
            got = bool(rules(t))
            mark = "ok " if got == want else "СЛОМАН"
            if got != want: bad += 1
            print(f"  контроль {i}: ожидалось {'брак' if want else 'чисто'}, получено "
                  f"{'брак' if got else 'чисто'}  {mark}")
        print(f"самопроверка: {len(SELFTEST)-bad}/{len(SELFTEST)}")
        if bad: sys.exit(1)
    ts = json.load(open(os.path.join(ROOT, "tasks", "tasks.json")))
    found = 0
    for t in ts:
        for b in rules(t):
            print(f"  БРАК {t['id']}: {b}")
            found += 1
    print(f"проверено задач: {len(ts)}, нарушений: {found}")
    sys.exit(1 if found else 0)

if __name__ == "__main__":
    main()
