# Audio Engineer Audit — Round 6

**Auditor**: Audio Engineer Persona  
**Date**: 2025-06-24  
**Scope**: Post-r5 verification; cycle-15 & cycle-18 closure validation; fresh audits of MIDI, MUSIC state, and test coverage gaps  
**Classification**: Code Review & Integration Risk Assessment  

---

## Executive Summary

Round 6 confirms that **all cycle-15 audio closures have landed and are correctly implemented** (SoundOwner array bounds + volume/reverb thread-safety). Round 5's three open items remain in pending state (VOC data_off validation, manifest freshness, plus test coverage now completed). 

Cycle-18 regression tests exist and cover critical cycle-15 closures, though **test coverage for FX_SetReverb/FX_SetFastReverb/FX_SetReverbDelay thread-safety is incomplete** (only FX_SetVolume is tested).

**New findings this round**:
1. **MIDI file parsing lacks explicit header length validation** (MEDIUM)
2. **No state-cleanup across map transitions for music** (MEDIUM)  
3. **Test regression gap**: FX_SetReverb variants not covered in SDL_LockAudio checks** (LOW)
4. **SoundOwner capacity management verified** (all voices now age out safely)

**Key Verified Closes**:
- ✅ `audio-r5-soundowner-overflow-fix` — SoundOwner array bounds + age-out at SOUNDS.C:440–461
- ✅ `fix-compat-volume-thread-safety` — All four FX_Set* volume/reverb functions wrapped with SDL_LockAudio/UnlockAudio

---

## 1. Verification of Cycle-15 Closes

### 1.1 SoundOwner Array Bounds (audio-r5-soundowner-overflow-fix)

**Status**: ✅ **CLOSED & VERIFIED**

**File**: `source/SOUNDS.C:440–461`

**Implementation**:
```c
if ( voice > FX_Ok )
{
    /* 
     * Bounds check: SoundOwner[num] can hold at most 4 owners.
     * If array is full (Sound[num].num >= 4), drop the oldest
     * and shift remaining owners down (age-out strategy).
     */
    if (Sound[num].num >= 4)
    {
        int j;
        FX_StopSound(SoundOwner[num][0].voice);
        for (j = 0; j < 3; j++)
            SoundOwner[num][j] = SoundOwner[num][j + 1];
        Sound[num].num--;
    }
    
    SoundOwner[num][Sound[num].num].i = i;
    SoundOwner[num][Sound[num].num].voice = voice;
    Sound[num].num++;
}
```

**Verification**:
- ✅ Bounds check (`Sound[num].num >= 4`) prevents out-of-bounds write
- ✅ Age-out mechanism: FX_StopSound + array shift (drops oldest, keeps newest 3)
- ✅ Counter decremented after shift (Sound[num].num--), then incremented after insert
- ✅ Protects against heap overflow in complex scenes with 5+ simultaneous sounds

**Functional correctness**: Prevents heap corruption when many sounds of same type play concurrently.

---

### 1.2 FX_Set* Thread-Safety Locking (fix-compat-volume-thread-safety)

**Status**: ✅ **CLOSED & VERIFIED**

**File**: `compat/audio_stub.c:415–480`

**Implementation**:
```c
void FX_SetVolume(int volume)
{
#ifdef HAVE_SDL2_MIXER
    if (mixer_initialized) {
        SDL_LockAudio();
        fx_volume = volume;
        SDL_UnlockAudio();
        Mix_Volume(-1, (volume > 255 ? MIX_MAX_VOLUME
                                     : (volume * MIX_MAX_VOLUME) / 255));
    } else {
        fx_volume = volume;
    }
#else
    fx_volume = volume;
#endif
}

void FX_SetReverb(int reverb)
{
#ifdef HAVE_SDL2_MIXER
    if (mixer_initialized) {
        SDL_LockAudio();
        fx_reverb = reverb;
        SDL_UnlockAudio();
    } else {
        fx_reverb = reverb;
    }
#else
    fx_reverb = reverb;
#endif
}

void FX_SetFastReverb(int reverb)
{
#ifdef HAVE_SDL2_MIXER
    if (mixer_initialized) {
        SDL_LockAudio();
        fx_reverb = reverb;
        SDL_UnlockAudio();
    } else {
        fx_reverb = reverb;
    }
#else
    fx_reverb = reverb;
#endif
}

void FX_SetReverbDelay(int delay)
{
#ifdef HAVE_SDL2_MIXER
    if (mixer_initialized) {
        SDL_LockAudio();
        fx_reverb_delay = delay;
        SDL_UnlockAudio();
    } else {
        fx_reverb_delay = delay;
    }
#else
    fx_reverb_delay = delay;
#endif
}
```

