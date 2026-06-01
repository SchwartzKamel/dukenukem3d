// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * mact_stub.c - Stub implementations for MACT library functions
 * and other missing functions from the precompiled Duke3D libraries.
 * These were originally in MACT386.LIB and the audiolib.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <ctype.h>
#include <fcntl.h>
#ifndef _MSC_VER
#include <unistd.h>
#endif
#include <sys/stat.h>
#include "compat.h"
#include "sdl_driver.h"
#include "log_stub.h"

/* ======================================================================
 * Script/Config file parsing (from MACT SCRIPLIB)
 * Minimal implementations that return default/empty values
 * ====================================================================== */

#define MAX_SCRIPTS 4
#define MAX_ENTRIES 256
#define MAX_ENTRY_LEN 256

typedef struct {
    char section[64];
    char key[64];
    char value[MAX_ENTRY_LEN];
} script_entry_t;

typedef struct {
    int active;
    script_entry_t entries[MAX_ENTRIES];
    int num_entries;
    char filename[256];
} script_t;

static script_t scripts[MAX_SCRIPTS];

static script_t *get_script(int handle) {
    if (handle < 0 || handle >= MAX_SCRIPTS) return NULL;
    if (!scripts[handle].active) return NULL;
    return &scripts[handle];
}

static script_entry_t *find_entry(script_t *sc, const char *section, const char *key) {
    int i;
    for (i = 0; i < sc->num_entries; i++) {
        if (strcasecmp(sc->entries[i].section, section) == 0 &&
            strcasecmp(sc->entries[i].key, key) == 0)
            return &sc->entries[i];
    }
    return NULL;
}

int SCRIPT_Load(char *filename) {
    FILE *f;
    char line[512], cursection[64] = "";
    int i;
    script_t *sc = NULL;

    for (i = 0; i < MAX_SCRIPTS; i++) {
        if (!scripts[i].active) { sc = &scripts[i]; sc->active = 1; break; }
    }
    if (!sc) return -1;

    sc->num_entries = 0;
    strncpy(sc->filename, filename, sizeof(sc->filename)-1);

    f = fopen(filename, "r");
    if (!f) {
        /* Release the slot we just claimed; otherwise repeated failures
         * exhaust the MAX_SCRIPTS pool (audit compat-layer-r29 P2). */
        sc->active = 0;
        return -1;
    }

    while (fgets(line, sizeof(line), f)) {
        char *p = line;
        while (*p && isspace((unsigned char)*p)) p++;
        if (*p == '[') {
            char *end = strchr(p, ']');
            if (end) { *end = 0; strncpy(cursection, p+1, 63); cursection[63] = '\0'; }
        } else if (*p && *p != ';' && *p != '#') {
            char *eq = strchr(p, '=');
            if (eq && sc->num_entries < MAX_ENTRIES) {
                script_entry_t *e = &sc->entries[sc->num_entries];
                *eq = 0;
                strncpy(e->section, cursection, 63); e->section[63] = '\0';
                /* trim key */
                { char *k = p; while (*k && isspace((unsigned char)*k)) k++;
                  char *ke = eq-1; while (ke > k && isspace((unsigned char)*ke)) *ke-- = 0;
                  strncpy(e->key, k, 63); e->key[63] = '\0'; }
                /* trim value — store raw, let accessors handle quotes */
                { char *v = eq+1; while (*v && isspace((unsigned char)*v)) v++;
                  char *ve = v + strlen(v) - 1; while (ve > v && isspace((unsigned char)*ve)) *ve-- = 0;
                  strncpy(e->value, v, MAX_ENTRY_LEN-1); e->value[MAX_ENTRY_LEN-1] = '\0'; }
                sc->num_entries++;
            }
        }
    }
    fclose(f);
    return (int)(sc - scripts);
}

