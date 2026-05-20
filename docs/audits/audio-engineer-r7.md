# Audio Engineer Audit — Round 7

**Auditor**: Audio Engineer Persona  
**Date**: 2025-07-15  
**Scope**: Cycles 20–24 closure validation; post-r6 verification of atomicity, MIDI validation, and error paths  
**Classification**: Code Review & Integration Risk Assessment  

---

## Executive Summary

Round 7 confirms that **cycles 20–24 audio hardening has landed solidly**: atomic writes in `generate_audio.py` (cycle 18/20), MIDI SMF header validation (cycle 18), and comprehensive error handling are all verified correct and in place. Voice catalog remains in perfect sync (21 entries); SDL2_mixer thread-safety locks (FX_Set*) are solid.

**New findings this round** (2 MEDIUM-severity resource leaks):
1. **SDL_RWops leak in mixer_play**: Mix_LoadWAV_RW failure path (line 185) leaks SDL_RWops
2. **SDL_RWops leak in mixer_play_3d**: Mix_LoadWAV_RW failure path (line 241) leaks SDL_RWops  
3. **Dangling RWops pointer in MUSIC_PlaySong**: Mix_LoadMUS_RW failure path (line 882) leaves stale RWops

**Key Verified Closures**:
- ✅ Atomic writes with tmp+rename pattern (generate_audio.py:24–42)
- ✅ MIDI header_len bounds checking (audio_stub.c:749–758)
- ✅ Error handling in parallel generation (generate_audio.py:295–310, 336–344)
- ✅ Voice catalog & manifest in perfect sync (21 entries, all metadata correct)
- ✅ FX_Set* SDL_LockAudio guards verified (all 4 functions: volume, reverb, fastreverb, reverbdelay)

**Regression Testing Status**: All cycle-15 tests passing; FX_SetReverb variants test coverage gap still open from r6.

---

## 1. Verification of Cycles 20–24 Closures

### 1.1 Atomic Writes in generate_audio.py

**Status**: ✅ **VERIFIED SOLID**

**File**: `tools/generate_audio.py:24–42`

**Implementation**:
```python
def _atomic_write_bytes(path: str, data: bytes) -> None:
    """Write bytes to a file atomically using tmp+rename pattern.
    
    This ensures that if the process is killed or hits an error mid-write,
    the original file (if it exists) is left untouched rather than corrupted.
    Uses POSIX atomic rename within the same filesystem.
    """
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.replace(tmp_path, path)
    except OSError:
        # Clean up temp file on error to avoid leaving stray .tmp files
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
```

**Verification**:
- ✅ tmp+rename atomic pattern on POSIX systems
- ✅ `os.replace()` is atomic rename (no intermediate corrupted state)
- ✅ Cleanup of temp file on OSError (prevents stray .tmp files)
- ✅ Used consistently at lines 298 and 377 (both AI and silence paths)
- ✅ Manifest also uses same pattern (lines 254–257)

**Functional correctness**: Ensures WAV output files are written atomically; partial writes never corrupt existing files.

---

### 1.2 MIDI SMF Header Validation (Cycle 18)

**Status**: ✅ **VERIFIED SOLID**

**File**: `compat/audio_stub.c:748–760`

**Implementation**:
```c
header_len = ((unsigned long)data[4]  << 24) |
             ((unsigned long)data[5]  << 16) |
             ((unsigned long)data[6]  << 8)  | data[7];
num_tracks = ((unsigned long)data[10] << 8)  | data[11];

/* Bounds check: header_len should be between 6 and reasonable upper bound */
if (header_len < 6 || header_len > max_size - 8) {
    fprintf(stderr, "midi_file_size: invalid header length %lu (out of bounds)\n", header_len);
    return 0;
}

/* Bounds check: num_tracks should be non-negative and reasonable */
if (num_tracks > 256) {
    fprintf(stderr, "midi_file_size: invalid track count %lu (> 256)\n", num_tracks);
    return 0;
}

pos = 8 + header_len;
```

