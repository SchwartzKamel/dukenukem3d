# Audio Engineering Audit Report — Round 2

**Auditor**: Audio Engineer Persona  
**Date**: 2025-05-21  
**Scope**: Post-parallelization audit of cycle 5 audio pipeline changes  
**Focus**: New parallel code paths (ThreadPoolExecutor + asyncio/aiohttp) and fresh integration issues  
**Classification**: Code Review & Integration Risk Assessment  

---

## Executive Summary

The parallel audio generation infrastructure introduces **three HIGH-severity issues** related to error handling, manifest integrity, and resource management. The async exception handling is sound (silent fallback), but the threading code lacks error guards that could cause silent failure or corruption on partial worker crashes.

**Key Changes Verified**:
- ✅ ThreadPoolExecutor for `--no-ai` (local WAV synthesis)
- ✅ asyncio + aiohttp for API path with `--workers` and `--concurrency` flags
- ✅ Graceful fallback to silence on API failures
- ⚠️ Manifest always written regardless of generation success
- 🔴 Thread exception handling missing in local path
- 🔴 Semaphore lacks acquire timeout in async path

---

## 1. ThreadPoolExecutor Error Handling (HIGH SEVERITY)

### Finding: Unguarded exception propagation in worker path

**File**: `tools/generate_audio.py:413–441`

**Issue**:
```python
430:         results = [None] * len(VOICE_LINES)
431:         for future in concurrent.futures.as_completed(futures):
432:             idx, filename, wav_data = future.result()  # ← NO try/except!
433:             out_path = os.path.join(OUTPUT_DIR, filename)
434:             with open(out_path, "wb") as f:
435:                 f.write(wav_data)
436:             results[idx] = filename
437:             print(f"    [Silence placeholder] OK")
```

If `future.result()` raises an exception (e.g., worker process crashes, OOM in struct.pack), the entire thread pool loop exits and crashes the script **before writing manifest**. This leaves:
1. Partial WAV files in `OUTPUT_DIR` (some completed, others not)
2. **No manifest** (line 404 never reached)
3. **No error reporting** to the user (traceback goes to stderr)

**Severity**: **HIGH** — Silent data loss & incomplete asset pipeline

**Recommended Fix**:
```python
try:
    idx, filename, wav_data = future.result()
    # ... write file ...
    results[idx] = filename
except Exception as e:
    print(f"    [!] Worker failed for index {idx}: {e}")
    results[idx] = None  # Mark as failed
```

---

## 2. Manifest Accuracy vs. Actual Output (HIGH SEVERITY)

### Finding: Manifest reflects static catalog, not real generation results

**File**: `tools/generate_audio.py:402–410` and `62–244`

**Issue**:
```python
402:     manifest_path = os.path.join(OUTPUT_DIR, "MANIFEST.json")
403:     with open(manifest_path, "w") as f:
404:         json.dump(SOUND_MANIFEST, f, indent=2, sort_keys=True)
```

The manifest is **always written from the static `SOUND_MANIFEST` array**, regardless of which WAVs actually generated successfully. Example:

**Scenario**:
- Run `python3 tools/generate_audio.py` with API endpoint broken
- 3 out of 21 VOICE_LINES fail to generate (get fallback silence)
- 21 WAV files are written (18 AI + 3 silence)
- Manifest still lists all 21 entries with `"notes": "AI-generated..."` for failed entries
- Downstream tools (GRP packer, asset validator) can't distinguish real from fallback audio

**Severity**: **HIGH** — Manifest doesn't reflect reality; breaks asset validation & CI logic

**Manifest should include**:
- A `"status"` field per entry: `"generated"`, `"fallback"`, or `"failed"`
- A `"version"` field to track schema changes
- Validation that written WAVs exist before writing manifest

---

## 3. Asyncio Semaphore Deadlock Risk (MEDIUM SEVERITY)

### Finding: No timeout on semaphore acquisition

