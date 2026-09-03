# Errata

Corrections to material already published. Nothing in `ep01-local-llm-bench/` is
edited after the fact — those files are the record of what the video actually
showed. Errors are listed here instead, with the numbers they changed.

---

## EP01 — two of the twenty tasks were broken (found 2026-09-02)

While building the next episode I ran the same 20 tasks against a second system.
Both sides failed the same task with the same complaint, which is how the bug
surfaced: when every model fails one item for the same reason, suspect the item.

### 1. `data-03` could not be answered by anyone

The prompt begins *"Same table. Which engine has the best (lowest) WER?"* — but
the table is not in it. `data-01` and `data-02` each carry the table inline;
`data-03` does not. Every task is a separate, independent call with no history,
so no model could see what it was being asked about.

Two of the four models said so plainly and were marked wrong for it:

```
ornith-agent  → "The user is asking about a table, but I don't see any table
                 in this conversation"
```

That is the correct behaviour for an agent handed incomplete input, and the
bench scored it as a failure.

**Effect:** every model lost exactly 1 of 20, uniformly. The ranking shown in
the video is unchanged; the percentages are not. `qwen3.5:9b` was presented as
14/20 = 70%. Excluding the broken task it is 14/19 = 73.7%.

### 2. `data-04` demanded a bare answer without asking for one

The strict judge takes the first number in the reply. Three of the four numeric
tasks say *"Answer with the number only"*. `data-04` did not — it said only
*"Answer with the ratio worst/best, rounded to a whole number."*

Models that computed the ratio correctly and showed their work were failed on a
formatting rule that was never stated. This is not strictness; the requirement
has to be made before it can be enforced.

**Effect:** an unknown number of failures on `data-04` were not model errors.
The re-run below separates them.

### What changed

- `tasks.json` fixed: `data-03` now carries the table; `data-04` now says
  *"Answer with the number only."*
- `tasks_check.py` added — a guard over the task file with a self-test. It
  rejects a task that refers to data it does not contain, and a task whose judge
  wants a bare value without saying so. Both original defects are wired into the
  self-test as controls: if the guard ever stops catching them, the self-test
  fails.
- `run.py`: a timeout is now logged as `TIMEOUT` with the limit that was in
  force, not as a plain failure. A model that was never waited for long enough
  used to look identical to a model that got the answer wrong.

### Corrected numbers

The four models were re-run on the fixed task set (2026-09-02, same judge, same
hardware, `ASK_TIMEOUT=600`). Raw log: `ep01-local-llm-bench/corrected/`.

| model | in the video | fixed task set | change |
|---|---|---|---|
| `qwen3.5:9b` | 14/20 = 70% | **15/20 = 75%** | +1 |
| `ornith-agent` 9B | 4/20 = 20% | 4/20 = 20% | — |
| `prompt-builder` 27B | 4/20 = 20% | 4/20 = 20% | — |
| `distill-agent` 9B | 1/20 = 5% | 1/20 = 5% | — |

The fix moved exactly one strict number. Only `qwen3.5:9b` had been answering
those two tasks well enough to be robbed by them; the other three were failing
them for their own reasons. The ranking in the video stands.

**The lenient side did move, and an earlier version of this page said it would
not.** The video's "95%" was 19/20 on the lenient judge for `ornith-agent` and
`distill-agent` — and the one task each of them missed was `data-03`, the broken
one. On the fixed set both score 20/20 under the lenient judge:

| model | lenient, in the video | lenient, fixed set | strict, fixed set |
|---|---|---|---|
| `ornith-agent` 9B | 19/20 = 95% | **20/20 = 100%** | 4/20 = 20% |
| `distill-agent` 9B | 19/20 = 95% | **20/20 = 100%** | 1/20 = 5% |
| `qwen3.5:9b` | 14/20 | 15/20 | 15/20 |
| `prompt-builder` 27B | 4/20 | 4/20 | 4/20 |

So the headline comparison is not "95% or 5%" but "100% or 5%": the gap between
the two judges got wider, not narrower. Raw log with both verdicts per answer:
`ep01-local-llm-bench/corrected/rerun-20260902.jsonl` (re-judged after the judge
fix below, so its `why` field matches the current judge).

An earlier version of this page estimated the effect arithmetically — "every
model loses 1 of 20, so score out of 19, qwen at 73.7%". That was wrong. The
fixed `data-03` is answerable, so the denominator stays 20, and the measured
result is 75%. The estimate is left mentioned here rather than quietly deleted.

To see the defects yourself:

```
python3 tasks_check.py --selftest    # 5/5, both defects wired in as controls
python3 tasks_check.py               # flags data-03 and data-04 in the EP01 set
```

### One more thing the re-run exposed

`run.py` used a 180 s timeout by default. The 27B model needs a median of 209 s
per task in the August run and 214 s in the September re-run, so re-running it
with the default silently scored 19 of 20 tasks as failures — a model that was never waited for long enough looked exactly like a
model that got the answer wrong. Timeouts are now logged as `TIMEOUT` together
with the limit that was in force.

The judge had a smaller version of the same problem: when a model returned
nothing, the placeholder text `<NO ANSWER: thinking only, 1500 tokens>` was fed
to the numeric check, which dutifully reported `got 1500.0`. The verdict was
correct either way, but the log read as if the model had answered 1500. Fixed
and verified against 120 stored answers: zero verdicts moved.
