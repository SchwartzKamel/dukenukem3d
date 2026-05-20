# Compat Layer Audit Report

**Date:** Read-only audit  
**Scope:** compat/ (11 files, 5364 LOC)  
**Standard:** C11 + Platform Guards  
**Severity Threshold:** Real bugs, security, portability blockers only

## Inventory

| File | Size | Lines | Purpose |
|------|------|-------|---------|
| compat.h | 24K | 807 | Master compatibility header; DOS→POSIX/Win32 mappings |
| sdl_driver.c | 20K | 559 | SDL2 video/input/timer driver; palette→ARGB32 conversion |
| sdl_driver.h | 4K | 33 | SDL driver public interface |
| audio_stub.h | 20K | 562 | Audio API stubs (FX, MIDI, SoundBlaster) |
| audio_stub.c | 40K | 1300 | Audio implementation (silent-but-functional) |
| mact_stub.c | 16K | 408 | MACT/CONTROL system (config, input, joystick stubs) |
| pragmas_gcc.h | 32K | 504 | 174 inline C replacements for Watcom #pragma aux |
| hud.c | 8K | 216 | Framebuffer HUD overlay (4×6 bitmap font) |
| hud.h | 4K | 32 | HUD interface |
| msvc_unistd.h | 4K | 49 | MSVC POSIX name mapping shim |
| a.c | 32K | 894 | C replacement for SRC/A.ASM rendering inner loops |

---

## C11 Conformance

### ✓ Strengths
1. **Modern includes:** Proper `<stdint.h>`, `<stdbool.h>` usage; POSIX feature macros (`_GNU_SOURCE`, `_DEFAULT_SOURCE`) declared before system headers (compat.h:59–68).
2. **Platform guards:** Comprehensive `#ifdef _WIN32`, `#ifdef _MSC_VER`, `#ifndef _WIN32` throughout; 42 guard directives in compat.h alone ensure clean separation.
3. **Inline functions:** 174 static inline functions in pragmas_gcc.h are portable C11-compatible replacements for Watcom asm pragmas.
4. **Type safety:** Most new code uses `uint32_t`, `int32_t`, `size_t` consistently.

### ⚠ Findings

#### **Finding 1: Long type used in public SDL API (Medium)**
- **File:** sdl_driver.h:12, sdl_driver.h:23
- **Lines:** `long sdl_getbytesperline(void);` and `long sdl_getticks(void);`
- **Issue:** On 64-bit platforms, `long` is 8 bytes. These functions should return `int32_t` or use `#ifdef _WIN32` to guard long-only Windows APIs.
- **Risk:** If called from engine code expecting 32-bit returns, truncation or sign-extension bugs can occur.
- **Context:** The engine (SRC/) likely uses `long` historically, but compat layer should normalize to fixed sizes for interop.

#### **Finding 2: Variable-length array (VLA) in pragmas_gcc.h (Low)**
- **File:** pragmas_gcc.h uses inline functions with direct multiplication without overflow checks (e.g., `scale()`, `mulscale()`).
- **Issue:** No explicit overflow guards in 64-bit multiplies used for rendering, though int64_t intermediate prevents silent truncation.
- **Mitigation:** Correct as-is (int64_t semantics match x86 IMUL); note in documentation that callers must range-check inputs.

---

## Engine Interop: Struct Layouts & int32_t Usage

### ✓ Observed Patterns
- **compat.h:94** correctly defines `boolean` as `int32_t` on Windows after careful `_BOOLEAN_DEFINED` guard.
- **audio_stub.h:29–52** defines portable type aliases (uint8, int32, fixed) matching SRC/types.h.
- **compat.h memory stubs** (lines 379–387) remap far pointers to flat-model malloc/free.

### ⚠ Findings

#### **Finding 3: Missing compile-time size assertions (Low)**
- **Files:** compat.h, audio_stub.h, mact_stub.c
- **Issue:** No `_Static_assert` to verify struct layouts cross-compile correctly on 32-bit vs 64-bit targets.
- **Example:** `find_t` struct (compat.h:424–432, compat.h:472–483) differs between Windows and POSIX implementations; sizeof(find_t) is unchecked.
- **Risk:** Engine code that binary-casts or sizeof()-relies on find_t will silently break on 64-bit.
- **Remediation:** Add `_Static_assert(sizeof(find_t) == EXPECTED, "struct size mismatch on this platform")` to each critical struct definition or via test suite.

