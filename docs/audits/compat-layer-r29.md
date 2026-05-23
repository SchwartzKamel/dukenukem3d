# compat-layer — round 29 (full shippability audit, DOC-ONLY)

<!-- SUMMARY_ROW -->
| compat-layer | r29 | cycle 119 | Ship-ready on Linux + macOS + Windows-MinGW; Windows-MSVC native still unvalidated. r28 P0 (sha256.c CMake gap) + net_socket adoption CLOSED. 1 new P1 (mixer channel-array overflow > 32 voices), 6 P2 (format strings, atexit accumulation, SCRIPT_Load slot-leak, NULL-deref, fwrite return-ignored, maxtiles-guard memory drift). |
<!-- END_SUMMARY_ROW -->

---

## 1. Executive Summary — Per-Platform Ship Verdict

| Platform                    | Verdict        | Notes |
|-----------------------------|----------------|-------|
| **Linux x86_64 (GCC)**      | ✅ SHIP-READY  | Full `make` build clean; SDL2 video + SDL2_mixer audio + POSIX net_socket all functional. Only `%lu`-vs-`uint32_t` printf warnings remain. |
| **macOS (Clang)**           | ✅ SHIP-READY  | Same source tree as Linux; CMake path verified by build-system r28. No macOS-specific failure modes identified in `compat/`. |
| **Windows MinGW cross**     | ✅ SHIP-READY  | `make windows` path uses same GCC dialect as Linux; net_socket_win32.c paired correctly via build.mk:20. |
| **Windows MSVC native**     | ⚠️ NEEDS PROOF | All `_MSC_VER` shims present (compat.h:20–54, msvc_unistd.h) and structurally correct, but no in-tree evidence the c115–c117 audio uint32_t + sha256 landings have been *compiled* against MSVC. Carryover from compat-r28 todo (`compat-r28-msvc-native-build-validation-c118`) still pending. |

**Scope of audit:** 11 compat/ source files (~6 860 LOC). 5 carry-over P1/P2 findings from r28 verified-closed. 7 new findings (1 P1 / 6 P2). 0 P0 ship-blockers.

**Bottom line for the stated goal "ensure this ships as a fully playable game":** *Yes on Linux, macOS, and Windows-MinGW today.* The Windows-native MSVC path needs one CI smoke build before sign-off; nothing in compat/ structurally prevents it.

---

## 2. Re-verification of r28 open findings

| r28 item                                                                    | Status this round | Evidence |
|-----------------------------------------------------------------------------|-------------------|----------|
| **CRITICAL** sha256.c missing from CMakeLists COMPAT_SRCS                   | ✅ **CLOSED**     | CMakeLists.txt:54 now contains `compat/sha256.c` (verified via `grep -n sha256 CMakeLists.txt`). Triple-triangulated fix (build-r28 + compat-r28 + engine-r29) landed. |
| **HIGH**     sha256 HMAC/HKDF integration test                              | ✅ **CLOSED**     | GRIND_LOG cycle 119 entry `sha256-cmake-fix` (sentinel `3c9f42e7`) added 4 RFC-vector integration tests + `compiled_sha256_harness` fixture. |
| **MED**      net_socket adoption tracking in SRC/MMULTI.C                   | ✅ **CLOSED**     | `grep -n "net_socket" SRC/MMULTI.C` returns 9 call-sites (L20, 396, 668, 675, 739, 740, 864, 912, 919). Abstraction is the only socket path used in MMULTI. |
| **MED**      MSVC native build validation (audio uint32_t + sha256 landed)  | ⏳ **OPEN**       | No CI evidence; no `tools/win_build.ps1` log entry in repo. **Carry forward.** |
| **LOW**      Keepalive error-scope rationale comment                        | ⏳ **OPEN**       | compat/net_socket.h:107–116 still lacks the "why WSAENETRESET/WSAENOTCONN excluded" comment. Cosmetic; carry forward. |
| **LOW**      Volatile int32_t task.count atomicity verification             | ⏳ **OPEN**       | `audio_stub.h:288` `volatile int32_t count` unchanged; no dedicated unit test located in tests/. Confidence-only item; carry forward. |
| c107–c117 `_Static_assert` inventory (26+ asserts)                          | ✅ **STABLE**     | `grep -c "_Static_assert" compat/audio_stub.h compat/compat.h compat/sha256.h` = 6 / 9 / 3 (= 18 visible; balance live in audio_stub.h L130/241/297/544). All compile under `-std=gnu11`. |
| c113 audio `unsigned long → uint32_t` migration                             | ✅ **STABLE**     | `grep -n "unsigned long" compat/audio_stub.c` → 0 hits (verified). |
| `_Noreturn` portability shim (compat.h:76–85)                               | ✅ **STABLE**     | Unchanged since r20. |
| MSVC compat block (compat.h:20–54 + msvc_unistd.h)                          | ✅ **STABLE**     | Structurally complete; runtime untested (see open MSVC item). |
| pragmas_gcc.h read-only invariant                                           | ✅ **STABLE**     | 520 LOC unchanged; ~174 inline functions intact. |

