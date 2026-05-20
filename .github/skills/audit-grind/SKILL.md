---
name: audit-grind
description: >-
  Drains the codebase audit backlog by dispatching specialized Copilot
  sub-agents in parallel. Reads pending todos (or mines docs/audits/*.md when
  the queue is empty), assigns each item to the correct persona in
  .github/agents/, dispatches up to 6 background sub-agents per cycle, then
  validates with build + pytest. Designed to be invoked on a recurring schedule
  via `/every 30m /audit-grind` so progress compounds while the operator is AFK.
user-invocable: true
scope: workspace
tags: [audit, backlog, fleet, dispatch, automation]
---

# Audit Grind — Backlog Dispatcher

## Purpose

This repo (DUKE3D: NEON NOIR) has a multi-agent codebase audit system that
generates findings faster than a single operator can address them. This skill
is the autonomous grinder: it picks the next batch of high-value work off the
audit backlog and dispatches specialized sub-agents in parallel to chew it
down — every 30 minutes by default.

You (the assistant) execute this skill end-to-end without asking the user for
input. The user has already approved the loop by invoking `/every`.

## Inputs

- **Audit reports**: `docs/audits/*.md` (one per persona) + `SUMMARY.md`
- **Personas**: `.github/agents/*.agent.md` (currently 10)
- **Todo state**: SQLite session table `todos(id, title, description, status)`
  with optional `todo_deps(todo_id, depends_on)`

## Execution Protocol

Run each step in order. Do not skip steps. Do not ask the user for input.

### 1. Health check (always first)

```bash
make clean && make -j$(nproc) 2>&1 | tail -5
python3 -m pytest -q 2>&1 | tail -5
```

Record baseline pass/fail counts. If `make` is already broken before you
dispatch anything, **STOP** — write a brief diagnostic report to
`docs/audits/RUN_<timestamp>.md` explaining the breakage, mark this run as
blocked in the todo table, and exit. Do not pile new work on a broken tree.

### 2. Pull the backlog

```sql
SELECT id, title, description FROM todos
WHERE status = 'pending'
  AND id NOT IN (
    SELECT td.todo_id FROM todo_deps td
    JOIN todos t ON td.depends_on = t.id
    WHERE t.status != 'done'
  )
ORDER BY ROWID
LIMIT 12;
```

If the result has rows, take the top **6** (skip dependencies that aren't
ready). Go to step 4.

### 3. Mine new work when the queue is empty

If step 2 returned 0 rows, harvest new todos by scanning audit reports:

1. Read `docs/audits/SUMMARY.md` — the "Critical & High Findings",
   "Cross-Cutting Themes", and "Prioritized Follow-Up Backlog" sections are
   the primary mine.
2. For any finding NOT already represented in the `todos` table (compare by
   title or file:line citation), `INSERT` it as a new pending todo. Assign:
   - `id` — short kebab-case, prefixed by domain (`fix-`, `add-`, `archive-`,
     `docs-`, `ci-`, `sec-`, `audio-`, `mp-`, `perf-`).
   - `description` — full enough that a sub-agent could execute it without
     re-reading the SUMMARY.
3. Cap mining at **10 new todos per run** to avoid backlog explosion.
4. Re-run step 2 to pick up the freshly seeded items.

If both the audit reports and the queue are exhausted, mine `IMPLEMENTATION_PLAN.md`,
the Roadmap section of `README.md`, and TODO/FIXME comments in `tools/`,
`compat/`, `source/`, `SRC/`. Pick the highest-leverage items only.

If after all of the above the backlog is genuinely empty, write a short status
report to `docs/audits/RUN_<timestamp>.md` declaring "backlog drained", do
nothing else, and exit cleanly.

### 4. Assign each todo to a persona

Match by domain. The mapping is exhaustive — every todo must map to exactly
one owning persona:

| Todo domain | Owner persona |
|-------------|---------------|
| K&R engine code, struct layouts, MMULTI, render loop | `engine-porter` |
| compat/ SDL2 driver, audio/network/mact stubs, msvc shim, pragmas | `compat-layer` |
| tools/ texture/map/GRP/palette/tables, FLUX, generate_assets | `asset-pipeline` |
| tools/generate_audio.py, voice catalog, audio_stub, SDL2_mixer | `audio-engineer` |
| Makefile, build.mk, CMakeLists.txt, build_windows.bat, CI workflows | `build-system` |
| tests/, pytest.ini, conftest, struct-size invariants | `test-engineer` |
| README, ARCHITECTURE.md, CONTRIBUTING, docs/audits/ index, doc drift | `documentation-curator` |
| .env*, .gitignore, secret scans, CVE posture, GPL compliance | `security-and-secrets` |
| SRC/MMULTI.C, networking, multiplayer test harness | `network-multiplayer` |
| tools/frame_analyzer.py, render-loop hotspots, perf regressions | `performance-profiler` |

If a todo touches multiple domains, assign the primary owner and tell the
sub-agent in its prompt which secondary personas to "consult" (i.e. read the
other agent files for context but do not split the work).

### 5. Dispatch (parallel, background)

Use the `task` tool with `agent_type: general-purpose`, `mode: background`,
`model: claude-haiku-4.5` (Haiku is fast and cheap; only escalate to Sonnet
for genuinely tricky work). Dispatch **up to 6 in the same response** —
parallel-safe because each touches different files. Each sub-agent prompt
MUST contain:

1. **Persona attribution**: "Adopt the `<persona>` persona
   (.github/agents/<persona>.agent.md)." If multiple personas are involved,
   name them all.
2. **Concrete task statement** copied/expanded from the todo description.
3. **File path citations** from the audit report so the sub-agent doesn't
   wander.
4. **Hard constraints**:
   - Do NOT commit to git unless the todo explicitly authorizes it. The
     operator reviews changes manually. (We learned this the hard way —
     earlier rounds had agents auto-committing.)
   - Do NOT modify files outside the persona's owned domain. If a fix
     requires cross-domain edits, stop and report.
   - Maintain the gnu89 / c11 standard split: SRC/ + source/ are gnu89;
     compat/ is c11.
   - Respect the memory-hack rules: no `/Tc` on .C files in CMake (rely on
     `LANGUAGE C`); `SDL2_VERSION` stays single-source in `build.mk`.
5. **Validation gates**:
   - `make clean && make -j$(nproc)` must succeed.
   - `pytest -q` must not regress (≥ baseline pass count from step 1).
   - Persona-specific extras (e.g. struct-size tests for engine-porter,
     `pytest tests/test_audio_pipeline.py` for audio-engineer).
6. **SQL bookkeeping**: on success run
   `UPDATE todos SET status='done' WHERE id='<todo-id>'`; on blockage run
   `UPDATE todos SET status='blocked' WHERE id='<todo-id>'` AND return a
   one-paragraph rationale.
7. **Return format**: short summary — files changed, validation outputs, any
   surprises.

Group the dispatch calls in **one single response** so they actually run in
parallel.

### 6. Wait, then verify

End your dispatch response with a one-line note that you're waiting on
notifications. When the runtime delivers completion notifications, read each
sub-agent's result with `read_agent`. For every one:

- If the sub-agent updated SQL correctly, proceed.
- If the sub-agent claimed success but SQL is still `pending`, set it to
  `done` yourself (verify the work landed first — `git status`, the file
  edit, the test pass).
- If the sub-agent reported `blocked`, leave the SQL row blocked and surface
  the blockage in the run report.

### 7. Post-run validation (always last)

Even though sub-agents validate individually, race conditions between
parallel `make clean` calls can corrupt the tree. Re-validate:

```bash
make clean && make -j$(nproc) 2>&1 | tail -10
python3 -m pytest -q 2>&1 | tail -5
```

Both must be green. If not, identify which sub-agent's change broke things
and surface it in the run report under "Human-attention items".

### 8. Write the run report

Append a section to `docs/audits/GRIND_LOG.md` (create if missing) with:

- Timestamp (ISO 8601)
- Todos picked up (id + title)
- Todos completed
- Todos blocked (with reason)
- Build/test deltas (pass count before → after)
- Notable findings (new bugs surfaced by sub-agents)
- Any human-attention items (commits made, decisions deferred)

Keep entries concise — this log is for the operator's morning standup, not a
novel.

## Hard Limits

- **Max 6 sub-agents per dispatch** (more = race conditions on `make clean`).
- **Max 10 new todos mined per run** (avoid runaway backlog growth).
- **No git commits** unless the todo's description says so explicitly.
- **No PR creation**. The operator handles PRs.
- **No long-running watchers**. Sub-agents must terminate.
- **No external API calls** with real credentials in sub-agent prompts. If a
  task requires FLUX or Azure audio, dispatch the `--no-ai` path.
- **Stop on a broken build**. Never compound damage on a red tree.

## Failure Modes & Recovery

| Symptom | Action |
|---------|--------|
| `make` fails at step 1 | Diagnose, write report, exit. Do NOT dispatch. |
| Sub-agent stuck running >10 min | `read_agent wait: false`; if still running, leave it — log it in GRIND_LOG and skip its todo for this cycle (it'll be re-picked next run). |
| Sub-agent committed unsolicited | Log loudly in GRIND_LOG under "Human-attention items"; do not revert (operator's call). |
| Two sub-agents edited overlapping files | Run `make` + `pytest` post-run; if green, leave; if red, mark both blocked and surface in the run report. |
| Backlog empty AND audits exhausted | Write "backlog drained" report, exit gracefully. Operator should re-run audits at this point. |

## Recommended Cadence

```
/every 30m /audit-grind
```

30 minutes is the sweet spot: long enough for 6 Haiku sub-agents to finish
(typical ≤5 min each) and validate the post-run state; short enough that
breakages are caught fast. Tighten to `/every 15m` for active dev days,
loosen to `/every 2h` overnight.

## Coordination with Other Skills / Workflows

- `/fleet` is already enabled in this session; this skill assumes it.
- `/delegate` (creates a real GitHub PR) is OUT OF SCOPE — that's the
  operator's deliberate action.
- `/review` (code review agent) is complementary; run it manually on the
  branch before merging changes accumulated by this skill.

## First-Run Sanity Check

The very first invocation should:
1. Verify all 10 personas exist in `.github/agents/`.
2. Verify `docs/audits/SUMMARY.md` exists.
3. Verify SQLite has the `todos` and `todo_deps` tables.
4. If any of these are missing, write a one-paragraph report explaining the
   gap and exit. Do NOT try to bootstrap audits from scratch — that's a
   separate skill (TBD).