**File**: `tools/generate_audio.py:451–470`

**Issue**:
```python
453:     semaphore = asyncio.Semaphore(concurrency)
454: 
456:     async def bounded_generate(session, idx, filename, prompt, voice):
457:         async with semaphore:  # ← NO timeout parameter
458:             wav_data, error = await generate_audio_async(...)
```

If `generate_audio_async()` hangs (e.g., network stall despite aiohttp timeout), the semaphore slot is held indefinitely. Other tasks waiting to acquire the semaphore will all timeout after 60s, but the hung task won't release its slot. This cascades:

1. Task A hangs in aiohttp, holds semaphore slot
2. Task B waits for slot, times out after 60s
3. Task C waits for slot, times out after 60s
4. ... all tasks timeout, no progress

**Root cause**: aiohttp's `timeout` parameter (line 464) does NOT interrupt the semaphore acquire; it only times out the HTTP request. If the request stalls *before* sending (DNS lookup, TCP connect), semaphore slot is held.

**Severity**: **MEDIUM** — Can cause full pipeline stall on network issues

**Recommended Fix**:
```python
async def bounded_generate(session, idx, filename, prompt, voice):
    try:
        async with asyncio.timeout(75):  # Python 3.11+, or use asyncio.wait_for()
            async with semaphore:
                wav_data, error = await generate_audio_async(...)
    except asyncio.TimeoutError:
        return idx, filename, None, "Semaphore timeout"
```

---

## 4. SOUND_MANIFEST Schema Lacks Versioning & Validation (MEDIUM SEVERITY)

### Finding: No schema version or enum constraints

**File**: `tools/generate_audio.py:59–244`

**Issues**:

1. **No `version` field**:
   - Manifest format could change (e.g., add `"generated_at"`, rename `"engine_sound_id"`)
   - Old tools expect old fields; new manifest breaks silently
   - No migration path

2. **No validation of `voice` enum**:
   - Valid values: `"alloy"`, `"echo"`, `"onyx"`
   - A typo like `"allloy"` in VOICE_LINES is never detected
   - Line 24: `("TAUNT01.WAV", "...", "alloy")` — no enum check
   - If someone edits line 24 to `"alloyy"`, voice mismatch propagates through GRP

3. **No validation of `category` enum**:
   - Valid values: `"taunt"`, `"pain"`, `"death"`, `"pickup"`, `"weapon"`, `"level_start"`, `"alarm"`, `"ambient"`
   - No constraint; typo `"pian"` instead of `"pain"` is silently accepted

4. **Missing `generated_at` timestamp**:
   - Can't determine if manifest is stale
   - Can't detect generation failures based on time

**Severity**: **MEDIUM** — Schema fragility; breaks on typos

