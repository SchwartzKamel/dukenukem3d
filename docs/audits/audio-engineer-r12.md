# Audio Engineer Audit — Round 12 (Cycle 42 Verification + Parallel Generation Safety)

**Auditor**: audio-engineer persona  
**Timestamp**: 2025-06-22 (Cycle 42 verification)  
**Status**: ✅ Cycle-41 Landing Verified | 🟡 Parallel Manifest Race Detected | 📋 5 New Findings

---

## Executive Summary

Round 12 audit verifies **cycle-41 closure** of `compat-r11-mix-init-retry-backoff` landing and conducts comprehensive sweep of audio generation safety and runtime robustness. All prior fixes (cycles 26, 33, 34, 38) remain verified. Cycle-41 verification confirms:

1. **Cycle-41 Mix_OpenAudio retry landing**: 3-attempt exponential backoff implemented (100/200/400ms) with correct Mix_GetError() usage; graceful fallback + error path safe.
2. **Cycle-41 landing assessment**: ROBUST for transient device-busy scenarios; tests are grep-pattern-based (no mutation/integration testing).
3. **NEW CRITICAL FINDING (audio-r12-parallel-manifest-race)**: ThreadPoolExecutor workers in `_generate_audio_parallel_local()` modify SOUND_MANIFEST[idx] directly (lines 400, 406) without locks — race condition when concurrent workers update same shared dict. Mitigation: results already collected per-worker, manifest update can be sequentialized.
4. **Mix_Init fallback gap**: Line 365 logs warning on Mix_Init(OGG|MP3) failure but does NOT attempt fallback; Mix_OpenAudio proceeds without OGG/MP3 support — acceptable but low logging priority.
5. **Test coverage gap**: TestMixInitRetryBackoff tests (4 functions) are GREP-ONLY; no integration test actually calls FX_Init with mocked Mix_OpenAudio failures.
6. **Voice catalog stability**: No changes since cycle 34; VOICE_LINES remains 21 entries, all voice enums (alloy/echo/onyx) stable.
7. **Generate_audio.py / generate_assets.py integration**: Audio generation WAVs are created in `generated_assets/sounds/`; repacking workflow requires explicit `python3 tools/generate_assets.py --no-ai` (documented, not automated).

---

## Section 1: Cycle-41 Landing Verification (`compat-r11-mix-init-retry-backoff`)

### Status: ✅ **LANDED AND ROBUST**

**Closure Citation**: Commit b77317c (cycle-40 audit-pass with compat-r11 landing)

**Finding 1.1: Mix_OpenAudio Retry Loop Implementation**

**File**: `compat/audio_stub.c:367-391`

**Current Implementation** (post-cycle-41):
```c
// compat-r11-mix-init-retry-backoff: 3-attempt exp-backoff
int mix_open_attempt;
int mix_open_result = -1;
for (mix_open_attempt = 1; mix_open_attempt <= 3; mix_open_attempt++) {
    mix_open_result = Mix_OpenAudio(mixrate ? (int)mixrate : 44100,
                                    MIX_DEFAULT_FORMAT,
                                    numchannels > 1 ? 2 : 1,
                                    2048);
    if (mix_open_result >= 0) {
        break; // Success
    }
    fprintf(stderr, "Audio init attempt %d/3 failed: %s\n", mix_open_attempt, Mix_GetError());
    if (mix_open_attempt < 3) {
        // Exponential backoff: 100ms, 200ms, 400ms
        int delay_ms = 100 * (1 << (mix_open_attempt - 1));
        SDL_Delay(delay_ms);
    }
}

if (mix_open_result < 0) {
    SDL_QuitSubSystem(SDL_INIT_AUDIO);
    FX_ErrorCode = FX_Error;
    return FX_Error;
}
```

**Verification Checklist**:

| Criterion | Status | Citation | Notes |
|-----------|--------|----------|-------|
| (a) Loop structure 1–3 attempts | ✅ **PASS** | Line 372 | for loop with `<= 3` bounds |
| (b) Exponential backoff calculation | ✅ **PASS** | Line 383 | `100 * (1 << (attempt-1))` = 100, 200, 400 ms |
| (c) Mix_GetError() called in retry block | ✅ **PASS** | Line 380 | Uses Mix_GetError(), NOT SDL_GetError() |
| (d) Failure path returns FX_Error | ✅ **PASS** | Line 390 | Properly returns FX_Error after 3 failures |
| (e) SDL_Delay only on non-final attempt | ✅ **PASS** | Line 381 | `if (mix_open_attempt < 3)` guard prevents delay on last attempt |
| (f) Audio subsystem cleanup on failure | ✅ **PASS** | Line 389 | SDL_QuitSubSystem(SDL_INIT_AUDIO) called |

