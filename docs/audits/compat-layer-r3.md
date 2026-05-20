# Compat Layer Audit Report – Round 3

**Auditor:** Copilot (compat-layer persona)  
**Date:** Post-R2 fix validation  
**Scope:** compat/ directory (11 files, ~5400 LOC)  
**Standard:** C11 + Platform Guards + Error Handling  
**Severity Threshold:** Real bugs, safety hazards, cleanup correctness  

---

## Executive Summary

**Since Round 2:**
- ✅ **Finding 1 FIXED:** `copybufreverse()` buffer underrun (pragmas_gcc.h:297) — now uses correct `d[i] = s[n-1-i]`
- ✅ **Finding 2 FIXED:** `sdl_quit_requested` now marked `volatile sig_atomic_t` (sdl_driver.c:47)

**New Round 3 Findings:**
- **1 MEDIUM:** `sdl_driver.c:231–246` — Partial SDL initialization leak if SDL_CreateRenderer/Texture fails
- **1 MEDIUM:** `audio_stub.c:248–259` — SDL audio subsystem not cleaned up if Mix_OpenAudio fails
- **1 MEDIUM/HIGH:** `audio_stub.c:54–64, 137–139` — Race condition in mixer_channel_done callback (audio thread vs main thread)
- **1 LOW:** `audio_stub.c:72–91` — VOC file header bounds check missing before p[20]/p[21] access
- **1 LOW:** `audio_stub.c:1027–1029` — CONTROL_JoysPresent[] never initialized to true; joystick support dormant

**New Severity Count:**
- MEDIUM/HIGH: 1
- MEDIUM: 2
- LOW: 2

**R2 Findings Status:** Both CRITICAL and MEDIUM issues have been fixed ✅

---

## Detailed Findings

### 1. MEDIUM: Partial SDL Initialization Leak (sdl_driver.c:231–246)

**File:** `compat/sdl_driver.c:212–246`

**Code:**
```c
window = SDL_CreateWindow("Duke Nukem 3D", ...);
if (!window) error_fatal("SDL Error", ...);  // ← line 216

renderer = SDL_CreateRenderer(window, -1, ...);
if (!renderer) error_fatal("SDL Error", ...);  // ← line 234: WINDOW LEAKED

texture = SDL_CreateTexture(renderer, ...);
if (!texture) error_fatal("SDL Error", ...);   // ← line 246: WINDOW + RENDERER LEAKED
```

**Issue:**
- Lines 208–217: Window creation with error_fatal exit on failure → OK
- Lines 220–235: Renderer creation, but error_fatal at line 234 exits immediately
  - **Window is NOT destroyed** before exit — resource leak
  - `sdl_shutdown()` (line 272) is never called on error path
- Lines 239–247: Texture creation, similar issue
  - Both window and renderer are leaked

**Root Cause:**
- `error_fatal()` calls `exit(1)` without unwinding cleanup
- `sdl_shutdown()` is not registered with `RegisterShutdownFunction()` (mact_stub.c:320)
- No atexit handler exists to clean up SDL resources

**Impact:**
- Low severity in practice (process dies and OS reclaims resources), but violates RAII principles
- On embedded or resource-constrained systems, repeated init/deinit cycles (e.g., video mode changes) could leak resources

**Remediation:**
Option A (Preferred):
```c
RegisterShutdownFunction(sdl_shutdown);  // Register in sdl_init() after SDL_Init succeeds
```

Option B (Explicit cleanup on partial init):
```c
if (!renderer) {
    SDL_DestroyWindow(window);  // Cleanup before error_fatal
    window = NULL;
    error_fatal("SDL Error", ...);
}
```

**Severity:** MEDIUM (violates resource cleanup contract)

---

### 2. MEDIUM: Audio Subsystem Not Cleaned Up on Mix_OpenAudio Failure (audio_stub.c:248–259)

**File:** `compat/audio_stub.c:244–290`