**Recommended JSON Schema**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "version": "1.0",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["wav", "voice", "category", "status"],
    "properties": {
      "wav": {"type": "string"},
      "voice": {"enum": ["alloy", "echo", "onyx"]},
      "category": {"enum": ["taunt", "pain", "death", "pickup", "weapon", "level_start", "alarm", "ambient"]},
      "status": {"enum": ["generated", "fallback", "failed"]},
      "engine_sound_id": {"type": ["string", "null"]},
      "engine_sound_id_int": {"type": ["integer", "null"]},
      "prompt_summary": {"type": "string"},
      "notes": {"type": "string"},
      "generated_at": {"type": "string", "format": "date-time"}
    }
  }
}
```

---

## 5. Voice Lines Catalog Consistency Check (LOW SEVERITY)

### Finding: VOICE_LINES and SOUND_MANIFEST must stay in sync

**File**: `tools/generate_audio.py:22–57` (VOICE_LINES) vs. `62–244` (SOUND_MANIFEST)

**Issue**: Two parallel data structures that must always match. If a new TAUNT is added to VOICE_LINES (line 22), the corresponding entry must be added to SOUND_MANIFEST (line 62), else:
- Entry 22 tries to generate TAUNT_NEW.WAV
- But MANIFEST lacks the entry
- Manifest JSON array has 21 elements, generated[] has 22

**Current state**: Both are in sync (21 entries each). ✓

**Risk**: Future maintainers might add to VOICE_LINES and forget SOUND_MANIFEST.

**Recommended Fix**: Programmatically generate SOUND_MANIFEST from VOICE_LINES at runtime (optional enhancement, LOW priority)

---

## 6. aiohttp Dependency Security & Version (MEDIUM SEVERITY)

### Finding: aiohttp pinned to 3.8.0–3.99.0; no security audit

**File**: `requirements.txt:3`

**Constraint**: `aiohttp>=3.8.0,<4.0.0`

**Issues**:

1. **Security**: aiohttp 3.8.0–3.8.5 had **CVE-2023-37276** (HTTP request smuggling via newline injection)
   - Fixed in 3.8.6
   - Current constraint allows 3.8.0–3.8.5 (vulnerable!)

2. **Compatibility**: aiohttp 3.9.0 had breaking changes in `web` module (not used here, but silent upgrade risk)

3. **No explicit lower bound reason**: Why not `aiohttp>=3.9.0,<4.0.0` (current stable)?

**Severity**: **MEDIUM** — Potential security vulnerability in CI/local builds

**Recommended Action**: Update to `aiohttp>=3.9.0,<4.0.0` or `aiohttp>=3.10.0,<4.0.0` (if 3.10 is stable)

---

## 7. CI/CD Audio Pipeline Coverage (LOW SEVERITY)

### Finding: Audio generation not tested; only used in release builds

**File**: `.github/workflows/release.yml`

**Current coverage**:
- Release builds: call `python3 tools/generate_audio.py --no-ai` ✓
- PR checks: **NO audio validation** ✗
- No test suite for generate_audio.py (no `pytest` invocations)

**What's missing**:
1. Unit tests for `generate_silence_wav()`
2. Integration test: `python3 tools/generate_audio.py --no-ai` && verify WAV headers
3. Manifest JSON validation (schema check)
4. ThreadPool exception handling verification
5. Async semaphore + timeout stress test

**Severity**: **LOW** — Parallel bugs would only surface in production builds (with real API), not in CI

**Recommended additions to CI**:
```yaml
- name: Test audio generation
  run: |
    python3 -m pytest tools/test_generate_audio.py -v
    python3 tools/generate_audio.py --no-ai
    python3 -m pytest tools/test_audio_manifest.py -v
