/*
 * sdl_driver.c - SDL2 platform layer for Duke Nukem 3D / BUILD engine port
 *
 * Provides video (8-bit palettized → ARGB texture), keyboard/mouse input
 * with DOS-scancode translation, and basic timer services.
 */

#define COMPAT_STARTUP_LOG_OWNER
#include "SDL.h"
#include "sdl_driver.h"
#include "compat.h"
#include "audio_stub.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* ── Video state ────────────────────────────────────────────────── */
static SDL_Window   *window   = NULL;
static SDL_Renderer *renderer = NULL;
static SDL_Texture  *texture  = NULL;
static unsigned char *screenbuf = NULL;
static int screen_width  = 320;
static int screen_height = 200;
static int screen_pitch;
static uint32_t palette32[256]; /* ARGB palette cache */

/* ── Input state ────────────────────────────────────────────────── */
static unsigned char keystatus_array[256];
static int mouse_dx = 0, mouse_dy = 0, mouse_buttons = 0;
int sdl_quit_requested = 0;

/* ── SDL scancode → DOS scancode mapping ────────────────────────── */
static int sdl_to_dos_scancode(SDL_Scancode sc)
{
    switch (sc) {
    case SDL_SCANCODE_ESCAPE:       return 0x01;
    case SDL_SCANCODE_1:            return 0x02;
    case SDL_SCANCODE_2:            return 0x03;
    case SDL_SCANCODE_3:            return 0x04;
    case SDL_SCANCODE_4:            return 0x05;
    case SDL_SCANCODE_5:            return 0x06;
    case SDL_SCANCODE_6:            return 0x07;
    case SDL_SCANCODE_7:            return 0x08;
    case SDL_SCANCODE_8:            return 0x09;
    case SDL_SCANCODE_9:            return 0x0A;
    case SDL_SCANCODE_0:            return 0x0B;
    case SDL_SCANCODE_MINUS:        return 0x0C;
    case SDL_SCANCODE_EQUALS:       return 0x0D;
    case SDL_SCANCODE_BACKSPACE:    return 0x0E;
    case SDL_SCANCODE_TAB:          return 0x0F;
    case SDL_SCANCODE_Q:            return 0x10;
    case SDL_SCANCODE_W:            return 0x11;
    case SDL_SCANCODE_E:            return 0x12;
    case SDL_SCANCODE_R:            return 0x13;
    case SDL_SCANCODE_T:            return 0x14;
    case SDL_SCANCODE_Y:            return 0x15;
    case SDL_SCANCODE_U:            return 0x16;
    case SDL_SCANCODE_I:            return 0x17;
    case SDL_SCANCODE_O:            return 0x18;
    case SDL_SCANCODE_P:            return 0x19;
    case SDL_SCANCODE_LEFTBRACKET:  return 0x1A;
    case SDL_SCANCODE_RIGHTBRACKET: return 0x1B;
    case SDL_SCANCODE_RETURN:       return 0x1C;
    case SDL_SCANCODE_LCTRL:        return 0x1D;
    case SDL_SCANCODE_A:            return 0x1E;
    case SDL_SCANCODE_S:            return 0x1F;
    case SDL_SCANCODE_D:            return 0x20;
    case SDL_SCANCODE_F:            return 0x21;
    case SDL_SCANCODE_G:            return 0x22;
    case SDL_SCANCODE_H:            return 0x23;
    case SDL_SCANCODE_J:            return 0x24;
    case SDL_SCANCODE_K:            return 0x25;
    case SDL_SCANCODE_L:            return 0x26;
    case SDL_SCANCODE_SEMICOLON:    return 0x27;
    case SDL_SCANCODE_APOSTROPHE:   return 0x28;
    case SDL_SCANCODE_GRAVE:        return 0x29;
    case SDL_SCANCODE_LSHIFT:       return 0x2A;
    case SDL_SCANCODE_BACKSLASH:    return 0x2B;
    case SDL_SCANCODE_Z:            return 0x2C;
    case SDL_SCANCODE_X:            return 0x2D;
    case SDL_SCANCODE_C:            return 0x2E;
    case SDL_SCANCODE_V:            return 0x2F;
    case SDL_SCANCODE_B:            return 0x30;
    case SDL_SCANCODE_N:            return 0x31;
    case SDL_SCANCODE_M:            return 0x32;
    case SDL_SCANCODE_COMMA:        return 0x33;
    case SDL_SCANCODE_PERIOD:       return 0x34;
    case SDL_SCANCODE_SLASH:        return 0x35;
    case SDL_SCANCODE_RSHIFT:       return 0x36;
    case SDL_SCANCODE_KP_MULTIPLY:  return 0x37;
    case SDL_SCANCODE_LALT:         return 0x38;
    case SDL_SCANCODE_SPACE:        return 0x39;
    case SDL_SCANCODE_CAPSLOCK:     return 0x3A;
    case SDL_SCANCODE_F1:           return 0x3B;
    case SDL_SCANCODE_F2:           return 0x3C;
    case SDL_SCANCODE_F3:           return 0x3D;
    case SDL_SCANCODE_F4:           return 0x3E;
    case SDL_SCANCODE_F5:           return 0x3F;
    case SDL_SCANCODE_F6:           return 0x40;
    case SDL_SCANCODE_F7:           return 0x41;
    case SDL_SCANCODE_F8:           return 0x42;
    case SDL_SCANCODE_F9:           return 0x43;
    case SDL_SCANCODE_F10:          return 0x44;
    case SDL_SCANCODE_NUMLOCKCLEAR: return 0x45;
    case SDL_SCANCODE_SCROLLLOCK:   return 0x46;
    case SDL_SCANCODE_KP_7:         return 0x47;
    case SDL_SCANCODE_KP_8:         return 0x48;
    case SDL_SCANCODE_KP_9:         return 0x49;
    case SDL_SCANCODE_KP_MINUS:     return 0x4A;
    case SDL_SCANCODE_KP_4:         return 0x4B;
    case SDL_SCANCODE_KP_5:         return 0x4C;
    case SDL_SCANCODE_KP_6:         return 0x4D;
    case SDL_SCANCODE_KP_PLUS:      return 0x4E;
    case SDL_SCANCODE_KP_1:         return 0x4F;
    case SDL_SCANCODE_KP_2:         return 0x50;
    case SDL_SCANCODE_KP_3:         return 0x51;
    case SDL_SCANCODE_KP_0:         return 0x52;
    case SDL_SCANCODE_KP_PERIOD:    return 0x53;
    case SDL_SCANCODE_F11:          return 0x57;
    case SDL_SCANCODE_F12:          return 0x58;
    /* Extended keys (0xE0 prefix in DOS, stored with high bit patterns) */
    case SDL_SCANCODE_KP_ENTER:     return 0x9C;
    case SDL_SCANCODE_RCTRL:        return 0x9D;
    case SDL_SCANCODE_KP_DIVIDE:    return 0xB5;
    case SDL_SCANCODE_RALT:         return 0xB8;
    case SDL_SCANCODE_HOME:         return 0xC7;
    case SDL_SCANCODE_UP:           return 0xC8;
    case SDL_SCANCODE_PAGEUP:       return 0xC9;
    case SDL_SCANCODE_LEFT:         return 0xCB;
    case SDL_SCANCODE_RIGHT:        return 0xCD;
    case SDL_SCANCODE_END:          return 0xCF;
    case SDL_SCANCODE_DOWN:         return 0xD0;
    case SDL_SCANCODE_PAGEDOWN:     return 0xD1;
    case SDL_SCANCODE_INSERT:       return 0xD2;
    case SDL_SCANCODE_DELETE:       return 0xD3;
    default:                        return -1;
    }
}

