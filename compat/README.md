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

---

## Networking Abstraction (Cycle 65 net_socket)

**Status:** ⏳ **UNINTEGRATED** — header and platform stubs exist, but not yet used by `SRC/MMULTI.C`.

| Component | File | Exposes | Purpose | Notes |
|-----------|------|---------|---------|-------|
| **Public API** | net_socket.h | Socket ops interface | Hide Win32 ↔ POSIX differences | Unified `net_socket_t`, error handling |
| **POSIX impl** | net_socket_posix.c | BSD socket wrappers | Linux/macOS/Unix | No-op init; uses native `socket()`, `connect()`, etc. |
| **Win32 impl** | net_socket_win32.c | Winsock2 wrappers | Windows native (MSVC) | `WSAStartup()`/`WSACleanup()` management |

**Next Step:** See todo **`net-r16-mmulti-adopt-net-socket-compat`** (cycle 66 grind) to integrate into MMULTI.C.

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

## Cross-References

- **[docs/ARCHITECTURE.md § Compatibility Layer](../docs/ARCHITECTURE.md#compatibility-layer-compat)** — High-level bridge architecture
- **[docs/ARCHITECTURE.md § E. GNU89 / C11 Split](../docs/ARCHITECTURE.md#e-gnu89--c11-split)** — Compilation standard split rationale
- **[docs/audits/build-system-r15.md](../docs/audits/build-system-r15.md)** — gnu89/gnu11 enforcement verification
- **[.github/agents/compat-layer.agent.md](../.github/agents/compat-layer.agent.md)** — Copilot persona owning compat layer
- **[.github/agents/documentation-curator.agent.md](../.github/agents/documentation-curator.agent.md)** — Documentation ownership

---

**Compat layer is the foundation of cross-platform success. Read before modifying `compat/`.**
