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
    if (!f) return (int)(sc - scripts);

    while (fgets(line, sizeof(line), f)) {
        char *p = line;
        while (*p && isspace((unsigned char)*p)) p++;
        if (*p == '[') {
            char *end = strchr(p, ']');
            if (end) { *end = 0; strncpy(cursection, p+1, 63); }
        } else if (*p && *p != ';' && *p != '#') {
            char *eq = strchr(p, '=');
            if (eq && sc->num_entries < MAX_ENTRIES) {
                script_entry_t *e = &sc->entries[sc->num_entries];
                *eq = 0;
                strncpy(e->section, cursection, 63);
                /* trim key */
                { char *k = p; while (*k && isspace((unsigned char)*k)) k++;
                  char *ke = eq-1; while (ke > k && isspace((unsigned char)*ke)) *ke-- = 0;
                  strncpy(e->key, k, 63); }
                /* trim value */
                { char *v = eq+1; while (*v && isspace((unsigned char)*v)) v++;
                  char *ve = v + strlen(v) - 1; while (ve > v && isspace((unsigned char)*ve)) *ve-- = 0;
                  /* strip quotes */
                  if (*v == '"') { v++; char *q = strchr(v, '"'); if (q) *q = 0; }
                  strncpy(e->value, v, MAX_ENTRY_LEN-1); }
                sc->num_entries++;
            }
        }
    }
    fclose(f);
    return (int)(sc - scripts);
}

void SCRIPT_Save(int handle) {
    script_t *sc = get_script(handle);
    FILE *f;
    int i;
    char lastsection[64] = "";

    if (!sc) return;
    f = fopen(sc->filename, "w");
    if (!f) return;

    for (i = 0; i < sc->num_entries; i++) {
        if (strcasecmp(sc->entries[i].section, lastsection) != 0) {
            if (i > 0) fprintf(f, "\n");
            fprintf(f, "[%s]\n", sc->entries[i].section);
            strncpy(lastsection, sc->entries[i].section, 63);
        }
        fprintf(f, "%s = \"%s\"\n", sc->entries[i].key, sc->entries[i].value);
    }
    fclose(f);
}

void SCRIPT_Free(int handle) {
    if (handle >= 0 && handle < MAX_SCRIPTS) scripts[handle].active = 0;
}

void SCRIPT_GetString(int handle, char *section, char *key, char *dest) {
    script_t *sc = get_script(handle);
    script_entry_t *e;
    dest[0] = 0;
    if (!sc) return;
    e = find_entry(sc, section, key);
    if (e) { strncpy(dest, e->value, 127); dest[127] = '\0'; }
}

void SCRIPT_GetDoubleString(int handle, char *section, char *key, char *dest1, char *dest2) {
    char buf[512];
    char *space;
    SCRIPT_GetString(handle, section, key, buf);
    dest1[0] = dest2[0] = 0;
    space = strchr(buf, ' ');
    if (space) {
        *space = 0;
        strncpy(dest1, buf, 79); dest1[79] = '\0';
        strncpy(dest2, space+1, 79); dest2[79] = '\0';
    } else {
        strncpy(dest1, buf, 79); dest1[79] = '\0';
    }
}

int SCRIPT_GetNumber(int handle, char *section, char *key, int32_t *dest) {
    char buf[256];
    SCRIPT_GetString(handle, section, key, buf);
    if (buf[0]) { *dest = (int32_t)atol(buf); return 1; }
    *dest = 0;
    return 0;
}

void SCRIPT_PutNumber(int handle, char *section, char *key, long value,
                      int hexadecimal, int defaultvalue) {
    script_t *sc = get_script(handle);
    script_entry_t *e;
    (void)hexadecimal; (void)defaultvalue;
    if (!sc) return;
    e = find_entry(sc, section, key);
    if (!e && sc->num_entries < MAX_ENTRIES) {
        e = &sc->entries[sc->num_entries++];
        strncpy(e->section, section, 63);
        strncpy(e->key, key, 63);
    }
    if (e) snprintf(e->value, MAX_ENTRY_LEN, "%ld", value);
}