/* ── Video ──────────────────────────────────────────────────────── */

int sdl_init(int xdim, int ydim)
{
    char errbuf[512];

    startup_log("  sdl_init(%d, %d) called", xdim, ydim);

    /* Clean up previous resources if re-initializing (e.g. video mode change) */
    if (texture)  { SDL_DestroyTexture(texture);   texture  = NULL; }
    if (renderer) { SDL_DestroyRenderer(renderer);  renderer = NULL; }
    if (window)   { SDL_DestroyWindow(window);      window   = NULL; }
    free(screenbuf); screenbuf = NULL;

    startup_log("  SDL_Init(VIDEO|TIMER)...");
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_TIMER) < 0) {
        startup_log("  FATAL: SDL_Init failed: %s", SDL_GetError());
        snprintf(errbuf, sizeof(errbuf),
            "SDL_Init failed: %s\n\n"
            "Make sure SDL2.dll is in the same folder as duke3d.exe.",
            SDL_GetError());
        error_fatal("SDL Error", errbuf);
    }
    startup_log("  SDL_Init OK");

    screen_width  = xdim;
    screen_height = ydim;

    startup_log("  SDL_CreateWindow(%d x %d)...", xdim, ydim);
    window = SDL_CreateWindow("Duke Nukem 3D",
                              SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                              xdim, ydim,
                              SDL_WINDOW_RESIZABLE | SDL_WINDOW_SHOWN);
    if (!window) {
        startup_log("  FATAL: SDL_CreateWindow failed: %s", SDL_GetError());
        snprintf(errbuf, sizeof(errbuf),
            "SDL_CreateWindow failed: %s", SDL_GetError());
        error_fatal("SDL Error", errbuf);
    }
    startup_log("  Window created OK");

    renderer = SDL_CreateRenderer(window, -1,
                                  SDL_RENDERER_ACCELERATED |
                                  SDL_RENDERER_PRESENTVSYNC);
    if (!renderer) {
        /* Fall back to software renderer */
        renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE);
        if (!renderer) {
            snprintf(errbuf, sizeof(errbuf),
                "SDL_CreateRenderer failed: %s", SDL_GetError());
            error_fatal("SDL Error", errbuf);
        }
    }

    SDL_RenderSetLogicalSize(renderer, xdim, ydim);

    texture = SDL_CreateTexture(renderer,
                                SDL_PIXELFORMAT_ARGB8888,
                                SDL_TEXTUREACCESS_STREAMING,
                                xdim, ydim);
    if (!texture) {
        snprintf(errbuf, sizeof(errbuf),
            "SDL_CreateTexture failed: %s", SDL_GetError());
        error_fatal("SDL Error", errbuf);
    }

    screenbuf = (unsigned char *)calloc(1, (size_t)xdim * ydim);
    if (!screenbuf) {
        error_fatal("SDL Error",
            "Failed to allocate screen buffer.\n\n"
            "The system may be out of memory.");
    }
    screen_pitch = xdim;

    SDL_SetRelativeMouseMode(SDL_TRUE);

    /* Default grey-ramp palette */
    for (int i = 0; i < 256; i++)
        palette32[i] = 0xFF000000u | ((uint32_t)i << 16) |
                        ((uint32_t)i << 8) | (uint32_t)i;

    memset(keystatus_array, 0, sizeof(keystatus_array));
    sdl_quit_requested = 0;

    return 0;
}