**Verification**:
- ✅ Lower bound on header_len (must be ≥ 6, standard MIDI header size)
- ✅ Upper bound on header_len (must fit within max_size - 8 to prevent arithmetic overflow)
- ✅ Validates num_tracks is reasonable (≤ 256, typical MIDI files have 1–16 tracks)
- ✅ Returns 0 (invalid) on bounds violations, preventing OOB reads
- ✅ Integer overflow prevention: `header_len > max_size - 8` prevents `pos = 8 + header_len` from exceeding max_size

**Functional correctness**: Prevents malformed MIDI files from causing integer overflow or out-of-bounds track parsing.

---

### 1.3 Error Path Coverage in generate_audio.py

**Status**: ✅ **VERIFIED SOLID**

**Files**: `tools/generate_audio.py:269–380`

**Coverage**:

| Path | Coverage | Location |
|------|----------|----------|
| Thread worker exception | ✅ Caught | Lines 295–310 (ThreadPoolExecutor.as_completed) |
| Semaphore timeout in API path | ✅ Caught | Lines 336–344 (asyncio.TimeoutError) |
| API error (HTTP non-200) | ✅ Caught | Lines 181–182 (async path) |
| JSON parse error | ✅ Caught | Line 185 (resp.json) |
| Base64 decode error | ✅ Caught | Line 187 (base64.b64decode) |
| Network exception | ✅ Caught | Lines 179, 188 (except Exception) |
| File write failure | ✅ Caught + cleanup | Lines 32–42 (_atomic_write_bytes exception path) |
| Temp file cleanup on error | ✅ Explicit | Lines 37–41 (os.remove fallback) |

**Verification**:
- ✅ Worker exceptions in thread pool cause `future.result()` to raise (caught at line 296)
- ✅ Failed generations fall back to silence with error logged (lines 360–370)
- ✅ Manifest entry marked as "failed" or "fallback" (lines 362, 373–374)
- ✅ Errors are recorded in manifest with timestamp (lines 308, 366)
- ✅ All generated WAVs written atomically; partial writes impossible

**Functional correctness**: Robust error handling; partial failures do not corrupt the output directory or manifest.

---

### 1.4 Voice Catalog & Manifest Sync (Re-Verified)

**Status**: ✅ **VERIFIED IN PERFECT SYNC**

**File**: `tools/generate_audio.py` (VOICE_LINES and SOUND_MANIFEST)

**Verification**:
- ✅ VOICE_LINES: 21 entries (lines 46–81)
- ✅ SOUND_MANIFEST: 21 entries (lines 86+)
- ✅ Filenames match in identical order (TAUNT01.WAV ... COMP01.WAV)
- ✅ Voice assignments (alloy/echo/onyx) are consistent across categories
- ✅ All metadata fields present: voice, category, prompt_summary, engine_sound_id, status, generated_at
- ✅ No schema drift detected since r5

**No catalog drift found.**

---

## 2. NEW FINDINGS: Resource Leak in SDL_RWops Handling (MEDIUM SEVERITY)

### Finding 2.1: SDL_RWops Leak in mixer_play (MEDIUM)

**File**: `compat/audio_stub.c:180–185`

**Current Code**:
```c
size = sound_file_size(ptr);
rw   = SDL_RWFromConstMem(ptr, (size_t)size);
if (!rw) return -1;

chunk = Mix_LoadWAV_RW(rw, 1);       // ← freesrc=1: SDL2_mixer owns rw cleanup
if (!chunk) return -1;                // ← BUG: returns without freeing rw!
```

**Issue**:
1. `SDL_RWFromConstMem` allocates an SDL_RWops structure
2. `Mix_LoadWAV_RW(rw, 1)` is called with `freesrc=1`, meaning SDL2_mixer will free rw when Mix_Chunk is freed
3. **If Mix_LoadWAV_RW returns NULL (parse error)**, the function returns -1 without freeing rw
4. **Result**: Orphaned SDL_RWops allocation (memory leak)

**Impact**:
- Garbled WAV files, truncated files, or invalid headers cause Mix_LoadWAV_RW to fail
- Each failure leaks ~64 bytes (size of SDL_RWops struct)
- In a long play session with many corrupt sounds, memory accumulates