void SCRIPT_Save(int handle, char *filename) {
    script_t *sc = get_script(handle);
    FILE *f;
    int i;
    char lastsection[64] = "";
    const char *savename;

    if (!sc) return;
    savename = (filename && filename[0]) ? filename : sc->filename;
    f = fopen(savename, "w");
    if (!f) return;

    for (i = 0; i < sc->num_entries; i++) {
        if (strcasecmp(sc->entries[i].section, lastsection) != 0) {
            if (i > 0) fprintf(f, "\n");
            fprintf(f, "[%s]\n", sc->entries[i].section);
            strncpy(lastsection, sc->entries[i].section, 63); lastsection[63] = '\0';
        }
        fprintf(f, "%s = \"%s\"\n", sc->entries[i].key, sc->entries[i].value);
    }
    fclose(f);
}

void SCRIPT_Free(int handle) {
    if (handle >= 0 && handle < MAX_SCRIPTS) scripts[handle].active = 0;
}

void SCRIPT_GetString(int handle, char *section, char *key, char *dest, int dest_size) {
    script_t *sc = get_script(handle);
    script_entry_t *e;
    dest[0] = 0;
    if (!sc || dest_size <= 0) return;
    e = find_entry(sc, section, key);
    if (e) {
        char *v = e->value;
        int len;
        /* strip surrounding quotes if present */
        if (*v == '"') {
            char *q;
            v++;
            q = strchr(v, '"');
            if (q) len = (int)(q - v); else len = (int)strlen(v);
        } else {
            len = (int)strlen(v);
        }
        if (len >= dest_size) len = dest_size - 1;
        memcpy(dest, v, len);
        dest[len] = '\0';
    }
}

void SCRIPT_GetDoubleString(int handle, char *section, char *key, char *dest1, int dest1_size, char *dest2, int dest2_size) {
    script_t *sc = get_script(handle);
    script_entry_t *e;
    char *v, *q;
    int len;

    dest1[0] = dest2[0] = 0;
    if (!sc) return;
    e = find_entry(sc, section, key);
    if (!e) return;
    v = e->value;

    /* Parse first quoted string: "str1" */
    while (*v && isspace((unsigned char)*v)) v++;
    if (*v == '"') {
        v++;
        q = strchr(v, '"');
        if (q) { len = (int)(q - v); if (len >= dest1_size) len = dest1_size - 1;
                 memcpy(dest1, v, len); dest1[len] = '\0'; v = q + 1; }
        else   { len = (int)strlen(v); if (len >= dest1_size) len = dest1_size - 1;
                 memcpy(dest1, v, len); dest1[len] = '\0'; return; }
    } else {
        /* unquoted single value */
        len = (int)strlen(v); if (len >= dest1_size) len = dest1_size - 1;
        memcpy(dest1, v, len); dest1[len] = '\0';
        return;
    }

    /* Skip comma/whitespace between quoted strings */
    while (*v && (*v == ',' || isspace((unsigned char)*v))) v++;

    /* Parse second quoted string: "str2" */
    if (*v == '"') {
        v++;
        q = strchr(v, '"');
        if (q) { len = (int)(q - v); } else { len = (int)strlen(v); }
        if (len >= dest2_size) len = dest2_size - 1;
        memcpy(dest2, v, len); dest2[len] = '\0';
    } else if (*v) {
        len = (int)strlen(v); if (len >= dest2_size) len = dest2_size - 1;
        memcpy(dest2, v, len); dest2[len] = '\0';
    }
}

int SCRIPT_GetNumber(int handle, char *section, char *key, int32_t *dest) {
    char buf[256];
    SCRIPT_GetString(handle, section, key, buf, sizeof(buf));
    if (buf[0]) { *dest = (int32_t)strtol(buf, NULL, 0); return 1; }
    *dest = 0;
    return 0;
}

void SCRIPT_PutNumber(int32_t handle, char *section, char *key, int32_t value,
                      int32_t hexadecimal, int32_t defaultvalue) { /* build-r16-lto-type: aligned to legacy K&R caller decl */
    script_t *sc = get_script((int)handle);
    script_entry_t *e;
    (void)hexadecimal; (void)defaultvalue;
    if (!sc) return;
    e = find_entry(sc, section, key);
    if (!e && sc->num_entries < MAX_ENTRIES) {
        e = &sc->entries[sc->num_entries++];
        strncpy(e->section, section, 63); e->section[63] = '\0';
        strncpy(e->key, key, 63); e->key[63] = '\0';
    }
    if (e) snprintf(e->value, MAX_ENTRY_LEN, "%d", (int)value);
}

