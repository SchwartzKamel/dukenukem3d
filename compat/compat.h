/*
 * compat.h - Master compatibility header for Duke Nukem 3D
 *
 * Replaces all DOS/Watcom-specific includes for GCC/Linux + MinGW/Windows SDL2 builds.
 * Include this instead of dos.h, conio.h, io.h, i86.h, bios.h, etc.
 */

#ifndef COMPAT_H_
#define COMPAT_H_
#pragma once

/* ======================================================================
 * MSVC compatibility
 *
 * MSVC lacks some GCC/POSIX features used throughout. Map them here
 * before any other headers are included.
 * ====================================================================== */

#ifdef _MSC_VER
  /* GCC attributes are not supported */
  #ifndef __attribute__
  #define __attribute__(x)
  #endif

  /* MSVC uses __restrict instead of __restrict__ */
  #define __restrict__ __restrict

  /* POSIX access() → MSVC _access() */
  #include <io.h>
  #define access _access
  #ifndef R_OK
  #define R_OK 4
  #endif

  /* Suppress deprecation warnings for POSIX names */
  #pragma warning(disable: 4996)
#endif

/* ======================================================================
 * Standard headers that replace DOS equivalents
 * ====================================================================== */

/* POSIX feature test macros - must precede all system includes */
#ifndef _WIN32
#define _GNU_SOURCE      /* FNM_CASEFOLD, etc. on glibc */
#define _DEFAULT_SOURCE  /* usleep, etc. on glibc >= 2.19 */
#define _BSD_SOURCE      /* usleep on older glibc */
#endif

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <ctype.h>
#include <signal.h>
#include <fcntl.h>      /* open, O_RDONLY, etc. */
#include <sys/types.h>  /* replaces sys\types.h */
#include <sys/stat.h>   /* replaces sys\stat.h */

#ifdef _WIN32
  #include <windows.h>
  #include <direct.h>   /* _mkdir, _getcwd */
  #include <io.h>       /* filelength, tell, _findfirst, etc. */
#else
  #include <strings.h>  /* strcasecmp */
  #include <unistd.h>   /* read, write, close, lseek, usleep */
#endif

/* ======================================================================
 * Watcom compiler keyword stubs
 * ====================================================================== */

/* #pragma aux is handled by -include or by wrapping; these keywords
   must become no-ops in GCC. */
#define __interrupt
#define __far
#define __pascal
#ifndef _WIN32
#define __cdecl
#endif
#define __near
#define __loadds
#define __saveregs
#define _fmemcpy  memcpy
#define _fmemset  memset
#define _fmalloc  malloc
#define _ffree    free

/* Watcom's "cdecl" without underscores sometimes appears */
#ifndef cdecl
#define cdecl
#endif

/* ======================================================================
 * O_BINARY - DOS distinguishes binary/text; POSIX does not
 * ====================================================================== */

#ifndef O_BINARY
#define O_BINARY 0
#endif

#ifndef O_TEXT
#define O_TEXT 0
#endif

/* SH_DENYNO and SH_COMPAT from share.h (used with sopen) */
#ifndef SH_DENYNO
#define SH_DENYNO 0
#endif

#ifndef SH_COMPAT
#define SH_COMPAT 0
#endif

/* ======================================================================
 * POSIX file I/O helpers that DOS had but POSIX lacks/names differently
 * ====================================================================== */

/* filelength(fd) and tell(fd) - available natively on Windows via <io.h> */
#ifndef _WIN32
static inline long filelength(int fd)
{
    struct stat st;
    if (fstat(fd, &st) == -1) return -1L;
    return (long)st.st_size;
}

static inline long tell(int fd)
{
    return (long)lseek(fd, 0, SEEK_CUR);
}
#endif /* !_WIN32 */

/* Watcom's sopen() - just map to open(), ignoring share flags */
#define sopen(path, oflag, shflag, ...)  open((path), (oflag), ##__VA_ARGS__)

/* ======================================================================
 * String function mappings
 * ====================================================================== */