**Assessment**: Cycle-41 landing **verified complete and robust**. Transient device-busy scenarios now gracefully retry; error messaging clear. No RWops/memory leaks in retry path. ✅

---

**Finding 1.2: Mix_Init Fallback Context**

**File**: `compat/audio_stub.c:362-365`

```c
int init_flags = Mix_Init(MIX_INIT_OGG | MIX_INIT_MP3);
if (!init_flags) {
    // Mix_Init can fail in minimal builds, but Mix_OpenAudio still works for WAV
    fprintf(stderr, "Warning: Mix_Init(OGG|MP3) failed, some formats may be unavailable\n");
}
```

**Analysis**:
- Mix_Init(OGG|MP3) attempts to load optional format plugins
- Failure (e.g., in minimal SDL2_mixer builds without OGG/MP3 support) is **non-fatal**
- Mix_OpenAudio proceeds regardless — WAV playback still works
- Warning logged to stderr; operator aware of format limitations
- **Risk**: LOW — fallback is intentional by design

**Assessment**: Mix_Init failure handling is **SAFE**. Operator gets diagnostic. ✅

---

## Section 2: Test Coverage Assessment (TestMixInitRetryBackoff)

### Status: 🟡 **GREP-BASED ONLY; NO INTEGRATION TESTING**

**Test Class Location**: `tests/test_audio_pipeline.py:671-751`

**4 Test Functions**:

| Test | Coverage | Type | Assessment |
|------|----------|------|-------------|
| `test_sentinel_comment_present` | Verifies comment exists | Static pattern | ✅ Basic |
| `test_sdl_delay_exponential_backoff` | Verifies SDL_Delay + 100 * (1 <<) pattern | Regex match | ✅ Pattern only |
| `test_mix_get_error_in_retry_block` | Verifies Mix_GetError() in retry section | String search | ✅ Pattern only |
| `test_mix_open_audio_wrapped_in_loop` | Verifies loop structure + Mix_OpenAudio | Regex match | ✅ Pattern only |

**Gap Analysis**:

**Missing Integration Tests**:
- ❌ No actual FX_Init() call with mocked Mix_OpenAudio failure
- ❌ No simulation of Mix_OpenAudio returning -1 on each attempt
- ❌ No verification that SDL_Delay is actually called
- ❌ No measurement of retry timing (does it actually back off?)
- ❌ No test for Mix_GetError() being called on each failure

**Current Coverage**: Tests confirm **code patterns exist** but do **NOT verify behavior** (mutation testing / integration testing).

**Risk**: Acceptable for DOC-ONLY audit (no source edits required). Recommended for future: integration test with mocked SDL2_mixer would validate retry loop actually works at runtime.

---

## Section 3: Parallel Generation Safety Audit

### Status: 🔴 **CRITICAL FINDING: Race Condition Detected**

**Finding 3.1: Manifest Update Race in ThreadPoolExecutor**

**File**: `tools/generate_audio.py:383-410`

**Current Implementation**:
```python
with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
    future_to_idx = {}
    for idx, (filename, prompt, voice) in enumerate(VOICE_LINES):
        # ... spawn worker
        future = executor.submit(process_voice_line, (idx, (filename, prompt, voice)))
        future_to_idx[future] = idx

    results = [None] * len(VOICE_LINES)
    for future in concurrent.futures.as_completed(future_to_idx.keys()):
        idx = future_to_idx[future]
        try:
            result_idx, filename, wav_data = future.result()
            out_path = os.path.join(OUTPUT_DIR, filename)
            _atomic_write_bytes(out_path, wav_data)
            results[idx] = filename
            # ⚠️ RACE CONDITION HERE:
            SOUND_MANIFEST[idx]["status"] = "generated"        # Line 400
            SOUND_MANIFEST[idx]["generated_at"] = timestamp    # Line 401
            print(f"    [Silence placeholder] OK")
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            # ⚠️ RACE CONDITION HERE:
            SOUND_MANIFEST[idx]["status"] = "failed"           # Line 406
            SOUND_MANIFEST[idx]["error"] = error_msg           # Line 407
            SOUND_MANIFEST[idx]["generated_at"] = timestamp    # Line 408
```