void SCRIPT_PutString(int handle, char *section, char *key, char *value) {
    script_t *sc = get_script(handle);
    script_entry_t *e;
    if (!sc) return;
    e = find_entry(sc, section, key);
    if (!e && sc->num_entries < MAX_ENTRIES) {
        e = &sc->entries[sc->num_entries++];
        strncpy(e->section, section, 63);
        strncpy(e->key, key, 63);
    }
    if (e) strncpy(e->value, value, MAX_ENTRY_LEN-1);
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

void *SafeMalloc(long size) {
    void *p = malloc((size_t)size);
    if (!p) { fprintf(stderr, "SafeMalloc: out of memory (%ld bytes)\n", size); exit(1); }
    return p;
}

void *SafeRealloc(void *ptr, long size) {
    void *p = realloc(ptr, (size_t)size);
    if (!p) { fprintf(stderr, "SafeRealloc: out of memory\n"); exit(1); }
    return p;
}

void SafeFree(void *ptr) {
    if (ptr) free(ptr);
}

long SafeOpenRead(const char *filename) {
    int fd = open(filename, O_RDONLY);
    if (fd < 0) { fprintf(stderr, "SafeOpenRead: can't open %s\n", filename); }
    return (long)fd;
}

void SafeRead(long handle, void *buf, long count) {
    read((int)handle, buf, (size_t)count);
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
    MessageBoxA(NULL, buf, "Duke Nukem 3D - Error", MB_OK | MB_ICONERROR);
#endif
    exit(1);
}

int CheckParm(char *check) {
    /* Check command line parameters - stub returns -1 (not found) */
    (void)check;
    return -1;
}

long Z_AvailHeap(void) {
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

void Music_SetVolume(int volume) { (void)volume; }
void PlayMusic(char *fn) { (void)fn; }

/* IntelLong: byte-swap for big-endian. On little-endian (x86), no-op */
long IntelLong(long val) { return val; }

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

long MOUSE_GetButtons(void) {
    int dx = 0, dy = 0, btn = 0;
    sdl_getmouse(&dx, &dy, &btn);
    return (long)btn;
}

/* Timer stubs if not already defined */
void inittimer1mhz(void) { }
void uninittimer1mhz(void) { }
long gettime1mhz(void) { return sdl_getticks() * 1000; }
long deltatime1mhz(void) { return 0; }
long readtimer(void) { return sdl_getticks(); }

/* Callback stub */
void testcallback(unsigned long val) { (void)val; }

/* Print char ASM stub */
void printchrasm(long offset, long col, long ch) {
    (void)offset; (void)col; (void)ch;
}

/* VBE_setPalette - called from some game files */
long VBE_setPalette(long start, long num, char *dapal) {
    sdl_setpalette((unsigned char *)dapal, (int)start, (int)num);
    return 1;
}

/* divscale generic (variable shift) */
long divscale(long a, long b, long c) {
    return (long)(((int64_t)a << c) / b);
}

/* FindDistance2D/3D */
long FindDistance2D(long x, long y) {
    long t;
    x = labs(x);
    y = labs(y);
    if (x < y) { t = x; x = y; y = t; }
    t = y + (y >> 1);
    return x - (x >> 5) - (x >> 7) + (t >> 2) + (t >> 6);
}

long FindDistance3D(long x, long y, long z) {
    long t;
    x = labs(x);
    y = labs(y);
    z = labs(z);
    if (x < y) { t = x; x = y; y = t; }
    if (x < z) { t = x; x = z; z = t; }
    t = y + z;
    return x - (x >> 4) + (t >> 2) + (t >> 3);
}

/* vgacompatible flag */
char vgacompatible = 0;