void SCRIPT_PutString(int handle, char *section, char *key, char *value) {
    script_t *sc = get_script(handle);
    script_entry_t *e;
    if (!sc) return;
    e = find_entry(sc, section, key);
    if (!e && sc->num_entries < MAX_ENTRIES) {
        e = &sc->entries[sc->num_entries++];
        strncpy(e->section, section, 63); e->section[63] = '\0';
        strncpy(e->key, key, 63); e->key[63] = '\0';
    }
    if (e) { strncpy(e->value, value, MAX_ENTRY_LEN-1); e->value[MAX_ENTRY_LEN-1] = '\0'; }
}

int SCRIPT_NumberEntries(int handle, char *section) {
    script_t *sc = get_script(handle);
    int count = 0, i;
    if (!sc) return 0;
    for (i = 0; i < sc->num_entries; i++)
        if (strcasecmp(sc->entries[i].section, section) == 0) count++;
    return count;
}

char *SCRIPT_Entry(int handle, char *section, int index) {
    script_t *sc = get_script(handle);
    int count = 0, i;
    if (!sc) return "";
    for (i = 0; i < sc->num_entries; i++) {
        if (strcasecmp(sc->entries[i].section, section) == 0) {
            if (count == index) return sc->entries[i].key;
            count++;
        }
    }
    return "";
}

/* ======================================================================
 * Utility functions (from MACT util_lib)
 * ====================================================================== */

int SafeFileExists(const char *filename) {
    return (access(filename, F_OK) == 0);
}

void *SafeMalloc(int32_t size) { /* build-r16-lto-type: aligned to legacy K&R caller decl */
    void *p = malloc((size_t)size);
    if (!p) { fprintf(stderr, "SafeMalloc: out of memory (%d bytes)\n", (int)size); exit(1); }
    return p;
}

void *SafeRealloc(void **ptr, int32_t newsize) { /* build-r16-lto-type: aligned to legacy K&R caller decl */
    void *p = realloc(*ptr, (size_t)newsize);
    if (!p) { fprintf(stderr, "SafeRealloc: out of memory\n"); exit(1); }
    *ptr = p;
    return p;
}

void SafeFree(void *ptr) {
    if (ptr) free(ptr);
}

int32_t SafeOpenRead(const char *filename, int32_t filetype) { /* build-r16-lto-type: aligned to legacy K&R caller decl */
    int fd = open(filename, O_RDONLY);
    if (fd < 0) { fprintf(stderr, "SafeOpenRead: can't open %s\n", filename); }
    (void)filetype;
    return (int32_t)fd;
}

void SafeRead(int32_t handle, void *buffer, int32_t count) { /* build-r16-lto-type: aligned to legacy K&R caller decl */
    ssize_t n = read((int)handle, buffer, (size_t)count);
    if (n < 0) {
        fprintf(stderr, "SafeRead: read error\n");
    } else if (n < (ssize_t)count) {
        fprintf(stderr, "SafeRead: short read (%zd of %d bytes)\n", n, (int)count);
    }
}

void Error(char *fmt, ...) {
    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    fprintf(stderr, "%s\n", buf);
    if (_startup_log) {
        fprintf(_startup_log, "ERROR: %s\n", buf);
        fflush(_startup_log);
    }
#ifdef _WIN32
    MessageBoxA(NULL, buf, "Atomic Shell - Error", MB_OK | MB_ICONERROR);
#endif
    exit(1);
}

char CheckParm(char *check) { /* build-r16-lto-type: aligned to legacy K&R caller decl */
    /* Check command line parameters - stub returns 0 (not found) */
    (void)check;
    return 0;
}