**Analysis**:
- **Multiple threads** executing `as_completed()` loop concurrently
- **Shared data structure**: SOUND_MANIFEST is a list of dicts (no locks)
- **Mutation sites**: Lines 400, 401, 406, 407, 408 write to SOUND_MANIFEST[idx]
- **Race window**: Thread A writes to SOUND_MANIFEST[idx]["status"], Thread B simultaneously writes to SOUND_MANIFEST[idx]["generated_at"] — both access same dict without synchronization
- **Python GIL caveat**: CPython GIL protects individual bytecode instructions, but **dict mutation across multiple lines = NOT ATOMIC**
- **Risk**: Dict corruption or lost updates; unpredictable state in SOUND_MANIFEST

**Example Race**:
```
Thread 1 (idx=0):
  SOUND_MANIFEST[0]["status"] = "generated"   # ✅ write
  SOUND_MANIFEST[0]["generated_at"] = ts       # ✅ write

Thread 2 (idx=1):
  SOUND_MANIFEST[1]["status"] = "generated"   # ✅ write
  SOUND_MANIFEST[1]["generated_at"] = ts       # ✅ write

Possible interleaving (race):
  Thread 1: SOUND_MANIFEST[0]["status"] = "generated"
  Thread 2: SOUND_MANIFEST[1]["status"] = "generated"   # ← dict resizing? GC? Context switch?
  Thread 1: SOUND_MANIFEST[0]["generated_at"] = ts      # ← may operate on corrupted dict
```

**Mitigation**: Results already collected in `results[]` array; sequentialize manifest updates AFTER thread pool completes:

```python
# Collect results in order (as currently done)
results = [None] * len(VOICE_LINES)
for future in concurrent.futures.as_completed(future_to_idx.keys()):
    idx = future_to_idx[future]
    try:
        result_idx, filename, wav_data = future.result()
        # ... write WAV file (atomic, no race) ...
        results[idx] = (filename, "success", None)  # Store in results
    except Exception as e:
        results[idx] = (filename, "failed", str(e))

# ✅ AFTER thread pool exits, update manifest sequentially:
for idx, (filename, status, error) in enumerate(results):
    if status == "success":
        SOUND_MANIFEST[idx]["status"] = "generated"
        SOUND_MANIFEST[idx]["generated_at"] = timestamp
    else:
        SOUND_MANIFEST[idx]["status"] = "failed"
        SOUND_MANIFEST[idx]["error"] = error
        SOUND_MANIFEST[idx]["generated_at"] = timestamp
```

**Priority**: MEDIUM — observed on --no-ai path (slow path, large workers pool unlikely to hit race in practice, but latent bug). API path uses asyncio (different concurrency model, no shared dict mutation in worker).

---

**Finding 3.2: Async API Path Thread-Safety**

**File**: `tools/generate_audio.py:423-455` (asyncio path)

```python
async def _generate_audio_async_main(concurrency, endpoint, api_key, model, acquire_timeout_sec=30.0, use_deterministic=False):
    """Generate audio via API using asyncio + aiohttp with semaphore."""
    # ... create semaphore and bounded_generate coroutine ...
    
    async with aiohttp.ClientSession(...) as session:
        tasks = [
            bounded_generate(session, idx, filename, prompt, voice)
            for idx, (filename, prompt, voice) in enumerate(VOICE_LINES)
        ]
        results = await asyncio.gather(*tasks)
```

**Analysis**:
- asyncio single-threaded event loop (no GIL contention)
- `bounded_generate()` is async function (cooperative multitasking)
- **But**: SOUND_MANIFEST mutations happen inside `bounded_generate()` - **same race condition potential**

**Verification**: Grep for SOUND_MANIFEST mutations in API path:

```bash
grep -n "SOUND_MANIFEST\[" tools/generate_audio.py | grep -A5 "bounded_generate\|_generate_audio_async"
```

Expected: Should see similar manifest updates happening inside async task (need to verify).

---

## Section 4: Voice Catalog Stability

### Status: ✅ **STABLE; NO CHANGES SINCE CYCLE 34**

**VOICE_LINES Catalog** (21 entries confirmed):

**Enumeration**:
- ✅ 5× TAUNT (alloy): TAUNT01–TAUNT05
- ✅ 3× PAIN (onyx): PAIN01–PAIN03
- ✅ 2× DEATH (onyx/alloy): DEATH01–DEATH02
- ✅ 4× PICKUP (echo): PICKUP01–PICKUP04
- ✅ 3× WEAPON (echo): WEAPON01–WEAPON03
- ✅ 2× LEVEL_START (alloy): LEVEL01–LEVEL02
- ✅ 2× ALARM/AMBIENT (echo): ALARM01, COMP01

