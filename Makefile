# Duke Nukem 3D - Modern GCC/SDL2 Makefile
# Supports Linux (native) and Windows x64 (cross-compilation via MinGW)

include build.mk

# Build type configuration: release (default) or debug
BUILD_TYPE ?= release

ifeq ($(BUILD_TYPE),debug)
  OPT_FLAGS = -O0 -g -DDEBUG
  WARN_FLAGS = -Wall
  LTO_FLAGS =
else
  OPT_FLAGS = -O2 -DNDEBUG
  WARN_FLAGS = -w
  LTO_FLAGS = -flto
endif

CC      = gcc
CFLAGS  = $(LEGACY_STD) $(OPT_FLAGS) $(WARN_FLAGS) $(LTO_FLAGS) $(COMMON_DEFINES) -DPLATFORM_UNIX

# ===== Smart SDL2 Detection =====
SDL2_CFLAGS := $(shell pkg-config --cflags sdl2 2>/dev/null || sdl2-config --cflags 2>/dev/null)
SDL2_LIBS := $(shell pkg-config --libs sdl2 2>/dev/null || sdl2-config --libs 2>/dev/null)

# Fallback: check common system paths
ifeq ($(SDL2_CFLAGS),)
  ifneq ($(wildcard /usr/include/SDL2/SDL.h),)
    SDL2_CFLAGS := -I/usr/include/SDL2
    SDL2_LIBS := -lSDL2
  else
    # Try Homebrew (Linux or macOS)
    SDL2_BREW := $(shell brew --prefix sdl2 2>/dev/null)
    ifneq ($(SDL2_BREW),)
      SDL2_CFLAGS := -I$(SDL2_BREW)/include/SDL2
      SDL2_LIBS := -L$(SDL2_BREW)/lib -lSDL2
    endif
  endif
endif

# Verify SDL2 was found
ifeq ($(SDL2_CFLAGS),)
  $(warning SDL2 not found! Install libsdl2-dev or set SDL2_CFLAGS/SDL2_LIBS manually)
endif

# ===== Smart SDL2_mixer Detection =====
HAVE_SDL2_MIXER := $(shell pkg-config --exists SDL2_mixer 2>/dev/null && echo yes)
ifeq ($(HAVE_SDL2_MIXER),yes)
  MIXER_LIBS := $(shell pkg-config --libs SDL2_mixer 2>/dev/null)
else
  MIXER_BREW := $(shell brew --prefix sdl2_mixer 2>/dev/null)
  ifneq ($(MIXER_BREW),)
    HAVE_SDL2_MIXER := yes
    MIXER_LIBS := -L$(MIXER_BREW)/lib -lSDL2_mixer
  endif
endif
ifeq ($(HAVE_SDL2_MIXER),yes)
  MIXER_CFLAGS = -DHAVE_SDL2_MIXER $(shell pkg-config --cflags SDL2_mixer 2>/dev/null)
endif

LIBS    = $(SDL2_LIBS) $(MIXER_LIBS) -lm

# ===== Windows x64 cross-compilation settings =====
# Smart MinGW SDL2 detection
WIN_CC = x86_64-w64-mingw32-gcc
WIN_CFLAGS  = $(LEGACY_STD) $(OPT_FLAGS) $(WARN_FLAGS) $(LTO_FLAGS) $(COMMON_DEFINES) -DPLATFORM_WIN32
WIN_SDL2_CFLAGS = $(if $(SDL2_WIN_CFLAGS),$(SDL2_WIN_CFLAGS),$(shell pkg-config --cflags sdl2 2>/dev/null))
ifeq ($(WIN_SDL2_CFLAGS),)
  # Check common MinGW SDL2 paths
  ifneq ($(wildcard /usr/x86_64-w64-mingw32/include/SDL2/SDL.h),)
    WIN_SDL2_CFLAGS = -I/usr/x86_64-w64-mingw32/include/SDL2
    WIN_SDL2_LIBS = -L/usr/x86_64-w64-mingw32/lib -lmingw32 -lSDL2main -lSDL2
  endif