/* stricmp, strcmpi, strnicmp - native on Windows, map to POSIX on Linux */
#ifndef _WIN32
  #ifndef stricmp
  #define stricmp  strcasecmp
  #endif
  #ifndef strcmpi
  #define strcmpi  strcasecmp
  #endif
  #ifndef strnicmp
  #define strnicmp strncasecmp
  #endif
#endif /* !_WIN32 */

/* strlwr/strupr/itoa/ltoa — provided by MinGW on Windows, need polyfills on POSIX */
#ifndef _WIN32
static inline char *strlwr(char *s)
{
    char *p = s;
    while (*p) { *p = tolower((unsigned char)*p); p++; }
    return s;
}

static inline char *strupr(char *s)
{
    char *p = s;
    while (*p) { *p = toupper((unsigned char)*p); p++; }
    return s;
}

static inline char *itoa(int val, char *buf, int radix)
{
    if (radix == 10) { snprintf(buf, 33, "%d", val); return buf; }
    if (radix == 16) { snprintf(buf, 33, "%x", val); return buf; }
    if (radix == 8)  { snprintf(buf, 33, "%o", val); return buf; }
    snprintf(buf, 33, "%d", val);
    return buf;
}

static inline char *ltoa(long val, char *buf, int radix)
{
    if (radix == 10) { snprintf(buf, 33, "%ld", val); return buf; }
    if (radix == 16) { snprintf(buf, 33, "%lx", val); return buf; }
    if (radix == 8)  { snprintf(buf, 33, "%lo", val); return buf; }
    snprintf(buf, 33, "%ld", val);
    return buf;
}
#endif /* !_WIN32 */

/* ======================================================================
 * min / max macros (DOS compilers often provided these)
 * ====================================================================== */

#ifndef min
#define min(a, b) (((a) < (b)) ? (a) : (b))
#endif

#ifndef max
#define max(a, b) (((a) > (b)) ? (a) : (b))
#endif

/* ======================================================================
 * Console I/O stubs (from conio.h)
 *
 * These will be replaced by SDL event handling at runtime;
 * the stubs prevent link errors during the porting process.
 * ====================================================================== */

/* kbhit() - returns nonzero if a key is waiting (SDL replaces this) */
static inline int kbhit(void) { return 0; }

/* getch() - blocking read of one character (SDL replaces this) */
static inline int getch(void) { return 0; }

/* getche() - getch with echo */
static inline int getche(void) { return 0; }

/* putch() - write one character to console */
static inline int putch(int c) { return putchar(c); }

/* cputs() - write a string to console */
static inline int cputs(const char *s) { return fputs(s, stdout); }

/* cprintf - console printf (just use printf) */
#define cprintf printf

/* inp / outp - x86 port I/O (no-ops on modern Linux userspace)
   On Windows, these are declared in intrin.h (via SDL2), so skip them. */
#ifndef _WIN32
static inline unsigned char inp(unsigned short port)
{
    (void)port;
    return 0;
}

static inline unsigned short inpw(unsigned short port)
{
    (void)port;
    return 0;
}

static inline void outp(unsigned short port, unsigned char val)
{
    (void)port; (void)val;
}

static inline void outpw(unsigned short port, unsigned short val)
{
    (void)port; (void)val;
}
#endif

/* ======================================================================
 * DOS interrupt stubs (from dos.h / i86.h)
 *
 * The original code calls BIOS/DOS via int386().
 * These structs/functions are no-ops — real functionality comes from SDL.
 * ====================================================================== */

/* Register unions used by int386() / int386x() */
struct WORDREGS {
    unsigned short ax, bx, cx, dx, si, di, cflag;
};

struct BYTEREGS {
    unsigned char al, ah, bl, bh, cl, ch, dl, dh;
};

union REGS {
    struct WORDREGS w;
    struct BYTEREGS h;
    struct {
        unsigned long eax, ebx, ecx, edx, esi, edi, cflag;
    } x;
};

struct SREGS {
    unsigned short cs, ds, es, fs, gs, ss;
};