**Verification**:
- ✅ **FX_SetVolume**: SDL_LockAudio/UnlockAudio guards fx_volume write (line 419–421)
- ✅ **FX_SetReverb**: SDL_LockAudio/UnlockAudio guards fx_reverb write (line 441–443)
- ✅ **FX_SetFastReverb**: SDL_LockAudio/UnlockAudio guards fx_reverb write (line 456–458)
- ✅ **FX_SetReverbDelay**: SDL_LockAudio/UnlockAudio guards fx_reverb_delay write (line 474–476)
- ✅ All guards conditional on mixer_initialized (prevents lock overhead when mixer is disabled)
- ✅ No data races on audio state variables

**Functional correctness**: Prevents race conditions between main thread (setting volume/reverb) and SDL audio thread (reading these values during playback).

---

## 2. Cycle-18 Regression Test Coverage Verification

**Status**: ✅ **TESTS EXIST** (with minor coverage gap noted)

**File**: `tests/test_engine_net_hardening_regressions.py`

**Coverage Confirmed**:
- ✅ RIFF validation (cycle 13): "RIFF" magic check
- ✅ WAVE format validation (cycle 13): "WAVE" marker check
- ✅ Mix_GroupOldest (cycle 13): Channel exhaustion retry logic
- ✅ FX_StopSound aging (cycle 15): SoundOwner age-out mechanism
- ✅ SDL_LockAudio (cycle 15): FX_SetVolume thread-safety

**Tests Present** (lines 206–233):
```python
class TestFXSetVolumeLocking:
    """Verify cycle-15 FX_SetVolume thread-safety in audio_stub.c."""

    def test_audio_stub_fx_setvolume_locking(self, repo_root):
        """audio_stub.c FX_SetVolume must use SDL_LockAudio."""
        audio_stub = repo_root / "compat" / "audio_stub.c"
        if not audio_stub.exists():
            pytest.skip(f"{audio_stub} not found")

        content = audio_stub.read_text(errors="replace")

        # Look for SDL_LockAudio in the function body
        fx_setvolume_section = re.search(
            r"(?:int|void)\s+FX_SetVolume.*?(?=\n(?:int|void)\s+\w+|$)",
            content,
            re.DOTALL
        )

        if fx_setvolume_section:
            section = fx_setvolume_section.group(0)
            has_lock = "SDL_LockAudio" in section
            assert has_lock, (
                "FX_SetVolume function must contain SDL_LockAudio for "
                "thread safety. Cycle-15 fix may have been reverted."
            )
        else:
            pytest.skip("FX_SetVolume function not found in audio_stub.c")
```

**Coverage Gap** (MEDIUM SEVERITY):
- ❌ Test does NOT verify SDL_LockAudio in FX_SetReverb, FX_SetFastReverb, FX_SetReverbDelay
- ❌ Only FX_SetVolume is tested (parametrized test at line 251 mentions only "SDL_LockAudio")
- **Impact**: If someone removes SDL_LockAudio from FX_SetReverb without updating FX_SetVolume, the revert would go undetected
- **Recommendation**: Extend TestFXSetVolumeLocking to check all four functions (FX_SetVolume, FX_SetReverb, FX_SetFastReverb, FX_SetReverbDelay)

---

## 3. Verification of R5 Open Items Status

### 3.1 VOC Data Offset Validation (audio-r5-voc-dataoff-validation)

**Status**: 🟡 **STILL PENDING**

**File**: `compat/audio_stub.c:102–123`

**Current Code**:
```c
static unsigned long voc_file_size(const unsigned char *p)
{
    unsigned short data_off;
    const unsigned char *cur, *limit;

    if (p[0] != 'C' || p[1] != 'r') return 0;
    /* SAFETY: p[20..21] unchecked — caller pre-condition (see header). */
    data_off = (unsigned short)(p[20] | ((unsigned)p[21] << 8));
    if (data_off < 26) data_off = 26;    // ← Lower bound OK
    // ✅ MISSING: Upper bound check!
    cur   = p + data_off;
    limit = p + MAX_SOUND_FILE_SIZE;
    while (cur < limit) {
        unsigned long blen;
        if (cur[0] == 0) { cur++; break; }       /* type 0 = terminator */
        if (cur + 4 > limit) { cur = limit; break; }
        blen = (unsigned long)cur[1]
             | ((unsigned long)cur[2] << 8)
             | ((unsigned long)cur[3] << 16);
        cur += 4 + blen;
    }
    return (unsigned long)(cur - p);
}
```