**Severity**: **MEDIUM** — Affects robustness under invalid asset data; not a critical crash, but a slow leak.

**Recommended Fix**:
```c
chunk = Mix_LoadWAV_RW(rw, 1);
if (!chunk) {
    SDL_FreeRW(rw);  // ← Free rw before returning
    return -1;
}
```

---

### Finding 2.2: SDL_RWops Leak in mixer_play_3d (MEDIUM)

**File**: `compat/audio_stub.c:237–241`

**Current Code**:
```c
rw   = SDL_RWFromConstMem(ptr, (size_t)size);
if (!rw) return -1;

chunk = Mix_LoadWAV_RW(rw, 1);
if (!chunk) return -1;  // ← Same leak as mixer_play
```

**Issue**: Identical to Finding 2.1 — Mix_LoadWAV_RW failure leaks SDL_RWops.

**Recommended Fix**: Same as 2.1 — free rw before returning on Mix_LoadWAV_RW failure.

---

### Finding 2.3: Dangling RWops Pointer in MUSIC_PlaySong (MEDIUM)

**File**: `compat/audio_stub.c:875–882`

**Current Code**:
```c
if (mixer_initialized && song) {
    unsigned long size = midi_file_size(song, 72000);
    free_current_music();                              // ← Frees old rw
    current_music_rw = SDL_RWFromConstMem(song, (size_t)size);  // ← New rw created
    if (current_music_rw) {
        current_music = Mix_LoadMUS_RW(current_music_rw, 0);   // ← freesrc=0: we own cleanup
        if (current_music)
            Mix_PlayMusic(current_music, loopflag ? -1 : 0);
    }
}
```

**Issue**:
1. `Mix_LoadMUS_RW(rw, 0)` is called with `freesrc=0`, meaning **we** are responsible for freeing rw
2. **If Mix_LoadMUS_RW returns NULL**, `current_music` is NULL but `current_music_rw` still points to the unfreed RWops
3. **Result**: On the *next* call to MUSIC_PlaySong, `free_current_music()` will try to free the stale RWops
   - `if (current_music_rw) { SDL_FreeRW(current_music_rw); ... }` at line 778 will free it
   - But there's a gap between line 882 failure and the next MUSIC_PlaySong call where the RWops is leaked

**Impact**:
- MIDI files that fail to parse (corrupted headers, unsupported format) cause a temporary RWops leak
- Subsequent MUSIC_PlaySong calls clean up the dangling pointer, but the leak persists until then
- In a single-level-per-session game, impact is minimal; in a mod with many level transitions, leaks accumulate

**Severity**: **MEDIUM** — Affects long-term session stability; not an immediate crash risk.

**Recommended Fix**:
```c
current_music = Mix_LoadMUS_RW(current_music_rw, 0);
if (!current_music) {
    SDL_FreeRW(current_music_rw);  // ← Free on failure
    current_music_rw = NULL;
}
if (current_music)
    Mix_PlayMusic(current_music, loopflag ? -1 : 0);
```

---

## 3. Verification of R5 Pending Items

### 3.1 VOC Data Offset Validation (audio-r5-voc-dataoff-validation)

**Status**: 🟡 **STILL PENDING**

**File**: `compat/audio_stub.c:109–111`

**Current Code**:
```c
data_off = (unsigned short)(p[20] | ((unsigned)p[21] << 8));
if (data_off < 26) data_off = 26;
// ✅ MISSING: Upper bound check!
```

**Note**: This was flagged in r6 as well. Still requires an upper-bound check to validate data_off is reasonable.

**Recommendation**: See r6 for proposed fix. Should be seeded as a formal todo.

---

### 3.2 Manifest Freshness Tracking (audio-r5-manifest-freshness-tracking)

**Status**: 🟡 **STILL PENDING**

**File**: `tools/generate_audio.py:273–277`

**Current State**:
```python
if use_deterministic:
    timestamp = "1970-01-01T00:00:00Z"
else:
    timestamp = datetime.now(timezone.utc).isoformat()
```

