# Duke Nukem 3D - Modern GCC/SDL2 Makefile
# Supports Linux (native) and Windows x64 (cross-compilation via MinGW)

CC      = gcc
CFLAGS  = -std=gnu89 -w -DSUPERBUILD -DPLATFORM_UNIX
SDL_CFLAGS = $(shell sdl2-config --cflags 2>/dev/null || echo "-I/home/linuxbrew/.linuxbrew/include/SDL2 -D_REENTRANT")
SDL_LIBS   = $(shell sdl2-config --libs 2>/dev/null || echo "-L/home/linuxbrew/.linuxbrew/lib -lSDL2")
LIBS    = $(SDL_LIBS) -lm

# ===== Windows x64 cross-compilation settings =====
WIN_CC      = x86_64-w64-mingw32-gcc
WIN_CFLAGS  = -std=gnu89 -w -DSUPERBUILD -DPLATFORM_WIN32
WIN_SDL_CFLAGS = $(if $(SDL2_WIN_CFLAGS),$(SDL2_WIN_CFLAGS),-I/usr/x86_64-w64-mingw32/include/SDL2 -D_REENTRANT)
WIN_SDL_LIBS   = $(if $(SDL2_WIN_LIBS),$(SDL2_WIN_LIBS),-L/usr/x86_64-w64-mingw32/lib -lmingw32 -lSDL2main -lSDL2)
WIN_LIBS    = $(WIN_SDL_LIBS) -lm -mwindows
WIN_TARGET  = duke3d.exe
WIN_BUILD_DIR = build_win

# Include paths
INCLUDES = -Icompat -ISRC -Isource

# Output
TARGET = duke3d

# Engine sources (BUILD engine)
ENGINE_SRCS = SRC/ENGINE.C SRC/CACHE1D.C SRC/MMULTI.C

# Game sources
GAME_SRCS = source/GAME.C source/ACTORS.C source/GAMEDEF.C source/GLOBAL.C \
            source/MENUES.C source/PLAYER.C source/PREMAP.C source/SECTOR.C \
            source/SOUNDS.C source/RTS.C source/CONFIG.C source/ANIMLIB.C

# Compat layer sources (a.c excluded - ENGINE.C has inline C replacements for ASM)
COMPAT_SRCS = compat/sdl_driver.c compat/audio_stub.c compat/mact_stub.c

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

.PHONY: all clean windows assets all-platforms

all: $(TARGET)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(TARGET): $(BUILD_DIR) $(ALL_OBJS)
	$(CC) $(ALL_OBJS) -o $@ $(LIBS)
	@echo "Build complete: $(TARGET)"

# Engine objects - compile with ENGINE defined, force C mode
$(BUILD_DIR)/engine_ENGINE.o: SRC/ENGINE.C | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(SDL_CFLAGS) $(INCLUDES) -DENGINE -x c -c $< -o $@

$(BUILD_DIR)/engine_CACHE1D.o: SRC/CACHE1D.C | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(SDL_CFLAGS) $(INCLUDES) -x c -c $< -o $@

$(BUILD_DIR)/engine_MMULTI.o: SRC/MMULTI.C | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(SDL_CFLAGS) $(INCLUDES) -x c -c $< -o $@

# Game objects - force C mode for uppercase .C files
$(BUILD_DIR)/game_%.o: source/%.C | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(SDL_CFLAGS) $(INCLUDES) -x c -c $< -o $@

# Compat objects - compile with C11 (these are modern code)
$(BUILD_DIR)/compat_%.o: compat/%.c | $(BUILD_DIR)
	$(CC) -std=gnu11 -Wall $(SDL_CFLAGS) $(INCLUDES) -c $< -o $@

# ===== Windows x64 cross-compilation targets =====

windows: $(WIN_TARGET)

$(WIN_BUILD_DIR):
	mkdir -p $(WIN_BUILD_DIR)

$(WIN_TARGET): $(WIN_BUILD_DIR) $(WIN_ALL_OBJS)
	$(WIN_CC) $(WIN_ALL_OBJS) -o $@ $(WIN_LIBS)
	@echo "Build complete: $(WIN_TARGET)"

$(WIN_BUILD_DIR)/engine_ENGINE.o: SRC/ENGINE.C | $(WIN_BUILD_DIR)
	$(WIN_CC) $(WIN_CFLAGS) $(WIN_SDL_CFLAGS) $(INCLUDES) -DENGINE -x c -c $< -o $@

$(WIN_BUILD_DIR)/engine_CACHE1D.o: SRC/CACHE1D.C | $(WIN_BUILD_DIR)
	$(WIN_CC) $(WIN_CFLAGS) $(WIN_SDL_CFLAGS) $(INCLUDES) -x c -c $< -o $@

$(WIN_BUILD_DIR)/engine_MMULTI.o: SRC/MMULTI.C | $(WIN_BUILD_DIR)
	$(WIN_CC) $(WIN_CFLAGS) $(WIN_SDL_CFLAGS) $(INCLUDES) -x c -c $< -o $@

$(WIN_BUILD_DIR)/game_%.o: source/%.C | $(WIN_BUILD_DIR)
	$(WIN_CC) $(WIN_CFLAGS) $(WIN_SDL_CFLAGS) $(INCLUDES) -x c -c $< -o $@

$(WIN_BUILD_DIR)/compat_%.o: compat/%.c | $(WIN_BUILD_DIR)
	$(WIN_CC) -std=gnu11 -Wall -DSUPERBUILD -DPLATFORM_WIN32 $(WIN_SDL_CFLAGS) $(INCLUDES) -c $< -o $@

# ===== Asset generation =====

assets:
	python3 tools/generate_assets.py

# ===== Multi-platform build =====

all-platforms: all windows

clean:
	rm -rf $(BUILD_DIR) $(WIN_BUILD_DIR) $(TARGET) $(WIN_TARGET)

# Quick test: try to compile each file individually
test-compile: $(BUILD_DIR)
	@for f in $(ENGINE_SRCS); do \
		echo "Compiling $$f..."; \
		$(CC) $(CFLAGS) $(SDL_CFLAGS) $(INCLUDES) -DENGINE -c $$f -o /dev/null 2>&1 | head -5 || true; \
	done
	@for f in $(GAME_SRCS); do \
		echo "Compiling $$f..."; \
		$(CC) $(CFLAGS) $(SDL_CFLAGS) $(INCLUDES) -c $$f -o /dev/null 2>&1 | head -5 || true; \
	done
	@for f in $(COMPAT_SRCS); do \
		echo "Compiling $$f..."; \
		$(CC) -std=gnu11 -Wall $(SDL_CFLAGS) $(INCLUDES) -c $$f -o /dev/null 2>&1 | head -5 || true; \
	done