void sdl_shutdown(void)
{
    if (texture)  { SDL_DestroyTexture(texture);   texture  = NULL; }
    if (renderer) { SDL_DestroyRenderer(renderer);  renderer = NULL; }
    if (window)   { SDL_DestroyWindow(window);      window   = NULL; }
    free(screenbuf); screenbuf = NULL;
    SDL_Quit();
}

void sdl_nextpage(void)
{
    void   *pixels;
    int     pitch;

    sdl_pollevents();

    if (!renderer || !texture || !screenbuf) return;

    if (SDL_LockTexture(texture, NULL, &pixels, &pitch) < 0) return;

    uint32_t *dst = (uint32_t *)pixels;
    int dst_stride = pitch / 4; /* pitch is in bytes, we need uint32 stride */

    for (int y = 0; y < screen_height; y++) {
        const unsigned char *src_row = screenbuf + y * screen_pitch;
        uint32_t *dst_row = dst + y * dst_stride;
        for (int x = 0; x < screen_width; x++)
            dst_row[x] = palette32[src_row[x]];
    }

    SDL_UnlockTexture(texture);
    SDL_RenderClear(renderer);
    SDL_RenderCopy(renderer, texture, NULL, NULL);
    SDL_RenderPresent(renderer);
}

void sdl_setpalette(unsigned char *pal, int start, int num)
{
    /*
     * BUILD engine VBE palette: setbrightness() writes 4 bytes per entry
     * in [B, G, R, 0] order (VBE DAC format).  Components are already
     * scaled to 8-bit by the brightness table (britable[]).
     */
    if (start < 0) start = 0;
    if (start + num > 256) num = 256 - start;
    if (num <= 0) return;

    for (int i = 0; i < num; i++) {
        int idx = start + i;
        unsigned int b = (unsigned int)pal[i * 4 + 0];
        unsigned int g = (unsigned int)pal[i * 4 + 1];
        unsigned int r = (unsigned int)pal[i * 4 + 2];
        /* pal[i * 4 + 3] is padding (always 0) */
        palette32[idx] = 0xFF000000u | (r << 16) | (g << 8) | b;
    }
}

