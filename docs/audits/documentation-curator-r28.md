# Audit Report: documentation-curator r28 (Cycle 120)

**Persona**: documentation-curator
**Round**: r28
**Cycle**: 120
**HEAD**: 50b4118 (cycle 119 just landed)
**Timestamp**: 2026-05-21T14:00:00Z

---

## 1. Verified Still Holds

- ✅ **ARCHITECTURE.md totalclocklock references** (lines 337–360): SRC/ENGINE.C:313 definition, SRC/ENGINE.C:855 assignment, BUILD.H:151 extern — all three verified accurate. Sentinel comment blocks intact. Anti-regression warning active.
- ✅ **README.md section structure** (468 lines): Roadmap (lines 398–405), Agents (lines 407–441), License (lines 444–453), Credits (lines 456–462) all present and current format.
- ✅ **SECURITY.md cycle annotations** (lines 1–114): c113 `.env` perms section (lines 49–65), c115 key-rotation section (lines 130–154), cycle-66 fake-author commits cited (line 113) — verified live.
- ✅ **docs/audits/SUMMARY.md row format** (10 persona rows, ~524 lines): All 10 persona rows maintain markdown table format with r-sequence links + narrative tails. No dangling rN references detected.
- ✅ **Persona file count** (10 `.agent.md` files): engine-porter, compat-layer, asset-pipeline, audio-engineer, build-system, test-engineer, documentation-curator, security-and-secrets, network-multiplayer, performance-profiler.
- ✅ **.github/skills/audit-grind/SKILL.md** (line 237): Verification step says "Verify all 10 personas exist" — matches actual count. NOT outdated.
- ✅ **CONTRIBUTING.md workflow** (922 lines): Build sections (make clean && make on Linux, CMake on macOS), asset pipeline (python3 tools/generate_assets.py, make assets), secrets setup (cp .env.example .env) — current and functional.
- ✅ **NOTICE file compliance** (referenced in SECURITY.md:74): Third-party GPL-2.0 attribution documented; CODEOWNERS protected paths (CI/CD, secrets detection, compat/sha256.*) verified in `.github/CODEOWNERS`.

---

## 2. Fresh Findings (Cycle 120)

### Finding 1: docs/audits/index.md — C119 Backfill Incomplete

**Severity**: HIGH

**Evidence**:
- c119 grind landing included commit 83d09409 (`docs-index-backfill`): GRIND_LOG.md reports "+15 r27-r29 entries (8 r27 + 6 r28 + 1 r29) for audit reports landed c116-c118"
- grep search confirms asset-pipeline-r29.md exists (ls confirms presence)
- grep search confirms test-engineer-r28.md exists (ls confirms presence)
- But: `grep -E "asset-pipeline-r29|test-engineer-r28" docs/audits/index.md` returns NO MATCHES
- index.md footer says "Generated: Cycle 111" — stale metadata

**File**: docs/audits/index.md (last updated: Cycle 111, now Cycle 120)

**Recommended Action**: 
1. Verify all r27/r28/r29 audit reports that landed c116-c119 are present in filesystem
2. Add missing entries (asset-pipeline-r29, test-engineer-r28) to the persona audit tables in index.md
3. Update "Generated" footer to "Cycle 120"
4. Verify sentinel commits 3c9f42e7, e8ea31b0, 83020209, 50d9700f, a7f2c9e5, 83d09409, a45d4bc0, 7c42f1e6 all appear in GRIND_LOG with matching narratives

### Finding 2: README.md Roadmap — SDL2_mixer Item Marked TODO But Implemented

**Severity**: MEDIUM

**Evidence**:
- README.md line 405: `[ ] 🔊 Runtime audio playback via SDL2_mixer`
- compat/audio_stub.c line 944: `Mix_PlayMusic(current_music, loopflag ? -1 : 0);` invoked when `HAVE_SDL2_MIXER` defined
- compat/audio_stub.c:932–951 function implements full MIDI playback via SDL2_mixer (Mix_LoadMUS_RW, Mix_PlayMusic)
- CMakeLists.txt:12–13 find_package + line 123–125 conditional target_link_libraries active
- SECURITY.md:77–86 documents SDL2_mixer as "OPTIONAL runtime dependency loaded in QUIET mode" — implies feature is active