```

---

## 8. Memory Usage: WAV Loading (LOW SEVERITY)

### Finding: WAVs are generated in-memory, then written to disk; no streaming

**File**: `tools/generate_audio.py:264–281` (silence generation) and `318–348` (async API call)

**Current flow**:
1. `generate_silence_wav(0.5)` returns entire 22KB WAV as bytes in RAM
2. `generate_audio_async()` decodes base64 → entire WAV in RAM
3. WAVs written to disk in `_generate_audio_parallel_local()` and `_generate_audio_async_main()`

**For 21 files**:
- ~22KB per file silence = ~462 KB total (negligible)
- AI-generated WAVs: typically 50–200 KB each = ~1–4 MB (still acceptable)

**Assessment**: ✅ **NO ISSUE** — 21 files at 50–200 KB is well within typical system RAM. File streaming not necessary.

**However**, if the audio catalog grows to 100+ files or includes longer videos, consider:
- Streaming generation: write chunks to disk as they arrive
- Async I/O: use `aiofiles` instead of blocking file writes

---

## 9. Voice Selection Logic & Engine Mapping (MEDIUM SEVERITY)

### Finding: Voice assignment convention exists but not validated

**File**: `tools/generate_audio.py:22–57` (prompts + voices)

**Mapping**:
- `"alloy"` → Taunts, level starts, death gasps (mercenary/rough)
- `"echo"` → HUD notifications, weapon alerts, alarms (electronic/synthetic)
- `"onyx"` → Pain, death screams (authoritative/deep)

**Issues**:

1. **No validation that voice matches category**:
   - If someone assigns `voice="echo"` to a pain sound, no error
   - Should be enforced: `pain → onyx`, `taunt → alloy`, `pickup → echo`

2. **Engine sound ID mapping incomplete**:
   - PAIN01.WAV → `"engine_sound_id": "DUKE_GRUNT"` ✓ (mapped)
   - TAUNT01.WAV → `"engine_sound_id": None` (unmapped)
   - If engine adds taunt support, the mapping must be updated
   - No cross-reference validation against `source/SOUNDEFS.H`

3. **Engine ID name vs. code mismatch**:
   - Manifest has `"DUKE_GRUNT"` but doesn't verify it exists in SOUNDEFS.H
   - No runtime check: if someone renames `DUKE_GRUNT → PLAYER_GRUNT`, manifest stales

**Severity**: **MEDIUM** — Silent mismatches; would only surface during gameplay testing

**Recommended Fix**:
```python
VOICE_CATEGORY_MAPPING = {
    "taunt": "alloy",
    "pain": "onyx",
    "death": ["onyx", "alloy"],  # onyx primary, alloy for variation
    "pickup": "echo",
    "weapon": "echo",
    "alarm": "echo",
    "ambient": "echo",
    "level_start": "alloy",
}

# In VOICE_LINES generation:
for filename, prompt, voice in VOICE_LINES:
    category = determine_category(filename)
    expected_voices = VOICE_CATEGORY_MAPPING.get(category, [])
    assert voice in (expected_voices if isinstance(expected_voices, list) else [expected_voices]), \
        f"{filename}: voice={voice} doesn't match category={category}"
