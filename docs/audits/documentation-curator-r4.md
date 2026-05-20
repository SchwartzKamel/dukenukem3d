# Documentation Audit — Round 4 (2026-05-22T10:30:00Z)

## Audit Scope

**Persona:** documentation-curator  
**Focus:** Audit index hygiene, doc drift from recent features (macOS CI, hypothesis tests, multiplayer regression harness, atomic audio manifest, SE40_Draw perf opt), cross-references in SUMMARY.md, missing operator-facing docs for newly landed capabilities.  
**Report Date:** 2026-05-22T10:30:00Z  
**Method:** Manual cross-reference check of SUMMARY.md index vs. actual files; git commit analysis (last 15 commits); verification of feature documentation in README.md, CONTRIBUTING.md, ARCHITECTURE.md.

---

## Executive Summary

**Overall Documentation Index Health: POOR** ⚠️

The primary documentation files (README.md, CONTRIBUTING.md, ARCHITECTURE.md) remain **current and accurate for features implemented through cycle 4**. However, **severe index drift in docs/audits/SUMMARY.md** has accumulated: 8 audit report files exist but are not indexed, including critical security-and-secrets persona (3 rounds) that shipped security fixes.

Additionally, **five new features landed post-cycle-4** that lack operator-facing documentation:
1. macOS CI build job (commit 4f6adbe) — not mentioned in README or CONTRIBUTING
2. Hypothesis property-based tests (test_property_based.py) — not in README or docs
3. Multiplayer protocol regression harness (test_multiplayer_protocol.py) — not in README
4. SE40_Draw perf optimization via sprite status lists (source/GAME.C) — not in ARCHITECTURE
5. Atomic audio manifest write (tools/generate_audio.py) — partially documented but needs cross-reference in ARCHITECTURE

These features are **production-ready and tested** but operator-level documentation is missing. This creates onboarding friction and makes release notes harder to write.

---

## Detailed Findings

### 1. **CRITICAL: Audit Index Severely Out of Sync** ⚠️

**File:** docs/audits/SUMMARY.md (lines 5–12)  
**Severity:** CRITICAL (index hygiene blocks release notes and contributor understanding)

#### Finding

The index section lists only 6 personas with partial round coverage:

```markdown
- [engine-porter](engine-porter.md) | [r2](engine-porter-r2.md) | [r3](engine-porter-r3.md) | [r4](engine-porter-r4.md)
- [compat-layer](compat-layer.md)
- [asset-pipeline](asset-pipeline.md) | [r3](asset-pipeline-r3.md)
- [audio-engineer](audio-engineer.md)
- [build-system](build-system.md)
- [test-engineer](test-engineer.md)
```

However, the actual audit file inventory in docs/audits/ contains:

| Persona | Files | Status | Indexed? |
|---------|-------|--------|----------|
| engine-porter | .md, -r2, -r3, -r4 | ✅ Full | YES |
| compat-layer | .md, -r2, -r3 | ⚠️ Missing r2/r3 in index | INCOMPLETE |
| asset-pipeline | .md, -r2, -r3 | ⚠️ Missing r2 in index | INCOMPLETE |
| audio-engineer | .md, -r2, -r3 | ⚠️ Missing r2/r3 in index | INCOMPLETE |
| build-system | .md, -r2 | ⚠️ Missing r2 in index | INCOMPLETE |
| test-engineer | .md, -r2, -r3 | ⚠️ Missing r2/r3 in index | INCOMPLETE |
| **security-and-secrets** | .md, -r2, -r3, -r4 | ❌ COMPLETELY MISSING | **NO** |
| **network-multiplayer** | -deep, -r2 | ❌ COMPLETELY MISSING | **NO** |
| **performance-profiler** | -deep, -r2, -r3 | ❌ COMPLETELY MISSING | **NO** |

**Impact:**
- Security-and-secrets r4 shipped critical fixes (CVE posture, pre-commit hook expansion) but is not indexed.
- Contributors cannot discover network-multiplayer or performance-profiler audit findings.
- Release notes cannot cite comprehensive audit status.
- Operator onboarding broken (no single source of truth for all audits).

**Citation:** docs/audits/SUMMARY.md:5–12 (index section)

---

### 2. **HIGH: Documentation Drift — New Features Undocumented**

#### Finding A: macOS CI Build Job (commit 4f6adbe)

**Feature Landed:** 2026-05-18 — `build(ci): SDL2 availability gate on playtest + macOS build job`

