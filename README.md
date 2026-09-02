# Agent Teardown — receipts

Every number said on the channel comes from a real run with a saved log.
This repository holds those runs: the scripts, the raw logs, and the exact
data that was measured. No number appears on screen unless it is in a file here.

| episode | what was measured | folder |
|---|---|---|
| EP01 | four local LLMs, 20 agent tasks, two judges — 95% or 5% | [`ep01-local-llm-bench`](ep01-local-llm-bench) |

Corrections to published material are in [`ERRATA.md`](ERRATA.md). Two of the
twenty EP01 tasks turned out to be broken; the original files are left exactly
as they were and the correction is written down instead.

`tasks_check.py` guards the task file against both defects and carries them as
controls in its self-test: `python3 tasks_check.py --selftest`.

Channel: **Agent Teardown** — teardowns of AI tooling, measured instead of reviewed.
