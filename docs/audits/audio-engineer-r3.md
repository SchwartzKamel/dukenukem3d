# Audio Engineering Audit Report — Round 3

**Auditor**: Audio Engineer Persona  
**Date**: 2025-05-21  
**Scope**: Post-r2 implementation verification; fresh findings in error handling, async timeout, and manifest consistency  
**Classification**: Code Review & Integration Risk Assessment  

---

## Executive Summary

Round 3 audit reveals **one HIGH-severity regression** (semaphore timeout parameter parsed but silently ignored), **two MEDIUM-severity issues** (manifest inconsistency between local/async paths, and 3D audio attenuation lacks validation), and **one LOW-severity gap** (no error handling on manifest write). The r2 fixes for ThreadPoolExecutor error handling are properly implemented in the local path, but the async path remains incomplete.

**Key Findings**:
- ⚠️ `--acquire-timeout-sec` parameter wired to call site but not to function (parameter dropped silently)
- ⚠️ Semaphore acquire not wrapped in timeout (asyncio.wait_for missing)
- ⚠️ Async path doesn't update SOUND_MANIFEST entries with status/generated_at/error
- ⚠️ 3D audio distance attenuation (×4 scale) lacks documentation and validation
- ✅ Local ThreadPoolExecutor error handling fixed in r2 (verified)
- ✅ WAV format correct for mono (22050 Hz, 16-bit, PCM verified)

---

## 1. Semaphore Timeout Parameter Regression (HIGH SEVERITY)

### Finding: `--acquire-timeout-sec` parsed but not applied

**File**: `tools/generate_audio.py:188–194, 217–218, 286–289, 293, 299`

**Issue**:

```python
# Line 188-194: CLI parser accepts the parameter
parser.add_argument(
    "--acquire-timeout-sec",
    type=float,
    default=30.0,
    help="Timeout in seconds for semaphore acquire in async mode (default: 30.0)",
)

# Line 217-218: Parameter passed to function
generated = _generate_audio_parallel_api(
    args.concurrency, endpoint, api_key, model, args.acquire_timeout_sec, args.no_ai  # ← extra params!
)

# Line 286: Function signature doesn't accept the parameter!
def _generate_audio_parallel_api(concurrency, endpoint, api_key, model):
    """Generate audio via API using asyncio + aiohttp with semaphore."""
    return asyncio.run(
        _generate_audio_async_main(concurrency, endpoint, api_key, model)  # ← not passed!
    )

# Line 293: Async function also doesn't accept it
async def _generate_audio_async_main(concurrency, endpoint, api_key, model):
    semaphore = asyncio.Semaphore(concurrency)
    
    async def bounded_generate(session, idx, filename, prompt, voice):
        async with semaphore:  # ← NO TIMEOUT!
            wav_data, error = await generate_audio_async(...)
```

**Root Cause**: 

The r2 commit message claims "wrap semaphore.acquire() in asyncio.wait_for() with that timeout", but the implementation is incomplete:
1. Call site passes `args.acquire_timeout_sec` but function doesn't accept it (Python silently drops extra args)
2. Function signature lacks the parameter
3. Semaphore is never wrapped in `asyncio.wait_for()` or `asyncio.timeout()`
4. Result: **The semaphore timeout feature is completely non-functional**

**Consequences**:
- If the async generator hangs while holding a semaphore slot (e.g., network stall before aiohttp timeout kicks in), the slot is held indefinitely
- All subsequent tasks timeout waiting for the slot
- Pipeline hangs with no progress for 60+ seconds before aiohttp timeout expires
- `--acquire-timeout-sec` CLI flag has no effect

**Severity**: **HIGH** — Semaphore deadlock risk that was supposed to be fixed remains unimplemented