**File**: README.md lines 398–405 (Roadmap section)

**Recommended Action**: Mark item as `[x] DONE` in README.md Roadmap (change `[ ]` to `[x]`). Optionally add note: "(SDL2_mixer OPTIONAL; graceful fallback to audio_stub if unavailable)" to clarify availability.

### Finding 3: Undocumented Recently-Shipped Constants in Code

**Severity**: LOW

**Evidence**:
- c119 commit 50d9700f (`engine-lzw-diag`): Introduced `LZW_LENG_WARN_THRESHOLD=16384` in SRC/CACHE1D.C with diagnostic printf at 4 sites
  - Not documented in ARCHITECTURE.md or README.md
  - Only cited in GRIND_LOG.md (docs/audits/GRIND_LOG.md row `engine-lzw-diag`)
- c119 commit e8ea31b0 (`mmulti-recvbuf`): Added `recv_buf_near_full_logged[i]=0` reset pattern in SRC/MMULTI.C
  - Not documented in ARCHITECTURE.md or README.md
  - Only cited in GRIND_LOG.md (docs/audits/GRIND_LOG.md row `mmulti-recvbuf`)

**Files**: ARCHITECTURE.md (lacks section on LZW thresholds/diagnostics), README.md (lacks engine behavior notes)

**Recommended Action**: 
1. Add subsection to ARCHITECTURE.md § "Engine Safety" or new § "Diagnostics & Thresholds" covering:
   - LZW_LENG_WARN_THRESHOLD: 16384 boundary; printf warnings in kdfread/dfread sites
   - MMULTI recv_buf hysteresis: near-full detection + diagnostic logging + state reset (cycles 115–119)
2. OR: Mine as LOW-priority todo for next round (accepts deferral if doc focus needed elsewhere)

### Finding 4: ARCHITECTURE.md Audit Infrastructure Section Incomplete

**Severity**: LOW

**Evidence**:
- ARCHITECTURE.md line 364–366: "The project maintains a comprehensive audit system run by 10 specialized Copilot agent personas. Audit reports are stored in `docs/audits/` and track technical health, compliance, and quality metrics."
- Followed by line 368–378 audit file table listing only 6 persona-based audits
- docs/audits/index.md actually contains: Baseline documents (10 persona roots), Deep-Dive documents (4 specialized audits), RUN documents (13 cycle-specific plans), GRIND_LOG manifest
- Section doesn't mention Deep-Dive, RUN documents, GRIND_LOG, STAGING contract, or c119 audit-pass DOC-ONLY pattern

**File**: ARCHITECTURE.md lines 364–378 (Audit Infrastructure subsection)

**Recommended Action**: 
1. Expand audit table to mention all document types:
   - Baseline: root persona reports (10 total)
   - Revision reports: r2–rN per persona (ongoing)
   - Deep-Dive: specialized audits for high-impact areas (e.g., engine-r22-palette-bounds, network-ipv6-scope-r23, performance-profiler-deep)
   - RUN documents: cycle-specific investigation/planning (13 active)
   - GRIND_LOG: master timeline of all audit events
   - STAGING contract: DOC-ONLY audit-pass pattern for parallel deployment
2. Update line 380 manifest notes reference
3. OR: Mine as LOW-priority todo

### Finding 5: docs/audits/SUMMARY.md — Persona Row Format Consistency Verified

**Severity**: None (verification pass)

**Evidence**:
- All 10 persona rows follow consistent format: `| [persona-name](baseline-doc.md) | [rN](rN-doc.md) | ... | r27 | [r28?] — scope (rX cycle Y: narrative). Sentinel marker) |`
- Format allows unlimited r-sequence links (e.g., documentation-curator: r2–r27 present)
- No dangling rN references to missing .md files
- No malformed markdown detected