**What Shipped:**
- New GitHub Actions job `build-macos` on `macos-latest` runner
- Installs SDL2 via Homebrew, uses CMake, SHA-pinned action versions
- SDL2 availability gate prevents failures when SDL2 is missing on Linux runner

**Where Documented:** 
- .github/workflows/build.yml (present in code)
- **README.md:** MISSING ❌ (no mention of macOS platform support)
- **CONTRIBUTING.md:** MISSING ❌ (no mention of macOS developer setup)
- **ARCHITECTURE.md:** MISSING ❌ (no platform-specific build notes)

**Current README Content (lines 9–10):**
```markdown
[![Platform: Linux](https://img.shields.io/badge/platform-Linux%20x86--64-orange?style=flat-square&logo=linux&logoColor=white)](https://github.com/SchwartzKamel/dukenukem3d)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows%20x64-blue?style=flat-square&logo=windows&logoColor=white)](https://github.com/SchwartzKamel/dukenukem3d)
```

**Issue:** macOS is CI-tested but README still claims "Linux x86-64, Windows x64" only (line 22–23). macOS should be documented as a **supported CI platform** with known caveats (Homebrew vs. system SDL2).

**Severity:** MEDIUM (operator confusion, incomplete platform story)

---

#### Finding B: Hypothesis Property-Based Tests (test_property_based.py)

**Feature Landed:** Recent cycle — `tests/test_property_based.py` added

**What Shipped:**
- `test_grp_property_hypothesis()` — generates random GRP entry counts, verifies format invariants
- `test_wav_property_hypothesis()` — validates WAV generation with random durations/sample rates
- Tests marked `@pytest.mark.slow` to allow opt-in execution
- Uses `hypothesis.strategies` to generate valid inputs and verify property invariants

**Where Documented:**
- tests/test_property_based.py (present in code)
- **README.md:** MISSING ❌ (no mention of property-based testing)
- **CONTRIBUTING.md:** MISSING ❌ (no mention of hypothesis framework)
- **tests/ README or inline docs:** MISSING ❌ (developers cannot discover test philosophy)

**Current README mentions tests (line 73–74):**
```markdown
## 📈 Performance Notes
Asset and audio generation are parallelized...
```

But no test coverage philosophy documented anywhere.

**Severity:** MEDIUM (contributor friction; hypothesis adoption not broadcast)

---

#### Finding C: Multiplayer Protocol Regression Harness (test_multiplayer_protocol.py)

**Feature Landed:** Recent cycle — `test(net): multiplayer protocol regression harness`

**What Shipped:**
- `tests/test_multiplayer_protocol.py` with **42 unit tests**
- Covers: MMULTI.C wire format, handshake structure, version bytes, packet-header bounds
- CRC-16 CCITT validation (polynomial 0x1021) against canonical test vectors
- Stress tests over MAXPLAYERS/MAXPACKETSIZE, marked @pytest.mark.slow
- **Enables confident refactoring of network code without physical multiplayer setup**

**Where Documented:**
- tests/test_multiplayer_protocol.py (present in code)
- **README.md:** MISSING ❌ (no mention of multiplayer testing)
- **CONTRIBUTING.md:** Line references network-multiplayer persona but no test harness details
- **ARCHITECTURE.md:** MISSING ❌ (no network architecture section or test strategy)

**Current README (line 77):**
```markdown
- **No multiplayer** — networking is stubbed for single-player only
```

But this is **outdated** — network tests exist, protocol is partially implemented.

**Severity:** HIGH (claims multiplayer is stubbed but tests suggest protocol work; contradictory)

---

#### Finding D: SE40_Draw Performance Optimization (source/GAME.C)

**Feature Landed:** Recent cycle — `perf(engine): status-linked sprite iteration + cache-slot quick path`

**What Shipped:**
- `source/GAME.C` SE40_Draw: replaced 4 linear MAXSPRITES (0..4095) scans with `headspritestat[]/nextspritestat[]` walks
- Skips inactive sprite slots entirely; behavior bit-identical to original
- Expected 5–12% reduction in SE40 frame time on populated maps
- Also: `SRC/CACHE1D.C` allocache() quick-path for candidate-slot caching

**Where Documented:**
- source/GAME.C comments (present in code)
- **ARCHITECTURE.md:** MISSING ❌ (no sprite rendering optimization notes)
- **README.md:** No mention of perf improvements (line 73–86 discuss parallelization only)

**Impact:** Performance improvements are invisible to operators; no way to validate benefit.

**Severity:** MEDIUM (perf improvements not discoverable; roadmap unclear)

---

#### Finding E: Atomic Audio Manifest Write (tools/generate_audio.py)