**Recommended Fix**:
```python
def _generate_audio_parallel_api(concurrency, endpoint, api_key, model, acquire_timeout_sec=30.0, use_deterministic=False):
    """Generate audio via API using asyncio + aiohttp with semaphore."""
    return asyncio.run(
        _generate_audio_async_main(concurrency, endpoint, api_key, model, acquire_timeout_sec, use_deterministic)
    )

async def _generate_audio_async_main(concurrency, endpoint, api_key, model, acquire_timeout_sec=30.0, use_deterministic=False):
    """Async generator for API calls with rate limiting and timeout."""
    if use_deterministic:
        timestamp = "1970-01-01T00:00:00Z"
    else:
        timestamp = datetime.now(timezone.utc).isoformat()
    
    semaphore = asyncio.Semaphore(concurrency)
    generated = [None] * len(VOICE_LINES)

    async def bounded_generate(session, idx, filename, prompt, voice):
        try:
            async with asyncio.timeout(acquire_timeout_sec + 60):  # semaphore + request
                async with semaphore:
                    wav_data, error = await generate_audio_async(...)
                    return idx, filename, wav_data, error
        except asyncio.TimeoutError:
            return idx, filename, None, "Semaphore + request timeout"
    
    # ... rest of function, update manifest with status/generated_at/error per entry
```

---

## 2. Async Path Doesn't Update Manifest Entries (MEDIUM SEVERITY)

### Finding: Status/generated_at/error fields not populated in async mode

**File**: `tools/generate_audio.py:316–328` (async path) vs. `269–278` (local path)

**Issue**:

The local (ThreadPoolExecutor) path correctly updates SOUND_MANIFEST entries:
```python
# Line 270-271: LOCAL PATH updates manifest
SOUND_MANIFEST[idx]["status"] = "generated"
SOUND_MANIFEST[idx]["generated_at"] = timestamp
```

But the async path writes WAVs without updating manifest:
```python
# Line 316-328: ASYNC PATH — no manifest update!
results = await asyncio.gather(*tasks)
for idx, filename, wav_data, error in results:
    if wav_data is None:
        wav_data = generate_silence_wav(0.5)
        if error:
            print(f"    [!] {error}")
        print(f"    [Fallback: silence] OK")
    else:
        print(f"    [AI] OK ({len(wav_data)} bytes)")

    out_path = os.path.join(OUTPUT_DIR, filename)
    with open(out_path, "wb") as f:
        f.write(wav_data)
    generated[idx] = filename
    # ← Missing: SOUND_MANIFEST[idx]["status"] = "generated" or "fallback"
    # ← Missing: SOUND_MANIFEST[idx]["generated_at"] = timestamp
    # ← Missing: if error: SOUND_MANIFEST[idx]["error"] = error
```

**Consequences**:
- After running with API (async path), all manifest entries still have `"status": "generated"` and `"generated_at": "1970-01-01T00:00:00Z"` (the hardcoded r2 value)
- No distinction between:
  - Files that were AI-generated successfully
  - Files that fell back to silence due to API failure
  - Files that timed out
- Downstream tools (GRP packer, asset validator) can't tell which audio is real vs. placeholder
- If a job fails partially, the manifest doesn't reflect the reality

**Severity**: **MEDIUM** — Manifest doesn't reflect actual generation outcomes in async path

**Recommended Fix**: Apply the same manifest update logic from local path (lines 270–278) to async path (within the loop at line 316–328):
```python
results = await asyncio.gather(*tasks)
for idx, filename, wav_data, error in results:
    is_fallback = False
    if wav_data is None:
        wav_data = generate_silence_wav(0.5)
        is_fallback = True
        status = "fallback"
        if error:
            print(f"    [!] {error}")
            status = "failed"
            SOUND_MANIFEST[idx]["error"] = error
        print(f"    [Fallback: silence] OK")
    else:
        status = "generated"
        print(f"    [AI] OK ({len(wav_data)} bytes)")

    # Update manifest for this entry
    SOUND_MANIFEST[idx]["status"] = status
    SOUND_MANIFEST[idx]["generated_at"] = timestamp

    out_path = os.path.join(OUTPUT_DIR, filename)
    with open(out_path, "wb") as f:
        f.write(wav_data)
    generated[idx] = filename
```

---

## 3. 3D Audio Distance Attenuation Undocumented (MEDIUM SEVERITY)

### Finding: Distance scale factor (×4) lacks validation and documentation

**File**: `compat/audio_stub.c:199–206` and `484–490`

**Issue**:

```c
// mixer_play_3d(), line 199-206
{
    int d = distance * 4;  // ← Scale factor of 4, no explanation
    sdl_dist = (Uint8)(d > 255 ? 255 : (d < 0 ? 0 : d));
}

// FX_Pan3D(), line 484-490
{
    int d = distance * 4;  // ← Same scale, no explanation
    Uint8 sdl_dist = (Uint8)(d > 255 ? 255 : (d < 0 ? 0 : d));
}
```

