# Compatibility Layer (`compat/`) — Subsystem Index

The `compat/` directory bridges the original 1996 BUILD engine (K&R C + DOS) to modern platforms (POSIX, Win32, MSVC). This is the **portability shim layer**, not the engine or game code.

## Overview

**Purpose:**  Provide platform-agnostic C11 abstractions for:
- Video/input (DOS VESA/VGA + keyboard → SDL2)
- Audio/music (DOS audiolib + MACT library → stubs, future: SDL2_mixer)
- Joystick/controller (DOS MACT → SDL input)
- Networking (DOS/IPX protocols → TCP sockets)
- MSVC compatibility (POSIX shims for Windows native builds)

**C Standard Split** (per [docs/ARCHITECTURE.md § E](../docs/ARCHITECTURE.md#e-gnu89--c11-split)):
- `SRC/*.C` + `source/*.C` → compile with **`-std=gnu89`** (legacy K&R C)
- `compat/*.c` + `compat/*.h` → compile with **`-std=gnu11`** (modern C11)

This separation ensures the legacy engine code remains in its original dialect while compat layer code benefits from C11 features.

---

## File Index

| File | Purpose | Header(s) Exposed | Key API | Status |
|------|---------|------------------|---------|--------|
| **sdl_driver.c/h** | SDL2 video/input layer | `sdl_driver.h` | `sdl_init()`, `sdl_nextpage()`, `sdl_keystatus()` | ✅ Active |
| **audio_stub.c/h** | Audio/music/KB/CONTROL stubs | `audio_stub.h` | `FX_*`, `MUSIC_*`, `TS_*`, `KB_*`, `CONTROL_*` | ✅ Active (stub) |
| **mact_stub.c** | MACT config + music + input | `audio_stub.h` | `Music_SetVolume()`, `PlayMusic()`, config parsing | ✅ Active (stub) |
| **compat.h** | Master compatibility header | `compat.h` | Includes all compat headers; DOS → POSIX bridges | ✅ Active |
| **log_stub.h** | Debug logging for stubs | `log_stub.h` | `STUB_LOG()` macro (cycle 68) | ✅ Active |
| **msvc_unistd.h** | POSIX shims for MSVC | (internal) | `getcwd()`, `chdir()`, `_sopen_s` | ✅ Active |
| **hud.c/h** | Framebuffer HUD overlay | `hud.h` | `hud_init()`, `hud_draw()` | ✅ Active |
| **pragmas_gcc.h** | GCC replacement for Watcom asm | (internal) | ~174 inline asm functions (read-only) | ✅ Active |
| **net_socket.h** | Socket abstraction (Windows/POSIX) | `net_socket.h` | `net_socket_create()`, `net_socket_send()` | ⏳ Unintegrated |
| **net_socket_posix.c** | POSIX (BSD) sockets impl | (via net_socket.h) | Platform-specific socket ops | ⏳ Unintegrated |
| **net_socket_win32.c** | Windows (Winsock2) impl | (via net_socket.h) | Platform-specific socket ops + WSAStartup | ⏳ Unintegrated |
| **maxtiles_engine_value.c** | Capture SRC/BUILD.H MAXTILES | (internal link) | `kEngineMaxTiles` (const) | ✅ Active |
| **maxtiles_game_value.c** | Capture source/BUILD.H MAXTILES | (internal link) | `kGameMaxTiles` (const) | ✅ Active |
| **maxtiles_guard.c** | Link-time MAXTILES assertion | (internal) | Stage 3 constructor abort on mismatch | ✅ Active |

---

## Active Stubs with DUKE3D_STUB_LOG (Cycle 68)

When `DUKE3D_STUB_LOG` is defined (`make DUKE3D_STUB_LOG=1`), these stubbed functions log once per process:

| Function | File | Purpose | Log on Call |
|----------|------|---------|-------------|
| `Music_SetVolume()` | mact_stub.c | Set music volume (DOS → stub) | Yes ✅ |
| `PlayMusic()` | mact_stub.c | Play music file (DOS → stub) | Yes ✅ |
| `CONTROL_WaitRelease()` | audio_stub.c | Wait for input release (stub) | Yes ✅ |
| `CONTROL_Ack()` | audio_stub.c | Acknowledge input (stub) | Yes ✅ |
| `FX_StopRecord()` | audio_stub.c | Stop sound recording (stub) | Yes ✅ |

**Usage:** Enable logging to understand which DOS APIs the game still uses:
```bash
make DUKE3D_STUB_LOG=1
./duke3d 2>&1 | grep "DUKE3D_STUB"
```

See [log_stub.h](log_stub.h) for implementation details.

### Stubs Without Logging (Intentionally Silent)

The following stub functions **deliberately do NOT log**, to avoid debug spam. They fall into two categories:

#### Per-Frame Polling (High Frequency)
These functions are called repeatedly during game loops and must remain silent:

| Function | File | Reason |
|----------|------|--------|
| `FX_GetVolume()` | audio_stub.c | Frequently called to read volume state |
| `FX_GetMaxReverbDelay()` | audio_stub.c | Frequently called to query reverb limit |
| `TS_LockMemory()`, `TS_UnlockMemory()` | audio_stub.c | Task scheduler memory locks (per-frame) |
| `inittimer1mhz()`, `uninittimer1mhz()` | mact_stub.c | Timer initialization (called once, but silent by design) |
| `deltatime1mhz()` | mact_stub.c | Per-frame delta time query |
| `CONTROL_PrintAxes()` | audio_stub.c | Developer-only debug output (intentionally no-op) |

#### Configuration / Rare Calls
These functions are called during setup or configuration, not during gameplay:

| Function | File | Reason |
|----------|------|--------|
| `MUSIC_SetMaxFMMidiChannel()` | audio_stub.c | FM synth channel setup (legacy DOS-only) |
| `MUSIC_SetMidiChannelVolume()` | audio_stub.c | MIDI channel control (legacy DOS-only) |
| `MUSIC_ResetMidiChannelVolumes()` | audio_stub.c | MIDI reset (legacy DOS-only) |
| `MUSIC_SetSongTick()`, `MUSIC_SetSongTime()`, `MUSIC_SetSongPosition()` | audio_stub.c | MIDI position seek (rarely called, silent by design) |
| `MUSIC_RegisterTimbreBank()` | audio_stub.c | Timbre registration (legacy DOS-only) |
| `testcallback()` | mact_stub.c | Internal test callback (no-op for stub mode) |

**Design:** If high-frequency stubs need logging in the future, they should be gated by a separate `DUKE3D_VERBOSE_STUBS` define to avoid frame-time overhead.

---

## Networking Abstraction (Cycle 65 net_socket)

**Status:** ⏳ **UNINTEGRATED** — header and platform stubs exist, but not yet used by `SRC/MMULTI.C`.

| Component | File | Exposes | Purpose | Notes |
|-----------|------|---------|---------|-------|
| **Public API** | net_socket.h | Socket ops interface | Hide Win32 ↔ POSIX differences | Unified `net_socket_t`, error handling |
| **POSIX impl** | net_socket_posix.c | BSD socket wrappers | Linux/macOS/Unix | No-op init; uses native `socket()`, `connect()`, etc. |
| **Win32 impl** | net_socket_win32.c | Winsock2 wrappers | Windows native (MSVC) | `WSAStartup()`/`WSACleanup()` management |

**Next Step:** See todo **`net-r16-mmulti-adopt-net-socket-compat`** (cycle 66 grind) to integrate into MMULTI.C.

### TCP Keepalive Tuning (Cycle 105, net-r22)

**POSIX systems** support per-socket keepalive tuning via `net_socket_enable_keepalive()`:

| Tunable | Env Var | Default | Range | Purpose |
|---------|---------|---------|-------|---------|
| TCP_KEEPIDLE | `DUKE_NET_KEEPIDLE` | 120 sec | 1–86400 | Time before first probe |
| TCP_KEEPINTVL | `DUKE_NET_KEEPINTVL` | 30 sec | 1–86400 | Interval between probes |
| TCP_KEEPCNT | `DUKE_NET_KEEPCNT` | 5 | 1–100 | Probes before timeout |

**Windows** uses system-wide keepalive settings (no per-socket tuning). Environment variables are ignored on Windows.

**Usage (lab/CI testing)**:
```bash
# Stress-test with aggressive keepalive (60s idle, 10s probe interval, 3 probes)
DUKE_NET_KEEPIDLE=60 DUKE_NET_KEEPINTVL=10 DUKE_NET_KEEPCNT=3 ./duke3d --net-host

# Or with pytest (sets env for all child processes):
DUKE_NET_KEEPIDLE=60 python3 -m pytest tests/test_net_keepalive.py -v
```

Invalid or out-of-range values fall back to defaults (logged as WARNING). See `compat/net_socket_posix.c:118–171` for implementation.

---

## Endianness Handling

The engine uses **little-endian integers** for binary format compatibility (Targa files, sprites, maps). Endianness is handled in:

- **mact_stub.c : 337–350** — `IntelLong()` inline function (comment notes endianness assumption)
- **Audit:** See todo **`audit-compat-endianness-big-endian-test`** (cycle 70+) to validate on big-endian platforms.

---

## Orphan / Archived Files

**Cycle 60 decision:** Orphaned compat implementations are moved to `docs/archive/compat/` for historical reference:

- Historical stub versions (e.g., early audio drivers, deprecated platform shims)
- **Location:** `docs/archive/compat/a.c` (renamed from `compat/a.c`)
- **Rationale:** Keeps compat/ clean for active code; preserves implementation history.

---

## Testing

| Test Suite | File | Count | Purpose |
|-----------|------|-------|---------|
| **compat_layer** | tests/test_compat_layer.py | 30+ | Struct size asserts, memory layout, int32_t safety |
| **net_socket** | tests/test_net_socket_compat.py | 32 | Platform abstraction; socket creation, options, error codes |
| **stub_logging** | tests/test_compat_layer.py | (via cycle 68) | DUKE3D_STUB_LOG macro verification |

Run tests:
```bash
pytest tests/test_compat_layer.py tests/test_net_socket_compat.py -v
```

Full validation (build + test):
```bash
make clean && make && pytest -q
```

---

## Adding New Compat Shims

When porting a DOS/Watcom API to modern platforms:

1. **Create header** in `compat/` with stable public interface
   - Example: `compat/my_api.h` — function declarations, platform guards
2. **Implement platform versions**
   - `compat/my_api_posix.c` (POSIX/Linux/macOS)
   - `compat/my_api_win32.c` (Windows Winsock2 / native)
   - OR use `#ifdef _WIN32` guards in a single `.c` file
3. **Add tests** in `tests/test_compat_*.py`
   - Struct size assertions (`_Static_assert`)
   - API contract verification (init, cleanup, error handling)
4. **Update build system**
   - `Makefile` (line 131 COMPAT_SRCS) — add new `.c` files
   - `build.mk` (line 132) — ensure COMPAT_STD = -std=gnu11
   - `CMakeLists.txt` (lines 81–82) — add to `COMPAT_SRCS`, set `LANGUAGE C`
5. **Document in this README** — add file to File Index table

---

## MUSIC Subsystem Initialization Order (Cycles 73 / compat-r12-r13)

**CRITICAL:** SDL2_mixer requires a strict initialization sequence. Violating this order causes silent failures, crashes, or corrupted audio state. This requirement is flagged by audit cycles 34, 12, 13, and verified in the compat layer initialization.

### Required Call Sequence (Strict Order)

```
1. SDL_InitSubSystem(SDL_INIT_AUDIO)  ← Platform audio device initialization
2. Mix_Init(MIX_INIT_OGG | MIX_INIT_MP3)  ← Register format decoders
3. Mix_OpenAudio(rate, format, channels, bufsize)  ← Open audio device, allocate buffers
4. Mix_AllocateChannels(numvoices)  ← Allocate mixer channels for SFX playback
5. [Load music files via Mix_LoadMUS_RW() - must happen AFTER steps 1-4]
6. Mix_PlayMusic(music_obj, loops)  ← Play music (now safe to call)
```

### Why Order Matters

- **`SDL_InitSubSystem(SDL_INIT_AUDIO)`** — Initializes the SDL audio subsystem on the current platform (ALSA/PulseAudio on Linux, CoreAudio on macOS, DirectSound on Windows). Must be first.
- **`Mix_Init(MIX_INIT_OGG | MIX_INIT_MP3)`** — Registers dynamic loader plugins for OGG Vorbis and MP3 formats. Failure here doesn't fatal-error; WAV still works, but OGG/MP3 are unavailable. This is **not** the same as opening the audio device.
- **`Mix_OpenAudio()`** — **This is the critical function.** It claims the OS audio device, allocates ring buffers, starts the audio thread, and prepares the mixer. `Mix_OpenAudio()` MUST come after `Mix_Init()`, or it may fail silently or hang trying to initialize already-claimed device handles.
- **`Mix_AllocateChannels()`** — Preallocates mixer channels for sound effects. Must happen after `Mix_OpenAudio()`. If called before, the call is ignored (no mixer is active yet).
- **Load/Play Music** — `Mix_LoadMUS_RW()` and `Mix_PlayMusic()` only work if steps 1–4 have completed and the mixer is live (`mixer_initialized == 1` in compat/audio_stub.c).

### Code Path in compat/

| Phase | Function | File:Line | Called From | Details |
|-------|----------|-----------|------------|---------|
| 1–4   | `FX_Init()` | compat/audio_stub.c:364 | source/SOUNDS.C:79, 83 | Executes all 4 steps in sequence. Sets `mixer_initialized = 1` on success. |
| 2     | `Mix_Init()` | compat/audio_stub.c:374 | → FX_Init | Registers OGG/MP3 decoders. Non-fatal if it fails. |
| 3     | `Mix_OpenAudio()` w/ retry | compat/audio_stub.c:385 | → FX_Init | 3-attempt exponential backoff (100ms, 200ms, 400ms) for transient device failures. Returns FX_Error if all retries exhausted. |
| 4     | `Mix_AllocateChannels()` | compat/audio_stub.c:405 | → FX_Init | Allocates channels for SFX. |
| —     | `MUSIC_Init()` | compat/audio_stub.c:843 | source/SOUNDS.C:165 | **Currently a no-op stub.** Does not call Mix_* functions. Real initialization is deferred to FX_Init. |
| 5–6   | `MUSIC_PlaySong()` | compat/audio_stub.c:915 | source/SOUNDS.C:256 (playmusic) | Checks `mixer_initialized` (line 918). If 0, returns silently. Calls `Mix_LoadMUS_RW()` and `Mix_PlayMusic()` iff `mixer_initialized && song`. |

### Engine Call Sites

```
source/SOUNDS.C:79 or 83     ← FX_Init( FXDevice, NumVoices, NumChannels, NumBits, MixRate )
source/SOUNDS.C:165          ← MUSIC_Init( MusicDevice, MidiPort )
source/SOUNDS.C:256          ← playmusic( char *fn ) → MUSIC_PlaySong()
source/MENUES.C:612, 2698    ← playmusic() calls at runtime (menus)
source/PREMAP.C:992, 1450    ← playmusic() calls at runtime (game level init)
source/GAME.C:6519           ← playmusic() calls at runtime (gameplay)
```

All music playback paths funnel through `playmusic()` in source/SOUNDS.C:256, which calls `MUSIC_PlaySong()` from compat/audio_stub.c:915.

### Common Failure Modes If Order Violated

| Symptom | Cause | Fix |
|---------|-------|-----|
| Music plays silently (no audio) | `Mix_PlayMusic()` called before `Mix_OpenAudio()` | Ensure `FX_Init()` completes successfully before any `MUSIC_PlaySong()` call. Check `mixer_initialized == 1`. |
| `Mix_OpenAudio()` returns -1 | Audio device busy, or `Mix_Init()` failed to register required format decoders | (a) Add retry with exponential backoff (already implemented at compat/audio_stub.c:384–398). (b) Check `Mix_GetError()` for OS-specific audio errors. |
| `MUSIC_PlaySong()` returns error silently | `mixer_initialized == 0` because `FX_Init()` was not called or failed | Verify FX_Init return value. Ensure game startup order is: SoundStartup() → MusicStartup() → playmusic(). |
| Crash on `Mix_LoadMUS_RW()` or `Mix_PlayMusic()` | Mixer channels not allocated (step 4 skipped) | Call `Mix_AllocateChannels()` after `Mix_OpenAudio()`. |
| Format loader plugin missing (OGG/MP3 unavailable) | `Mix_Init()` failed or format libs not linked | Non-fatal; WAV still works. See stderr warning at compat/audio_stub.c:377. |

### Cleanup Order (Reverse Sequence)

When shutting down, reverse the init order:

```c
// In FX_Shutdown (compat/audio_stub.c:417):
1. Mix_HaltMusic()  ← Stop playback first
2. Mix_CloseAudio()  ← Close audio device (deallocates channels, stops audio thread)
3. Mix_Quit()  ← Unload format plugins
4. SDL_QuitSubSystem(SDL_INIT_AUDIO)  ← Release OS audio resources
5. mixer_initialized = 0  ← Signal mixer is inactive
```

See compat/audio_stub.c:417–431 for implementation.

### SDL2_mixer Version Notes

- **SDL2_mixer 2.0.x:** `Mix_Init()` was optional for basic WAV playback; OGG/MP3 decoders were built-in or optional at compile-time. `Mix_OpenAudio()` could be called before `Mix_Init()` (order not enforced).
- **SDL2_mixer 2.4+:** `Mix_Init()` became mandatory; format loaders are now plugins loaded at runtime. If `Mix_Init()` is not called before `Mix_OpenAudio()`, some format decoders will not be available, and `Mix_LoadMUS()` may fail for OGG/MP3.
- **SDL2_mixer 3.0+ (future):** Strict order enforcement may be tightened further; `Mix_Init()` must precede `Mix_OpenAudio()` or the call will fail with an error code instead of silently missing decoders.

**Current build uses SDL2_mixer 2.x.** See build.mk for exact version. If upgrading to 3.0, verify compat/audio_stub.c:374–388 works unchanged, or add conditional version detection.

### Cross-Reference: Audit Cycles

- **compat-r9-mix-init-recovery-test** (cycle 34): Tests `Mix_OpenAudio()` retry semantics and recovery from transient device failures.
- **compat-r11-mix-init-retry-backoff** (cycle 71): Implements 3-attempt exponential backoff in FX_Init (compat/audio_stub.c:384–398).
- **compat-r12-verify-music-subsystem-init-order** (cycle 73): Verify strict init order in engine startup sequence.
- **compat-r13-music-subsystem-init-docs** (cycle 73): Document init order (this section).

---

## MSVC Pragmas Status (Compat-R19 Clarification)

**Original compat-r10 backlog item:** Create `pragmas_msvc.h` or expand compat.h MSVC section with pragma documentation.

**Resolution:** ✅ **pragmas_msvc.h is not needed; MSVC pragma support is complete via compat.h.**

### Findings

1. **pragmas_msvc.h does NOT exist** — File not found in repository. Never created.

2. **MSVC pragma support IS complete** via existing files:
   - **compat.h (lines 20–54):** Master MSVC compatibility section
     - `__attribute__(x)` macro substitution (GCC feature unavailable in MSVC)
     - `__builtin_expect(expr, val)` no-op on MSVC
     - `__restrict__` → `__restrict` (MSVC name variant)
     - POSIX → MSVC I/O name mappings (access → \_access, alloca → \_alloca)
   - **compat.h (line 53):** `#pragma warning(disable: 4996)` suppresses POSIX deprecation warnings (MSVC-specific)
   - **msvc_unistd.h:** Windows I/O shims for getcwd(), chdir(), \_sopen_s

3. **pragmas_gcc.h exists (520 lines)** but serves a different purpose:
   - Replaces Watcom `#pragma aux` inline assembly declarations (GCC/Clang only)
   - Not MSVC-specific; MSVC has different inline assembly syntax (not in compat layer)
   - compat.h lines 582–590 document Watcom pragma handling for GCC

### Design Rationale

- **GNU builds (-std=gnu89):** Use pragmas_gcc.h for inline assembly performance optimizations
- **MSVC builds:** Use compat.h MSVC section (lines 20–54) + msvc_unistd.h for Windows shims
- **No separate pragmas_msvc.h needed** because:
  - MSVC pragma directives are already centralized in compat.h
  - MSVC has limited use for inline assembly in compat layer (primary use is macro shims + I/O mappings)
  - pragmas_gcc.h is a **GCC-specific replacement** for Watcom inline asm, not a platform-level pragma guide

### Cross-Reference

- **compat-r10 audit:** docs/audits/compat-layer-r10.md lines 140–160 (original finding)
- **compat-r19 audit:** docs/audits/compat-layer-r19.md lines 186–202 (clarification request)
- **Related todo:** compat-r19-pragmas-msvc-clarify (RESOLVED in compat-r19 cycle)

---

## Cross-References

- **[docs/ARCHITECTURE.md § Compatibility Layer](../docs/ARCHITECTURE.md#compatibility-layer-compat)** — High-level bridge architecture
- **[docs/ARCHITECTURE.md § E. GNU89 / C11 Split](../docs/ARCHITECTURE.md#e-gnu89--c11-split)** — Compilation standard split rationale
- **[docs/audits/build-system-r15.md](../docs/audits/build-system-r15.md)** — gnu89/gnu11 enforcement verification
- **[.github/agents/compat-layer.agent.md](../.github/agents/compat-layer.agent.md)** — Copilot persona owning compat layer
- **[.github/agents/documentation-curator.agent.md](../.github/agents/documentation-curator.agent.md)** — Documentation ownership

---

**Compat layer is the foundation of cross-platform success. Read before modifying `compat/`.**
