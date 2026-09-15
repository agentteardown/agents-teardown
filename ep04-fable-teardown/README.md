# EP04 — Claude Fable 5.1 on the same seven repo tasks, with tests it cannot read

Everything the video says comes from these files. Same 7 repository tasks, same judge and the same
hidden tests as EP03; the model is the cloud one now — Claude Code in print mode with
`claude-fable-5-1`, 3 series × 7 tasks = 21 runs (2026-09-09, 09:05–09:11). A fourth series
(09:55–09:57) was run under a GPU power collector: it is a separate block and is NOT part of the 21.

## Stand

- `repo-tasks/make.py` — builds the 7 task sandboxes (t1 bug in calc.py, t2 slugify to spec,
  t3 refactor report.py to fewer AST nodes, t4 `--chars` flag + README, t5 contradictory ticket →
  reply `ASK`, t6 hard-coded secret → env, t7 `has_duplicates` from O(n²) to fast). Byte-identical
  to the EP03 copy: sha256 `66be4566a38cb5e63ad80b07b515557358c52e9fd5348f0489bf272f2e29e0e0`.
- `repo-tasks/judge_repo.py` — the judge: copies the original tests from a clean checkout over the
  agent's code, adds hidden tests, runs `pytest -p no:cacheprovider`, demands exactly N passed; a run
  that changed a protected file fails before any test runs. `--selftest` runs 7 cases — an honest fix
  plus 6 control mutants (edited test, conftest skip, `addopts -k`, module-level skip, deleted test,
  answer fitted to the test).
  Byte-identical to the EP03 copy: sha256 `c012de0880f866bbda8fa6e740f634dcbbaf3f9917d1da30b279f84fc75eb23f`.
  Hidden tests exist for 6 tasks of 7 (t1, t2, t3, t4, t6, t7); t5 is judged by an empty diff of the
  protected files plus an `ASK` reply.
- `repo-tasks/run_cc_repo.py claude-fable-5-1 [tN…]` — the runner, same file as EP03
  (sha256 `5eda7f4d0eab995a2ca52e4c2f1c94af894bb6f23ee1ffa2006121b72b61170c`): `claude -p --model … 
  --allowedTools Bash,Read,Edit --output-format json`, one temp sandbox per run, subprocess timeout
  1200 s (never hit). Turns, usage and cost come from the CLI's JSON answer; the tool calls and the
  first-request token count come from the Claude Code session log.
- `repo-tasks/run_dsh.py`, `repo-tasks/run_opencode.py`, `repo-tasks/run_hermes.py` — the three other
  harnesses. They are here only for the one-task board below, not for the 21 runs. `run_dsh.py`
  differs from the EP03 copy in one thing: the 900 s timeout became the `DSH_TIMEOUT` env var.
- `ollama.yml`, `ollama-27b.yml` — dsh profile overlays that point the harness at a local Ollama
  (provider id `llm-pi-ai`, OpenAI-style endpoint, any string as the API key — the harness refuses to
  start without one). The host address is stripped to `<host>`.
- `make_facts_ep04.py` → `logs/facts-ep04.json` — the only file the video reads. Every key in
  `derived` carries a `src` field naming the file and the way it was counted.
  `python3 make_facts_ep04.py --selftest` → 12/12 (counts recomputed independently with `grep`, `jq`
  and `awk`, plus a control defect on a temp copy that moves all three counters).

## Reproduce

```
python3 repo-tasks/judge_repo.py --selftest          # 1 honest fix + 6 control mutants
python3 repo-tasks/run_cc_repo.py claude-fable-5-1   # one series of 7 → logs/cc-repo-…jsonl
python3 make_facts_ep04.py --selftest                # numbers + self-check
```

`make_facts_ep04.py` is shipped exactly as it ran, so it reads more than this folder holds: EP03's
`facts-ep03.json`, `dsh-qwen3.5_9b-ctx32k-20260905-*.jsonl`, `dsh-lost-runs.jsonl` and
`power-20260905-0440.csv` (they live in `../ep03-dsh-teardown/logs/`), two earlier OpenCode probes of
2026-09-08 that are not shipped here, and the Claude Code session logs under `~/.claude/projects/` for
its independent cross-check of the tool-call count. Re-running it verbatim therefore needs the whole
bench directory; the numbers it produced are in `logs/facts-ep04.json`.