**Questions**:

1. **Is ×4 the correct scale?** No evidence provided. The comment says "Scale ×4 for audible attenuation" but doesn't cite game design docs or testing data.
2. **What is the BUILD distance unit?** The code comments say "distance arrives as (BUILD_dist >> 6)", i.e., a pre-shifted value. But what's the original range? 0–2048? 0–4096?
3. **Is clamping to 255 correct?** SDL_mixer expects distance 0–255, but are we clipping audio too aggressively?
4. **No test data**: No test vectors showing what game distances map to what SDL distances.

**Consequences**:
- 3D audio attenuation could be wrong by a factor of 2–10x
- Players might hear footsteps too loud or too quiet
- Impossible to debug without game asset logs

**Severity**: **MEDIUM** — Plausible but unvalidated implementation; would only surface during gameplay testing

**Recommended Action**:
1. Add documentation to the code:
   ```c
   /*
    * distance arrives as (BUILD_dist >> 6), pre-scaled by engine.
    * Original BUILD distance units are 0–4096 (full map diagonal).
    * After >>6 shift, we get 0–64 (roughly).
    * SDL_mixer distance scale: 0 = close, 255 = far.
    * Empirical ×4 scale chosen via audio QA testing [reference needed].
    * Test vectors: distance_build 64 → sdl_dist 255 (far); distance_build 0 → sdl_dist 0 (close).
    */
   ```
2. Add test to validate attenuation curve (not required for r3, but recommended for r4)

---

## 4. No Error Handling on Manifest Write (LOW SEVERITY)

### Finding: Manifest JSON written without try/catch

**File**: `tools/generate_audio.py:227–230`

**Issue**:

```python
manifest_path = os.path.join(OUTPUT_DIR, "MANIFEST.json")
with open(manifest_path, "w") as f:
    json.dump(SOUND_MANIFEST, f, indent=2, sort_keys=True)
print(f"\n=== Manifest written to {manifest_path} ===")
```

If manifest writing fails (disk full, permission denied, JSON serialization error), the exception propagates and crashes the script before cleanup or error reporting.

**Consequence**: Silent failure or confusing error message if disk is full or permissions are wrong.

**Severity**: **LOW** — Rare in practice; local dev machines have space; CI runs in fresh containers

**Recommended Fix**:
```python
try:
    manifest_path = os.path.join(OUTPUT_DIR, "MANIFEST.json")
    with open(manifest_path, "w") as f:
        json.dump(SOUND_MANIFEST, f, indent=2, sort_keys=True)
    print(f"\n=== Manifest written to {manifest_path} ===")
except Exception as e:
    print(f"[!] Failed to write manifest: {e}")
    return 1
```

---

## 5. WAV Format Generation (VERIFIED ✓)

### Finding: Mono WAV format correct; no stereo support

**File**: `tools/generate_audio.py:82–99`

**Status**: ✅ **PASS** — WAV format is correct for mono

Verified:
- RIFF header: correct size calculation
- fmt chunk: PCM (format 1), mono (channels 1), 22050 Hz, 16-bit
- ByteRate: 44100 (= 22050 * 1 * 2) ✓
- BlockAlign: 2 (= 1 * 2) ✓
- data chunk: correct size for 0.5s silence (22050 bytes)

**Observation**: Function only supports mono. If API-generated audio is stereo, fallback is mono → audio mismatch. Not an issue for v1 (all audio will be mono), but document limitation.

---

## 6. Error Recovery in Local Path (VERIFIED ✓)

### Finding: ThreadPoolExecutor error handling implemented correctly in r2

**File**: `tools/generate_audio.py:261–279`

**Status**: ✅ **FIXED** in r2 commit 0f77a37

Verified:
```python
try:
    result_idx, filename, wav_data = future.result()
    # ... process ...
    SOUND_MANIFEST[idx]["status"] = "generated"
except Exception as e:
    error_msg = f"{type(e).__name__}: {str(e)}"
    SOUND_MANIFEST[idx]["status"] = "failed"
    SOUND_MANIFEST[idx]["error"] = error_msg
    print(f"    [ERROR] {SOUND_MANIFEST[idx]['wav']}: {error_msg}")
```