**Issue**: No upper bound check on data_off. A malformed VOC with `data_off = 0xFFFF` (65535) could cause `cur` to point far beyond the actual file size, reading into potentially unallocated memory.

**Recommended Fix** (as per r5):
```c
data_off = (unsigned short)(p[20] | ((unsigned)p[21] << 8));
if (data_off < 26) data_off = 26;
if (data_off >= MAX_SOUND_FILE_SIZE) return 0;  // ← ADD THIS
cur = p + data_off;
```

**Note**: This fix is straightforward and low-risk. Should be seeded as a formal todo.

---

### 3.2 Manifest Freshness Tracking (audio-r5-manifest-freshness-tracking)

**Status**: 🟡 **STILL PENDING**

**File**: `tools/generate_audio.py:64–244, 251–256`

**Current State**:
All SOUND_MANIFEST entries have:
```python
'generated_at': '1970-01-01T00:00:00Z',  # ← Hardcoded to epoch
```

**Issue**: When `--no-ai` is used (default in CI), all manifest entries are stamped with epoch (Jan 1, 1970), making it impossible to detect stale regenerations or distinguish when audio was last generated.

**Problem Scenario**:
1. Developer runs `python3 tools/generate_audio.py --no-ai` on July 1, 2025
2. Manifest entries still show `generated_at: 1970-01-01T00:00:00Z`
3. Downstream tools cannot verify freshness
4. If someone forgets to re-run generation after updating VOICE_LINES, stale audio silently ends up in build

**Recommended Fix** (as per r5):
```python
# Track actual generation time separately from deterministic output time
actual_generation_time = datetime.now(timezone.utc).isoformat()
if use_deterministic:
    output_timestamp = "1970-01-01T00:00:00Z"  # For GRP reproducibility
else:
    output_timestamp = actual_generation_time

# Update manifest entries
SOUND_MANIFEST[idx]['generated_at'] = output_timestamp
SOUND_MANIFEST[idx]['generation_method'] = 'silence' if is_fallback else 'ai'
```

**Note**: This fix requires manifest schema change + logging infrastructure. Should be seeded as a formal todo.

---

### 3.3 Audio Playback Round-Trip Tests (test-audio-round-trip-playback)

**Status**: ✅ **CLOSED (Cycle 15)**

**File**: `tests/test_audio_playback_roundtrip.py`

**Test Coverage Confirmed**:
- ✅ WAV header validation (RIFF + fmt + data chunks)
- ✅ Corrupt WAV rejection (invalid magic, invalid sizes)
- ✅ WAV silence sample generation
- ✅ Manifest sync with VOICE_LINES
- ✅ Voice line metadata completeness
- ✅ Mixer format compatibility checks
- ✅ SoundOwner capacity bounds (21 entries, max 4 per sound)
- ✅ Manifest entry count validation

**Tests Present** (18 test methods):
```python
def test_generate_silence_wav_valid_header(self):
def test_wav_header_round_trip(self):
def test_corrupt_wav_magic_rejected(self):
def test_corrupt_wav_size_field(self):
def test_wav_silence_samples_are_zero(self):
def test_manifest_wav_files_exist(self):
def test_manifest_wav_files_are_readable(self):
def test_manifest_wav_parseable_by_wave_module(self):
def test_voice_lines_and_manifest_in_sync(self):
def test_manifest_entry_voice_matches_voice_lines(self):
def test_all_generated_wavs_valid_for_mixer(self):
def test_manifest_entry_count_within_sound_owner_capacity(self):
def test_manifest_entries_have_required_metadata(self):
def test_sound_owner_category_bounds(self):
def test_mixer_availability_reported(self):
def test_wav_compatible_with_mixer_format(self):
def test_voice_lines_have_all_required_metadata(self):
def test_manifest_file_generation_integrity(self):
```

**Verification**: Round-trip audio generation, storage, validation, and mixer compatibility are comprehensively tested. **This todo is correctly closed.**

---

## 4. NEW Finding: MIDI Header Length Validation Gap (MEDIUM SEVERITY)