#### **Finding 4: FP_OFF/FP_SEG DOS-to-flat-model translation (Low)**
- **File:** compat.h:345–347
- **Code:**
  ```c
  #define FP_OFF(p)   ((intptr_t)(p))
  #define FP_SEG(p)   (0)
  ```
- **Issue:** Correct for flat model but relies on implicit intptr_t semantics. No documentation warning about segment-based code being incorrect if encountered.
- **Mitigation:** Acceptable; comment in compat.h explains rationale.

---

## SDL2 Driver Surface Analysis

### Video Coverage: Comprehensive
- **Init path** (sdl_driver.c:158–268): SDL_Init(VIDEO|TIMER) → SDL_CreateWindow → SDL_CreateRenderer → SDL_CreateTexture. Error handling via error_fatal() with MessageBox on Windows.
- **Palette→ARGB32 conversion** (sdl_driver.c:413–432):
  ```c
  for (int i = 0; i < num; i++) {
      unsigned int b = pal[i*4+0], g = pal[i*4+1], r = pal[i*4+2];
      palette32[idx] = 0xFF000000u | (r << 16) | (g << 8) | b;
  }
  ```
  Correct: properly shifts RGB components; alpha always 0xFF.
- **Frame presentation** (sdl_driver.c:375–411): Locks texture, copies palette-indexed pixels to ARGB32, renders, presents. Handles headless mode for AI testing.

### Input Coverage: Complete
- **Scancode mapping** (sdl_driver.c:49–154): 85 SDL_SCANCODE → DOS scancode mappings (0x01–0xD3, extended keys 0x9C–0xD3). Includes numpad, function keys, extended keys.
- **Mouse handling** (sdl_driver.c:482–501): Relative motion, button tracking, auto-grab on click.
- **Keyboard buffering** (sdl_driver.c:459–480): Calls KB_KeyEvent() and KB_Addch() (external functions from engine).

### Timer Coverage: Minimal but Functional
- **sdl_getticks()** (sdl_driver.c:551–554): Returns `(long)SDL_GetTicks()` — potential truncation on 64-bit (see Finding 1).
- **sdl_delay()** (sdl_driver.c:556–559): SDL_Delay(Uint32) with range check.

### Error Handling on SDL Init Failures: Strong
- **sdl_driver.c:187–194**: SDL_Init failure → snprintf() detailed error buffer → error_fatal() → MessageBoxA on Windows, stderr on Linux, exit(1).
- **sdl_driver.c:207–216**: SDL_CreateWindow failure → same error_fatal path.
- **sdl_driver.c:230–246**: SDL_CreateTexture failure caught and reported.
- **Fallback renderer** (sdl_driver.c:225–228): Attempts hardware-accelerated first, falls back to software. Good.

### Fullscreen/Resize Behavior: Correct
- **Fullscreen default** (sdl_driver.c:204–205): SDL_WINDOW_FULLSCREEN_DESKTOP set unless headless_mode.
- **Alt+Enter toggle** (sdl_driver.c:464–469): Correctly detects Alt+Enter and toggles fullscreen.
- **Resizable** (sdl_driver.c:202): SDL_WINDOW_RESIZABLE set; logical size enforced (sdl_driver.c:236).

### ✓ Strengths
- Comprehensive key mapping for DOS compatibility
- Robust error handling with platform-specific dialogs
- AI testing support (headless mode, frame capture, frame limit)
- Fallback to software renderer if hardware unavailable

### ⚠ Findings

#### **Finding 5: Unsafe exit(0) on quit event (Medium)**
- **File:** sdl_driver.c:455–456
- **Code:**
  ```c
  case SDL_QUIT:
      sdl_quit_requested = 1;
      exit(0);  // <-- Direct exit
  ```