endif
WIN_SDL2_LIBS ?= $(if $(SDL2_WIN_LIBS),$(SDL2_WIN_LIBS),-L/usr/x86_64-w64-mingw32/lib -lmingw32 -lSDL2main -lSDL2)
WIN_LIBS    = $(WIN_SDL2_LIBS) -lm -lws2_32 -mwindows -static-libgcc
WIN_TARGET  = duke3d.exe
WIN_BUILD_DIR = build_win

# Include paths
INCLUDES = $(INCLUDE_DIRS)

# Output
TARGET = duke3d

# All sources
ALL_SRCS = $(ENGINE_SRCS) $(GAME_SRCS) $(COMPAT_SRCS)

# Object files (in build/ directory)
BUILD_DIR = build
ENGINE_OBJS = $(patsubst SRC/%.C,$(BUILD_DIR)/engine_%.o,$(ENGINE_SRCS))
GAME_OBJS   = $(patsubst source/%.C,$(BUILD_DIR)/game_%.o,$(GAME_SRCS))
COMPAT_OBJS = $(patsubst compat/%.c,$(BUILD_DIR)/compat_%.o,$(COMPAT_SRCS))
ALL_OBJS    = $(ENGINE_OBJS) $(GAME_OBJS) $(COMPAT_OBJS)

# Windows object files (in build_win/ directory)
WIN_ENGINE_OBJS = $(patsubst SRC/%.C,$(WIN_BUILD_DIR)/engine_%.o,$(ENGINE_SRCS))
WIN_GAME_OBJS   = $(patsubst source/%.C,$(WIN_BUILD_DIR)/game_%.o,$(GAME_SRCS))
WIN_COMPAT_OBJS = $(patsubst compat/%.c,$(WIN_BUILD_DIR)/compat_%.o,$(COMPAT_SRCS))
WIN_ALL_OBJS    = $(WIN_ENGINE_OBJS) $(WIN_GAME_OBJS) $(WIN_COMPAT_OBJS)

.PHONY: all clean windows assets audio all-platforms debug release info

all: $(TARGET)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(TARGET): $(BUILD_DIR) $(ALL_OBJS)
	$(CC) $(LTO_FLAGS) $(ALL_OBJS) -o $@ $(LIBS)
	@echo "Build complete: $(TARGET) ($(BUILD_TYPE))"

# Engine objects - compile with ENGINE defined, force C mode
# ENGINE.C uses integer/fixed-point rendering math, safe for -ffast-math
$(BUILD_DIR)/engine_ENGINE.o: SRC/ENGINE.C | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(ENGINE_EXTRA_FLAGS) $(SDL2_CFLAGS) $(INCLUDES) -x c -c $< -o $@

$(BUILD_DIR)/engine_CACHE1D.o: SRC/CACHE1D.C | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(SDL2_CFLAGS) $(INCLUDES) -x c -c $< -o $@

$(BUILD_DIR)/engine_MMULTI.o: SRC/MMULTI.C | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(SDL2_CFLAGS) $(INCLUDES) -x c -c $< -o $@

# Game objects - force C mode for uppercase .C files
$(BUILD_DIR)/game_%.o: source/%.C | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(SDL2_CFLAGS) $(INCLUDES) -x c -c $< -o $@

# Compat objects - compile with C11 (these are modern code)
$(BUILD_DIR)/compat_%.o: compat/%.c | $(BUILD_DIR)
	$(CC) $(COMPAT_STD) $(OPT_FLAGS) -Wall $(LTO_FLAGS) $(SDL2_CFLAGS) $(MIXER_CFLAGS) $(INCLUDES) -c $< -o $@

# ===== Windows x64 cross-compilation targets =====

windows: $(WIN_TARGET)

$(WIN_BUILD_DIR):
	mkdir -p $(WIN_BUILD_DIR)

$(WIN_TARGET): $(WIN_BUILD_DIR) $(WIN_ALL_OBJS)
	$(WIN_CC) $(LTO_FLAGS) $(WIN_ALL_OBJS) -o $@ $(WIN_LIBS)
	@echo "Build complete: $(WIN_TARGET) ($(BUILD_TYPE))"

