/*
 * hud.c - Simple framebuffer HUD for Duke Nukem 3D compat layer
 *
 * Renders health, ammo, armor, and crosshair directly into the 8-bit
 * framebuffer.  Uses a tiny embedded bitmap font (4x6 glyphs) so it
 * has zero dependency on the tile / art system.
 */

#include "hud.h"
#include <string.h>
#include <stdio.h>

/* ---- 4×6 bitmap font (digits 0-9) ---- */
static const unsigned char digit_font[10][6] = {
    {0x6,0x9,0x9,0x9,0x9,0x6},  /* 0 */
    {0x2,0x6,0x2,0x2,0x2,0x7},  /* 1 */
    {0x6,0x9,0x2,0x4,0x8,0xF},  /* 2 */
    {0x6,0x9,0x2,0x1,0x9,0x6},  /* 3 */
    {0x9,0x9,0xF,0x1,0x1,0x1},  /* 4 */
    {0xF,0x8,0xE,0x1,0x9,0x6},  /* 5 */
    {0x6,0x8,0xE,0x9,0x9,0x6},  /* 6 */
    {0xF,0x1,0x2,0x4,0x4,0x4},  /* 7 */
    {0x6,0x9,0x6,0x9,0x9,0x6},  /* 8 */
    {0x6,0x9,0x7,0x1,0x1,0x6},  /* 9 */
};

/* ---- 4×6 bitmap font (letters A-Z) ---- */
static const unsigned char letter_font[26][6] = {
    {0x6,0x9,0xF,0x9,0x9,0x9},  /* A */
    {0xE,0x9,0xE,0x9,0x9,0xE},  /* B */
    {0x6,0x9,0x8,0x8,0x9,0x6},  /* C */
    {0xE,0x9,0x9,0x9,0x9,0xE},  /* D */
    {0xF,0x8,0xE,0x8,0x8,0xF},  /* E */
    {0xF,0x8,0xE,0x8,0x8,0x8},  /* F */
    {0x6,0x8,0xB,0x9,0x9,0x6},  /* G */
    {0x9,0x9,0xF,0x9,0x9,0x9},  /* H */
    {0x7,0x2,0x2,0x2,0x2,0x7},  /* I */
    {0x1,0x1,0x1,0x1,0x9,0x6},  /* J */
    {0x9,0xA,0xC,0xA,0x9,0x9},  /* K */
    {0x8,0x8,0x8,0x8,0x8,0xF},  /* L */
    {0x9,0xF,0xF,0x9,0x9,0x9},  /* M */
    {0x9,0xD,0xB,0x9,0x9,0x9},  /* N */
    {0x6,0x9,0x9,0x9,0x9,0x6},  /* O */
    {0xE,0x9,0xE,0x8,0x8,0x8},  /* P */
    {0x6,0x9,0x9,0xB,0x9,0x6},  /* Q */
    {0xE,0x9,0xE,0xA,0x9,0x9},  /* R */
    {0x7,0x8,0x6,0x1,0x1,0xE},  /* S */
    {0x7,0x2,0x2,0x2,0x2,0x2},  /* T */
    {0x9,0x9,0x9,0x9,0x9,0x6},  /* U */
    {0x9,0x9,0x9,0x9,0x6,0x6},  /* V */
    {0x9,0x9,0x9,0xF,0xF,0x9},  /* W */
    {0x9,0x9,0x6,0x6,0x9,0x9},  /* X */
    {0x9,0x9,0x6,0x2,0x2,0x2},  /* Y */
    {0xF,0x1,0x2,0x4,0x8,0xF},  /* Z */
};

static int hud_initialized = 0;

/* Palette indices — chosen from the generated cyberpunk palette */
static unsigned char col_cyan     = 96;
static unsigned char col_green    = 80;
static unsigned char col_red      = 32;
static unsigned char col_yellow   = 64;
static unsigned char col_white    = 254;
static unsigned char col_darkgray = 8;
static unsigned char col_magenta  = 128;

void hud_init(void) {
    hud_initialized = 1;
}

/* ---- drawing primitives ---- */

static inline void put_pixel(unsigned char *buf, int pitch, int w, int h,
                              int x, int y, unsigned char color) {
    if (x >= 0 && x < w && y >= 0 && y < h)
        buf[y * pitch + x] = color;
}

static void fill_rect(unsigned char *buf, int pitch, int w, int h,
                       int x, int y, int rw, int rh, unsigned char color) {
    for (int dy = 0; dy < rh; dy++)
        for (int dx = 0; dx < rw; dx++)
            put_pixel(buf, pitch, w, h, x + dx, y + dy, color);
}

static void hline(unsigned char *buf, int pitch, int w, int h,
                   int x1, int x2, int y, unsigned char color) {
    for (int x = x1; x <= x2; x++)
        put_pixel(buf, pitch, w, h, x, y, color);
}

/* ---- glyph rendering ---- */