---

## 3. Carry-Forwards from r27 (Still Pending)

**Citation**: docs/audits/documentation-curator-r27.md (cycle 116)

- docs-r27-readme-build-sync (MED): Verify build commands in README match Makefile + CMakeLists.txt changes — **CARRY FORWARD** (routine verification, low priority)
- docs-r27-security-cycle-attribution-stale-check (LOW): Verify cycle 113/115 security citations remain accurate — **CARRY FORWARD** (audit-pass performed; can defer to r29)

---

## 4. Mined Todos Preview

Based on findings above, the following high-value todos are candidates for the grind backlog:

1. **docs-r28-index-backfill-c119-r28-r29** (HIGH): Add missing asset-pipeline-r29 + test-engineer-r28 entries to docs/audits/index.md; verify all c119 sentinel commits present in GRIND_LOG; update "Generated" footer.

2. **docs-r28-readme-roadmap-sdl2mixer-done** (MEDIUM): Update README.md Roadmap line 405 from `[ ]` to `[x]` for SDL2_mixer runtime playback; add optional clarification on OPTIONAL + fallback behavior.

3. **docs-r28-lzw-threshold-doc** (LOW): Add ARCHITECTURE.md subsection documenting LZW_LENG_WARN_THRESHOLD constant (16384 boundary), printf diagnostic sites (4 locations in kdfread/dfread), and hysteresis behavior; cite c119 commit 50d9700f.

4. **docs-r28-mmulti-recv-buf-doc** (LOW): Add ARCHITECTURE.md or README.md coverage of recv_buf_near_full_logged hysteresis pattern, diagnostic logging, and state reset behavior; cite c119 commit e8ea31b0 + c115 cycle notes.

5. **docs-r28-arch-audit-infrastructure-expand** (LOW): Expand ARCHITECTURE.md Audit Infrastructure section (lines 364–378) to describe Deep-Dive, RUN documents, GRIND_LOG, STAGING contract pattern; update manifest notes; consider moving to dedicated "Audit System Overview" subsection.

---

<!-- SUMMARY_ROW -->
| documentation-curator | r28 | cycle 120 | C119 backfill incomplete (index.md); SDL2_mixer todo→done; ship-undoc constants; audit-sec stale |
<!-- END_SUMMARY_ROW -->

---

<!-- GRIND_LOG_ENTRY -->
**Cycle 120 audit-pass — documentation-curator r28**: Deep re-audit of README, ARCHITECTURE, SECURITY, CONTRIBUTING, docs/audits/{SUMMARY,index}.md. Verified totalclocklock refs, persona count (10 correct), cycle annotations, and CONTRIBUTING workflow current. **Found 1 HIGH**: docs/audits/index.md missing c119 backfill (asset-pipeline-r29 + test-engineer-r28 entries). **Found 1 MEDIUM**: README Roadmap marks SDL2_mixer as TODO but Mix_PlayMusic implemented in compat/audio_stub.c:944 — should be DONE. **Found 3 LOW**: LZW_LENG_WARN_THRESHOLD + recv_buf_near_full_logged undocumented; ARCHITECTURE Audit Infrastructure section incomplete. 5 mined todos (1 HIGH, 1 MEDIUM, 3 LOW). All verified-still-holds intact. Carry-forwards from r27 deferred (routine, low priority).
<!-- END_GRIND_LOG_ENTRY -->

---