**Code:**
```c
int FX_Init(...) {
#ifdef HAVE_SDL2_MIXER
    if (SDL_InitSubSystem(SDL_INIT_AUDIO) < 0) {
        FX_ErrorCode = FX_Error;
        return FX_Error;  // ← Early return, SDL audio subsystem initialized
    }
    if (Mix_OpenAudio(mixrate, ...) < 0) {
        FX_ErrorCode = FX_Error;
        return FX_Error;  // ← Early return, mixer_initialized still FALSE
    }
    ...
    mixer_initialized = 1;  // ← Only set if Mix_OpenAudio succeeds
    ...
}

int FX_Shutdown(void) {
#ifdef HAVE_SDL2_MIXER
    if (mixer_initialized) {  // ← If false, no cleanup happens
        ...
        Mix_CloseAudio();
        SDL_QuitSubSystem(SDL_INIT_AUDIO);  // ← Never called if mixer_initialized is false
    }
#endif
}
```

**Issue:**
1. `SDL_InitSubSystem(SDL_INIT_AUDIO)` initializes the audio subsystem
2. If `Mix_OpenAudio()` fails, `mixer_initialized` is NOT set (remains 0)
3. On shutdown, the check at line 274 prevents cleanup
4. Result: SDL audio subsystem remains initialized but never cleaned up

**Scenario:**
```
FX_Init() called
  → SDL_InitSubSystem(SDL_INIT_AUDIO) succeeds
  → Mix_OpenAudio() fails (requested sample rate unavailable, device error, etc.)
  → mixer_initialized = 0
  → FX_Init returns FX_Error
  
Later, FX_Shutdown() called
  → mixer_initialized == 0, so cleanup block skipped
  → SDL audio subsystem never uninitialized → resource leak
```

**Impact:**
- Audio system stuck in half-initialized state
- Repeated init/shutdown cycles accumulate unreleased resources
- On some platforms (e.g., embedded, ALSA), this may cause device to be held open

**Remediation:**
```c
int FX_Init(...) {
#ifdef HAVE_SDL2_MIXER
    int audio_subsystem_inited = 0;
    
    if (SDL_InitSubSystem(SDL_INIT_AUDIO) < 0) {
        FX_ErrorCode = FX_Error;
        return FX_Error;
    }
    audio_subsystem_inited = 1;
    
    if (Mix_OpenAudio(...) < 0) {
        FX_ErrorCode = FX_Error;
        if (audio_subsystem_inited)
            SDL_QuitSubSystem(SDL_INIT_AUDIO);
        return FX_Error;
    }
    mixer_initialized = 1;
#endif
    return FX_Ok;
}
```

**Severity:** MEDIUM (resource cleanup contract violation)

---

### 3. MEDIUM/HIGH: Race Condition in Mixer Channel Callback (audio_stub.c:54–64, 137–139, 171–173)

**File:** `compat/audio_stub.c:54–64, 114–147, 150–195`

**Code (callback):**
```c
static void mixer_channel_done(int channel)  // ← Called by SDL2_mixer from audio thread
{
    if (channel < 0 || channel >= MIXER_MAX_CHANNELS) return;
    if (mixer_channel_chunk[channel]) {      // ← Shared array accessed WITHOUT LOCK
        Mix_FreeChunk(mixer_channel_chunk[channel]);
        mixer_channel_chunk[channel] = NULL;
    }
    if (fx_callback)
        fx_callback(mixer_channel_cbval[channel]);  // ← Reads shared array
}
```

**Code (mixer_play, called from main thread):**
```c
static int mixer_play(...) {
    ...
    channel = Mix_PlayChannel(-1, chunk, loops);
    if (channel < 0) { Mix_FreeChunk(chunk); return -1; }
    
    if (channel < MIXER_MAX_CHANNELS) {
        mixer_channel_chunk[channel] = chunk;      // ← Writes shared array, NO LOCK
        mixer_channel_cbval[channel] = cbval;      // ← Writes shared array, NO LOCK
    }
    ...
}
```

**Shared State:**
```c
static Mix_Chunk     *mixer_channel_chunk[MIXER_MAX_CHANNELS];    // Line 51
static unsigned long  mixer_channel_cbval[MIXER_MAX_CHANNELS];    // Line 52
```

**Issue:**
- `mixer_channel_done()` is invoked by SDL2_mixer from the **audio thread** when playback completes
- `mixer_play()` is called from the **main thread** (via FX_PlayVOC, etc.)
- Both threads access `mixer_channel_chunk[]` and `mixer_channel_cbval[]` **without synchronization**
- Potential race:
  1. Main thread writes `mixer_channel_chunk[5] = new_chunk` at line 137
  2. Audio thread reads `mixer_channel_chunk[5]` at line 58 (stale value)
  3. Audio thread frees wrong pointer or NULL dereference
  4. Data corruption, double-free, or crash