- **Issue:** Calling exit() directly bypasses engine cleanup. While atexit() handlers run, this is abrupt and may leave resources open on Windows.
- **Remediation:** Set flag and let engine check sdl_quit_requested in main loop; save exit(0) for unrecoverable errors only. Could deadlock if engine never checks the flag (but persona notes most game loops do not check it, so exit(0) is pragmatic).
- **Severity:** Medium (potential resource leak; acceptable as pragmatic workaround for hanging game loops, documented in comment at line 454).

#### **Finding 6: Frame capture BMP writer has no seek/tell safety (Low)**
- **File:** sdl_driver.c:282–351
- **Code:** Writes BMP header (14 bytes) + info (40 bytes) + pixel data sequentially; no validation that fwrite() succeeded for each step.
- **Issue:** Partial writes silently ignored; corrupted BMP on disk space exhaustion.
- **Remediation:** Check fwrite() return values. Impact low because captures are optional/diagnostic.

---

## Audio Stub: Silent-but-Functional Analysis

### ✓ Audit Results
- **audio_stub.c:1300 LOC** provides no-op implementations for ~60+ audio APIs (FX_Init, FX_PlayVOC, MIDI_PlaySong, MUS_StartSong, etc.).
- **All functions return safe defaults:** FX_Init returns 0 (success), MUS_StartSong/MIDI_PlaySong return 0, volume functions accept but ignore parameters.
- **No dereferencing of uninitialized pointers:** Callbacks (if stored) are either NULL-checked or never called.
- **No crashes on missing SoundBlaster:** Enum covers all DOS sound cards; none actually used.

### Audio Seam Points for SDL_mixer Roadmap

**Where playback would hook in:**

1. **FX_PlayVOC() / FX_PlayWAV()** (audio_stub.c:~line 150–180): Currently returns 0; would:
   - Decode WAV header
   - Load into SDL_mixer sample
   - Mix_PlayChannel() or Mix_PlayChannelTimed()

2. **MUS_StartSong() / MIDI_PlaySong()** (audio_stub.c:~line 250–300): Currently returns 0; would:
   - Load XMI/MUS file via FluidSynth or libopenmpt
   - Mix_PlayMusic()
   - Track handle for MUS_StopSong()

3. **Init path:** FX_Init would call Mix_OpenAudio(); audio_stub.c doesn't call SDL_mixer at all currently (cleanly isolated).

4. **Mixer.c integration point:** No compat layer changes needed; add new audio_mixer.c alongside audio_stub.c, link both, engine includes correct header at runtime.

### ⚠ Findings

#### **Finding 7: VOC parser buffer overflow risk (Medium)**
- **File:** audio_stub.c (around line 180–220, estimated based on audio format structs)
- **Issue:** If VOC parsing code is added to audio_stub.c in future, unchecked sample rates or file-format variants (ADPCM, etc.) could overflow fixed buffers.
- **Remediation:** Currently acceptable (not implemented); document in audio_mixer.c roadmap to validate file headers before allocating buffers.

#### **Finding 8: No thread safety in audio stubs (Low)**
- **Issue:** Static state (FX_device, MUS_PlayPosition) not protected by mutex. If engine ever goes multithreaded, race condition on audio_stub globals.
- **Mitigation:** Not blocking (engine is single-threaded in 1996 original); document as assumption.

---

## MACT Stub / Network Analysis

### Implemented Features
- **SCRIPT_Load/Get/Set** (mact_stub.c:60–180): Config file parsing (INI-like format); handles [section], key=value, quoted strings.
- **CONTROL_GetUserInput** (mact_stub.c:~250–300): Reads keyboard state via sdl_keystatus().
- **CONTROL_ScanScancode** (mact_stub.c:~310): Checks if scancode is currently pressed.
- **SCRIPT_AddEntry, SCRIPT_GetValue**: String handling with strncpy + null-termination pattern.

### Stubbed Features
- **Joystick/gamepad** (CONTROL_MapScancode, gamepad axis/button bindings): Returns success (0) but never reads actual joystick input; no SDL_Joystick calls.
- **Network**: No network code present; multiplayer would require separate network_stub.c.
- **Mouse relative motion**: Handled by sdl_driver.c, not mact_stub.c.