<!-- MINED_TODOS -->
INSERT INTO todos (id, title, description, status) VALUES
 ('docs-r28-index-backfill-c119-r28-r29', 'Complete docs/audits/index.md c119 backfill', 'The c119 grind landing (commit 83d09409) claimed +15 r27-r29 entries in docs/audits/index.md backfill, but asset-pipeline-r29.md and test-engineer-r28.md audit reports (which exist and landed c119) are NOT listed in index.md. Missing from persona audit tables. Action: Add asset-pipeline-r29 and test-engineer-r28 entries to appropriate tables in docs/audits/index.md; verify all c119 sentinel commits (3c9f42e7, e8ea31b0, 83020209, 50d9700f, a7f2c9e5, 83d09409, a45d4bc0, 7c42f1e6) appear in GRIND_LOG.md with matching narratives; update footer metadata "Generated: Cycle 111" → "Cycle 120". Files: docs/audits/index.md, docs/audits/GRIND_LOG.md.', 'pending'),
 ('docs-r28-readme-roadmap-sdl2mixer-done', 'Mark SDL2_mixer audio playback as DONE in README Roadmap', 'README.md line 405 marks "[ ] 🔊 Runtime audio playback via SDL2_mixer" as TODO, but the feature is implemented: compat/audio_stub.c:944 calls Mix_PlayMusic(current_music, loopflag ? -1 : 0) when HAVE_SDL2_MIXER defined; CMakeLists.txt:123-125 conditionally links SDL2_mixer::SDL2_mixer; SECURITY.md:77-86 documents it as OPTIONAL runtime dependency. Action: Change README.md line 405 from "[ ] 🔊 Runtime audio playback via SDL2_mixer" to "[x] 🔊 Runtime audio playback via SDL2_mixer" and optionally add note clarifying OPTIONAL availability + graceful fallback to audio_stub.', 'pending'),
 ('docs-r28-lzw-threshold-doc', 'Document LZW_LENG_WARN_THRESHOLD constant in ARCHITECTURE.md', 'Cycle 119 commit 50d9700f introduced LZW_LENG_WARN_THRESHOLD=16384 constant in SRC/CACHE1D.C with diagnostic printf warnings at 4 sites (kdfread L546/L567, dfread L604/L625). Feature is shipped but not documented in main docs (only in GRIND_LOG). Action: Add ARCHITECTURE.md subsection under "Engine Safety" or new "Diagnostics & Thresholds" covering: (1) LZW_LENG_WARN_THRESHOLD: 16384 boundary rationale and diagnostic printf sites; (2) Integration with hard bounds (unchanged). Cite commit 50d9700f. File: docs/ARCHITECTURE.md (recommend after line 320 or under "Memory Layout" section).', 'pending'),
 ('docs-r28-mmulti-recv-buf-doc', 'Document recv_buf_near_full_logged hysteresis pattern', 'Cycle 119 commit e8ea31b0 refined SRC/MMULTI.C recv_buf handling with recv_buf_near_full_logged[i]=0 reset in uninitmultiplayers() teardown path + pre-memmove guard. Feature enhances c115/c117 recv_buf threshold work but lacks main documentation (audit-only). Action: Add coverage to ARCHITECTURE.md or README.md describing hysteresis pattern, diagnostic logging behavior, and state reset mechanics. Cite c115 (recv_buf threshold), c117 (diagnostic), c119 (e8ea31b0 reset codify). File: docs/ARCHITECTURE.md (recommend new "Network & Hysteresis" subsection after MMULTI description).', 'pending'),
 ('docs-r28-arch-audit-infrastructure-expand', 'Expand ARCHITECTURE.md Audit Infrastructure section', 'ARCHITECTURE.md lines 364-378 describe audit system but omit Deep-Dive audits, RUN documents, GRIND_LOG, and STAGING contract pattern. docs/audits/index.md actually maintains: 10 Baseline personas + r-sequence revisions, 4 Deep-Dive specialized audits (engine-r22-palette, network-ipv6-scope-r23, performance-deep, allocache-r22), 13 RUN cycle-specific investigation documents, GRIND_LOG master timeline, SUMMARY.md cross-cutting narrative. Action: Expand table/section to enumerate all document types; add row: "Deep-Dive Audits" + "RUN Documents" + "GRIND_LOG" + "STAGING Contract (DOC-ONLY parallel audit-pass pattern)"; update Manifest Notes (line 380+) to reference all types. Consider moving to dedicated "Audit System Architecture" subsection. File: docs/ARCHITECTURE.md (lines 364-395).', 'pending');
<!-- END_MINED_TODOS -->

---

**Sentinel**: 2f8a3e1d

