# Duke Nukem 3D - Modern GCC/SDL2 Makefile
# Ported from Watcom C/DOS to GCC/Linux

CC      = gcc
CFLAGS  = -std=gnu89 -w -DSUPERBUILD -DPLATFORM_UNIX
SDL_CFLAGS = $(shell sdl2-config --cflags 2>/dev/null || echo "-I/home/linuxbrew/.linuxbrew/include/SDL2 -D_REENTRANT")
SDL_LIBS   = $(shell sdl2-config --libs 2>/dev/null || echo "-L/home/linuxbrew/.linuxbrew/lib -lSDL2")
LIBS    = $(SDL_LIBS) -lm

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

.PHONY: all clean

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

clean:
	rm -rf $(BUILD_DIR) $(TARGET)

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
