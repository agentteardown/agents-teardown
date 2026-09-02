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

The four models are being re-scored on the fixed task set; the table lands here
with the next episode, together with the raw log. The EP01 files stay exactly as
published — this page is the correction, not a rewrite of the record.

To see the defects yourself:

```
python3 tasks_check.py --selftest    # 5/5, both defects wired in as controls
python3 tasks_check.py               # flags data-03 and data-04 in the EP01 set
```