Worker crashes no longer crash the entire pipeline. ✓

---

## 7. aiohttp Security Upgrade (VERIFIED ✓)

### Finding: CVE-2023-37276 fixed in r2

**File**: `requirements.txt:3`

**Status**: ✅ **FIXED** in r2 commit 0f77a37

Verified: `aiohttp>=3.9.0,<4.0.0` (no longer allows vulnerable 3.8.0–3.8.5)

---

## 8. Voice Lines Catalog Sync (VERIFIED ✓)

### Finding: VOICE_LINES and SOUND_MANIFEST in sync

**File**: `tools/generate_audio.py:22–57, 62–244`

**Status**: ✅ **PASS** — 21 entries each, filenames match

Verified programmatically; no orphaned entries.

---

## Summary of Findings

| # | Finding | Severity | File:Line | Already Fixed? | NEW Todo? |
|---|---------|----------|-----------|---|---|
| 1 | Semaphore timeout parameter silently ignored | HIGH | 217–218, 286, 293, 299 | ❌ NO | ✅ YES |
| 2 | Async path doesn't update manifest entries | MEDIUM | 316–328 vs. 269–278 | ❌ NO | ✅ YES |
| 3 | 3D audio distance attenuation ×4 scale undocumented | MEDIUM | 199–206, 484–490 | ✅ DESIGNED | ⚠️ OPTIONAL |
| 4 | No error handling on manifest write | LOW | 227–230 | ❌ NO | ⚠️ OPTIONAL |
| 5 | WAV format generation (mono only) | N/A | 82–99 | ✅ CORRECT | ❌ NO |
| 6 | ThreadPoolExecutor error recovery | N/A | 261–279 | ✅ FIXED R2 | ❌ NO |
| 7 | aiohttp CVE-2023-37276 | N/A | requirements.txt | ✅ FIXED R2 | ❌ NO |
| 8 | Voice catalog sync | N/A | 22–57, 62–244 | ✅ VERIFIED | ❌ NO |

---

## Recommendations

### CRITICAL (Fix before release)
1. **Wire semaphore timeout to async path** (Issue #1)
   - Signature: `def _generate_audio_parallel_api(..., acquire_timeout_sec, use_deterministic)`
   - Wrap: `async with asyncio.timeout(acquire_timeout_sec)` around semaphore acquire
   - Test: Verify timeout fires within ±2 seconds

### HIGH (Next sprint)
2. **Update manifest in async path** (Issue #2)
   - Mirror local path logic (status, generated_at, error fields)
   - Test: Run with API failure, verify manifest reflects failed entries

### MEDIUM (Future)
3. **Document 3D audio attenuation** (Issue #3)
   - Add code comments explaining ×4 scale rationale
   - Reference game design docs or QA test vectors
   - Add to CONTRIBUTING.md if not already there

4. **Add error handling to manifest write** (Issue #4)
   - Wrap manifest write in try/catch
   - Return error code on failure

---

## Verification Checklist: Post-r2 Implementation

- [x] ThreadPoolExecutor error handling works (verified)
- [x] aiohttp ≥3.9.0 security fix applied (verified)
- [x] Manifest has status/generated_at/error fields (verified in local path)
- [ ] **Semaphore timeout wired and functional** ← NEEDS FIX
- [ ] **Async path updates manifest** ← NEEDS FIX
- [x] WAV format correct for mono (verified)
- [x] Voice catalog in sync (verified)
- [x] Local path manifest update works (verified)

---

## Conclusion

Round 3 reveals that the r2 fix for semaphore timeout was **implemented in the call site and parameter parsing, but never wired to the actual async function**. The manifest update logic works correctly in the local (ThreadPoolExecutor) path but is missing entirely from the async (aiohttp) path, leading to inconsistency.

The 3D audio attenuation scale factor (×4) is well-implemented but lacks documentation and validation. No functional bugs detected, but design intent is unclear.

**Estimated fix time**: 1–2 hours for both critical items (wire timeout + add manifest updates to async path).

---

**Audit Completed**: 2025-05-21  
**Auditor**: Audio Engineer Persona  
**Next Review**: Post-fix validation (round 4)  
**License**: GPL-2.0
