# build.mk — Single source of truth for Duke3D build configuration
# Included by Makefile. Also parsed by CMakeLists.txt and build_windows.bat.

# ===== Source Files =====
# Engine sources (Ken Silverman's BUILD engine)
ENGINE_SRCS = SRC/ENGINE.C SRC/CACHE1D.C SRC/MMULTI.C

# Game sources (Duke Nukem 3D game logic)
GAME_SRCS = source/GAME.C source/ACTORS.C source/GAMEDEF.C source/GLOBAL.C \
            source/MENUES.C source/PLAYER.C source/PREMAP.C source/SECTOR.C \
            source/SOUNDS.C source/RTS.C source/CONFIG.C source/ANIMLIB.C

# Compatibility layer (modern platform support)
COMPAT_SRCS = compat/sdl_driver.c compat/audio_stub.c compat/mact_stub.c compat/hud.c compat/a.c

# ===== Common Defines =====
COMMON_DEFINES = -DSUPERBUILD

# ===== Compiler Flags by File Type =====
# Legacy C files (1996 K&R-style code)
LEGACY_STD = -std=gnu89

# Modern compat layer
COMPAT_STD = -std=gnu11

# ENGINE.C-specific (fixed-point math benefits from fast-math)
ENGINE_EXTRA_FLAGS = -ffast-math -DENGINE

# ===== Include Paths =====
INCLUDE_DIRS = -Icompat -ISRC -Isource

# ===== SDL2 Version (pinned) =====
SDL2_VERSION = 2.30.9
SDL2_MINGW_URL = https://github.com/libsdl-org/SDL/releases/download/release-$(SDL2_VERSION)/SDL2-devel-$(SDL2_VERSION)-mingw.tar.gz
