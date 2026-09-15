# EP03 — one 9B model, two harnesses: DeepSeek Harness vs Claude Code, every tool call counted

Everything the video says comes from these files. Same local model (qwen3.5 9B via Ollama,
`num_ctx 32768`), same 7 repository tasks, 3 runs per task per harness, one judge.

## Stand

- `repo-tasks/make.py` — builds the 7 task sandboxes (t1 bug in calc.py, t2 slugify to spec,
  t3 refactor report.py to fewer AST nodes, t4 `--chars` flag + README, t5 contradictory ticket →
  reply `ASK`, t6 hard-coded secret → env, t7 `has_duplicates` from O(n²) to fast).
- `repo-tasks/judge_repo.py` — the judge: copies the original tests from a clean checkout over
  the agent's code, adds hidden tests, runs `pytest -p no:cacheprovider`, demands exactly N
  passed; a run that changed a protected file fails before any test runs. `--selftest` = 7 control
  mutants.
- `repo-tasks/run_dsh.py <model> [tN…]` — DeepSeek Harness 0.1.2-rc.1, headless, patched to a
  local Ollama (`ollama.yml`: provider id `llm-pi-ai`, OpenAI-style endpoint, any string as the
  API key — the harness refuses to start without one).
- `repo-tasks/run_cc_repo.py local:<model>|haiku|sonnet [tN…]` — Claude Code in print mode;
  `local:` goes through `ANTHROPIC_BASE_URL` to the same Ollama (0.32.1 serves the
  Anthropic-style messages endpoint).
- `repo-tasks/main_loop.sh` — the 3×7×2 batch with START/END stamps (resumable).
- `repo-tasks/dsh_calls.py`, `repo-tasks/cc_errors.py` — count every tool call and error from the
  session logs (dsh: `~/.dsh/sessions/*/session-*/session.jsonl.zstd`; Claude Code:
  `~/.claude/projects/<slug>/*.jsonl`). `dsh_trace.py` prints one dsh session as a trace.
- `repo-tasks/summary_ep03.py`, `make_facts_ep03.py` → `logs/facts-ep03.json` — the only file the
  video reads. Watt-hours = mean `nvidia-smi power.draw` over the run (1 sample/s) × seconds.

## Logs

- `logs/dsh-qwen3.5_9b-ctx32k-20260905-*.jsonl`, `logs/cc-repo-local-qwen3.5_9b-ctx32k-20260905-*.jsonl`
  — one line per run: task, verdict, why, seconds, and for Claude Code turns/tokens/tool calls.
  Two runs (t6, then t1) were re-done because the log file name was per-minute and a next task
  overwrote the previous file; file names now carry seconds.
- `logs/main-20260905-0440.out` — START/END stamps of the batch; the batch was interrupted twice
  (machine sleep) and resumed from the last task, which is visible in the RESTART lines.
- `logs/power-20260905-0440.csv` — GPU power log, one sample per second.
- `logs/dsh-calls.json` — per-run tool calls, errors, error kinds and errors per tool for DeepSeek Harness.
- `logs/traces/` — every counted run as a plain-text trace: `dsh-*.txt` (tool/call, result, isError,
  from the dsh session log) and `cc-*.txt` (tool_use / tool_result from the Claude Code session
  log). The two `*-EXCLUDED-rerun.txt` files are re-done runs that are NOT counted (see below).
- `logs/dsh-lost-runs.jsonl`, `logs/cc-lost-runs.jsonl` — three runs whose per-run log file was
  overwritten by the next task finishing in the same minute (dsh t6 run 1: FAIL in 23.6 s; dsh t1
  run 2: pass in 25.6 s; Claude Code t6 run 3: pass in 32.5 s). Their verdicts and seconds are
  taken from `main-20260905-0440.out`, their tool calls from the surviving session logs. The
  re-done runs made the same day are excluded from every number in the video.
- `logs/cc-repo-sonnet-20260905-0035.jsonl`, `logs/cc-repo-haiku-20260905-0037.jsonl` — the cloud
  ceiling on the same tasks (7/7 each).

## Headline numbers (from `facts-ep03.json`)

| | DeepSeek Harness + 9B | Claude Code + 9B |
|---|---|---|
| runs passed | 12 / 21 | 14 / 21 |
| tool calls / errors | 220 / 33 | 271 / 33  |
| per passed task | 362 s · 11.2 Wh | 405 s · 16.1 Wh |
| tokens before the task (first request) | 7 988 | 21 241 |

Caveat: the third batch (after 09:25) shared the card with another model for part of the time;
medians per task are unaffected, the absolute Wh of that batch are an upper bound. The first
attempt at the power measurement had a foreign process on the card and was discarded entirely.