static inline int int386(int intno, union REGS *in, union REGS *out)
{
    (void)intno;
    if (out != in) memcpy(out, in, sizeof(union REGS));
    memset(out, 0, sizeof(union REGS));
    return 0;
}

static inline int int386x(int intno, union REGS *in, union REGS *out, struct SREGS *seg)
{
    (void)intno; (void)seg;
    if (out != in) memcpy(out, in, sizeof(union REGS));
    memset(out, 0, sizeof(union REGS));
    return 0;
}

/* int86 - 16-bit variant sometimes used */
static inline int int86(int intno, union REGS *in, union REGS *out)
{
    return int386(intno, in, out);
}

static inline void segread(struct SREGS *seg)
{
    memset(seg, 0, sizeof(struct SREGS));
}

/* DOS far pointer macros (meaningless in flat-memory model) */
#define FP_OFF(p)   ((unsigned)(uintptr_t)(p))
#define FP_SEG(p)   (0)
#define MK_FP(s, o) ((void *)(uintptr_t)(o))

/* Underscore-prefixed aliases (some Watcom code uses both forms) */
#define _REGS REGS
#define _SREGS SREGS

/* dos_getvect / dos_setvect - interrupt vector manipulation */
#define _dos_getvect(n)       ((void(*)(void))0)
#define _dos_setvect(n, h)    ((void)0)
#define _chain_intr(h)        ((void)0)

/* ======================================================================
 * BIOS stubs (from bios.h)
 * ====================================================================== */

#define _KEYBRD_READ       0
#define _KEYBRD_READY      1
#define _NKEYBRD_READ      0x10
#define _NKEYBRD_READY     0x11

static inline unsigned short _bios_keybrd(unsigned cmd)
{
    (void)cmd;
    return 0;
}

/* ======================================================================
 * Memory allocation stubs
 *
 * DOS had near/far/huge heap variants; Linux has a flat address space.
 * ====================================================================== */

#define farmalloc(n)    malloc(n)
#define farfree(p)      free(p)
#define farcalloc(n, s) calloc((n), (s))
#define halloc(n, s)    calloc((n), (s))
#define hfree(p)        free(p)

/* Watcom's _nmalloc / _nfree (near heap) */
#define _nmalloc(n) malloc(n)
#define _nfree(p)   free(p)

/* ======================================================================
 * Misc DOS functions
 * ====================================================================== */

/* delay(ms) - sleep for N milliseconds */
#ifdef _WIN32
static inline void delay(unsigned int ms)
{
    Sleep(ms);
}
#else
static inline void delay(unsigned int ms)
{
    usleep((unsigned int)ms * 1000u);
}
#endif

/* ======================================================================
 * DOS directory search stubs (find_t, _dos_findfirst, _dos_findnext)
 * ====================================================================== */

/* DOS file attribute bits */
#ifndef _A_NORMAL
#define _A_NORMAL  0x00
#define _A_RDONLY  0x01
#define _A_HIDDEN  0x02
#define _A_SYSTEM  0x04
#define _A_VOLID   0x08
#define _A_SUBDIR  0x10
#define _A_ARCH    0x20
#endif

#ifdef _WIN32
/* Windows: use _findfirst/_findnext from <io.h> */

struct find_t {
    char           reserved[21];
    char           attrib;
    unsigned short wr_time;
    unsigned short wr_date;
    unsigned long  size;
    char           name[256];
    intptr_t       _handle;
};

static inline int _dos_findnext(struct find_t *f)
{
    struct _finddata_t fd;
    if (f->_handle == -1) return 1;
    if (_findnext(f->_handle, &fd) != 0) {
        _findclose(f->_handle);
        f->_handle = -1;
        return 1;
    }
    strncpy(f->name, fd.name, sizeof(f->name)-1);
    f->name[sizeof(f->name)-1] = 0;
    f->size = fd.size;
    f->attrib = (fd.attrib & _A_SUBDIR) ? _A_SUBDIR : _A_NORMAL;
    return 0;
}