$(WIN_BUILD_DIR)/engine_ENGINE.o: SRC/ENGINE.C | $(WIN_BUILD_DIR)
	$(WIN_CC) $(WIN_CFLAGS) $(ENGINE_EXTRA_FLAGS) $(WIN_SDL2_CFLAGS) $(INCLUDES) -x c -c $< -o $@

$(WIN_BUILD_DIR)/engine_CACHE1D.o: SRC/CACHE1D.C | $(WIN_BUILD_DIR)
	$(WIN_CC) $(WIN_CFLAGS) $(WIN_SDL2_CFLAGS) $(INCLUDES) -x c -c $< -o $@

$(WIN_BUILD_DIR)/engine_MMULTI.o: SRC/MMULTI.C | $(WIN_BUILD_DIR)
	$(WIN_CC) $(WIN_CFLAGS) $(WIN_SDL2_CFLAGS) $(INCLUDES) -x c -c $< -o $@

$(WIN_BUILD_DIR)/game_%.o: source/%.C | $(WIN_BUILD_DIR)
	$(WIN_CC) $(WIN_CFLAGS) $(WIN_SDL2_CFLAGS) $(INCLUDES) -x c -c $< -o $@

$(WIN_BUILD_DIR)/compat_%.o: compat/%.c | $(WIN_BUILD_DIR)
	$(WIN_CC) $(COMPAT_STD) $(OPT_FLAGS) -Wall $(LTO_FLAGS) $(COMMON_DEFINES) -DPLATFORM_WIN32 $(WIN_SDL2_CFLAGS) $(INCLUDES) -c $< -o $@

# ===== Asset generation =====

assets:
	python3 tools/generate_assets.py --no-ai

audio:
	python3 tools/generate_audio.py

# ===== Multi-platform build =====

all-platforms: all windows

# ===== Build type convenience targets =====

debug:
	$(MAKE) BUILD_TYPE=debug

release:
	$(MAKE) BUILD_TYPE=release

clean:
	rm -rf $(BUILD_DIR) $(WIN_BUILD_DIR) $(TARGET) $(WIN_TARGET)

# ===== Build info =====

.PHONY: info
info:
	@echo "=== Duke3D Build Configuration ==="
	@echo "Platform:      $(shell uname -s -m)"
	@echo "CC:            $(CC)"
	@echo "Build type:    $(BUILD_TYPE)"
	@echo "SDL2 CFLAGS:   $(SDL2_CFLAGS)"
	@echo "SDL2 LIBS:     $(SDL2_LIBS)"
	@echo "SDL2_mixer:    $(if $(HAVE_SDL2_MIXER),yes ($(MIXER_LIBS)),no)"
	@echo "MinGW CC:      $(shell which $(WIN_CC) 2>/dev/null || echo 'not found')"
	@echo "Engine srcs:   $(words $(ENGINE_SRCS)) files"
	@echo "Game srcs:     $(words $(GAME_SRCS)) files"
	@echo "Compat srcs:   $(words $(COMPAT_SRCS)) files"
	@echo "=================================="

# Quick test: try to compile each file individually
test-compile: $(BUILD_DIR)
	@for f in $(ENGINE_SRCS); do \
		echo "Compiling $$f..."; \
		$(CC) $(CFLAGS) $(SDL2_CFLAGS) $(INCLUDES) -DENGINE -c $$f -o /dev/null 2>&1 | head -5 || true; \
	done
	@for f in $(GAME_SRCS); do \
		echo "Compiling $$f..."; \
		$(CC) $(CFLAGS) $(SDL2_CFLAGS) $(INCLUDES) -c $$f -o /dev/null 2>&1 | head -5 || true; \
	done
	@for f in $(COMPAT_SRCS); do \
		echo "Compiling $$f..."; \
		$(CC) $(COMPAT_STD) -Wall $(SDL2_CFLAGS) $(INCLUDES) -c $$f -o /dev/null 2>&1 | head -5 || true; \
	done