### Finding: MIDI parser doesn't validate header_len field bounds

**File**: `compat/audio_stub.c:733–760`

**Current Code**:
```c
static unsigned long midi_file_size(const unsigned char *data,
                                    unsigned long max_size)
{
    unsigned long header_len, num_tracks, pos, i;

    if (max_size < 14) return max_size;
    if (data[0] != 'M' || data[1] != 'T' ||
        data[2] != 'h' || data[3] != 'd')
        return max_size;

    /* Extract header length from bytes 4..7 (big-endian) */
    header_len = ((unsigned long)data[4]  << 24) |
                 ((unsigned long)data[5]  << 16) |
                 ((unsigned long)data[6]  << 8)  | data[7];
    num_tracks = ((unsigned long)data[10] << 8)  | data[11];
    pos = 8 + header_len;  // ← Problem: header_len not validated

    for (i = 0; i < num_tracks && pos + 8 <= max_size; i++) {
        unsigned long track_len;
        if (data[pos] != 'M' || data[pos+1] != 'T' ||
            data[pos+2] != 'r' || data[pos+3] != 'k')
            break;
        track_len = ((unsigned long)data[pos+4] << 24) |
                    ((unsigned long)data[pos+5] << 16) |
                    ((unsigned long)data[pos+6] << 8)  | data[pos+7];
        pos += 8 + track_len;
    }
    return pos > max_size ? max_size : pos;
}
```

**Issue**:
1. **No bounds check on header_len**: If a malformed MIDI has `header_len = 0xFFFFFFFF`, then `pos = 8 + 0xFFFFFFFF` causes integer overflow (or wraps in 32-bit scenarios)
2. **No validation that pos < max_size before entering track loop**: Loop condition checks `pos + 8 <= max_size`, but if `pos` starts way out of bounds, first iteration may skip
3. **num_tracks read from bytes 10–11 without validating that header is large enough to contain them**: Standard MIDI headers are 6 bytes; num_tracks at bytes 10–11 assumes header_len >= 3. Malformed MIDI could have header_len = 2, making bytes 10–11 part of next track data.

**Consequence**: A crafted MIDI file could cause integer overflow, pointer arithmetic errors, or out-of-bounds track parsing.

**Severity**: **MEDIUM** — Defensive check; real MIDI files have reasonable header lengths. But the code should validate before arithmetic.

**Recommended Fix**:
```c
header_len = ((unsigned long)data[4]  << 24) |
             ((unsigned long)data[5]  << 16) |
             ((unsigned long)data[6]  << 8)  | data[7];

/* Validate header length: typical MIDI header is 6 bytes, max reasonable ~100 bytes */
if (header_len < 6 || header_len > 1024) return max_size;

/* Prevent integer overflow */
if (header_len > max_size - 8) return max_size;

num_tracks = ((unsigned long)data[10] << 8)  | data[11];
pos = 8 + header_len;

if (pos >= max_size) return max_size;  // ← Ensure pos is in bounds before loop

for (i = 0; i < num_tracks && pos + 8 <= max_size; i++) {
    ...
}
```

---

## 5. NEW Finding: No Music State Cleanup Across Map Transitions (MEDIUM SEVERITY)

### Finding: MUSIC_PlaySong is called on map load without stopping previous music

**File**: `source/SOUNDS.C:278`

**Current Code**:
```c
// Line 278 in SOUNDS.C
MUSIC_PlaySong( MusicPtr, MUSIC_LoopSong );
```

**Issue**:
1. **No explicit MUSIC_StopSong() before MUSIC_PlaySong()**: When transitioning from one map to another, the code directly calls MUSIC_PlaySong() with the new music pointer
2. **Potential resource leak**: If the previous music Mix_Music handle is still allocated, calling Mix_LoadMUS_RW again without freeing it first could leak memory
3. **Undefined behavior**: Some audio libraries require stopping playback before loading new music; SDL2_mixer may or may not handle this gracefully

**Scenario**:
1. Player starts Level 1 → MUSIC_PlaySong called with level1_music.mid
2. Player finishes and starts Level 2 → MUSIC_PlaySong called with level2_music.mid
3. Previous Mix_Music handle may not be freed; Mix_Chunk data may remain allocated

**Consequence**: Gradual memory leak across level transitions in a long play session.

**Severity**: **MEDIUM** — Impacts long-term play session stability and memory footprint.

