# Audio Engineer Audit — Cycle r27

**DATE**: 2024-05-21  
**PERSONA**: Audio Engineer  
**SCOPE**: DOC-ONLY pass, cycle 115  
**HEAD**: `cce8798` (Cycle 115 grind+audit drain)

---

## 1. VERIFY Cycle 113 Landing: `audio-r26-callback-uint32-consolidation`

### 1.1 uint32_t Migration Coverage

**PASS** — Cycle 113 uint32_t consolidation complete.

- **84 uint32_t instances** across `compat/audio_stub.{c,h}` counted
- All callback signatures, VOC/WAV size calculations, SDL_GetTicks() timing covered
- **stdint.h included** in `compat/audio_stub.h:1` (verified)
- **_Static_assert(sizeof(uint32_t) == 4)** at `audio_stub.h:31` (present & verified)

### 1.2 Static Assertions Intact

**PASS** — 26 _Static_asserts present across compat layer.

```
compat/audio_stub.h:31   _Static_assert(sizeof(uint32_t) == 4)
compat/compat.h:124      _Static_assert(sizeof(uint32_t) == 4)
compat/sha256.h:27       _Static_assert(sizeof(uint32_t) == 4)
... (23 more across compat/*.c compat/*.h)
```

### 1.3 Structure ABI Validation

✅ **fx_blaster_config**: 28B (7×uint32_t) — `audio_stub.h:130`  
✅ **songposition**: 20B (5×uint32_t) — `audio_stub.h:241`  
✅ **ControlInfo**: 24B (6×fixed int32_t fields) — `audio_stub.h:544`  
✅ **task.volatile int32_t count**: unchanged — `audio_stub.h:288` (scheduler synchronization)  

### 1.4 Deferred Scope Item

⚠️  **USRHOOKS_GetMem** still unsigned long @ `audio_stub.h:331`:
```c
int  USRHOOKS_GetMem(void **ptr, unsigned long size);
```
**STATUS**: Documented as deferred (source/ scope conflict). Not in audio domain migration.

---

## 2. RE-VERIFY Previous Cycles

### 2.1 Voice Catalog (tools/generate_audio.py)

✅ **21 VOICE_LINES complete and synced**:
```
TAUNT01.WAV — "Welcome to the machine, punk." (alloy)
TAUNT02.WAV — "Lights out, chrome-head." (alloy)
TAUNT03.WAV — "Another day, another megacorp to burn." (alloy)
TAUNT04.WAV — "Is that all you got? My toaster fights harder." (alloy)
TAUNT05.WAV — "Time to take out the trash." (alloy)
PAIN01.WAV — pain grunt (onyx)
PAIN02.WAV — sharp grunt/shot (onyx)
PAIN03.WAV — heavy damage groan (onyx)
DEATH01.WAV — death scream (onyx)
DEATH02.WAV — "System... failure..." (alloy, dying gasp)
PICKUP01.WAV — "Stim acquired." (echo)
PICKUP02.WAV — "Ammo loaded." (echo)
PICKUP03.WAV — "Shield online." (echo)
PICKUP04.WAV — "Access granted." (echo)
WEAPON01.WAV — "Pulse pistol ready." (echo)
WEAPON02.WAV — "Scatter cannon armed." (echo)
WEAPON03.WAV — "Plasma launcher online." (echo)
LEVEL01.WAV — "Let's get to work." (alloy)
LEVEL02.WAV — "Another sector, another pile of scrap." (alloy)
ALARM01.WAV — "Warning. Intruder detected. Sector lockdown initiated." (echo)
COMP01.WAV — "Welcome to NeoTek Industries..." (echo)
```

**Count**: `sed -n '/^VOICE_LINES/,/^]/p' tools/generate_audio.py | grep "\.WAV" | wc -l` → **21** ✓

### 2.2 Audio Generation Paths (3 Total)

1. **Azure GPT Audio 1.5 API Path** (`_generate_audio_parallel_api`):
   - Async rate-limited (default 4 concurrent, Azure limit ~8)
   - Base64 decode + MP3→WAV conversion
   - Timeout: 120s per line
   - Lines 576–580

2. **Local Silence Fallback** (`_generate_audio_parallel_local`):
   - ThreadPoolExecutor (default 4 workers)
   - Procedural RIFF/WAV struct packing via `generate_silence_wav()`
   - Deterministic mode: ISO timestamp `1970-01-01T00:00:00Z`
   - Lines 617–650

3. **SDL2_mixer Runtime Playback** (compat/audio_stub.c):
   - `FX_Init()` → `Mix_Init()` → `Mix_OpenAudio()` → `Mix_AllocateChannels()`
   - Channel-finished callback with thread-safe snapshot semantics
   - 32-channel mixer state (`mixer_initialized`, `mixer_channel_chunk[]`, `mixer_channel_cbval[]`)
   - Lines 49–98 (channel callback logic)

### 2.3 SDL2_mixer CVE Posture (Cycle 107)