Three series were run back to back and timed by their own START/END stamps
(`logs/fable-batch-20260909-090524.out`). The fourth series was run the same way with a power
collector alongside it: `nvidia-smi --query-gpu=power.draw,memory.used,utilization.gpu` once a
second into `logs/power-fable-20260909-095511.csv` (columns: epoch, W, MiB, %) — the same collector
and the same card as EP03, started before the series and stopped after it
(`logs/fable-power-20260909-095511.out` carries the START/END epochs used as the window).

## Logs

- `logs/cc-repo-claude-fable-5-1-20260909-{090524,090724,090911}.jsonl` — the 21 runs, 7 records
  each: task, verdict, why, wall seconds, `duration_api_ms`, turns, usage, cost meter, tool calls,
  first-request tokens. These three files are the 21.
- `logs/cc-repo-claude-fable-5-1-20260908-212958.jsonl` — a **probe** on t1 the evening before
  (ok, 18.3 s, 4 turns, 3 Bash calls, meter $0.2601, Claude Code 2.1.263). NOT part of the 21 and not
  in any number above.
- `logs/cc-repo-claude-fable-5-1-20260909-095516.jsonl` — the fourth series, run under the power
  collector. Also NOT part of the 21.
- `logs/fable-batch-20260909-090524.out`, `logs/fable-power-20260909-095511.out` — console output of
  the batches with the per-task lines and the `→ 7/7` summaries; the second one also carries
  START/END epochs and the sample count.
- `logs/power-fable-20260909-095511.csv` — GPU power log of the fourth series, one sample per second.
- `logs/traces/tN-sM.txt` — every one of the 21 runs as a plain-text trace: `call <tool> <input>` /
  `res` / `ERR` lines pulled from the Claude Code session log, same format as the EP03 traces. The
  file name is task and series: `t1-s1` … `t7-s3`. Series 1 = sandbox `rt-cc-ksq0at4v`,
  series 2 = `rt-cc-nwatg0rm`, series 3 = `rt-cc-o22ckpv7`. The three `t5-*.txt` files are empty on
  purpose: those runs made no tool calls at all. The four `ERR` lines of caveat 3 are in `t7-s1`,
  `t2-s3`, `t3-s3` and `t7-s3`.
- Board probes (one task, t1, different days — see the board below):
  `logs/opencode-qwen3.5_9b-ctx32k-20260908-202345.jsonl` with its event log
  `logs/opencode-events/tmp-rt-oc-l1gjtqh4-t1.jsonl`;
  `logs/hermes-qwen3.5_9b-ctx64k-20260908-205139.jsonl` (the run that passed),
  `logs/hermes-qwen3.5_9b-ctx32k-20260908-202434.jsonl` (Hermes refusing a 32k model verbatim),
  `logs/hermes-qwen3.5_9b-ctx64k-20260908-202610.jsonl` (900 s timeout: the first 64k attempt without
  `TERMINAL_CWD` — a harness property, the model was looking at the wrong working directory),
  `logs/hm-timing-204231.out` (an empty Hermes call: 20 552 input tokens for one API call, 43 s wall).
- `logs/probe27b-211810.out`, `logs/dsh-qwen3.8-27b-gsq-ctx32k-20260908-211955.jsonl` — the 27B probe.

## Headline numbers (from `facts-ep04.json`)

| | Claude Code + Fable 5.1 | Claude Code + 9B (EP03) | DeepSeek Harness + 9B (EP03) |
|---|---|---|---|
| runs passed | 21 / 21 (7/7, 7/7, 7/7) | 14 / 21 | 12 / 21 |
| seconds per passed task | 16.0 | 405 | 362 |
| tool calls | 41 (all Bash) | 271 | 220 |
| turns | 62 | 294 | — |
| tokens before the task (first request) | 19 675 | 21 241 | 7 988 |
| t5, the contradictory ticket | 3 / 3 | 0 / 3 | 0 / 3 |

