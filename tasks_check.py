#!/usr/bin/env python3
"""Guard over the task file.

Two defects shipped in EP01 and were only found while building EP02:
`data-03` referred to a table that was not in its own prompt, and `data-04`
required a bare number without ever asking for one. Both are wired into the
self-test below as controls — if this guard stops catching them, the self-test
fails and says so.

Rules:
  R1  a prompt that refers to earlier data ("same table", "the table above",
      "previous") must carry that data itself — every task is an independent
      call with no history between them;
  R2  a task whose judge wants a bare value (number / oneof) must say "only"
      in the prompt, otherwise the format is demanded silently;
  R3  a numeric answer must be derivable from numbers present in the prompt.

Usage:  python3 tasks_check.py --selftest
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BARE = ("number", "oneof")
# "starts" is deliberately absent: it only checks the beginning of the reply,
# and the trailing text is part of the task ("ASK followed by one question").
REFERS = re.compile(r"\b(same table|the table above|previous (table|answer|question)|as above)\b", re.I)
# a data row: two or more space-separated fields on one line. The inner spacing
# must not match a newline, or the pattern swallows the whole prompt as one row.
DATAROW = re.compile(r"^[^\S\n]*\S+(?:[^\S\n]+\S+)+[^\S\n]*$", re.M)


def rules(t):
    bad = []
    p, c = t["prompt"], t["check"]
    if REFERS.search(p):
        digits = sum(ch.isdigit() for ch in p)
        if digits < 8 or len(DATAROW.findall(p)) < 2:
            bad.append("R1 refers to earlier data that is not in the prompt")
    if c["type"] in BARE and "only" not in p.lower():
        bad.append(f"R2 judge '{c['type']}' wants a bare value, prompt never says 'only'")
    if c["type"] == "number":
        if not re.findall(r"-?\d+(?:\.\d+)?", p.replace(",", ".")):
            bad.append("R3 numeric answer expected, prompt contains no numbers")
    return bad


SELFTEST = [
    # (task, should the guard flag it?)
    ({"prompt": "Same table. Which engine is best? Answer with the name only.",
      "check": {"type": "oneof", "expect": ["kokoro"]}}, True),   # the real data-03 defect
    ({"prompt": "Log:\n  a 1\n  b 2\nGive the ratio.",
      "check": {"type": "number", "expect": 2}}, True),           # the real data-04 defect
    ({"prompt": "From this table pick the lowest. Answer with the name only.\n"
                "engine  WER\nkokoro  0.0066\nindex   0.0199",
      "check": {"type": "oneof", "expect": ["kokoro"]}}, False),
    ({"prompt": "Same table. Which engine is best? Answer with the name only.\n"
                "engine  WER\nkokoro  0.0066\nindex   0.0199",
      "check": {"type": "oneof", "expect": ["kokoro"]}}, False),  # refers, data present
    ({"prompt": "If the task is unambiguous, answer with the command. If information is "
                "missing, answer with the single word ASK followed by one question.",
      "check": {"type": "starts", "expect": "ask"}}, False),      # 'starts' is not a bare value
]


def main():
    if "--selftest" in sys.argv:
        bad = 0
        for i, (t, want) in enumerate(SELFTEST, 1):
            got = bool(rules(t))
            if got != want: bad += 1
            print(f"  control {i}: expected {'flag' if want else 'clean'}, got "
                  f"{'flag' if got else 'clean'}  {'ok' if got == want else 'BROKEN'}")
        print(f"selftest: {len(SELFTEST)-bad}/{len(SELFTEST)}")
        if bad: sys.exit(1)
    cands = [os.path.join(ROOT, "tasks", "tasks.json"),
             os.path.join(ROOT, "ep02-claude-vs-local", "tasks", "tasks.json"),
             os.path.join(ROOT, "ep01-local-llm-bench", "tasks", "tasks.json")]
    path = next((c for c in cands if os.path.exists(c)), None)
    if path is None:
        # a guard that silently checks nothing is worse than no guard
        print("no tasks.json found in: " + ", ".join(os.path.relpath(c, ROOT) for c in cands))
        sys.exit(2)
    print(f"file: {os.path.relpath(path, ROOT)}")
    ts = json.load(open(path))
    found = 0
    for t in ts:
        for b in rules(t):
            print(f"  FAIL {t['id']}: {b}")
            found += 1
    print(f"tasks checked: {len(ts)}, violations: {found}")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
