# asset-pipeline — round 30 (DOC-ONLY ship-readiness audit)

<!-- SUMMARY_ROW -->
| asset-pipeline | r30 | 2026-05-23 | ⚠️ **Ship-ready for procedural (`--no-ai`) path; AI path has P1 secret-leak + reliability gaps in `generate_audio.py` + `tools/ci/generate_assets.sh` that must land before flipping `--ai` in CI** |
<!-- END_SUMMARY_ROW -->

---

## Executive Summary

**Verdict: CONDITIONAL SHIP.**

The procedural (`--no-ai`) pipeline is production-grade: deterministic, hash-order-safe, and produces a byte-reproducible `DUKE3D.GRP` from a clean checkout. All carry-forwards from r29 remain stable. **However**, three P1 issues persist on the AI path and the canonical CI entry script that block enabling `--ai` in CI without leaking endpoint hostnames in error logs or silently swallowing worker failures:

1. **`tools/generate_audio.py` sync `generate_audio()` (lines 453–464) has neither retry logic nor `_redact_endpoint()` redaction** — `requests` `ConnectionError`/`Timeout` stringification leaks the full URL (with hostname + path) to stdout via `print(f"    [!] Failed: {e}")`.
2. **`tools/generate_audio.py` async `generate_audio_async()` (lines 509–518) has the same leak** — bare `Exception` catch logs `f"Failed: {e}"`; `aiohttp.ClientConnectorError` embeds `host=...`.
3. **`tools/ci/generate_assets.sh` (lines 53–56) error-reporting block is unreachable** under `set -euo pipefail`: `wait $PID; RC=$?` propagates `wait`'s nonzero exit through `set -e` before the assignment, so the diagnostic `echo "audio_rc=…"` never fires and the script aborts at line 53 without context.

Determinism risk: **LOW** (timestamps confined to log/sidecar paths; no hash-order leak into binary outputs; numpy `argmin` ties broken to lowest palette index deterministically). `--no-ai` fallback completeness: **PASS** for textures/sprites/audio. Secret-leak audit: **3 leaks identified**, all on AI paths.

P0: 0 · P1: 4 · P2: 5 · P3: 2

---

## Determinism Risk Assessment — LOW

| Source | Risk | Verdict |
|--------|------|---------|
| Wallclock timestamps | `datetime.now()` at `tools/generate_assets.py:118,147,323` and `tools/generate_audio.py:565,693,758` | ✅ Isolated to `GENERATION_LOG.jsonl`, `audio_manifest.freshness.json`, and the `generated_at` field of `MANIFEST.json` *only* when `--no-ai` is **not** active. When `--no-ai` is set, manifest timestamps are hardcoded to `1970-01-01T00:00:00Z` (line 691, 756). GRP manifest (`_emit_grp_manifest`) accepts `generated_at` parameter but `main()` (line 2685) does not override it — this is the **one residual non-determinism**: `GRP_MANIFEST.json` contains a wallclock `generated_at` even in `--no-ai` mode. *See P2 #5 below.* |
| Hash iteration order | `multiprocessing.Pool.imap_unordered` at `tools/generate_assets.py:2468,2480,2492` returns results in arbitrary order | ✅ Re-assembled into `tiles` dict keyed by integer `tile_num`; ART writer (`tools/art_format.py`) sorts by tile number. `tools/grp_format.py:32` calls `sorted(files_dict.keys())`. Verified. |
| Multiprocessing fork bleed | Default `fork` start method on Linux | ✅ Workers receive immutable `palette` list and self-seeded `random.Random(N)` instances (seeds 42–61 hardcoded in `proc_*` functions at lines 662–1132). No PID/timing leak into pixel data. |
| Threading interleave | `ThreadPoolExecutor` in `generate_audio.py:700` (local path) | ✅ Results written to pre-sized `results[idx]` list keyed by enumerate index; manifest update sequentialized post-pool (line 729, `audio-r12-parallel-manifest-race`). |
| numpy argmin tie-break | `tools/palette.py:332` `dists_squared.argmin(axis=1)` | ✅ NumPy returns the **lowest** index on ties — deterministic across platforms. |
| PYTHONHASHSEED | not pinned | ✅ No `set()`/`dict` iteration order escapes into binary output; all callers sort by integer keys. |