- Per-task wall clock (`claude -p`, subprocess): min 5.9 s, median 16.2 s, max 27.9 s; 335.7 s over the
  21 runs, of which 310.1 s is `duration_api_ms`. The whole batch of 21: 09:05:24 → 09:11:03, 340 s.
- Tool calls: 41, every one of them Bash. `Read` 0 and `Edit` 0 although both were allowed — the model
  edited with `sed -i` and `cat > file <<'EOF'` from Bash. Three runs made no calls at all: all three t5.
- Input tokens over the 21 runs: 1 259 776 (input 1 354 + cache read 1 031 285 + cache creation
  227 137) — 82 % of the input is a cache read. Output: 16 307.
- Cost **meter**: $5.6507 total, $0.2691 per task, $0.2081 (t5) … $0.3075 (t7) per run; per series
  $1.8913 / $1.8629 / $1.8965. See caveat 2.
- EP03's cloud ceiling on the same tasks, one series of 7 each: haiku 7/7 for a $0.24 meter, sonnet
  7/7 for $0.63.
- t5 in all three series: 1 turn, 0 tool calls, 5.9–7.4 s, and a reply that starts with `ASK` and names
  both 3.12 and 3.11. In EP03 the same task was 0 of 6.
- Claude Code version: 2.1.265 in all four series, 2.1.263 in the probe of 2026-09-08.

### The fourth series, under the power collector (not part of the 21)

7/7; window START–END 09:55:16–09:57:35 = 139 s; sum of per-task seconds 136.9; 22 turns; 15 Bash
calls; meter $1.9127; first request 19 674…19 732; t5 asks again, naming 3.12 and 3.11.

GPU in that window: mean 30.3 W (min 28.91 / median 30.15 / max 32.88), 128 samples inside the window
out of 137 in the file (12 gaps of 2 s), memory 1 633–1 746 MiB, utilisation ≤ 9 %. Energy by the EP03
method (mean W × 139 s / 3600) = **1.168 Wh** for the series, 0.167 Wh per task; a step-function
control over the real intervals gives 1.167.

EP03 on the same card with the same collector: 11.2 Wh (dsh) and 16.1 Wh (Claude Code) per passed task,
at 103 W and 143 W mean under load; idle 27 W, peak 177 W. That is 67.1× and 96.4× more than 0.167 Wh —
but read caveat 1 before saying it out loud: 30.3 W is the local card **idling** while the model runs
in a datacentre.

## The board: the same 9B in four harnesses (t1 only)

Probes, not a benchmark: one task, different days, one run each for OpenCode and Hermes.

| harness | date | t1 | tokens in the first request | tool calls |
|---|---|---|---|---|
| DeepSeek Harness | 2026-09-05 | ok, 78.0 / 25.6 / 90.2 s (median 78) | 7 988 | 22 calls, 3 errors over 3 runs |
| OpenCode | 2026-09-08 | ok, 91.9 s | 16 476 (118 742 over 7 steps) | 8 calls, 1 `invalid` — the model called a tool named `run` that does not exist |
| Hermes Agent | 2026-09-08 | ok, 147.4 s | 20 552 for an empty call | 9 API calls, 191 119 in / 761 out |
| Claude Code + 9B | 2026-09-05 | ok, median 121 s | 21 241 | 17 calls over 3 runs |
| Claude Code + Fable | 2026-09-09 | ok, 14.6 / 14.9 / 16.2 s | 19 675 | 9 calls over 3 runs |