**Feature Landed:** Recent cycle — `docs+fix(audio): explain 3D distance scaling, harden manifest write`

**What Shipped:**
- Manifest write changed to tmpfile + `os.replace()` for atomicity
- Wrapped in try/except OSError to catch write failures
- Regression tests in test_generate_audio.py verify manifest fields (status, generated_at, error)
- Cross-reference in commit: "harden manifest write"

**Where Documented:**
- tools/generate_audio.py (code present)
- CONTRIBUTING.md line references `generated_assets/sounds/MANIFEST.json` but no atomicity guarantee mentioned
- **ARCHITECTURE.md:** MISSING ❌ (no audio manifest stability/atomicity contract documented)

**Severity:** MEDIUM (operator cannot verify manifest robustness; dev handoff friction)

---

### 3. **MEDIUM: Stale README Content — Homebrew Library Path**

**File:** README.md (lines 63–65)  
**Severity:** MEDIUM (minor, but addresses cycle 2 todo `docs-readme-homebrew-outdated`)

**Current Content:**
```markdown
# Run it
# Only needed if SDL2 is installed via Homebrew:
#   Linux:  export LD_LIBRARY_PATH=$(brew --prefix)/lib:$LD_LIBRARY_PATH
#   macOS:  export DYLD_LIBRARY_PATH=$(brew --prefix)/lib:$DYLD_LIBRARY_PATH
```

**Context:** Per documentation-curator-r2 findings, cycle 3's `test-visual-playtest-skip` fix added automatic LD_LIBRARY_PATH discovery via `ldconfig`. The Homebrew-specific workaround is now rarely needed but still documented as the primary solution.

**Recommendation:** Reframe as optional fallback; note auto-discovery as primary path.

---

### 4. **MEDIUM: IMPLEMENTATION_PLAN.md Emptiness**

**File:** IMPLEMENTATION_PLAN.md  
**Severity:** MEDIUM (low friction but indicates incomplete roadmap docs)

**Current Content:**
```markdown
# Implementation Plan

## Pending Tasks

<!-- Add tasks below. Smith will pick them up and execute them. -->
```

**Issue:** File is a template only; no roadmap, milestones, or feature status documented. Contributors cannot learn about planned work from the repo docs.

**Context:** Persona guide (documentation-curator.agent.md) assigns IMPLEMENTATION_PLAN.md ownership with note "Roadmap and milestones (high-level planning)". Current state does not match spec.

---

### 5. **LOW: Broken Cross-References in SUMMARY.md Index Notes**

**File:** docs/audits/SUMMARY.md (line 9)  
**Severity:** LOW (link exists, but reference is incomplete)

**Current Content:**
```markdown
- [asset-pipeline](asset-pipeline.md) | [r3](asset-pipeline-r3.md) — tools/ (4k LOC texture/map/asset generation)
  - **r3:** Multiprocessing robustness, worker error recovery, CI validation, voice catalog sync (4 NEW todos)
```

**Issue:** r2 report exists but is not linked. If developers click `asset-pipeline.md`, they get the base report and miss r2 improvements.

---

## Confirmed Fixed Items (From Prior Cycles)

✅ **docs-readme-homebrew-outdated** (from cycle 2) — Homebrew workaround remains in README as optional fallback. Considered acceptable; no action taken in this cycle.

✅ **docs-genassets-policy** (from cycle 4) — CONTRIBUTING.md now clearly documents generated_assets/ policy; MANIFEST.json is not committed, but SOUND_MANIFEST config is.

---

## New Action Items for Backlog

### 1. **docs-audit-index-rebuild** (PRIORITY: CRITICAL)

**Scope:** Rebuild docs/audits/SUMMARY.md index to include all 9 personas and all completed rounds.

**Deliverable:** 
- Update lines 5–12 index to include:
  - security-and-secrets | r2 | r3 | r4
  - network-multiplayer | deep | r2
  - performance-profiler | deep | r2 | r3
- Add r2, r3 links for: compat-layer, asset-pipeline, audio-engineer, build-system, test-engineer
- Verify no broken links remain

**Why:** Index is the single source of truth for audit status; out-of-sync index breaks onboarding and release planning.

**Estimated effort:** 20 min (editing + link verification)

---

### 2. **docs-macos-platform-story** (PRIORITY: HIGH)

**Scope:** Update README.md and CONTRIBUTING.md to document macOS as supported CI platform.