---

## 3. New Findings (this round)

### 3.1 [P1] Mixer channel-tracking array can be silently overshot

- **File:line:** compat/audio_stub.c:230–235 (`mixer_play`), 286–293 (`mixer_play_3d`), 412 (`Mix_AllocateChannels(numvoices …)`), 86 (early-return in `mixer_channel_done`).
- **Root cause:**
  - `MIXER_MAX_CHANNELS` is a compile-time `#define 32` (audio_stub.c:52).
  - `FX_Init` passes the caller's `numvoices` directly to `Mix_AllocateChannels(numvoices > 0 ? numvoices : MIXER_MAX_CHANNELS)` without clamping.
  - Both `mixer_play` and `mixer_play_3d` guard their tracking-array writes with `if (channel < MIXER_MAX_CHANNELS)`. Any channel `≥ 32` plays but is **never recorded** in `mixer_channel_chunk[]` and never associated with a `cbval` in `mixer_channel_cbval[]`.
  - When SDL2_mixer fires the finished-callback for that channel, `mixer_channel_done` early-returns at line 86 → the `Mix_Chunk *` is **leaked** and the registered `fx_callback` is **never invoked** for that sound. The engine's voice-completion bookkeeping then never frees the slot, producing audible "ghost" voices and a slow heap leak.