**Verification in compat/audio_stub.c**:
Looking at MUSIC_PlaySong (lines 859–878), it calls `free_current_music()` at line 864:
```c
int MUSIC_PlaySong(unsigned char *song, int loopflag)
{
#ifdef HAVE_SDL2_MIXER
    if (mixer_initialized && song) {
        unsigned long size = midi_file_size(song, 72000);
        free_current_music();  // ← Good! Cleans up old music
        current_music_rw = SDL_RWFromConstMem(song, (int)size);
        ...
    }
#endif
    music_loop    = loopflag;
    music_playing = 1;
    return MUSIC_Ok;
}

static void free_current_music(void)
{
    if (current_music) { Mix_FreeMusic(current_music); current_music = NULL; }
    if (current_music_rw) { SDL_FreeRW(current_music_rw); current_music_rw = NULL; }
}
```

**Actual Finding**: ✅ **VERIFIED SAFE** — The SDL2_mixer implementation correctly frees the old music before loading new music. **No issue here.**

**False Alarm Clarification**: The engine-level code (SOUNDS.C) doesn't need to call MUSIC_StopSong() explicitly because MUSIC_PlaySong() internally calls free_current_music(), which is the correct pattern.

---

## 6. Concurrency & Volume/Pan Math: VERIFIED CLEAN (No Regressions)

**Status**: ✅ **PASS** — No new race conditions

**File**: `compat/audio_stub.c:55–85 (mixer_channel_done), 415–480 (FX_Set*)`

**Verification**:
- ✅ mixer_channel_done() is safe to call from SDL audio thread (no re-entrant locks)
- ✅ All FX_Set* volume/reverb functions wrap writes in SDL_LockAudio/UnlockAudio
- ✅ mixer_play() and mixer_play_3d() wrap channel array updates in locks (lines 210–213, 263–266)
- ✅ Volume clamping arithmetic is safe: `(vol * MIX_MAX_VOLUME) / 255` with 255 * 128 = 32,640 (no overflow)
- ✅ Pan clamping is safe: range checks ensure 0–255 byte bounds

**Conclusion**: Cycle-11 and cycle-15 concurrency fixes are solid; no new races detected.

---

## 7. Voice Catalog & Manifest Sync (VERIFIED ✓)

**Status**: ✅ **PASS** — 21 entries match in sync

**File**: `tools/generate_audio.py` (VOICE_LINES and SOUND_MANIFEST)

**Verification**:
- ✅ VOICE_LINES: 21 entries (lines 24–59)
- ✅ SOUND_MANIFEST: 21 entries (lines 64–244 compacted into one large dict)
- ✅ All filenames match in same order
- ✅ Voice assignments (alloy/echo/onyx) are consistent
- ✅ Categories (taunt, pain, death, etc.) are consistent
- ✅ No unread manifest fields; all fields are present in generated output

**No schema drift detected.**

---

## 8. 3D Positional Audio Math (VERIFIED ✓)

**Status**: ✅ **PASS**

**File**: `compat/audio_stub.c:634–649 (FX_Pan3D)`

**Math Verification**:
- ✅ Angle conversion: `(angle * 360) / 32` correctly maps Duke3D angle units (0–32) to degrees (0–360)
- ✅ Angle wrapping: `if (sdl_angle < 0) sdl_angle += 360; sdl_angle %= 360;` ensures 0–359 range
- ✅ Distance scaling: `d = distance * 4` with Uint8 clamp to 0–255 is safe
- ✅ Edge cases handled: distance = 0 → sdl_dist = 0, distance > 63 → sdl_dist = 255

**No arithmetic overflows or logic errors found.**

---

## Summary of Findings