int32_t Z_AvailHeap(void) { /* build-r16-lto-type: aligned to legacy K&R caller decl */
    return 16 * 1024 * 1024; /* Report 16MB available */
}

void RegisterShutdownFunction(void (*func)(void)) {
    atexit(func);
}

void Shutdown(void) {
    /* Cleanup stub */
}

/* ======================================================================
 * Additional engine/game functions that may be missing
 * ====================================================================== */

/* These are called from GAME.C but defined in engine - provide weak stubs
   that get overridden by the real engine implementations */

void Music_SetVolume(int volume) { STUB_LOG("Music_SetVolume(%d)", volume); (void)volume; }
void PlayMusic(char *fn) { STUB_LOG("PlayMusic(%s)", fn ? fn : "<NULL>"); (void)fn; }

/* IntelLong: Convert from little-endian file format to native byte order.
   Currently a no-op since all supported build targets (Linux x86, Windows x86)
   are little-endian. On big-endian systems, this would need byte-swapping.
   WAD file format uses little-endian for multi-byte integers (DooM/Duke3D spec). */
int32_t IntelLong(int32_t val) { /* build-r16-lto-type: aligned to legacy K&R caller decl */
    return val;
}

/* Mouse functions - forward to SDL driver */
void setupmouse(void) { /* handled by SDL init */ }
void readmousexy(short *x, short *y) {
    int dx = 0, dy = 0, btn = 0;
    sdl_getmouse(&dx, &dy, &btn);
    *x = (short)dx;
    *y = (short)dy;
}
void readmousebstatus(short *bstatus) {
    int dx = 0, dy = 0, btn = 0;
    sdl_getmouse(&dx, &dy, &btn);
    *bstatus = (short)btn;
}

int32_t MOUSE_GetButtons(void) { /* build-r16-lto-type: aligned to legacy K&R caller decl */
    int dx = 0, dy = 0, btn = 0;
    sdl_getmouse(&dx, &dy, &btn);
    return (int32_t)btn;
}

/* Timer stubs if not already defined */
void inittimer1mhz(void) { }
void uninittimer1mhz(void) { }
int32_t gettime1mhz(void) { return sdl_getticks() * 1000; }
int32_t deltatime1mhz(void) { return 0; }
int32_t readtimer(void) { return sdl_getticks(); }

/* Callback stub */
void testcallback(unsigned long val) { (void)val; }

/* Print char ASM stub */
void printchrasm(long offset, long col, long ch) {
    (void)offset; (void)col; (void)ch;
}

/* VBE_setPalette - called from some game files */
int32_t VBE_setPalette(int32_t start, int32_t num, char *dapal) { /* build-r16-lto-type: aligned to legacy K&R caller decl */
    sdl_setpalette((unsigned char *)dapal, (int)start, (int)num);
    return 1;
}

/* divscale generic (variable shift) */
int32_t divscale(int32_t a, int32_t b, int32_t c) { /* build-r16-lto-type: aligned to legacy K&R caller decl */
    return (int32_t)(((int64_t)a << c) / b);
}

/* FindDistance2D/3D */
int32_t FindDistance2D(int32_t x, int32_t y) { /* build-r16-lto-type: aligned to legacy K&R caller decl */
    int32_t t;
    x = labs((int)x);
    y = labs((int)y);
    if (x < y) { t = x; x = y; y = t; }
    t = y + (y >> 1);
    return x - (x >> 5) - (x >> 7) + (t >> 2) + (t >> 6);
}

int32_t FindDistance3D(int32_t x, int32_t y, int32_t z) { /* build-r16-lto-type: aligned to legacy K&R caller decl */
    int32_t t;
    x = labs((int)x);
    y = labs((int)y);
    z = labs((int)z);
    if (x < y) { t = x; x = y; y = t; }
    if (x < z) { t = x; x = z; z = t; }
    t = y + z;
    return x - (x >> 4) + (t >> 2) + (t >> 3);
}

/* vgacompatible flag */
char vgacompatible = 0;
