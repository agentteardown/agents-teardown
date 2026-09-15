# Agent Teardown — receipts

Every number said on the channel comes from a real run with a saved log.
This repository holds those runs: the scripts, the raw logs, and the exact
data that was measured. No number appears on screen unless it is in a file here.

| episode | what was measured | folder |
|---|---|---|
| EP01 | four local LLMs, 20 agent tasks, two judges — 95% or 5% | [`ep01-local-llm-bench`](ep01-local-llm-bench) |
| EP02 | Claude Code (haiku, sonnet) vs four local models, same 20 tasks, strict judge — a free 9B at 20/20 after the harness cap was raised | [`ep02-claude-vs-local`](ep02-claude-vs-local) |
| EP03 | one 9B model (qwen3.5 9B, Ollama) in two harnesses — DeepSeek Harness vs Claude Code, same 7 repo tasks, 3 runs each, one judge, every tool call counted | [`ep03-dsh-teardown`](ep03-dsh-teardown) |
| EP04 | Claude Fable 5.1 (Claude Code) on the same 7 repo tasks with hidden tests — 21 of 21, 16 s per task, against the 9B's 12 and 14 of 21 | [`ep04-fable-teardown`](ep04-fable-teardown) |

Corrections to published material are in [`ERRATA.md`](ERRATA.md). Two of the
twenty EP01 tasks turned out to be broken; the original files are left exactly
as they were and the correction is written down instead.

`tasks_check.py` guards the task file against both defects and carries them as
controls in its self-test: `python3 tasks_check.py --selftest`.

Channel: **Agent Teardown** — teardowns of AI tooling, measured instead of reviewed.
