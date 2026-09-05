# EP02 — Claude Code vs four local models, same 20 tasks, strict judge

Everything the video says comes from these files.

- `tasks/tasks.json` — the fixed task set (see `../ERRATA.md` for what was broken).
- `run.py` — local models through Ollama. `ASK_TIMEOUT` and `NUM_PREDICT` are env vars
  and are printed in the run header; both decided results in this episode.
- `run_cc.py` — Claude Code in print mode, empty folder, `--restricted` (no shell, no
  code execution), cost and tokens per call from the CLI's JSON output.
- `judge.py` — strict judge, code only; `soft_judge.py` — lenient judge. On 2026-09-03 the
  strict judge stopped forgiving a markdown fence where the task forbids one (`no_fence`
  in `tasks.json`, fmt-01). All logs here are re-judged with that judge; the only verdicts it
  moved were haiku's fmt-01 in runs 1 and 3 (20/20 → 19/20).
- `tasks_check.py` — guard over the task file, both EP01 defects as self-test controls.
- `make_facts_ep02.py` → `logs/facts-ep02.json` — the only file the video reads.

Logs:
- `cc-20260902-1726.jsonl` — haiku + sonnet on the BROKEN task set: the run that exposed
  the bug (both models: "I don't see a table").
- `cc-20260902-1741.jsonl` — haiku + sonnet, run 1 on the fixed set (the one shown in tables);
  `cc-20260903-1007.jsonl`, `cc-20260903-1010.jsonl` — runs 2 and 3. Token accounting in
  run 1 omits cache-creation tokens (fixed in `run_cc.py` before runs 2–3); the video quotes
  input tokens from runs 2–3.
- `run-20260902-2104.jsonl` — qwen3.5 / ornith / distill, cap 1500, timeout 600.
- `run-20260902-1937.jsonl` — prompt-builder 27B, cap 1500, timeout 600.
- `run-20260902-1836.jsonl` — 27B at the default 180 s timeout: 19 of 20 TIMEOUT. Kept
  on purpose — this is the harness failure the video talks about.
- `run-20260903-1007.jsonl` — qwen3.5 with `NUM_PREDICT=4000`: 20/20.
- `ollama-models-20260831.json` — model sizes from `ollama /api/tags`.

Not yet done: the 27B at cap 4000. It is the next episode.