static inline int _dos_findfirst(const char *path, unsigned attr, struct find_t *f)
{
    struct _finddata_t fd;
    (void)attr;
    f->_handle = _findfirst(path, &fd);
    if (f->_handle == -1) return 1;
    strncpy(f->name, fd.name, sizeof(f->name)-1);
    f->name[sizeof(f->name)-1] = 0;
    f->size = fd.size;
    f->attrib = (fd.attrib & _A_SUBDIR) ? _A_SUBDIR : _A_NORMAL;
    return 0;
}

#else
/* POSIX: use dirent + fnmatch */
#include <dirent.h>
#include <fnmatch.h>

#ifndef FNM_CASEFOLD
#define FNM_CASEFOLD 0
#endif

struct find_t {
    char           reserved[21];
    char           attrib;
    unsigned short wr_time;
    unsigned short wr_date;
    unsigned long  size;
    char           name[256];
    /* internal: POSIX directory state */
    DIR           *_dir;
    char           _pattern[256];
    char           _path[256];
};

static inline int _dos_findnext(struct find_t *f)
{
    struct dirent *de;
    struct stat st;
    char fullpath[512];
    if (!f->_dir) return 1;
    while ((de = readdir(f->_dir)) != NULL) {
        if (fnmatch(f->_pattern, de->d_name, FNM_CASEFOLD) == 0) {
            strncpy(f->name, de->d_name, sizeof(f->name)-1);
            snprintf(fullpath, sizeof(fullpath), "%s/%s", f->_path, de->d_name);
            if (stat(fullpath, &st) == 0) {
                f->size = st.st_size;
                f->attrib = S_ISDIR(st.st_mode) ? _A_SUBDIR : _A_NORMAL;
            }
            return 0;
        }
    }
    closedir(f->_dir);
    f->_dir = NULL;
    return 1;
}

static inline int _dos_findfirst(const char *path, unsigned attr, struct find_t *f)
{
    char dirpart[256], *slash;
    (void)attr;
    strncpy(dirpart, path, sizeof(dirpart)-1);
    dirpart[sizeof(dirpart)-1] = 0;
    slash = strrchr(dirpart, '/');
    if (!slash) slash = strrchr(dirpart, '\\');
    if (slash) {
        strncpy(f->_pattern, slash+1, sizeof(f->_pattern)-1);
        *slash = 0;
        strncpy(f->_path, dirpart, sizeof(f->_path)-1);
    } else {
        strncpy(f->_pattern, path, sizeof(f->_pattern)-1);
        strcpy(f->_path, ".");
    }
    f->_dir = opendir(f->_path);
    if (!f->_dir) return 1;
    return _dos_findnext(f);
}
#endif /* _WIN32 */

/* clock tick / timing */
#define CLOCKS_PER_SEC_DOS 18.2

/* getenv is already POSIX - no mapping needed */

/* ======================================================================
 * Path separator handling
 * ====================================================================== */

#ifdef _WIN32
  #define PATH_SEP_CHAR '\\'
  #define PATH_SEP_STR "\\"
  /* mkdir on Windows: _mkdir takes one argument */
  #define mkdir(path, mode) _mkdir(path)
#else
  #ifndef PATH_SEP_CHAR
  #define PATH_SEP_CHAR '/'
  #endif
  #ifndef PATH_SEP_STR
  #define PATH_SEP_STR "/"
  #endif
#endif

/* ======================================================================
 * Suppress Watcom #pragma directives
 *
 * GCC ignores unknown #pragma, so most Watcom pragmas produce warnings
 * at worst. For "#pragma aux", we rely on pragmas_gcc.h replacing the
 * entire PRAGMAS.H. For others:
 * ====================================================================== */

/* #pragma off (unreferenced) - Watcom warning control */
/* #pragma on  (unreferenced) */
/* These are silently ignored by GCC. */

/* ======================================================================
 * Forward declarations for SDL-based driver functions
 *
 * These replace the VESA/VGA/DOS driver layer. Implemented in the
 * SDL video/input/audio driver files.
 * ====================================================================== */