| # | Finding | Severity | File:Line | Type | Status |
|---|---------|----------|-----------|------|--------|
| 1 | SoundOwner bounds overflow fix | N/A | SOUNDS.C:440–461 | Cycle-15 Close | ✅ VERIFIED |
| 2 | FX_Set* thread-safety locks | N/A | audio_stub.c:415–480 | Cycle-15 Close | ✅ VERIFIED |
| 3 | Cycle-18 regression tests | N/A | test_engine_net_hardening_regressions.py | Cycle-18 Coverage | ✅ EXISTS (gap noted) |
| 4 | VOC data_off validation | MEDIUM | audio_stub.c:109–111 | R5 Pending | 🟡 STILL OPEN |
| 5 | Manifest freshness tracking | MEDIUM | generate_audio.py:251–256 | R5 Pending | 🟡 STILL OPEN |
| 6 | Audio round-trip tests | N/A | test_audio_playback_roundtrip.py | R5 Pending | ✅ CLOSED (Cycle 15) |
| 7 | MIDI header_len validation | MEDIUM | audio_stub.c:743–747 | NEW | 🟡 OPEN |
| 8 | Music state cleanup | N/A | SOUNDS.C:278 / audio_stub.c:859+ | NEW | ✅ SAFE (verified) |
| 9 | Test gap: FX_SetReverb locking | LOW | test_engine_net_hardening_regressions.py:206+ | NEW | 🟡 OPEN |
| 10 | Concurrency safety | N/A | audio_stub.c | General | ✅ VERIFIED CLEAN |
| 11 | Volume/pan arithmetic | N/A | audio_stub.c:415–649 | General | ✅ VERIFIED SAFE |
| 12 | Voice catalog sync | N/A | generate_audio.py | General | ✅ VERIFIED IN SYNC |
| 13 | 3D audio math | N/A | audio_stub.c:634–649 | General | ✅ VERIFIED CORRECT |

---

## Recommendations

### CRITICAL (Before Release)
None — cycle-15 fixes are solid and in place.

### HIGH (Next Sprint)
1. **Add MIDI header_len validation** (Issue #7)
   - Bounds-check header_len before arithmetic (6 ≤ header_len ≤ 1024)
   - Prevent integer overflow in `pos = 8 + header_len`
   - Validate pos is in bounds before track loop

### MEDIUM (Current Sprint / Backlog)
2. **Improve VOC data_off validation** (Issue #4, r5 pending)
   - Add upper-bound check on data_off (Issue #4)
   - Validate offset is within reasonable bounds (< MAX_SOUND_FILE_SIZE)

3. **Fix manifest freshness tracking** (Issue #5, r5 pending)
   - Track actual generation time separately from deterministic output time
   - Add `generation_method` and generation timestamp to manifest entries
   - Document determinism vs. freshness tradeoff in CONTRIBUTING.md

4. **Extend regression test coverage** (Issue #9, new)
   - Add test for SDL_LockAudio in FX_SetReverb, FX_SetFastReverb, FX_SetReverbDelay
   - Extend TestFXSetVolumeLocking to check all four functions

### LOW (Future / Nice-to-Have)
None identified this cycle.

---

## Verification Checklist: Post-r5 & Cycle-15/18 State

- [x] SoundOwner bounds checked + age-out (cycle-15 close verified)
- [x] FX_SetVolume/SetReverb/SetFastReverb/SetReverbDelay all have SDL_LockAudio (cycle-15 close verified)
- [x] Cycle-18 regression tests exist and cover RIFF/WAVE/Mix_GroupOldest/FX_StopSound/SDL_LockAudio
- [x] Audio round-trip tests are comprehensive (r5 pending item closed)
- [x] Concurrency races: none detected
- [x] Volume/pan math: overflow-safe
- [x] Voice catalog: in sync with manifest
- [x] 3D positional audio: math is correct
- [x] Music state cleanup: correctly implemented (free_current_music called before new MUSIC_PlaySong)
- [ ] **VOC data_off upper-bound validated** ← NEW TODO
- [ ] **MIDI header_len bounds-checked** ← NEW TODO
- [ ] **Manifest freshness tracked** ← r5 TODO (not closed in r6)
- [ ] **FX_SetReverb variants in regression tests** ← NEW TODO (low priority)

---

## Conclusion

Round 6 audit confirms the two cycle-15 closes (SoundOwner array bounds + FX_Set* thread-safety) are correctly implemented and robust. Audio pipeline is structurally sound with well-placed SDL2_mixer integration and proper error handling in the mixer layer.

**Two NEW issues identified**:
1. **MIDI header_len validation** (MEDIUM) — defensive bounds-check recommended
2. **Test coverage gap for reverb locking** (LOW) — extend regression tests

**One r5 pending item still open**:
- Manifest freshness tracking — requires schema + logging changes

**Estimated fix time**: 
- MIDI header_len: 30–45 minutes (straightforward bounds checks)
- Test coverage: 15–20 minutes (parametrized test extension)
- Manifest freshness: 1–2 hours (schema + logging infrastructure)

---

**Audit Completed**: 2025-06-24  
**Auditor**: Audio Engineer  
**Next Review**: Post-r6 fixes (if any)  
**License**: GPL-2.0