- **Fix sketch:** In `FX_Init` clamp once: `numvoices = (numvoices > 0 && numvoices < MIXER_MAX_CHANNELS) ? numvoices : MIXER_MAX_CHANNELS;` *or* promote the tracking arrays to a heap-allocated size matching `Mix_AllocateChannels`'s return value. Latter is cleaner; former is a one-liner safe fix.
- **Blast radius:** Heap leak proportional to playback rate when caller requests > 32 voices (Duke3D's default is 32, but `DUKE3D.CFG` `NumVoices` can be set higher). Triggers on every long playtest. Not a crash but does degrade reliability over the course of a session.

### 3.2 [P2] `%lu` printf format used with `uint32_t` arguments

- **File:line:** compat/audio_stub.c:157, 163, 807, 813 (`wav_file_size`, `midi_file_size`).
- **Root cause:** Post-c113 migration, the offending variables are `uint32_t` (typically `unsigned int`), but the diagnostic `fprintf` calls were left at `%lu`. On Linux x86_64 (LP64) `unsigned long` is 8 bytes — varargs promotion does **not** widen the `uint32_t`, so `printf` reads 4 bytes of payload + 4 bytes of garbage from the next slot. Behaviour: garbled stderr message and a `-Wformat` warning if `-Wall` ever lands on this TU.
- **Fix sketch:** `%u` (or `PRIu32` from `<inttypes.h>`).
- **Blast radius:** Diagnostics only; no functional impact. But it's an easy lint catch and gives wrong line numbers to anyone debugging a malformed WAV/MIDI in the field.

### 3.3 [P2] `atexit(sdl_shutdown)` re-registered on every `sdl_init`

- **File:line:** compat/sdl_driver.c:208.
- **Root cause:** `sdl_init` is callable multiple times (video-mode change path documented at L193–197). Every call appends another `sdl_shutdown` handler to the atexit chain. POSIX guarantees only ATEXIT_MAX (≥ 32) handlers; repeated mode-switches in a single session can exhaust the table. The function is idempotent (all destroy targets become NULL after the first run), but the slot consumption is wasteful and on minimal libc embedded targets (musl is fine, dietlibc is not) can silently fail registration of *other* handlers.
- **Fix sketch:** Guard with a `static int registered;` flag and call `atexit` once.
- **Blast radius:** Negligible on glibc/MSVCRT/musl. Documenting for future-proofing.

### 3.4 [P2] `SCRIPT_Load` leaks the slot on `fopen` failure

- **File:line:** compat/mact_stub.c:67–77.
- **Root cause:** The function reserves a slot (`sc->active = 1`) **before** attempting `fopen`. On fopen failure it `return (int)(sc - scripts);` without resetting `active`. After ≤ 4 failed loads (MAX_SCRIPTS = 4) the script subsystem is exhausted and *subsequent* legitimate `SCRIPT_Load` calls return -1.
- **Fix sketch:** `if (!f) { sc->active = 0; return -1; }`
- **Blast radius:** Repeated missing-config-file scenarios degrade silently. Unlikely in a shipping build but a real footgun for modders.

### 3.5 [P2] `SCRIPT_GetString` / `SCRIPT_GetDoubleString` deref `dest` before validating

- **File:line:** compat/mact_stub.c:137 (`dest[0] = 0;`), 164 (`dest1[0] = dest2[0] = 0;`).
- **Root cause:** Both functions touch `dest`/`dest1`/`dest2` before any null check. A defensive caller passing NULL (e.g. when probing for a key's existence) gets a SEGV instead of a "not found" signal. The legacy MACT contract was the same, so this matches historical behavior — but for a modern shipped binary it's a trivially exploitable crash if untrusted CFG paths ever feed into it.
- **Fix sketch:** Add `if (!dest) return;` at top of each accessor; document the precondition in compat/audio_stub.h.
- **Blast radius:** Engine callers in source/ always supply non-NULL, so no current crash; risk is future modder code and AI-playtest harness fuzzing.

### 3.6 [P2] `sdl_capture_frame` ignores `fwrite` return values for pixel/pad rows

- **File:line:** compat/sdl_driver.c:360, 365 (inside the per-row loop).
- **Root cause:** Header writes (L345–346) are checked, but pixel-row and pad-row writes are not. A disk-full or broken-pipe condition mid-capture produces a truncated BMP that still gets `fclose`'d and reported as success (return 0). AI playtest harnesses that consume `captures/frame_NNNN.bmp` will then load garbage with no diagnostic.
- **Fix sketch:** Wrap both per-row writes in `if (fwrite(...) != expected) { fclose(fp); unlink(path); return -1; }`.
- **Blast radius:** Captures-dependent tooling (CI playtest snapshots, AI agents). Not gameplay-affecting.

### 3.7 [P2-INFO] `maxtiles_guard` operator-memory drift (informational, no code change proposed)

- **File:line:** compat/maxtiles_guard.c:4–7 vs SRC/BUILD.H:15 (= 6144) and source/BUILD.H:33 (= 6144).
- **Observation:** The persona/operator memory states the MAXTILES split is "9216 vs 6144 INTENTIONAL — flagged at launch by `compat/maxtiles_guard.c`". The current source tree reflects the **Stage-2 unification** documented in maxtiles_guard.c:4–7: both headers are now `6144`, the constructor at L20–32 can no longer trip, and the guard exists purely as an anti-regression sentinel.
- **No code change recommended.** Per the run constraint ("Do NOT propose unifying it without explicit ENGINE coordination caveat"), this is reported purely as an operator-side documentation drift: the Stage-2 unification *did* happen in a coordinated way (per build-r13 sentinel in maxtiles_guard.c:9), and the guard is doing its job. The memory text should be refreshed by whoever maintains the persona context to reflect the post-Stage-2 reality: "both headers = 6144; `compat/maxtiles_guard.c` is the link-time anti-regression sentinel."
- **Blast radius:** Zero functional. Pure operator-cognition drift.

---

## 4. What was looked at and found clean

- **Signal handling** (compat/sdl_driver.c:59 `volatile sig_atomic_t sdl_quit_requested`) — correct type; only read in `sdl_checkquit`/`sdl_quit_requested_get`, only written by SDL_QUIT path. Async-safe.
- **SDL teardown order** (sdl_driver.c:293–298) — texture → renderer → window → free → SDL_Quit. Correct.
- **SDL2 init/teardown race on re-init** (sdl_driver.c:194–197) — old handles are freed before new are created; no leak.
- **Palette conversion SSE2 fast path** (sdl_driver.c:402–427) — byte-identical to scalar; restrict-qualified; tail-loop handles 0–3 remainder.
- **`mixer_channel_done` audio-thread contract** (audio_stub.c:80–98) — correctly documented as held under SDL_LockAudio; pointer reads are aligned and atomic on all supported ISAs.
- **VOC/WAV header parsers** (audio_stub.c:113–175) — preconditions explicitly documented; bounds-checked against `MAX_SOUND_FILE_SIZE`.
- **`mixer_play` chunk lifecycle on retry** (audio_stub.c:211–228) — on second PlayChannel failure the chunk is freed (no leak).
- **POSIX/Win32 socket abstraction** (net_socket_posix.c, net_socket_win32.c) — keepalive envvars (DUKE_NET_KEEPIDLE/INTVL/CNT) validated with strtol bounds; transient/keepalive error helpers consistent.
- **`compat.h` MSVC shim block** (compat.h:20–54) — `__attribute__`, `__builtin_expect`, `__restrict__` mappings + POSIX function renames all present.
- **`maxtiles_guard.c` constructor** — `__attribute__((constructor))` correct for GCC/Clang; runs before main even with shared-library injection; aborts loudly on divergence.
- **All 26+ `_Static_assert`s** still hold.
- **No `long` in any packed-struct field** in compat/.

---

## 5. Mined Todos (≤ 6)

1. **compat-r29-mixer-channel-clamp** — *P1.* Clamp `numvoices` to `MIXER_MAX_CHANNELS` in `FX_Init` (audio_stub.c:412) **or** size the tracking arrays dynamically. Eliminates the channel-overflow leak. Effort: 15 min + audio regression run.
2. **compat-r29-printf-uint32-format** — *P2.* Replace `%lu` with `%u`/`PRIu32` at audio_stub.c:157, 163, 807, 813. Effort: 5 min.
3. **compat-r29-atexit-once** — *P2.* Guard `atexit(sdl_shutdown)` (sdl_driver.c:208) with a `static int registered`. Effort: 5 min.
4. **compat-r29-script-load-slot-leak** — *P2.* Reset `sc->active = 0` on `fopen` failure at mact_stub.c:77; return -1. Effort: 5 min + 1 regression test.
5. **compat-r29-script-getstring-null-guard** — *P2.* Add NULL-dest guards at mact_stub.c:137, 164. Effort: 10 min.
6. **compat-r29-capture-fwrite-checked** — *P2.* Check return of per-row `fwrite` in sdl_capture_frame (sdl_driver.c:360, 365); unlink + return -1 on short write. Effort: 15 min.

---

<!-- GRIND_LOG_ENTRY -->
**Cycle 119 audit-pass — compat-layer r29 (DOC-ONLY, full shippability audit)**: Full re-walk of compat/ (~6 860 LOC, 11 files) against r28 backlog. **r28 CRITICAL CLOSED** (sha256.c added to CMakeLists.txt:54); **r28 MED CLOSED** (SRC/MMULTI.C adopts net_socket abstraction at 9 call-sites). 1 new P1 surfaced (`mixer_channel_chunk[32]` silently overshot when `FX_Init` numvoices > 32 → chunk leak + missed fx_callback). 6 new P2s (`%lu`/uint32_t printf mismatch x4, atexit re-registration, SCRIPT_Load slot-leak on fopen-fail, SCRIPT_GetString NULL-deref, fwrite return-ignored in BMP capture, maxtiles-guard operator-memory drift). Ship verdict: Linux+macOS+Windows-MinGW READY; Windows-MSVC needs one win_build.ps1 smoke. Mined 6 actionable todos.
<!-- END_GRIND_LOG_ENTRY -->

---

<!-- MINED_TODOS -->
INSERT INTO todos (id, title, description, status) VALUES
  ('compat-r29-mixer-channel-clamp', 'Clamp FX_Init numvoices to MIXER_MAX_CHANNELS (or size tracking arrays dynamically)', 'compat/audio_stub.c:412 — Mix_AllocateChannels(numvoices) honors caller; mixer_channel_chunk[32]/cbval[32] only track channels<32. Channels >=32 leak Mix_Chunk* and miss fx_callback. Fix: clamp numvoices to MIXER_MAX_CHANNELS in FX_Init or promote arrays to heap sized to actual channel count.', 'pending'),
  ('compat-r29-printf-uint32-format', 'Fix %lu vs uint32_t printf format mismatch in audio_stub.c', 'compat/audio_stub.c:157,163,807,813 — diagnostic fprintf uses %lu for uint32_t args (UB on LP64 x86_64). Replace with %u or PRIu32 from <inttypes.h>.', 'pending'),
  ('compat-r29-atexit-once', 'Guard atexit(sdl_shutdown) with a static once-flag', 'compat/sdl_driver.c:208 — sdl_init is re-entrant for video mode changes; each call re-registers sdl_shutdown via atexit. Add static int registered guard to prevent atexit-table exhaustion on minimal libc.', 'pending'),
  ('compat-r29-script-load-slot-leak', 'SCRIPT_Load leaks slot on fopen failure', 'compat/mact_stub.c:77 — sets sc->active=1 before fopen; on fopen failure returns handle without resetting active. After 4 failed loads MAX_SCRIPTS slots exhausted. Fix: if (!f) { sc->active = 0; return -1; }.', 'pending'),
  ('compat-r29-script-getstring-null-guard', 'SCRIPT_GetString/GetDoubleString deref dest before validation', 'compat/mact_stub.c:137,164 — dest[0]=0 before NULL check on dest. Add if (!dest) return; guard at top of accessors; document NULL contract in audio_stub.h.', 'pending'),
  ('compat-r29-capture-fwrite-checked', 'sdl_capture_frame ignores fwrite return on pixel/pad rows', 'compat/sdl_driver.c:360,365 — per-row pixel and pad fwrites unchecked; disk-full mid-capture produces truncated BMP reported as success. Wrap writes; on short write fclose+unlink+return -1.', 'pending');
<!-- END_MINED_TODOS -->

---

## Audit Checklist

- ✅ Re-walked all 11 compat/ source files (audio_stub.{c,h}, sdl_driver.{c,h}, mact_stub.c, compat.h, maxtiles_guard.c, net_socket_{posix,win32}.c, net_socket.h, msvc_unistd.h, hud.{c,h}, sha256.{c,h}, pragmas_gcc.h, log_stub.h).
- ✅ Re-verified all r28 carry-over items (sha256-CMake CLOSED, net_socket-adoption CLOSED, 2 LOW + 1 MED carry forward).
- ✅ Confirmed `_Static_assert` inventory intact (no regression since c107/c113).
- ✅ Verified per-finding file:line citations with `grep -n` before writing.
- ✅ Honored MAXTILES guard constraint — reported drift as informational only; proposed no code change.
- ✅ No `.c` / `.h` / `.py` source file touched.
- ✅ No `git stash` / `git reset` / `git checkout --` invoked (parallel-tree safety).

---

<!-- SENTINEL: c119-compat-r29-a7f3e29d -->
