#!/usr/bin/env python3
"""Judge for the local-model bench. Every answer is checked mechanically —
no LLM grades another LLM. Run --selftest first: a judge that cannot catch a
planted defect will not catch a real one (channel rule, learned the hard way)."""
import json, re, sys, math

def _num(s):
    m = re.findall(r"-?\d+(?:\.\d+)?", s.replace(",", "."))
    return float(m[0]) if m else None

def _json_blob(s):
    s = re.sub(r"^```[a-z]*|```$", "", s.strip(), flags=re.M).strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = s.find(opener), s.rfind(closer)
        if i >= 0 and j > i:
            try: return json.loads(s[i:j+1])
            except Exception: pass
    return None

def check(ans, spec):
    """-> (ok, why). Deliberately strict: 'almost right' is wrong."""
    a = (ans or "").strip()
    t = spec["type"]
    if t == "json":
        # задание запрещает markdown-забор (fmt-01: «No prose, no markdown fence») —
        # ответ в ``` это провал, а не «почти правильно». До 03.09 судья молча срезал
        # забор, и haiku проходила fmt-01 с забором в двух прогонах из трёх, пока
        # sonnet за «number only» проваливалась: судья был асимметричен
        if spec.get("no_fence") and a.lstrip().startswith("```"):
            return False, "fenced JSON where the task forbids a fence"
        d = _json_blob(a)
        if not isinstance(d, dict): return False, "not a json object"
        for k in spec["keys"]:
            if k not in d: return False, f"missing key {k}"
        for k, v in spec.get("values", {}).items():
            got = d.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                if got is None or abs(float(got) - float(v)) > 1e-6: return False, f"{k}={got} != {v}"
            elif got != v: return False, f"{k}={got!r} != {v!r}"
        return True, ""
    if t == "json_array":
        d = _json_blob(a)
        if not isinstance(d, list): return False, "not a json array"
        got = sorted(str(x).lower().strip() for x in d)
        return (got == sorted(spec["expect"]), f"got {got}")
    if t == "json_contains":
        d = _json_blob(a)
        if not isinstance(d, dict) or spec["key"] not in d: return False, "no key"
        v = str(d[spec["key"]]).lower()
        if not all(m.lower() in v for m in spec["must"]): return False, f"missing parts in {v!r}"
        if spec.get("any") and not any(m.lower() in v for m in spec["any"]): return False, f"no count flag in {v!r}"
        return True, ""
    if t == "oneof":
        low = a.lower()
        first = re.split(r"[\s,.;:\n]+", low.strip())[0] if low.strip() else ""
        return (any(e == first or low.strip() == e or low.strip().startswith(e) for e in spec["expect"]),
                f"got {a[:60]!r}")
    if t == "starts":
        return (a.lower().lstrip("*_`\"' ").startswith(spec["expect"]), f"got {a[:60]!r}")
    if t == "number":
        # синтетическая метка «ответа не было» содержит счётчик токенов, и судья
        # выцеплял его как ответ модели: в логе стояло «got 1500.0» там, где
        # модель не сказала ничего (02.09.2026)
        if a.startswith("<NO ANSWER") or a.startswith("<TIMEOUT") or a.startswith("<ERROR"):
            return False, "ответа не было: " + a[:60]
        n = _num(a)
        if n is None: return False, "no number"
        ok = abs(n - spec["expect"]) <= spec.get("tol", 0.01)
        # «первое число длинного рассуждения» и «голое число» — разные вещи, и в
        # логе они выглядели одинаково; задача просит голый ответ, так что
        # вердикт тот же, но причина должна быть видна
        bare = a.strip().rstrip(".%").replace(",", ".").lstrip("*_`\"' ")
        tail = "" if _num(bare) is not None and len(bare) <= 12 else " (первое число ответа, не голое)"
        return (ok, f"got {n}{tail}")
    return False, "unknown check"

SELFTEST = [
    ("fenced json where the task forbids a fence", '```json\n{"ok": true}\n```', {"type":"json","keys":["ok"],"values":{"ok":True},"no_fence":True}, False),
    ("bare json where the task forbids a fence", '{"ok": true}', {"type":"json","keys":["ok"],"values":{"ok":True},"no_fence":True}, True),
    ("json ok", '{"file": "app/db.py", "line": 214}', {"type":"json","keys":["file","line"],"values":{"file":"app/db.py","line":214}}, True),
    ("json wrong line", '{"file": "app/db.py", "line": 215}', {"type":"json","keys":["file","line"],"values":{"file":"app/db.py","line":214}}, False),
    ("json in fence", '```json\n{"ok": true}\n```', {"type":"json","keys":["ok"],"values":{"ok":True}}, True),
    ("prose instead of json", 'The file is app/db.py at line 214.', {"type":"json","keys":["file"],"values":{"file":"app/db.py"}}, False),
    ("tool right", 'run_shell', {"type":"oneof","expect":["run_shell"]}, True),
    ("tool wrong", 'read_file', {"type":"oneof","expect":["run_shell"]}, False),
    ("tool with prose", 'run_shell — because we need the local python', {"type":"oneof","expect":["run_shell"]}, True),
    ("asked", 'ASK which server should it go to?', {"type":"starts","expect":"ask"}, True),
    ("guessed instead of asking", 'ssh deploy@prod ./deploy.sh', {"type":"starts","expect":"ask"}, False),
    ("number ok", 'The error rate is 3.6%', {"type":"number","expect":3.6,"tol":0.06}, True),
    ("number off", '3.9', {"type":"number","expect":3.6,"tol":0.06}, False),
    ("array ok", '["redis","postgres","nginx"]', {"type":"json_array","expect":["redis","postgres","nginx"]}, True),
    ("array with dup", '["redis","redis","postgres","nginx"]', {"type":"json_array","expect":["redis","postgres","nginx"]}, False),
]

def selftest():
    ok = True
    for name, ans, spec, want in SELFTEST:
        got, why = check(ans, spec)
        mark = "ok " if got == want else "!! "
        if got != want: ok = False
        print(f"  {mark}{name}: expected {want}, got {got} {why}")
    print("JUDGE SELFTEST:", "sound" if ok else "BROKEN")
    return ok

if __name__ == "__main__":
    sys.exit(0 if selftest() else 1)