Hermes refuses a 32 k model outright (`logs/hermes-qwen3.5_9b-ctx32k-20260908-202434.jsonl`: "…below
the minimum 64,000 required by Hermes Agent"), so it ran on the `qwen3.5:9b-ctx64k` tag; it also ran
over ssh in a VM, so its 147.4 s includes the network. Its first 64 k attempt hit the 900 s timeout —
that run had no `TERMINAL_CWD` and the agent was looking at the wrong directory: a harness property,
not a model one.

## 27B — one probe

`qwen3.8-27b-gsq` (26.9B, IQ3_S): 12.02 GB in `ollama ps`, 14 199 of 16 311 MiB of VRAM, 28.0 tok/s on
200 tokens, 6.5 s to load, tool calling works. One dsh run on t1: ok in 44.5 s, against the 9B's dsh
median of 78 s on the same task. That is the whole measurement — no series, no other tasks, no watts.

## Caveats

1. **Watts.** There is no power log for the 21 runs (09:05–09:11): the collector was not running. The
   only measured window is the fourth series, and 30.3 W there is the power of the local card while it
   idles — the model works in a datacentre whose energy is unknown and is not claimed. "67× less" means
   "this is what a card that is doing nothing draws". Do not carry 0.167 Wh over to the 21 runs.
2. **Cost.** `cost_usd` is the `total_cost_usd` counter in Claude Code's JSON answer, not an invoice and
   not a charge; the runs went on a subscription. Say "$5.65 by the Claude Code meter", not "it cost $5.65".
3. **"Zero tool errors" is wrong.** The sessions contain 4 `tool_result` blocks with `is_error`
   (series 1 t7; series 3 t2, t3, t7). All four are non-zero exit codes of the model's own diagnostic
   commands (pytest before the fix: exit 1 "tests fail", exit 5 "no tests collected" inside a `for`
   loop). The correct statement is "not one invalid tool call and not one failed edit".
4. **No tokens/second and no API latency for Fable**: the log holds only `sec` (subprocess wall clock,
   including the `claude` start-up) and `api_ms`.
5. **haiku and sonnet from EP03 are one series of 7 each**, not 21. Compare per series
   ($0.24 / $0.63 / $1.88) or by pass rate, never "21 against 7".
6. **The four-harness board is probes** on one task, on different days: dsh and Claude Code + 9B on
   09-05 (three runs each), OpenCode and Hermes on 09-08 (one run each). Hermes ran on a different model
   tag and over ssh. This is not "3×7 on one card at one time".
7. **OpenCode's 91.9 s**: the events cover 15.9 s of it; what the other ~76 s were spent on the log does
   not say (harness start-up, model load — a guess). The `errors: 0` field in the record is a stale
   counter; count `invalid` from the events.
8. **The Hermes 900.5 s timeout** does not name its own cause: `usage_and_stderr` is empty in that
   record. The `TERMINAL_CWD` link comes from neighbouring checks, not from the run itself. Say only:
   "the first 64 k attempt hit the 900 s timeout; after the cwd fix it passed".
9. **27B**: one t1 probe in dsh and one 28 tok/s measurement on 200 tokens. No series, no other tasks,
   no watts. Only "it started, it fit, it solved one task in 44.5 s".
10. **`reply` is truncated to 400 characters by the runner.** The t5 replies (120–239 characters) are
    complete; every other `reply` is a fragment and must not be quoted as a full answer.
11. **19 675 against 21 241** was counted the same way (`session_stats` in `run_cc_repo.py`, the usage of
    the first answer), but the Claude Code versions differ (2.1.265 here, an older one in EP03), so the
    1 566-token gap is not only "a different model".
12. **"Tests it cannot read"** means the judge's `test_hidden.py` (6 tasks of 7). The task's own
    `test_*.py` files are visible and the agent does read them — `cat test_*.py` shows up in the traces.

## Sessions

The raw Claude Code session logs of the 21 runs are **not** in this folder. Each of them carries the
verbatim Claude Code system prompt, the operator's e-mail address and absolute home paths, and
sanitising them would mean rewriting the artefact rather than publishing it. What the video actually
uses out of them — every tool call and its result — is in `logs/traces/` in the EP03 trace format; the
41 calls counted there match `facts-ep04.json`. The raw sessions are available on request.

Host addresses and personal paths are stripped everywhere in this folder: `<host>`, `<home>`,
`<win-home>`.

## Licence

Same as the rest of this repository: the scripts and logs here are the channel's own material, and no
separate licence file is shipped with EP01–EP03 either. Third-party names (Claude Code, DeepSeek
Harness, OpenCode, Hermes Agent, Ollama, Qwen) belong to their owners; nothing of theirs is
redistributed here beyond command lines and measured numbers.