**Severity:** MEDIUM/HIGH (potential data corruption, crash, or memory leak on audio thread)

**Remediation:**
Use `SDL_LockAudio()` / `SDL_UnlockAudio()`:
```c
static int mixer_play(...) {
    ...
    if (channel < MIXER_MAX_CHANNELS) {
        SDL_LockAudio();
        mixer_channel_chunk[channel] = chunk;
        mixer_channel_cbval[channel] = cbval;
        SDL_UnlockAudio();
    }
    ...
}

static void mixer_channel_done(int channel) {
    if (channel < 0 || channel >= MIXER_MAX_CHANNELS) return;
    SDL_LockAudio();
    if (mixer_channel_chunk[channel]) {
        Mix_FreeChunk(mixer_channel_chunk[channel]);
        mixer_channel_chunk[channel] = NULL;
    }
    SDL_UnlockAudio();
    
    if (fx_callback)
        fx_callback(mixer_channel_cbval[channel]);
}
```

**Note:** `fx_callback()` may not need to be in the lock, but dereferencing `mixer_channel_cbval[]` requires it.

---

### 4. LOW: VOC File Header Bounds Check Missing (audio_stub.c:72–91)

**File:** `compat/audio_stub.c:72–92`

**Code:**
```c
static unsigned long voc_file_size(const unsigned char *p)
{
    unsigned short data_off;
    
    if (p[0] != 'C' || p[1] != 'r') return 0;    // ← Reads p[0], p[1] (assumes ≥2 bytes)
    data_off = (unsigned short)(p[20] | ((unsigned)p[21] << 8));  // ← BOUNDS CHECK MISSING
    if (data_off < 26) data_off = 26;
    cur   = p + data_off;
    limit = p + MAX_SOUND_FILE_SIZE;
    ...
}
```

**Issue:**
- Line 77: Reads `p[0]`, `p[1]` without validating buffer size
  - If buffer < 2 bytes: out-of-bounds read
- Line 78: Reads `p[20]`, `p[21]` without validating buffer size
  - If buffer < 22 bytes: out-of-bounds read (undefined behavior)
- Partially mitigated by `sound_file_size()` (line 109) capping result at `MAX_SOUND_FILE_SIZE`
  - But that doesn't prevent the OOB read itself

**Scenario:**
```c
char *audio_ptr = some_small_buffer;  // e.g., 10 bytes, looks like "Cr.........."
mixer_play(audio_ptr, ...);
  → sound_file_size(audio_ptr)
    → voc_file_size(audio_ptr)
      → p[0], p[1] read OK
      → p[20], p[21] read BEYOND buffer → undefined behavior
```

**Impact:**
- Low in practice: most sound data comes from loaded files or assets (likely sized correctly)
- High if engine allows crafted/malformed audio pointers (e.g., mod/plugin abuse)
- Potential to read sensitive memory or crash on strict bounds-checking platforms

**Remediation:**
```c
static unsigned long voc_file_size(const unsigned char *p)
{
    unsigned short data_off;
    // ... (header validation should specify minimum size first)
    if (p[0] != 'C' || p[1] != 'r') return 0;
    // NOTE: Caller should validate buffer size ≥ MAX_SOUND_FILE_SIZE
    // OR we could add a size parameter: voc_file_size(p, size)
    data_off = (unsigned short)(p[20] | ((unsigned)p[21] << 8));
    ...
}
```

**Severity:** LOW (mitigated by capping, plus normal usage likely safe)

---

### 5. LOW: Joystick Support Never Initialized (audio_stub.c:1027–1029)

**File:** `compat/audio_stub.c:1027–1029`

**Code:**
```c
boolean CONTROL_JoysPresent[MaxJoys] = { false, false };  // ← Line 1027, never set to true
boolean CONTROL_JoystickEnabled  = false;                  // ← Line 1029, never set to true
```

