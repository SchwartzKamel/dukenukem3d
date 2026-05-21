# Silent Stubs Determinism Contract (Compat-R24)

**Cycle:** 105 grind, todo `compat-r24-silent-stubs-determinism`  
**Audit:** Per compat-r24 (cycles 102-104), 14 silent stubs verified deterministic and stable.  
**Purpose:** Formalize determinism guarantee for stub functions that intentionally suppress logging.

---

## Overview

The 14 stubs cataloged below are "silent" (never log) and deterministic (return constants or no-op). They fall into two categories:

1. **Per-Frame Polling (6 stubs):** Called repeatedly during game loops; must remain silent to avoid debug spam.
2. **Configuration / Rare Calls (8 stubs):** Called during setup or configuration; logging suppressed by design.

Each stub is:
- **Deterministic:** Always returns the same constant value for the same input (if any).
- **Side-Effect-Free:** No global state mutation; safe to call without side effects.
- **Regression-Tested:** 6 core stubs covered by `tests/test_compat_silent_stubs.py`.

---

## Per-Frame Polling Stubs (High Frequency, Silent by Design)

### 1. FX_GetVolume()

**Signature:** `int FX_GetVolume(void)`  
**Location:** `compat/audio_stub.c:482`  
**Return Value:** `fx_volume` (default 255)  
**Rationale:**  
- Called frequently by engine to read current sound volume state.
- No logging because per-frame polling would spam debug output.
- Deterministic: Returns cached volume; no side effects.

**Classification:** Per-Frame (sound system state query)

---

### 2. FX_GetMaxReverbDelay()

**Signature:** `int FX_GetMaxReverbDelay(void)`  
**Location:** `compat/audio_stub.c:517`  
**Return Value:** `256` (constant)  
**Rationale:**  
- Frequently called to query maximum reverb delay limit.
- Returns DOS-era fixed constant; no SDL2_mixer equivalent needed.
- Silent by design: Query-only, no state mutation.

**Classification:** Per-Frame (reverb property query)

---

### 3. TS_LockMemory()

**Signature:** `int TS_LockMemory(void)`  
**Location:** `compat/audio_stub.c:1087`  
**Return Value:** `TASK_Ok` (constant)  
**Rationale:**  
- Task scheduler memory lock (DOS MACT library legacy).
- On modern systems with virtual memory, no-op is safe (OS handles paging).
- Called by timer/task code during game loop; silent by design.

**Classification:** Per-Frame (timer/task utility)

---

### 4. TS_UnlockMemory()

**Signature:** `void TS_UnlockMemory(void)`  
**Location:** `compat/audio_stub.c:1086`  
**Return Value:** `void` (no-op)  
**Rationale:**  
- Pair with TS_LockMemory(); DOS MACT task scheduler legacy.
- No-op on modern systems; no logging needed.
- Called during game loop; per-frame silent by design.

**Classification:** Per-Frame (timer/task utility)

---

### 5. inittimer1mhz()

**Signature:** `void inittimer1mhz(void)`  
**Location:** `compat/mact_stub.c:375`  
**Return Value:** `void` (no-op)  
**Rationale:**  
- Initialize 1 MHz timer (DOS timer calibration, MACT library).
- SDL_GetTicks() provides millisecond resolution; no DOS calibration needed.
- Called once at startup; silent by design (one-time init).

**Classification:** Per-Frame (timer setup)

---

### 6. deltatime1mhz()

**Signature:** `int32_t deltatime1mhz(void)`  
**Location:** `compat/mact_stub.c:378`  
**Return Value:** `0` (constant)  
**Rationale:**  
- Query delta time since last timer tick (DOS MACT timer).
- SDL_GetTicks() already provides system time; no per-frame delta calculation needed.
- Called during game frame timing; silent to avoid frame-time overhead.

**Classification:** Per-Frame (frame timing query)

---

## Configuration / Rare Calls Stubs (Startup/Config, Silent by Design)

### 7. MUSIC_SetMaxFMMidiChannel()

**Signature:** `void MUSIC_SetMaxFMMidiChannel(int channel)`  
**Location:** `compat/audio_stub.c:876`  
**Return Value:** `void` (no-op)  
**Rationale:**  
- Set maximum FM synth MIDI channel (DOS Adlib hardware legacy).
- SDL2_mixer has no FM synth API; no configuration possible.
- Called during music system setup; silent by design (legacy DOS-only).

**Classification:** Configuration (music setup)

---

### 8. MUSIC_SetMidiChannelVolume()

**Signature:** `void MUSIC_SetMidiChannelVolume(int channel, int vol)`  
**Location:** `compat/audio_stub.c:888`  
**Return Value:** `void` (no-op)  
**Rationale:**  
- Control individual MIDI channel volume (DOS MIDI sequencer).
- SDL2_mixer does not expose per-channel MIDI control; operation impossible.
- Rarely called (legacy music system); silent by design.

**Classification:** Configuration (music channel control)

---

### 9. MUSIC_ResetMidiChannelVolumes()