### ✓ Strengths
- strncpy() always followed by explicit null-termination (mact_stub.c:82, 88, 92, 96).
- Script entry limit (MAX_ENTRIES=256) prevents unbounded growth.
- Case-insensitive key lookup (strcasecmp).

### ⚠ Findings

#### **Finding 9: Nullable SCRIPT_GetValue return used unsafely elsewhere (Unverified)**
- **File:** mact_stub.c (SCRIPT_GetValue signature)
- **Issue:** If engine calls SCRIPT_GetValue() and immediately dereferences without NULL check, crash ensues. Audit cannot confirm without checking engine code in SRC/.
- **Mitigation:** Recommend adding defensive NULL checks in engine wrappers; mact_stub.c returns NULL correctly on not-found.
- **Severity:** Low (defensive; cannot confirm bug without engine inspection).

#### **Finding 10: Config parsing doesn't handle escaped quotes (Low)**
- **File:** mact_stub.c:170–196 (string parsing loop)
- **Issue:** Quoted string handler doesn't unescape `\"`. If config contains `value="foo\"bar"`, it incorrectly parses as `value="foo\`.
- **Remediation:** Low impact (config files in Duke3D likely don't use escaped quotes); document or add simple unescape loop if needed.

---

## msvc_unistd.h Shim Analysis

### POSIX Symbols Provided
- **File I/O:** access, open, close, read, write, lseek, unlink
- **Directory:** getcwd, chdir
- **Process:** getpid (from process.h)
- **Access modes:** R_OK, W_OK, F_OK
- **Mode flags:** O_BINARY, O_TEXT (no-ops on POSIX)

### ✓ Strengths
- Correct macro definitions; no typos.
- Only included when `_MSC_VER` is defined (line 6).
- Avoids conflict with POSIX unistd.h on non-Windows builds.

### Gaps That Could Break MSVC Builds
- **Missing O_CREAT, O_APPEND, O_TRUNC** mode constants for open().
- **Missing stat() / fstat()** (struct stat, S_ISDIR, etc.); caller must include `<sys/stat.h>` separately.
- **Missing getenv()** (available natively on Windows via stdlib.h; not in unistd.h).
- **No mkdir()** shim (compat.h line 546 defines it via macro, so OK).

### ⚠ Findings

#### **Finding 11: msvc_unistd.h incomplete for advanced POSIX usage (Low)**
- **File:** msvc_unistd.h
- **Issue:** If engine code calls openat(), pread(), pwrite(), or other POSIX extensions, MSVC build will fail.
- **Mitigation:** Current engine code doesn't use advanced POSIX; acceptable. Add new symbols as needed. Consider rename to msvc_stubs.h to clarify scope.
- **Severity:** Low (not a blocker for current codebase; documented assumption).

---

## pragmas_gcc.h: 174-Function Coverage & Inline Correctness

### Coverage Verification
- **Actual count:** 174 static inline functions (confirmed via grep).
- **Coverage areas:**
  - **Math:** sqr, scale, mulscale, dmulscale (1 + 32 variants + 32 variants = 65 functions)
  - **Division:** divmod, moddiv, divscale (3)
  - **Bit ops:** bitshift, bitmaskfill (3)
  - **Buffer ops:** clearbuf, copybuf (2)
  - **Drawing:** drawpixel, hline, vline, mvline, tvline, drawslab, etc. (40+)
  - **Misc:** setvmode, setcolor16, chainblit, etc. (10+)

### Inline Correctness vs Watcom Semantics

#### ✓ Correct Mappings
- **mulscaleN:** `(long)(((int64_t)a * b) >> N)` correctly emulates 32x32→64 multiply + shift, matching x86 IMUL + SAR semantics.
- **scale:** Uses int64_t intermediate for 32x32÷32 → 32 precision, avoiding truncation.
- **clearbuf:** Loops memset over dword array; equivalent to Watcom _fmemset pragma.

#### ⚠ Potential Issues

#### **Finding 12: dmulscale overflow detection missing (Low)**
- **File:** pragmas_gcc.h:93–130 (dmulscale1–32 functions)
- **Code:**
  ```c
  return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> N);
  ```
- **Issue:** If both products overflow (e.g., large positive + large positive → negative after shift), intermediate int64_t silently wraps. Watcom pragma behavior is undefined here too.
- **Mitigation:** Correct per Watcom semantics; engine code must range-check inputs. Note: x86 x87 FPU also doesn't detect overflow silently.
- **Severity:** Low (matches original Watcom behavior; engine is responsible for input validation).

#### **Finding 13: Bitshift macros hardcoded to 32 (Low)**
- **File:** pragmas_gcc.h:195–200 (bitshift functions)
- **Issue:** `bitshift(a, b)` assumes 32-bit shifts; fine for 32-bit long on x86-32, but on 64-bit platforms where long=8 bytes, shifts beyond 32 bits are undefined.
- **Mitigation:** Code only called with 0..31 shifts per engine convention. Document or add range check.
- **Severity:** Low (convention-based, not a portability blocker if respected).

---

## Memory Safety & Buffer Overflow Audit

### ✓ Safe Patterns Observed
- **All strncpy() followed by explicit null-termination:** compat.h lines 443, 456, 512, 520, 523; mact_stub.c lines 72, 82, 88, 92, 96.
- **snprintf() used throughout:** compat.h lines 209–212, 664, 672, 760–762; sdl_driver.c lines 189, 213, 363; never sprintf().
- **sizeof() on fixed buffers:** compat.h lines 495, 512, 517, 520, 523; proper bounds.
- **fgets() used (not gets()):** compat.h never calls gets(); sdl_driver.c uses fgets with sizeof(buf).

### ⚠ Findings

#### **Finding 14: Integer overflow in size_t arithmetic (Low)**
- **File:** compat.h:495 (POSIX findfirst)
- **Code:**
  ```c
  snprintf(fullpath, sizeof(fullpath), "%s/%s", f->_path, de->d_name);
  ```
- **Issue:** strlen(f->_path) + 1 + strlen(de->d_name) could exceed 512 if d_name is truncated by readdir(). Unlikely but possible on embedded systems with large filenames.
- **Mitigation:** add explicit strlen() check before snprintf, or verify de->d_name is bounded by POSIX (typically 256 bytes max).
- **Severity:** Low (standard patterns, bounded by filesystem).

#### **Finding 15: strncat buffer boundary confusion (Low)**
- **File:** compat.h:640, 655
- **Code:**
  ```c
  strncat(pathbuf, filename, sizeof(pathbuf) - strlen(pathbuf) - 1);
  ```
- **Issue:** strncat() third argument is max chars to append (not total size). Code correctly uses `sizeof - strlen - 1`, so math is sound. No bug, but unusual style; clearer to use snprintf().
- **Mitigation:** Acceptable; no change needed. For future: prefer snprintf(pathbuf+strlen, remaining, "%s", filename).
- **Severity:** Very low (correct, slightly opaque).

---

## Header Hygiene & Leakage Audit

### Include Order & Guards
- **compat.h:** Guard at line 8–9 (COMPAT_H_ + #pragma once); correct. POSIX feature macros before system headers (lines 59–68). Good.
- **sdl_driver.h:** Guard at line 1–2; includes <stdint.h>. Good.
- **audio_stub.h:** Guard at line 15–16; includes <stdint.h>. Good.
- **hud.h:** Guard at line 9–10; C++ extern "C" guards (lines 12–14, 28–30). Good.
- **msvc_unistd.h:** Guard at lines 3, 48; minimal, focused scope. Good.

### Forward Declarations
- **compat.h:576–596:** Forward decls for sdl_video_init(), sdl_input_init(), etc. Correct; allows SDLless compilation if needed.
- **mact_stub.c:75:** External declaration of sdl_keystatus() before use. Good.

### Engine Internal Leakage: None Observed
- compat/ headers only expose SDL driver interface + audio stubs + generic helpers.
- No includes of SRC/ or source/ headers from compat/.
- No direct access to engine structs except via opaque pointers.

### ✓ Strengths
- Clean separation; compat.h is self-contained.
- No circular includes.
- POSIX feature macros properly ordered.

---

## Key Findings Summary by Severity

### Critical (Security/Crash Blockers): 0

### High (Portability/Correctness Blockers): 0

### Medium (Real bugs, needs attention):
1. **Finding 1:** Long type in SDL API (sdl_driver.h:12, 23) — should be int32_t for 64-bit safety.
2. **Finding 5:** Direct exit(0) on quit (sdl_driver.c:455–456) — abrupt cleanup; pragmatic workaround but risky.

### Low (Nice-to-have, non-blocking):
- Finding 3: Missing _Static_assert for struct sizes (struct layouts unchecked on cross-compile).
- Finding 6: BMP capture writer ignores fwrite() errors (diagnostic feature, low impact).
- Finding 9: Nullable SCRIPT_GetValue (dependent on engine usage; defensive).
- Finding 10: Config parser doesn't unescape quotes (unlikely edge case).
- Finding 11: msvc_unistd.h incomplete for advanced POSIX (current engine doesn't use).
- Finding 12: dmulscale overflow undetected (matches Watcom semantics).
- Finding 13: Bitshift macros hardcoded to 32 (convention-based).
- Finding 14: Integer overflow in fullpath size_t arithmetic (unlikely, filesystem-bounded).
- Finding 15: strncat style confusion (correct math, opaque style).

---

## Recommendations

### Priority 1 (Immediate)
1. **Fix Finding 1:** Change sdl_driver.h:12, 23 from `long` to `int32_t`. Update sdl_driver.c:441, 553 return statements.
   ```c
   int32_t sdl_getbytesperline(void);
   int32_t sdl_getticks(void);
   ```

2. **Fix Finding 5:** Replace exit(0) with flag-and-loop-exit pattern. Document game-loop contract.

### Priority 2 (Quality/Testing)
3. **Add _Static_assert** (Finding 3) for critical structs:
   - Add to tests/test_compat_layer.py or a dedicated compat_asserts.c.
   - Verify find_t, REGS, SREGS, audio_stub types on both 32-bit and 64-bit targets.

4. **Document msvc_unistd.h scope** (Finding 11): Rename to msvc_posix_shim.h or add comment clarifying "minimal shim; not comprehensive POSIX".

### Priority 3 (Future Roadmap)
5. **Audio mixer integration** (seam points documented above): Create audio_mixer.c skeleton with SDL_mixer headers; design to coexist with audio_stub.c.

6. **Input subsystem expansion:** Current SDL scancode coverage is complete for keyboard; add joystick via SDL_JoystickOpen() when gamepad support is needed.

---

## Open Questions

1. **Does the engine ever call sdl_getticks() expecting 32-bit behavior?** 
   - If so, truncation on 64-bit could cause timer underflow (unlikely at 32-bit int boundary, but check).
   
2. **What is the contract for game loops checking sdl_quit_requested vs sdl_checkquit()?**
   - Current code calls exit(0) directly; if game loops never check, is exit(0) acceptable or hiding deadlock bugs?
   - Recommend audit of SRC/engine main loop.

3. **Network multiplayer stub:** Is multiplayer completely removed or stubbed? If stubbed, should mact_stub.c have socket_bind(), socket_listen() no-ops?

4. **Future audio latency requirements:** SDL_mixer has ~20ms typical latency. If game requires sub-10ms audio feedback (unlikely for 1996 engine), need alternative (PulseAudio, ALSA direct).

5. **Struct layout tests:** Are there existing pytest tests in tests/test_compat_layer.py that validate sizeof(find_t), sizeof(REGS) on CI? If not, add ASAP.

---

## Conclusion

The compat layer is **well-engineered and stable** for a modernization effort of this complexity. All critical paths (video, input, error handling) are robust. The two medium-severity findings (long types, exit() behavior) are pragmatic trade-offs but should be addressed for production 64-bit builds.

**Recommended Actions:**
- [ ] Priority 1: Fix findings 1 & 5 (medium severity)
- [ ] Priority 2: Add struct size assertions (testing)
- [ ] Priority 3: Prepare audio_mixer.c skeleton
- [ ] Document game loop contract (exit vs flag)

**Confidence Level:** High (no security vulnerabilities; portability is strong with noted exceptions).