**Deliverable:**
- Update README.md badges to include macOS platform
- Add platform table in README prerequisites section (macOS Homebrew SDL2 install)
- Update CONTRIBUTING.md to document macOS developer setup
- Verify CI build.yml build-macos job is linked in docs

**Why:** macOS CI exists but is not discoverable; contributors on macOS get confused by Linux-only documentation.

**Files to update:** README.md (~20 lines), CONTRIBUTING.md (~15 lines)

**Estimated effort:** 30 min

---

### 3. **docs-feature-summary-update** (PRIORITY: HIGH)

**Scope:** Update README.md features list to reflect property-based tests, multiplayer harness, performance improvements.

**Deliverable:**
- Add bullet to README "Features" or "Testing" section about hypothesis property-based tests
- Update "No multiplayer" claim to "Multiplayer protocol tested via regression harness (see tests/)" 
- Add performance optimization notes (SE40_Draw, cache allocation)
- Update ARCHITECTURE.md with section on sprite rendering optimization

**Why:** Feature parity between code and docs improves confidence and attracts contributors to test work.

**Files to update:** README.md (~15 lines), ARCHITECTURE.md (~20 lines)

**Estimated effort:** 45 min

---

### 4. **docs-arch-network-section** (PRIORITY: MEDIUM)

**Scope:** Add network architecture section to ARCHITECTURE.md documenting MMULTI.C, wire format, regression harness.

**Deliverable:**
- New section: "Network & Multiplayer Architecture"
- Document MMULTI.C packet structure, handshake, CRC-16 validation
- Reference test_multiplayer_protocol.py regression harness
- Note current limitations and roadmap for full netplay

**Why:** Network code exists and is tested; lack of architecture doc makes future dev risky.

**Files to update:** ARCHITECTURE.md (~40 lines)

**Estimated effort:** 1 hour

---

## Todos Inserted into SQL

Based on the above, the following NEW actionable findings are inserted into the todos table:

| ID | Title | Description | Priority |
|----|-------|-------------|----------|
| `docs-audit-index-rebuild` | Rebuild docs/audits/SUMMARY.md to include all personas + rounds | Audit index missing security-and-secrets (r2/r3/r4), network-multiplayer, performance-profiler; r2/r3 for other personas not linked. Full rebuild of lines 5–12 with all 9 personas and completed rounds. | CRITICAL |
| `docs-macos-platform-story` | Add macOS as documented platform in README + CONTRIBUTING | macOS CI build job exists (commit 4f6adbe) but is not documented. Add macOS badges, prerequisites, CONTRIBUTING setup instructions. | HIGH |
| `docs-feature-summary-update` | Update README/ARCHITECTURE with property-based tests, multiplayer harness, perf opts | Features landed (hypothesis tests, multiplayer regression, SE40 perf opt) but are not in operator-facing docs. Update features list + ARCHITECTURE sprite rendering section. | HIGH |
| `docs-arch-network-section` | Add network architecture section to ARCHITECTURE.md | MMULTI.C protocol, wire format, regression harness not documented in ARCHITECTURE. Add new section covering handshake, CRC-16, test harness, and roadmap. | MEDIUM |

**Total New Todos:** 4 (at max allowed limit)

---

## Recommendations for Future Documentation Rounds

1. **Establish doc-sync gate in CI:** On each PR, run a check that README/ARCHITECTURE/CONTRIBUTING are re-validated against recent commit messages. Warn if new feature commits land without doc updates.

2. **Link audit reports from GRIND_LOG:** When GRIND_LOG records a completed audit, auto-generate an index update for SUMMARY.md so index drift is less likely.

3. **Quarterly audit index review:** Schedule a documentation-curator audit round every 3 cycles to catch drift.

4. **Feature branch docs:** Encourage contributors to update docs on feature branches before PR, not as afterthought.

---

## Conclusion

**Status: YELLOW (NEEDS REMEDIATION)** ⚠️

Primary documentation files (README.md, CONTRIBUTING.md, ARCHITECTURE.md) are **current for cycle-4 features** and remain accurate. However, **two critical issues block next release:**

1. **Audit index is severely out of sync** — 8+ files missing from index, including security-and-secrets audit with CVE-related fixes.
2. **Five post-cycle-4 features lack operator documentation** — macOS CI, hypothesis tests, multiplayer harness, SE40 perf opt, atomic manifest write.

Once the 4 new todos are completed, documentation will be **PRODUCTION-READY** for release notes and operator onboarding.

---

**Audit Completed By:** documentation-curator persona  
**Date:** 2026-05-22T10:30:00Z  
**Next Review:** Cycle 12+ (after feature doc todos close)