**Signature:** `void MUSIC_ResetMidiChannelVolumes(void)`  
**Location:** `compat/audio_stub.c:889`  
**Return Value:** `void` (no-op)  
**Rationale:**  
- Reset all MIDI channel volumes to default (DOS MIDI sequencer).
- SDL2_mixer does not support this operation.
- Rarely called (music initialization); silent by design.

**Classification:** Configuration (music reset)

---

### 10. MUSIC_SetSongTick()

**Signature:** `void MUSIC_SetSongTick(unsigned long t)`  
**Location:** `compat/audio_stub.c:957`  
**Return Value:** `void` (no-op)  
**Rationale:**  
- Seek music to tick position (DOS MIDI sequencer).
- SDL2_mixer provides Mix_SetMusicPosition() for fade, but not tick-level seeking.
- Rarely called (legacy music control); silent by design.

**Classification:** Configuration (music positioning, rare)

---

### 11. MUSIC_SetSongTime()

**Signature:** `void MUSIC_SetSongTime(unsigned long ms)`  
**Location:** `compat/audio_stub.c:958`  
**Return Value:** `void` (no-op)  
**Rationale:**  
- Seek music to millisecond position (DOS MIDI sequencer).
- SDL2_mixer does not support precise seek-by-time for music.
- Rarely called (legacy music control); silent by design.

**Classification:** Configuration (music positioning, rare)

---

### 12. MUSIC_SetSongPosition()

**Signature:** `void MUSIC_SetSongPosition(int m, int b, int t)`  
**Location:** `compat/audio_stub.c:959`  
**Return Value:** `void` (no-op)  
**Rationale:**  
- Seek music to measure/beat/tick position (DOS MIDI sequencer).
- SDL2_mixer does not support measure/beat positioning.
- Rarely called (legacy music control); silent by design.

**Classification:** Configuration (music positioning, rare)

---

### 13. MUSIC_RegisterTimbreBank()

**Signature:** `void MUSIC_RegisterTimbreBank(unsigned char *timbres)`  
**Location:** `compat/audio_stub.c:1007`  
**Return Value:** `void` (no-op)  
**Rationale:**  
- Register MIDI timbre/instrument bank (DOS MIDI sequencer).
- SDL2_mixer loads instruments from MIDI file; no explicit timbre registration API.
- Rarely called (music initialization); silent by design.

**Classification:** Configuration (music timbre setup, DOS-only)

---

### 14. testcallback()

**Signature:** `void testcallback(unsigned long val)`  
**Location:** `compat/mact_stub.c:382`  
**Return Value:** `void` (no-op)  
**Rationale:**  
- Internal test callback function (MACT library diagnostic).
- Never called by engine in production code; stub for completeness.
- Silent by design (internal debug utility).

**Classification:** Utility (test callback, internal)

---

## Determinism Guarantees

### Invariant 1: Return Value Constancy
- **Per-frame polling stubs** return fixed constants (0, 1, 256, TASK_Ok).
- **Rare-call stubs** are no-ops (void) or return fixed constants.
- **No dynamic behavior:** Return value never depends on runtime state (except volume queries, which are deterministic reads).

### Invariant 2: Side-Effect-Free Execution
- **No global state mutation:** Stubs never modify engine state, audio device state, or game logic.
- **No I/O:** No file reads, network calls, or system calls (except reads to cached state like volume).
- **Safe to call multiple times:** Multiple calls produce identical results.

### Invariant 3: Conditional Logging (Orthogonal)
- **No logging:** These 14 stubs never call STUB_LOG(), SDL_LogDebug(), or fprintf().
- **Design:** Per-frame silence prevents debug spam (stubs called 60+ times/sec are silent); rare-call silence avoids legacy DOS noise.
- **Logging control:** Only 5 stubs use DUKE3D_STUB_LOG (Music_SetVolume, PlayMusic, CONTROL_Ack, etc.); this catalog is distinct.

---

## Testing Strategy

**Test Suite:** `tests/test_compat_silent_stubs.py` (≥6 regression tests, all passing)

**Coverage:** 6 core stubs selected by frequency and risk:
1. **FX_GetVolume()** — Most-called sound query; high risk if broken
2. **FX_GetMaxReverbDelay()** — Frequently queried reverb property
3. **TS_LockMemory()** / **TS_UnlockMemory()** — Timer utility pair; per-frame frequency
4. **deltatime1mhz()** — Frame-time query; high frequency
5. **MUSIC_SetMaxFMMidiChannel()** — Configuration stub; representative of rare-call category

**Invariants Tested:**
- Each stub returns documented constant value
- Stubs are re-entrant (multiple calls safe)
- No exceptions or crashes on repeated calls
- Silent (zero log output when called)

---

## References

- **compat/README.md § Stubs Without Logging** — Design rationale for silence
- **compat/audio_stub.c, mact_stub.c** — Implementation source
- **compat-layer-r24.md (cycle 104)** — Audit pass; verified 14 stubs deterministic
- **todo: compat-audit-silent-stubs-determinism** — Formalize regression test coverage (cycle 105 grind)

---

**Determinism Status:** ✅ **VERIFIED STABLE (R24 audit pass, cycle 104)**  
**Regression Tests:** ✅ **IMPLEMENTED (cycle 105, test_compat_silent_stubs.py)**