static void draw_digit(unsigned char *buf, int pitch, int w, int h,
                        int x, int y, int digit, unsigned char color, int scale) {
    if (digit < 0 || digit > 9) return;
    for (int row = 0; row < 6; row++) {
        unsigned char bits = digit_font[digit][row];
        for (int col = 0; col < 4; col++) {
            if (bits & (0x8 >> col))
                fill_rect(buf, pitch, w, h,
                          x + col * scale, y + row * scale, scale, scale, color);
        }
    }
}

static void draw_number(unsigned char *buf, int pitch, int w, int h,
                         int x, int y, int num, unsigned char color, int scale) {
    if (num < 0) num = 0;
    char str[12];
    int len = snprintf(str, sizeof(str), "%d", num);
    int char_w = 5 * scale;  /* 4 pixel glyph + 1 pixel gap */
    int start_x = x - len * char_w;
    for (int i = 0; i < len; i++)
        draw_digit(buf, pitch, w, h, start_x + i * char_w, y,
                   str[i] - '0', color, scale);
}

static void draw_letter(unsigned char *buf, int pitch, int w, int h,
                         int x, int y, char ch, unsigned char color, int scale) {
    int idx = -1;
    if (ch >= 'A' && ch <= 'Z') idx = ch - 'A';
    else if (ch >= 'a' && ch <= 'z') idx = ch - 'a';
    if (idx < 0) return;
    for (int row = 0; row < 6; row++) {
        unsigned char bits = letter_font[idx][row];
        for (int col = 0; col < 4; col++) {
            if (bits & (0x8 >> col))
                fill_rect(buf, pitch, w, h,
                          x + col * scale, y + row * scale, scale, scale, color);
        }
    }
}

static void draw_string(unsigned char *buf, int pitch, int w, int h,
                         int x, int y, const char *str, unsigned char color,
                         int scale) {
    int char_w = 5 * scale;
    for (int i = 0; str[i]; i++) {
        if (str[i] == ' ') { x += char_w; continue; }
        draw_letter(buf, pitch, w, h, x, y, str[i], color, scale);
        x += char_w;
    }
}

/* ---- crosshair ---- */

static void draw_crosshair(unsigned char *buf, int pitch, int w, int h) {
    int cx = w / 2, cy = h / 2;
    int size = 4;
    for (int i = -size; i <= size; i++) {
        if (i == 0) continue;
        put_pixel(buf, pitch, w, h, cx + i, cy, col_cyan);
    }
    for (int i = -size; i <= size; i++) {
        if (i == 0) continue;
        put_pixel(buf, pitch, w, h, cx, cy + i, col_cyan);
    }
    put_pixel(buf, pitch, w, h, cx, cy, col_white);
}

/* ---- public API ---- */

void hud_draw(unsigned char *framebuf, int pitch, int width, int height,
              int health, int ammo, int armor, int current_weapon) {
    if (!hud_initialized || !framebuf) return;
    (void)current_weapon;  /* reserved for future weapon icon */

    int scale  = (width >= 640) ? 2 : 1;
    int bar_h  = 12 * scale;
    int margin = 4 * scale;
    int y_base = height - bar_h - margin;

    /* Dark bar background at screen bottom */
    fill_rect(framebuf, pitch, width, height,
              0, y_base - margin, width, bar_h + margin * 2, col_darkgray);

    /* Cyan accent lines */
    hline(framebuf, pitch, width, height,
          0, width - 1, y_base - margin, col_cyan);
    hline(framebuf, pitch, width, height,
          0, width - 1, y_base + bar_h + margin - 1, col_cyan);

    /* HEALTH — left side */
    unsigned char hp_color = (health > 30) ? col_green : col_red;
    draw_string(framebuf, pitch, width, height,
                margin, y_base, "HP", col_cyan, scale);
    draw_number(framebuf, pitch, width, height,
                margin + 18 * scale, y_base, health, hp_color, scale);

    /* Health bar */
    int bar_x = margin + 20 * scale;
    int bar_w = health * scale;
    if (bar_w > 100 * scale) bar_w = 100 * scale;
    if (bar_w < 0) bar_w = 0;
    fill_rect(framebuf, pitch, width, height,
              bar_x, y_base + 7 * scale, bar_w, 3 * scale, hp_color);

    /* ARMOR — left-center */
    int armor_x = margin + 130 * scale;
    draw_string(framebuf, pitch, width, height,
                armor_x, y_base, "AR", col_magenta, scale);
    draw_number(framebuf, pitch, width, height,
                armor_x + 18 * scale, y_base, armor, col_magenta, scale);

    /* AMMO — right side */
    int ammo_x = width - margin - 60 * scale;
    draw_string(framebuf, pitch, width, height,
                ammo_x, y_base, "AMMO", col_yellow, scale);
    draw_number(framebuf, pitch, width, height,
                width - margin, y_base, ammo, col_yellow, scale);

    /* Crosshair in screen center */
    draw_crosshair(framebuf, pitch, width, height);
}