/* Video (replaces VESA/VGA) */
extern void sdl_video_init(int xres, int yres);
extern void sdl_video_shutdown(void);
extern void sdl_video_setpalette(unsigned char *pal, int numcols);
extern void sdl_video_flip(void *framebuffer);
extern void sdl_video_setmode(int mode);
extern int  sdl_video_checkmode(int *x, int *y, int *bpp);

/* Input (replaces keyboard ISR + mouse driver) */
extern void sdl_input_init(void);
extern void sdl_input_shutdown(void);
extern void sdl_input_poll(void);
extern int  sdl_input_getkeystate(int scancode);

/* Audio (replaces Sound Blaster / GUS direct hardware) */
extern void sdl_audio_init(int rate, int channels, int bufsize);
extern void sdl_audio_shutdown(void);

/* Timer (replaces PIT 8254 programming) */
extern void sdl_timer_init(void);
extern void sdl_timer_shutdown(void);
extern unsigned long sdl_timer_getticks(void);

/* ======================================================================
 * POSIX name conflicts
 *
 * The game uses a global variable named 'sync' which clashes with
 * the POSIX sync() function declared in <unistd.h>.
 * ====================================================================== */

#define sync duke3d_sync

/* ======================================================================
 * GRP / game file path resolution
 *
 * Searches for a game file in multiple locations:
 *   1. Current working directory
 *   2. Directory containing the executable
 *   3. ./data/ subdirectory
 *   4. $DUKE3D_DATA environment variable directory
 * Returns pointer to found path (static buffer), or NULL.
 * ====================================================================== */

static const char *find_game_file(const char *filename)
{
    static char pathbuf[1024];

    /* 1. Current working directory */
    if (access(filename, R_OK) == 0)
        return filename;

    /* 2. Directory of the executable */
#ifdef _WIN32
    {
        DWORD len = GetModuleFileNameA(NULL, pathbuf, sizeof(pathbuf) - 1);
        if (len > 0) {
            char *slash;
            pathbuf[len] = 0;
            slash = strrchr(pathbuf, '\\');
            if (!slash) slash = strrchr(pathbuf, '/');
            if (slash) {
                slash[1] = 0;
                strncat(pathbuf, filename, sizeof(pathbuf) - strlen(pathbuf) - 1);
                if (_access(pathbuf, 4) == 0)
                    return pathbuf;
            }
        }
    }
#else
    {
        ssize_t len = readlink("/proc/self/exe", pathbuf, sizeof(pathbuf) - 1);
        if (len > 0) {
            char *slash;
            pathbuf[len] = 0;
            slash = strrchr(pathbuf, '/');
            if (slash) {
                slash[1] = 0;
                strncat(pathbuf, filename, sizeof(pathbuf) - strlen(pathbuf) - 1);
                if (access(pathbuf, R_OK) == 0)
                    return pathbuf;
            }
        }
    }
#endif

    /* 3. ./data/ subdirectory */
    snprintf(pathbuf, sizeof(pathbuf), "data/%s", filename);
    if (access(pathbuf, R_OK) == 0)
        return pathbuf;

    /* 4. DUKE3D_DATA environment variable */
    {
        const char *datadir = getenv("DUKE3D_DATA");
        if (datadir) {
            snprintf(pathbuf, sizeof(pathbuf), "%s/%s", datadir, filename);
            if (access(pathbuf, R_OK) == 0)
                return pathbuf;
        }
    }

    return NULL;
}

/* ======================================================================
 * Fatal error reporting — shows MessageBox on Windows, stderr on Linux
 * ====================================================================== */

static inline void error_fatal(const char *title, const char *msg)
{
#ifdef _WIN32
    MessageBoxA(NULL, msg, title, MB_OK | MB_ICONERROR);
#else
    fprintf(stderr, "%s: %s\n", title, msg);
#endif
    exit(1);
}

#endif /* COMPAT_H_ */