**Status**: **IMPROVED** (r7 finding)
- ✅ Non-deterministic mode now tracks actual generation time (datetime.now)
- 🟡 Deterministic mode still uses epoch (for GRP reproducibility)
- 🟡 No `generation_method` field to distinguish AI vs. silence fallback

**Recommendation**: Add `generation_method` field to manifest (ai, silence, fallback) to allow downstream tools to detect stale re-generations.

---

## 4. Test Coverage Gap (R6 Pending Item)

### Finding: FX_SetReverb/FastReverb/ReverbDelay Locking Not Tested

**Status**: 🟡 **STILL OPEN**

**File**: `tests/test_engine_net_hardening_regressions.py:206–233`

**Current Test**:
```python
class TestFXSetVolumeLocking:
    """Verify cycle-15 FX_SetVolume thread-safety in audio_stub.c."""
    def test_audio_stub_fx_setvolume_locking(self, repo_root):
        """audio_stub.c FX_SetVolume must use SDL_LockAudio."""
        # ... checks for SDL_LockAudio in FX_SetVolume only
```

**Gap**:
- ❌ Test does NOT verify SDL_LockAudio in FX_SetReverb, FX_SetFastReverb, FX_SetReverbDelay
- ✅ Code has locks in place (verified at lines 441–443, 456–458, 474–476)
- ❌ But regression test could catch accidental reverts

**Recommendation**: Parametrize test to check all four functions (volume, reverb, fastreverb, reverbdelay).

---

## 5. Thread-Safety & Concurrency (Re-Verified ✓)

**Status**: ✅ **PASS** — No new race conditions

**File**: `compat/audio_stub.c:55–85 (mixer_channel_done), 415–483 (FX_Set*)`

**Verification**:
- ✅ mixer_channel_done() is safe to call from SDL audio thread (no re-entrant locks)
- ✅ All FX_Set* volume/reverb functions wrap writes in SDL_LockAudio/UnlockAudio
- ✅ mixer_play() and mixer_play_3d() wrap channel array updates in locks (lines 210–213, 263–266)
- ✅ Volume/pan arithmetic is overflow-safe (verified in r6)
- ✅ fx_callback writes are protected by SDL_LockAudio (lines 403–405)

**Conclusion**: Cycle-15 concurrency fixes remain solid; no new races detected.

---

## 6. Truncation & WAV/MIDI Robustness (Re-Verified)

**Status**: ✅ **ROBUST**

**Files**: `compat/audio_stub.c:125–158 (WAV), 733–773 (MIDI)`

**Verification**:
- ✅ WAV_file_size validates RIFF magic, WAVE format marker, and chunk size bounds
- ✅ MIDI_file_size validates header_len, num_tracks, and track parsing loops with bounds checks
- ✅ Truncated files detected: returns 0 (invalid) on magic/format mismatch
- ✅ VOC_file_size loops with `cur < limit` bounds (line 113)
- ✅ No buffer overreads in parsing loops

**Conclusion**: Format parsing is defensive and safe against truncation/corruption.

---

## Summary of Findings

| # | Finding | Severity | File:Line | Type | Status |
|---|---------|----------|-----------|------|--------|
| 1 | Atomic writes (tmp+rename) | N/A | generate_audio.py:24–42 | Cycle-20 Close | ✅ VERIFIED |
| 2 | MIDI header_len validation | N/A | audio_stub.c:748–760 | Cycle-18 Close | ✅ VERIFIED |
| 3 | Error handling (exceptions) | N/A | generate_audio.py:295–310, 336–344 | Cycle-20 Coverage | ✅ VERIFIED |
| 4 | Voice catalog & manifest sync | N/A | generate_audio.py | General | ✅ VERIFIED (21/21 in sync) |
| 5 | FX_Set* SDL_LockAudio guards | N/A | audio_stub.c:415–483 | Cycle-15 Close | ✅ RE-VERIFIED |
| 6 | SDL_RWops leak in mixer_play | **MEDIUM** | audio_stub.c:185 | **NEW** | 🟡 **OPEN** |
| 7 | SDL_RWops leak in mixer_play_3d | **MEDIUM** | audio_stub.c:241 | **NEW** | 🟡 **OPEN** |
| 8 | Dangling RWops in MUSIC_PlaySong | **MEDIUM** | audio_stub.c:882 | **NEW** | 🟡 **OPEN** |
| 9 | VOC data_off validation | MEDIUM | audio_stub.c:109–111 | R5 Pending | 🟡 STILL OPEN |
| 10 | Manifest freshness tracking | MEDIUM | generate_audio.py:273–277 | R5 Pending | 🟡 IMPROVED (needs generation_method field) |
| 11 | Test coverage: FX_SetReverb locking | LOW | test_engine_net_hardening_regressions.py:206+ | R6 Pending | 🟡 STILL OPEN |
| 12 | Thread-safety & concurrency | N/A | audio_stub.c | General | ✅ VERIFIED CLEAN |
| 13 | WAV/MIDI/VOC truncation robustness | N/A | audio_stub.c | General | ✅ VERIFIED ROBUST |