char *sdl_getscreen(void)
{
    return (char *)screenbuf;
}

long sdl_getbytesperline(void)
{
    return (long)screen_pitch;
}

/* ── Input ──────────────────────────────────────────────────────── */

void sdl_pollevents(void)
{
    SDL_Event ev;
    while (SDL_PollEvent(&ev)) {
        switch (ev.type) {
        case SDL_QUIT:
            sdl_quit_requested = 1;
            /* Terminate immediately — many game loops never check the flag,
               so the process would hang as a zombie.  atexit handlers
               (including ShutDown) still run via exit(). */
            exit(0);
            break;

        case SDL_KEYDOWN:
        case SDL_KEYUP: {
            int dos_sc = sdl_to_dos_scancode(ev.key.keysym.scancode);
            if (dos_sc >= 0 && dos_sc < 256) {
                int pressed = (ev.type == SDL_KEYDOWN) ? 1 : 0;
                keystatus_array[dos_sc] = (unsigned char)pressed;
                KB_KeyEvent(dos_sc, pressed);
                if (pressed)
                    KB_Addch((char)dos_sc);
            }
            break;
        }

        case SDL_MOUSEMOTION:
            mouse_dx += ev.motion.xrel;
            mouse_dy += ev.motion.yrel;
            break;

        case SDL_MOUSEBUTTONDOWN:
            if (ev.button.button == SDL_BUTTON_LEFT)   mouse_buttons |= 1;
            if (ev.button.button == SDL_BUTTON_RIGHT)  mouse_buttons |= 2;
            if (ev.button.button == SDL_BUTTON_MIDDLE) mouse_buttons |= 4;
            break;

        case SDL_MOUSEBUTTONUP:
            if (ev.button.button == SDL_BUTTON_LEFT)   mouse_buttons &= ~1;
            if (ev.button.button == SDL_BUTTON_RIGHT)  mouse_buttons &= ~2;
            if (ev.button.button == SDL_BUTTON_MIDDLE) mouse_buttons &= ~4;
            break;

        default:
            break;
        }
    }
}

int sdl_keystatus(int scancode)
{
    if (scancode < 0 || scancode >= 256) return 0;
    return keystatus_array[scancode];
}

void sdl_setkeystatus(int scancode, int state)
{
    if (scancode >= 0 && scancode < 256)
        keystatus_array[scancode] = (unsigned char)state;
}

void sdl_getmouse(int *dx, int *dy, int *buttons)
{
    if (dx)      *dx      = mouse_dx;
    if (dy)      *dy      = mouse_dy;
    if (buttons) *buttons = mouse_buttons;
    mouse_dx = 0;
    mouse_dy = 0;
}

int sdl_checkquit(void)
{
    return sdl_quit_requested;
}

/* ── Timer ──────────────────────────────────────────────────────── */

void sdl_inittimer(void)
{
    /* SDL timer is already initialised by SDL_Init(SDL_INIT_TIMER) */
}

long sdl_getticks(void)
{
    return (long)SDL_GetTicks();
}

void sdl_delay(int ms)
{
    if (ms > 0) SDL_Delay((Uint32)ms);
}