**Issue:**
- `CONTROL_JoysPresent[]` is a global array indicating which joystick ports have devices
- Initialized to all `false` and **never modified** (grep finds no assignments)
- If engine checks `CONTROL_JoysPresent[0]`, it will always see `false`, even if user plugs in a joystick
- No joystick enumeration, calibration, or button mapping implemented

**Status:**
- Likely intentional: audio_stub.c is a **stub** implementation
- Joystick support deferred to future enhancement (TODO in project notes)
- Not a bug, but worth documenting as a **dormant feature**

**Impact:**
- Engine cannot detect or use joysticks
- Game playable with keyboard/mouse only
- Not breaking; just a missing feature

**Recommendation:**
- Document in compat.h / audio_stub.h that joystick support is stubbed
- Add comment in CONTROL_JoysPresent declaration
- Add `//TODO: Implement joystick enumeration (SDL_JoystickOpen, etc.)`

**Severity:** LOW (feature stub, not a bug)

---

## Summary of Round 3 Findings

| ID | Severity | Component | Issue | Status |
|---|----------|-----------|-------|--------|
| R3-1 | MEDIUM | sdl_driver.c | Partial SDL init leak on error | NEW |
| R3-2 | MEDIUM | audio_stub.c | Audio subsystem leak on Mix_OpenAudio fail | NEW |
| R3-3 | MEDIUM/HIGH | audio_stub.c | Race condition in mixer_channel_done callback | NEW |
| R3-4 | LOW | audio_stub.c | VOC header bounds check missing | NEW |
| R3-5 | LOW | audio_stub.c | Joystick support never initialized | NEW |

---

## Todos Created (Max 6, Highest Priority First)

1. **fix-compat-sdl-init-cleanup** (MEDIUM)
   - Register `sdl_shutdown()` with `RegisterShutdownFunction()`
   - Prevent resource leak on partial SDL initialization failure

2. **fix-compat-audio-subsystem-leak** (MEDIUM)
   - Clean up SDL audio subsystem even if `Mix_OpenAudio()` fails
   - Ensure `SDL_QuitSubSystem(SDL_INIT_AUDIO)` is always called

3. **fix-compat-mixer-race-condition** (MEDIUM/HIGH)
   - Add SDL_LockAudio/UnlockAudio guards to mixer_channel_done and mixer_play
   - Protect shared access to mixer_channel_chunk[] and mixer_channel_cbval[]

4. **audit-compat-voc-bounds-check** (LOW)
   - Document or fix: voc_file_size() reads p[20]/p[21] without size validation
   - Consider adding buffer-size parameter or defensive minimum checks

5. **audit-compat-joystick-stub** (LOW)
   - Document in compat.h that CONTROL_JoysPresent[] is a stub
   - Add TODO for future joystick enumeration via SDL_Joystick API

---

## Validation Against R2 Fixes

| R2 Finding | Fix Status | Verification |
|-----------|-----------|--------------|
| **CRITICAL: copybufreverse() buffer underrun** | ✅ FIXED | pragmas_gcc.h:297 now uses `s[n-1-i]` (correct) |
| **MEDIUM: sdl_quit_requested not volatile** | ✅ FIXED | sdl_driver.c:47 now declares `volatile sig_atomic_t` |

---

## Recommendations

### Immediate (MEDIUM Priority)
1. **Fix SDL init cleanup** — Register `sdl_shutdown()` with `RegisterShutdownFunction()`
2. **Fix audio subsystem leak** — Clean up on `Mix_OpenAudio()` failure
3. **Fix mixer race condition** — Add lock guards to protect `mixer_channel_*` arrays

### Short Term (LOW Priority)
4. **Document joystick stub** — Clarify in header that joystick support is deferred
5. **Audit VOC bounds checking** — Either add size validation or defensive reads

### Testing
- Simulate SDL initialization failures (e.g., force SDL_CreateRenderer to fail)
- Run with `ASAN` or `Valgrind` to detect resource leaks
- Test audio on multi-threaded platforms (ARM, PowerPC) to verify mixer lock correctness

---

## Conclusion

Compat layer continues to be in good shape. R2 fixes were correctly applied. Three new issues found (all medium/low priority), mostly edge-case error paths and thread synchronization. No security vulnerabilities; primary concern is resource cleanup on error and thread safety in audio callback.

**Recommended Action:** Create todos for MEDIUM findings (1, 2, 3); document LOW findings (4, 5).