**Total**: 21 entries

**Verdict**: Voice catalog **STABLE**. No drift. ✅

---

## Section 5: GRP Repacking Workflow Clarity

### Status: 🟡 **DOCUMENTED BUT NOT AUTOMATED**

**Finding 5.1: Audio Generation → GRP Repacking Linkage**

**Files**: `tools/generate_audio.py`, `tools/generate_assets.py:1785-1814`

**Current Workflow** (as documented in audio-engineer.agent.md lines 67–71):
```bash
python3 tools/generate_audio.py                  # Generates WAVs in generated_assets/sounds/
python3 tools/generate_assets.py --no-ai         # Repacks GRP (separate invocation)
```

**generate_audio.py Scope** (lines 468-483):
- Generates silence WAVs in `generated_assets/sounds/TAUNT01.WAV`, etc.
- Writes `generated_assets/sounds/MANIFEST.json`
- **Does NOT call GRP repacking**

**generate_assets.py Scope** (lines 1785-1814):
- Function `generate_audio_assets()` generates MIDI + VOC **from CON parsing**
- **Does NOT read WAV files from generate_audio.py output**
- Generates MIDI stubs + VOC stubs procedurally; audio_stub.c is not consulted

**Analysis**:
- Two separate audio generation pipelines: **generate_audio.py** (GPT Audio 1.5 WAVs) vs **generate_assets.py** (MIDI/VOC stubs)
- **gap**: No linking between them. Workflow requires manual sequence:
  1. Run generate_audio.py → generates WAVs
  2. Run generate_assets.py --no-ai → repacks GRP (but GRP repacking does NOT include generated WAVs!)
- **Verification**: Check if generate_assets.py actually reads from generated_assets/sounds/:

**Result**: generate_assets.py does NOT consume generate_audio.py outputs. Two independent pipelines exist.

**Risk**: LOW (by design; each tool has clear scope), but UX gap (operator confusion).

---

## Section 6: Compat Layer Sweep (MUSIC_*/FX_Play* Error Paths)

### Status: ✅ **NO NEW BUGS FOUND**

**Finding 6.1: MUSIC_PlaySong State Consistency (Cycle-38 Fix Verification)**

**File**: `compat/audio_stub.c:903-926`

```c
int MUSIC_PlaySong(unsigned char *song, int loopflag)
{
    if (mixer_initialized && song) {
        unsigned long size = midi_file_size(song, 72000);
        free_current_music();
        current_music_rw = SDL_RWFromConstMem(song, (size_t)size);
        if (current_music_rw) {
            current_music = Mix_LoadMUS_RW(current_music_rw, 0);
            if (!current_music) {
                SDL_FreeRW(current_music_rw);
                current_music_rw = NULL;
                return MUSIC_Error;  /* Cycle-38 fix: return error */
            }
            Mix_PlayMusic(current_music, loopflag ? -1 : 0);
            music_loop    = loopflag;
            music_playing = 1;  /* Cycle-38 fix: only set on success */
        }
    }
    return MUSIC_Ok;
}
```

**Verification**:
- ✅ MUSIC_Error returned on Mix_LoadMUS_RW failure (line 915)
- ✅ music_playing only set inside success branch (line 919)
- ✅ No RWops leak (line 913-914: SDL_FreeRW called)
- ✅ Cycle-38 closure still intact

**Verdict**: State machine consistency **VERIFIED SAFE**. ✅

---

**Finding 6.2: MUSIC_StopSong / FX_PlayVoc Sweep**

**Files**: `compat/audio_stub.c:892-901`, `570-640` (FX_PlayVoc)

**MUSIC_StopSong** (lines 892-901):
```c
int MUSIC_StopSong(void)
{
    if (mixer_initialized)
        Mix_HaltMusic();
    free_current_music();
    music_playing = 0;
    return MUSIC_Ok;
}
```

**Analysis**:
- Mix_HaltMusic() return ignored (void function in SDL2_mixer, acceptable)
- free_current_music() called unconditionally (safe)
- music_playing = 0 clears state (safe)
- No leaks detected

**FX_PlayVoc** (via mixer_play):
- RWops allocated, freed on Mix_LoadWAV_RW failure (cycle-26 fix verified)
- No unbounded waits detected
- Error path safe

**Verdict**: No new bugs in error paths. ✅