**Risk score: LOW.** Only the GRP manifest wallclock leak (P2 #5) needs addressing for true byte-reproducibility of `GRP_MANIFEST.json`.

---

## `--no-ai` Fallback Completeness — PASS

| AI path | Fallback | Status |
|---------|----------|--------|
| FLUX texture (`generate_texture_ai` line 489) | `PROCEDURAL_MAP[tile_num]` (line 956+) | ✅ All `TEXTURE_DEFS` tiles have entries; `--no-ai` flag short-circuits at line 2455 into multiprocessing pool of `_generate_texture_worker` |
| FLUX startup validation failure | Graceful downgrade to `--no-ai` (line 2440 `use_ai = False`) | ✅ |
| AUDIO sync `generate_audio` | `generate_silence_wav(0.5)` (line 697) | ✅ (but sync path is dead code — `_generate_audio_parallel_api` only uses async — see P3 #1) |
| AUDIO async failure | Returns `(None, error)` → caller marks entry as `failed` in manifest | ✅ |
| AUDIO startup validation failure | Graceful downgrade (`tools/generate_audio.py:628–629`) | ✅ |

---

## Secret-Leak Audit — 3 FAILURES

| Path | Leak | Severity |
|------|------|----------|
| `tools/generate_audio.py:463` `print(f"    [!] Failed: {e}")` | `requests.ConnectionError` stringifies as `HTTPSConnectionPool(host='real-host.openai.azure.com', port=443): …` — full hostname + port | **P1** |
| `tools/generate_audio.py:510` `error_msg = f"Failed: {e}"` (async) | `aiohttp.ClientConnectorError` stringifies as `Cannot connect to host real-host.openai.azure.com:443` | **P1** |
| `tools/generate_assets.py:599,607` `error_msg = f"Network error: {type(e).__name__}: {e}"` then `print(f"    [!] {error_msg}")` | `requests.ConnectionError` → same leak | **P1** |

Findings: `_redact_endpoint`/`_redact_hostname` helpers exist in both modules but are only wired at startup validation (`tools/generate_assets.py:443,445`, `tools/generate_audio.py:109,111,635`). The retry/exception-catch paths in `generate_texture_ai` and both `generate_audio` variants forward raw `{e}` interpolation. Fix sketch:

```python
# Replace at generate_assets.py:599
error_msg = f"Network error: {type(e).__name__}: {_redact_endpoint(endpoint)}"
```

(The exception's underlying socket details are *not* needed for diagnostics — `type(e).__name__` already disambiguates `Timeout` vs `ConnectionError`.)

---

## Findings

### P1 #1 — `tools/generate_audio.py:453–464` sync `generate_audio()` lacks redaction + retry

**Root cause:** Bare `except Exception as e: print(f"    [!] Failed: {e}")` (line 462–463). Sync path is also missing the exponential-backoff retry that the async path implements (lines 491–518) and missing Retry-After parsing.

**Risk:** `requests.ConnectionError` carries the full HTTPS URL in its `__str__`. Anyone reading stdout (CI logs, GitHub Actions, user terminals) sees `AUDIO_ENDPOINT` hostname. Also, transient 5xx/429 from Azure surfaces as a hard failure with no retry.

**Fix sketch:** Either delete the sync function (verified unused by `_generate_audio_parallel_api` → `_generate_audio_async_main` → `generate_audio_async`) **or** mirror the async retry + redaction patterns. Confirmed dead code: `grep -n "generate_audio(" tools/generate_audio.py` shows only definitions and async wrapper calls.

```bash
$ grep -n "^\s*\(=\s*\)\?generate_audio(" tools/generate_audio.py
# (no callers — function is dead)
```

**Recommendation:** Delete `generate_audio()` (lines 433–464). Drops 31 lines of unmaintained code with a known P1 leak.

---

### P1 #2 — `tools/generate_audio.py:509–510` async retry leaks endpoint

**Root cause:**
```python
except Exception as e:
    error_msg = f"Failed: {e}"
```
`aiohttp.ClientConnectorError` → `"Cannot connect to host {hostname}:{port} …"`.

**Fix sketch:**
```python
except Exception as e:
    error_msg = f"Failed ({type(e).__name__}) calling {_redact_endpoint(endpoint)}"
```

Citation verified: `grep -n "Failed: {e}" tools/generate_audio.py` → line 510.

---

### P1 #3 — `tools/generate_assets.py:597–608` network error leaks endpoint

**Root cause:** Same pattern — `f"Network error: {type(e).__name__}: {e}"` (line 599). `requests.ConnectionError`/`Timeout` includes `HTTPSConnectionPool(host=…)`.

**Fix sketch:**
```python
except (requests.Timeout, requests.ConnectionError) as e:
    error_msg = f"Network error ({type(e).__name__}) to {_redact_endpoint(endpoint)}"
```

Note: `_redact_endpoint` does not exist in `generate_assets.py` — only `_redact_hostname`. Either import/duplicate `_redact_endpoint` from `generate_audio.py`, or call `_redact_hostname(urlparse(endpoint).hostname)`.

---

### P1 #4 — `tools/ci/generate_assets.sh:47–62` `set -e` defeats error-capture block

**Root cause:**
```bash
set -euo pipefail            # line 6
…
wait $AUDIO_PID              # line 53 — if non-zero, set -e aborts HERE
AUDIO_RC=$?                  # line 54 — never executed
wait $ASSETS_PID
ASSETS_RC=$?
if [ $AUDIO_RC -ne 0 ] …     # diagnostic at line 59 never runs
```

**Risk:** CI failure surface is **silent abort at line 53** with no `audio_rc=… assets_rc=…` diagnostic. Operator sees `Error on line 53` from the `trap` (line 7) and has no idea which sub-job failed.

**Fix sketch:**
```bash
wait $AUDIO_PID || AUDIO_RC=$?
AUDIO_RC=${AUDIO_RC:-0}
wait $ASSETS_PID || ASSETS_RC=$?
ASSETS_RC=${ASSETS_RC:-0}
```

Additionally line 18: `if [ "$1" = "--ai" ]` will fail with `unbound variable` under `set -u` when script invoked with **zero arguments** (the documented usage `bash tools/ci/generate_assets.sh`). Must be `"${1:-}"`.

Verified:
```bash
$ bash -c 'set -u; [ "$1" = "--ai" ]'
bash: $1: unbound variable
```

---

### P2 #1 — `tools/generate_audio.py:460` uncaught `KeyError` on malformed API JSON

**Root cause:** `audio_b64 = result["choices"][0]["message"]["audio"]["data"]` (sync, line 460) and line 507 (async) assume the Azure response always has the nested shape. Azure returns `{"error": {...}}` on quota exhaustion / content filter trip / model deprecation, which raises `KeyError: 'choices'` → caught by bare `except Exception` (sync line 462; async line 509), surfaced as `f"Failed: {e}"` → user sees `Failed: 'choices'` with no actionable info.

**Fix sketch:** Wrap response extraction in a typed try block and log `result.get("error", {}).get("message")` when present (sanitized).

---

### P2 #2 — `tools/generate_audio.py` async path has no `Retry-After` parsing

**Root cause:** `generate_audio_async` (lines 491–518) uses pure exponential backoff with no parity to `_parse_retry_after_header()` that `generate_assets.py` implements (lines 452–486). Azure GPT-Audio rate-limits with `Retry-After`; ignoring it causes thundering-herd retries that compound throttling.

**Fix sketch:** Promote `_parse_retry_after_header` from `generate_assets.py` to a shared util (e.g. new `tools/_http_retry.py`) and wire into the `if resp.status == 429:` branch around line 494.

---

### P2 #3 — `_parse_retry_after_header` 0-second edge case (carryover from r29)

**Status:** ⚠️ STILL OPEN.

**Location:** `tools/generate_assets.py:469–471`:
```python
seconds = int(header_value)
return min(float(seconds), max_wait)
```

When `header_value == "0"` returns `0.0` → tight loop. Fix sketch (from r29):
```python
seconds = int(header_value)
if seconds <= 0:
    return None     # fall back to exponential backoff
return min(float(seconds), max_wait)
```

Todo mined in r29 as `asset-r29-retry-after-zero-edge-case` — **still pending**.

---

### P2 #4 — `tools/generate_assets.py:521` raw `resp.text[:200]` could mirror back leaked headers

**Root cause:** `error_msg = f"API returned {resp.status_code}: {resp.text[:200]}"` (line 521) prints the **server response body** verbatim. If FLUX or an upstream proxy echoes the `Authorization` header (some misconfigured WAFs do this), the bearer token leaks to stdout.

**Risk:** LOW probability, HIGH impact. Mitigated by FLUX being a controlled vendor, but not zero.

**Fix sketch:** Sanitize `resp.text` against the API key:
```python
body = resp.text[:200].replace(api_key, "<redacted>")
error_msg = f"API returned {resp.status_code}: {body}"
```

Same applies to `tools/generate_audio.py:456,495`.

---

### P2 #5 — `GRP_MANIFEST.json` non-deterministic `generated_at` in `--no-ai` mode

**Root cause:** `tools/generate_assets.py:2685` calls `_emit_grp_manifest(grp_out, grp_contents, manifest_out)` without overriding `generated_at`. Default at line 322–323:
```python
if generated_at is None:
    generated_at = datetime.now(timezone.utc).isoformat()
```

**Risk:** Breaks byte-reproducibility of `GRP_MANIFEST.json` between clean-checkout runs. `DUKE3D.GRP` itself remains byte-reproducible (the GRP format has no timestamps), but the sidecar manifest changes every run, defeating CI cache validation.

**Fix sketch:** Pass `generated_at="1970-01-01T00:00:00Z"` when `--no-ai` (or always); use the freshness-sidecar pattern from `generate_audio.py:547–574` if real timestamp tracking is needed.

---

### P2 #6 — `tools/ci/generate_assets.sh` parallel spawn never validates outputs

**Root cause:** After `wait`-ing both jobs, the script does `wc -c < DUKE3D.GRP` (line 66) but never invokes `tools/validate_generated_artifacts.py`. A successful exit code can ship with missing TILES000.ART or zero-byte PALETTE.DAT (e.g. if a worker crashed late and the script returned success because the parent process didn't propagate worker failure).

**Fix sketch:** Append `python3 tools/validate_generated_artifacts.py --set textures --set grp --set audio --set maps --set scripts` before exit. The validator already exists (`tools/validate_generated_artifacts.py:28–49`).

---

### P3 #1 — `tools/generate_audio.py:433–464` `generate_audio()` (sync) is dead code

**Root cause:** No callers (confirmed by `grep`). Adds maintenance surface and contains the P1 leak from #1.

**Fix sketch:** Delete the function.

---

### P3 #2 — `tools/palette.py:234,246` `_nearest_color` not vectorized inside `create_palette_dat`

**Root cause:** Cycle-121 vectorized `quantize_image` but `create_palette_dat` still calls `_nearest_color` 8192 (shade) + 65536 (translucency) = 73728 times per palette build (each scanning 256 entries). Not a determinism issue, but a 2–3 second startup cost on slow CI runners.

**Fix sketch:** Vectorize with numpy `argmin` of pairwise distances; share helper with `quantize_image`.

---

## Multiprocessing UX (carryover from r28/r29 — INFO)

`asset-r29-multiprocessing-failure-summary-audit` still open. Lines 2438, 2455–2482, 2705–2710. Low priority cosmetic enhancement.

---

## Prior open findings — re-verification

| Item | Location | Status r30 |
|------|----------|------------|
| Cycle 113 FLUX hardening (startup validation, Retry-After parsing, redaction) | `tools/generate_assets.py:407–486` | ✅ Persistent |
| Cycle 117 AUDIO endpoint validation | `tools/generate_audio.py:73–115, 624–629` | ✅ Persistent |
| Audio freshness sidecar | `tools/generate_audio.py:547–574, 678` | ✅ Persistent |
| NumPy 5.5× quantize vectorization | `tools/palette.py:299–334` | ✅ Persistent |
| GRP determinism (`sorted(files_dict.keys())`) | `tools/grp_format.py:32` | ✅ Persistent |
| `asset-r29-retry-after-zero-edge-case` | `tools/generate_assets.py:469–471` | ⚠️ **STILL OPEN** (re-graded P2 in r30) |
| `asset-r29-windows-bootstrap-clarification` | n/a | INFO carryover |
| `asset-r29-multiprocessing-failure-summary-audit` | line 2438+ | INFO carryover |
| Hostname redaction wiring | `_redact_hostname` exists but only at startup paths | ⚠️ **GAPS** at runtime error paths (P1 #1–#3) |
| Generator writes to project root | `generate_assets.py:2693,2704` writes `DUKE3D.GRP` + `GRP_MANIFEST.json` to project root | ✅ **EXPECTED** — both gitignored per CONTRIBUTING.md §.gitignore Policy. Not the cycle-56 false-alarm pattern. |

---

## Test Suite Status

Inherited from r29 baseline: `1952 passed, 3 skipped, 17 warnings`. No new tests recommended in r30 — fixes proposed should be accompanied by:

- A unit test asserting `_redact_endpoint` is called in `generate_audio_async` error path (mock `aiohttp.ClientSession` to raise `ClientConnectorError`, assert stdout does not contain the test hostname).
- A bash test for `tools/ci/generate_assets.sh` that fails one of the background jobs and asserts the diagnostic line is emitted.

---

## Cross-Domain Notes

- **Audio Engineer**: P1 #1, #2 and P2 #1, #2 are in audio territory. Recommend dispatching to Audio Engineer for fix.
- **Build System**: P1 #4 (CI shell script) is build-system-owned. Recommend dispatching to Build System persona.
- **Security & Secrets**: P2 #4 (response body could mirror tokens) overlaps with Security persona scope.

---

## Summary of Mined Todos (≤6)

1. **asset-r30-generate-audio-sync-dead-code** (P1, easy): Delete unused `tools/generate_audio.py:433–464` `generate_audio()` (sync). Drops leak + 31 LOC.
2. **asset-r30-audio-async-redact-endpoint** (P1): In `tools/generate_audio.py:509–510`, replace `f"Failed: {e}"` with `f"Failed ({type(e).__name__}) calling {_redact_endpoint(endpoint)}"`.
3. **asset-r30-flux-network-redact-endpoint** (P1): In `tools/generate_assets.py:599`, replace `f"Network error: {type(e).__name__}: {e}"` with redacted form. Import/duplicate `_redact_endpoint` helper.
4. **asset-r30-ci-shell-set-e-wait-rc** (P1): Patch `tools/ci/generate_assets.sh` lines 18, 53–56: use `"${1:-}"` and `wait $PID || RC=$?` idiom so diagnostic block fires.
5. **asset-r30-grp-manifest-deterministic-timestamp** (P2): Pass `generated_at="1970-01-01T00:00:00Z"` in `_emit_grp_manifest` calls at `tools/generate_assets.py:2685,2696` (under `--no-ai`); add freshness sidecar if needed.
6. **asset-r30-audio-async-retry-after** (P2): Promote `_parse_retry_after_header` to shared util; wire into `generate_audio_async` 429 branch (parity with FLUX).

---

## Code Change Summary

**Type**: Documentation audit (no code changes)
**Files Modified**: 1 (`docs/audits/index.md` — r30 row appended)
**Files Created**: 2 (`asset-pipeline-r30.md`, `STAGING_asset-pipeline_r30.md`)

---

## Grind Log Entry

<!-- GRIND_LOG_ENTRY -->

**Cycle 122 audit-pass — asset-pipeline r30**: Full ship-readiness audit of `tools/` pipeline. Procedural (`--no-ai`) path is production-grade and byte-reproducible. **AI path has 4 P1 issues blocking CI `--ai` enablement**: (1) `generate_audio.py` sync `generate_audio()` is dead code with secret-leak + no retries — delete it; (2) async `generate_audio_async` `except Exception as e: print(f"Failed: {e}")` leaks aiohttp hostname; (3) `generate_assets.py` network-error path forwards `{e}` containing `requests.ConnectionError` URL; (4) `tools/ci/generate_assets.sh` error-reporting block unreachable under `set -e` because `wait $PID; RC=$?` aborts before assignment, plus `$1` is unbound under `set -u` with zero args. P2: Retry-After:0 carryover still open; GRP_MANIFEST.json non-deterministic `generated_at`; async path missing Retry-After parsing; CI script never invokes validate_generated_artifacts.py; API response body could mirror bearer tokens. Determinism risk LOW (timestamps quarantined except for GRP manifest sidecar). All r28/r29 carry-forwards re-verified stable. 6 mined todos for cycle 123+ dispatch. **Verdict: CONDITIONAL SHIP** — procedural path safe to ship; AI path needs P1 fixes before `--ai` is wired in CI.

<!-- END_GRIND_LOG_ENTRY -->

---

## Sign-off

**Auditor**: Asset Pipeline Engineer (persona)
**Baseline Verification**: ✅ All r29 carry-forwards persistent
**Fresh Findings**: 4 P1, 5 P2, 2 P3 (procedural path clean; AI/CI path needs fixes)
**Determinism Risk**: LOW
**Recommendation**: Ship procedural pipeline; gate `--ai` CI rollout behind P1 #1–#4 fixes.

---

<!-- MINED_TODOS -->
INSERT INTO todos (id, title, description, status) VALUES
 ('asset-r30-generate-audio-sync-dead-code', 'Delete dead generate_audio() sync function', 'tools/generate_audio.py lines 433-464: synchronous generate_audio() has no callers (verified by grep). Contains P1 secret leak via print(f"Failed: {e}") on requests.ConnectionError. Delete the function entirely to drop 31 LOC of unmaintained surface.', 'pending'),
 ('asset-r30-audio-async-redact-endpoint', 'Redact endpoint in generate_audio_async error path', 'tools/generate_audio.py lines 509-510: replace error_msg = f"Failed: {e}" with f"Failed ({type(e).__name__}) calling {_redact_endpoint(endpoint)}". aiohttp.ClientConnectorError stringifies with full host:port; leaks AUDIO_ENDPOINT hostname to CI logs.', 'pending'),
 ('asset-r30-flux-network-redact-endpoint', 'Redact FLUX endpoint in network error path', 'tools/generate_assets.py lines 597-608: replace error_msg = f"Network error: {type(e).__name__}: {e}" with redacted form using _redact_endpoint or _redact_hostname(urlparse(endpoint).hostname). requests.ConnectionError stringifies with HTTPSConnectionPool(host=...) leaking FLUX_ENDPOINT.', 'pending'),
 ('asset-r30-ci-shell-set-e-wait-rc', 'Fix CI shell set -e + wait RC capture', 'tools/ci/generate_assets.sh: (1) line 18 use "${1:-}" instead of "$1" to survive set -u with zero args; (2) lines 53-56 use `wait $PID || RC=$?; RC=${RC:-0}` idiom so the diagnostic echo at line 60 fires under set -e instead of silent abort.', 'pending'),
 ('asset-r30-grp-manifest-deterministic-timestamp', 'Make GRP_MANIFEST.json byte-deterministic', 'tools/generate_assets.py lines 2685, 2696: _emit_grp_manifest defaults generated_at to datetime.now() (line 322-323). Pass generated_at="1970-01-01T00:00:00Z" under --no-ai (or always) and add a freshness sidecar (pattern from generate_audio.py _write_freshness_sidecar at line 547).', 'pending'),
 ('asset-r30-audio-async-retry-after', 'Add Retry-After parsing to async audio path', 'tools/generate_audio.py generate_audio_async (lines 491-518) does pure exponential backoff with no Retry-After header parsing. Promote _parse_retry_after_header from generate_assets.py:452-486 into a shared tools/_http_retry.py util and wire into the resp.status == 429 branch.', 'pending');
<!-- END_MINED_TODOS -->

---

<!-- SENTINEL: r30-2026-05-23 -->