---

## Recommendations

### CRITICAL (Before Release)
None — cycle-15/18/20 hardening is solid and in place.

### HIGH (Next Sprint)
1. **Fix SDL_RWops leaks in mixer_play and mixer_play_3d** (Issues #6, #7)
   - Free SDL_RWops in Mix_LoadWAV_RW failure path
   - Estimated: 10–15 minutes

2. **Fix dangling RWops pointer in MUSIC_PlaySong** (Issue #8)
   - Free SDL_RWops in Mix_LoadMUS_RW failure path
   - Estimated: 10–15 minutes

### MEDIUM (Current Sprint / Backlog)
3. **Add VOC data_off upper-bound check** (Issue #9, r5 pending)
   - Validate offset is < MAX_SOUND_FILE_SIZE
   - Estimated: 15 minutes

4. **Add generation_method field to manifest** (Issue #10, r5 improvement)
   - Track AI vs. silence vs. fallback in SOUND_MANIFEST entries
   - Requires schema update + logging
   - Estimated: 45 minutes

5. **Extend regression test to FX_SetReverb variants** (Issue #11, r6 pending)
   - Parametrize test to verify SDL_LockAudio in all 4 FX_Set* functions
   - Estimated: 20 minutes

### LOW (Future / Nice-to-Have)
None identified this cycle.

---

## Verification Checklist: Post-Cycles 20–24 State

- [x] Atomic writes with tmp+rename (cycle-20 closure verified)
- [x] MIDI SMF header validation with bounds checks (cycle-18 closure verified)
- [x] Comprehensive error handling in generate_audio.py (cycle-20 closure verified)
- [x] Voice catalog: 21 entries in perfect sync with manifest
- [x] FX_Set* SDL_LockAudio guards (all 4 functions: volume, reverb, fastreverb, reverbdelay)
- [x] Thread-safety: no new race conditions
- [x] WAV/MIDI/VOC parsing: robust against truncation/corruption
- [ ] **SDL_RWops freed on Mix_LoadWAV_RW failure** ← NEW TODO
- [ ] **SDL_RWops freed on Mix_LoadMUS_RW failure** ← NEW TODO
- [ ] **VOC data_off upper-bound validated** ← R5 TODO (carried forward)
- [ ] **Manifest generation_method field added** ← R5 TODO (improved)
- [ ] **FX_SetReverb variants in regression tests** ← R6 TODO (carried forward)

---

## Conclusion

Round 7 audit confirms that **cycles 20–24 audio hardening is solid**. Atomic writes, MIDI validation, and error handling are all correctly implemented and verified. Voice catalog remains in perfect sync.

**Three NEW MEDIUM-severity resource leaks identified** in SDL_RWops error paths — these should be fixed before release, though they have limited impact in typical gameplay (leaks only occur on corrupt/truncated audio files). All fixes are straightforward (5–10 minutes each).

**Three R5/R6 pending items remain open** but are non-critical and can be addressed in parallel work.

Overall audio subsystem is **robust, well-integrated, and production-ready** with minor resource management improvements recommended.

---

**Audit Completed**: 2025-07-15  
**Auditor**: Audio Engineer  
**Next Review**: Post-r7 closure of leaks (if fixed)  
**License**: GPL-2.0