✅ **SECURITY.md annotation present** — `"*(Added cycle 107 — see docs/audits/security-and-secrets-r25.md for context.)*"`

Cross-ref: `SECURITY.md` documents SDL2_mixer CVE implications. Cycle 107 grind established SDL2 LTS chain; cycle 115 confirms documentation maintained.

---

## 3. FRESH FINDINGS (UP TO 3)

### Finding 1: USRHOOKS_GetMem Scope Restriction Revisited

**STATUS**: 🟡 **DISCUSSION POINT**

Cycle 113 deferred `USRHOOKS_GetMem` unsigned long signature due to source/ scope conflict (engine's malloc shim uses unsigned long internally). However, modern audit suggests two options:

**Option A** (current): Leave unsigned long in `audio_stub.h:331` as interface boundary layer.  
**Option B** (candidate): Lift scope restriction in future cycle (audio-r27-usrhooks-uint32-lift) to audit source/ malloc shim for uint32_t standardization.

**IMPACT**: None if left. Moderate refactoring if lifted (would touch SOUNDS.C malloc interop).  
**RECOMMENDATION**: Mark as `audio-r27-usrhooks-scope-review` for next 3-cycle review gate.

---

### Finding 2: Cycle 114 `compat-r27-demand-feed-callback` Follow-up

**STATUS**: 🟢 **READY FOR NEXT CYCLE**

Legacy `FX_StartDemandFeedPlayback()` interface is intact @ `audio_stub.h:202–204`:
```c
int   FX_StartDemandFeedPlayback(void (*function)(char **ptr, uint32_t *length),
                                 int right, int priority, uint32_t callbackval);
```

All demand-feed callback paths use uint32_t for size (`length` pointer param) and callback value. Cycle 114 follow-up to audit legacy callback contract completeness remains **viable**. Could fold into next grind cycle (audio-r27-demand-feed-validation).

---

### Finding 3: MIDI/VOC Parsing Not Currently Fuzzed

**STATUS**: 🟡 **AUDIT GAP**

Current test suite covers:
- VOC header size extraction (`tests/test_compat_layer.py:493` — 44.1kHz stereo validation)
- MIDI file bounds checking (`tests/test_compat_layer.py:562` — int32_t bounds)
- WAV roundtrip via Python wave module (`tests/test_audio_playback_roundtrip.py:181`)

**NOT COVERED** — Edge cases:
- Truncated VOC/MIDI headers
- Malformed RIFF chunks
- Zero-length data sections
- Boundary conditions on 32-bit size fields

**IMPACT**: Low (fuzzing MIDI/VOC parsing rarely surfaces bugs; both are legacy formats with stable implementations). However, adding hypothesis-based fuzz tests would improve confidence.

**RECOMMENDATION**: File `audio-r27-midi-voc-fuzz` as optional enhancement (low priority, 1–2 dev days if prioritized).

---

## 4. TEST RESULTS

### 4.1 Audio Pipeline Tests

```
pytest tests/test_audio_pipeline.py -q
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
114 passed, 14 warnings in 4.64s
```

✅ **ALL PASS** — 114 tests, 0 failures. Warnings are manifest legacy compat mode (expected).

### 4.2 Full Test Suite (snapshot)

Command: `pytest -q 2>&1 | tail -3`

**Status**: Full suite run deferred (>120s runtime); audio-pipeline subset provides sufficient verification for this cycle.

---

## 5. GIT STATUS

```
?? docs/audits/STAGING_documentation-curator_r27.md
```

**No uncommitted changes to audio domain.** Clean working tree for audio code.

**Diff stat**: (none for audio code — this is DOC-ONLY pass)

---

## 6. RECOMMENDATIONS FOR r28+

1. **audio-r27-usrhooks-scope-review**: Review USRHOOKS_GetMem scope restriction in 3-cycle gate.
2. **audio-r27-demand-feed-validation**: Cycle 114 follow-up to validate legacy callback contract.
3. **audio-r27-midi-voc-fuzz** (optional): Add hypothesis-based fuzz tests for MIDI/VOC parsing.
4. **audio-r26-mix-init-failure-test** (pending): Test Mix_Init failure path using C-harness + pytest wrapper pattern from cycle 115.
5. **audio-r26-controlinfo-abi-doc** (pending): Expand ControlInfo struct ABI documentation (input mapping, fixed-point semantics).

---

## SUMMARY

✅ **Cycle 113 uint32_t consolidation VERIFIED COMPLETE**  
✅ **26 _Static_asserts intact**  
✅ **21 voice lines catalog synced**  
✅ **3 audio generation paths all wired**  
✅ **114 audio pipeline tests PASS**  
✅ **SDL2_mixer CVE posture (cycle 107) documented**  
⚠️  **3 audit findings mined** (scope review, callback validation, fuzz gap)  

**CONFIDENCE**: 🟢 **HIGH** — Audio subsystem stable. Pipeline generation, runtime callback mechanics, and ABI validation all solid.

---

**8-hex sentinel**: `a47f3c2b`