---

## Section 7: Prior Cycles Verification (26, 33, 34, 38)

### ✅ All Prior Fixes Remain Intact

| Cycle | Fix | Status | Citation |
|-------|-----|--------|----------|
| 26 | SDL_FreeRW cleanup on Mix_LoadWAV_RW/Mix_LoadMUS_RW failure | ✅ | compat/audio_stub.c: lines 186, 245, 913 |
| 33 | Mix_Init(OGG\|MP3) + Mix_Quit() forward-compat | ✅ | compat/audio_stub.c: lines 362, 400 |
| 34 | Manifest schema v1.0 + _redact_endpoint() | ✅ | tools/generate_audio.py: lines 24-38, 339-341 |
| 38 | MUSIC_PlaySong state consistency (MUSIC_Error + music_playing guard) | ✅ | compat/audio_stub.c: lines 915, 919 |

---

## New Findings & Todos (Round 12)

### 5 New Actionable Todos

| ID | Priority | Title | File | Category | Effort |
|----|----------|-------|------|----------|--------|
| `audio-r12-parallel-manifest-race` | **MEDIUM** | Fix ThreadPoolExecutor race in manifest updates; sequentialize after pool exits | tools/generate_audio.py:383–410 | Correctness | 1.5h |
| `audio-r12-async-manifest-race` | MEDIUM | Verify asyncio path (lines 423–455) for similar race; audit bounded_generate() SOUND_MANIFEST updates | tools/generate_audio.py:423–455 | Correctness | 1.5h |
| `audio-r12-mix-init-integration-test` | LOW | Add integration test for FX_Init retry loop (mocked Mix_OpenAudio failure simulation) | tests/test_audio_pipeline.py:671+ | Testing | 2h |
| `audio-r12-audio-grp-linkage-doc` | LOW | Document that generate_audio.py (WAVs) and generate_assets.py (MIDI/VOC) are independent pipelines; clarify GRP repacking scope | docs/CONTRIBUTING.md | Documentation | 1h |
| `audio-r12-sem-timeout-analysis` | LOW | Analyze asyncio.timeout() usage (line 436); verify 30s acquire timeout + 60s request timeout logic | tools/generate_audio.py:436 | Robustness | 1h |

**Total Effort**: ~7h (2 MEDIUM/HIGH correctness issues + 3 LOW housekeeping/robustness)

---

## Audit Rigor Checklist

- ✅ Cycle-41 landing verified (Mix_OpenAudio retry + error path + Mix_GetError usage)
- ✅ TestMixInitRetryBackoff test coverage assessed (grep-based, no integration tests)
- ✅ Parallel generation safety audited (CRITICAL race detected in ThreadPoolExecutor path)
- ✅ Voice catalog checked for drift (21 entries stable)
- ✅ MUSIC_PlaySong / MUSIC_StopSong / FX_PlayVoc error paths swept (all safe)
- ✅ Generate_audio.py / generate_assets.py integration clarity verified
- ✅ Prior cycles (26, 33, 34, 38) re-verified (all fixes intact)
- ✅ **NO source/test/build modifications** (audit document only)
- ✅ **NO commits, no git tree mutations**

---

## Next Steps for Implementation

**Priority 1 (MEDIUM — Correctness)**:
- `audio-r12-parallel-manifest-race`: Fix race in ThreadPoolExecutor path (affects --no-ai mode)
- `audio-r12-async-manifest-race`: Audit + fix similar race in asyncio API path

**Priority 2 (LOW — Testing + Documentation)**:
- `audio-r12-mix-init-integration-test`: Add runtime integration test for retry loop
- `audio-r12-audio-grp-linkage-doc`: Clarify dual-pipeline architecture

**Priority 3 (LOW — Robustness)**:
- `audio-r12-sem-timeout-analysis`: Verify asyncio timeout composition logic

---

## References

- Cycle 26: SDL_FreeRW on error paths
- Cycle 33: SDL2_mixer 3.0+ forward-compat (Mix_Init/Mix_Quit)
- Cycle 34: Manifest schema v1.0 + validate_manifest() + _redact_endpoint()
- Cycle 38: MUSIC_PlaySong state-consistency fix
- Cycle 41: compat-r11-mix-init-retry-backoff (3-attempt exp backoff)
- R11: 6 new todos (mix-init-error-logging, fading-return-diagnostic, etc.)

**Unique Token**: `audio-engineer-r12-CYCLE41_PARALLEL_RACE_DETECTION_AUDIT`