```

---

## 10. compat/audio_stub.c Mixer Thread Race (UNRESOLVED BLOCKER)

### Finding: Round-3 compat audit identified mixer thread race; status unknown

**File**: `compat/audio_stub.c:114–195` (mixer_play, mixer_play_3d)

**Reference**: `docs/audits/compat-layer-r3.md:371–373`

**Issue**:
- `mixer_channel_chunk[]` and `mixer_channel_cbval[]` are accessed without SDL_LockAudio/UnlockAudio guards
- If SDL mixer thread callbacks (`mixer_channel_done()`) run concurrently with main thread calls to `mixer_play()`, race conditions occur:
  - Data corruption in `mixer_channel_chunk[]`
  - Use-after-free if chunk is freed while being loaded

**Status**: **OPEN** — No evidence of fix in current code

**Does this block audio features?**
- ✅ `--no-ai` mode: No audio playback (no SDL mixer), unaffected
- ✅ API mode with silence fallback: No audio playback, unaffected
- ❌ Runtime audio playback (once SDL2_mixer integrated): **BLOCKED** until race is fixed

**Severity**: **HIGH** (for runtime audio) — **UNRESOLVED** from round-3

**No action needed for this audit**, but this is a known blocker for audio feature completeness.

---

## 11. Windows/macOS aiohttp Compatibility (LOW SEVERITY)

### Finding: Event loop handling differs on Windows

**File**: `tools/generate_audio.py:446`

**Code**:
```python
return asyncio.run(_generate_audio_async_main(concurrency, endpoint, api_key, model))
```

**Issue on Windows**:
- `asyncio.run()` uses `ProactorEventLoop` on Windows (default in Python 3.10+)
- aiohttp requires special setup on Windows: may need `WindowsSelectorEventLoopPolicy`
- No explicit event loop policy set

**Symptoms (if occurs)**:
- OSError: [WinError 10038] An operation was attempted on something that is not a socket
- Intermittent failures on Windows builds

**Severity**: **LOW** — Typically works; only manifests on edge cases

**Safe fix**:
```python
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
return asyncio.run(_generate_audio_async_main(...))
```

---

## Summary of Findings

| # | Finding | Severity | File:Line | Already Tracked? |
|---|---------|----------|-----------|------------------|
| 1 | ThreadPoolExecutor missing try/catch on future.result() | HIGH | 432 | ❌ NEW |
| 2 | Manifest always written regardless of generation success | HIGH | 404 | ❌ NEW |
| 3 | Asyncio semaphore lacks acquire timeout (deadlock risk) | MEDIUM | 453 | ❌ NEW |
| 4 | Manifest schema lacks version & enum validation | MEDIUM | 62–244 | ❌ NEW |
| 5 | aiohttp 3.8.0–3.8.5 vulnerable to CVE-2023-37276 | MEDIUM | requirements.txt:3 | ❌ NEW |
| 6 | Voice selection logic not validated | MEDIUM | 22–57 | ❌ NEW |
| 7 | CI/CD doesn't test audio generation | LOW | release.yml | ⚠️ KNOWN |
| 8 | Windows event loop policy not set | LOW | 446 | ❌ NEW |
| 9 | VOICE_LINES/SOUND_MANIFEST sync enforcement | LOW | 22–244 | ⚠️ MINOR |
| 10 | compat mixer thread race (from R3 compat audit) | HIGH | compat/audio_stub.c | ✅ TRACKED |

---

## Recommendations

### CRITICAL (Fix before release)
1. **Add try/catch guards** to ThreadPoolExecutor results collection (line 432)
2. **Add `status` field** to manifest to track generation success
3. **Upgrade aiohttp** to 3.9.0+ to eliminate CVE-2023-37276

### HIGH (Next sprint)
4. Implement **semaphore acquire timeout** using `asyncio.timeout()` or `asyncio.wait_for()`
5. Add **voice category validation** to VOICE_LINES generation
6. Implement **manifest schema versioning** and JSON-schema validation

### MEDIUM (Future)
7. Add **CI/CD audio test suite** (silence generation + manifest validation)
8. Implement **Windows event loop policy** guard
9. Monitor **mixer thread race** fix progress in compat audit

### LOW (Documentation)
10. Document that **VOICE_LINES and SOUND_MANIFEST must stay in sync** in CONTRIBUTING.md

---

## Verification Checklist: Post-Parallelization

- [x] ThreadPoolExecutor for `--no-ai` works (silence files generated correctly)
- [x] asyncio + aiohttp for API path works (with semaphore + concurrency limits)
- [x] Graceful fallback on API errors (silence + error message)
- [x] Manifest generated correctly (JSON valid, all 21 entries present)
- [ ] ~~Error handling complete in ThreadPoolExecutor~~ → **NEEDS FIX** (Issue #1)
- [ ] ~~Manifest accuracy validated~~ → **NEEDS FIX** (Issue #2)
- [ ] ~~Semaphore timeout protection~~ → **NEEDS FIX** (Issue #3)
- [x] aiohttp connector limit matches Azure endpoint capability
- [x] Voice assignments respect documented convention (alloy/echo/onyx)

---

## Conclusion

The parallel audio generation infrastructure is **functionally correct for silent placeholder mode** but **introduces three HIGH-severity error handling gaps** in the threading path and manifest validation. The async path is more robust (silent fallback on errors) but lacks semaphore timeout protection.

**Key blockers for production audio**:
1. ThreadPoolExecutor error propagation (can cause silent data loss)
2. Manifest doesn't track which files actually generated (breaks asset validation)
3. Mixer thread race in compat layer (blocks runtime audio playback entirely)

**Estimated fix time**: 4–6 hours for all critical & high-priority items.

---

**Audit Completed**: 2025-05-21  
**Auditor**: Audio Engineer Persona  
**Next Review**: Post-fix validation (round-3)  
**License**: GPL-2.0
