// SPDX-License-Identifier: GPL-2.0-or-later
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

  /* GCC built-in branch prediction hint — no-op on MSVC */
  #ifndef __builtin_expect
  #define __builtin_expect(expr, val) (expr)
  #endif

  /* MSVC uses __restrict instead of __restrict__ */
  #define __restrict__ __restrict

  /* POSIX → MSVC name mappings */
  #include <io.h>
  #include <malloc.h>  /* _alloca */
  #define access _access
  #define alloca _alloca
  #define strcasecmp _stricmp
  #define strncasecmp _strnicmp

  #ifndef R_OK
  #define R_OK 4
  #endif
  #ifndef W_OK
  #define W_OK 2
  #endif
  #ifndef F_OK
  #define F_OK 0
  #endif

  /* Suppress deprecation warnings for POSIX names */
  #pragma warning(disable: 4996)
  
    /* MSVC C89 mode (/Tc) does not support C11 _Static_assert */
    #if !defined(__cplusplus) && (!defined(_MSC_VER) || _MSC_VER < 1900 || !defined(_Static_assert))
    #define _STATIC_ASSERT_GLUE(a, b) a ## b
    #define _STATIC_ASSERT_JOIN(a, b) _STATIC_ASSERT_GLUE(a, b)
    #define _Static_assert(expr, msg) typedef char _STATIC_ASSERT_JOIN(static_assertion_, __LINE__)[(expr) ? 1 : -1]
    #endif
  #endif

/* ======================================================================
 * C11 feature compatibility
 * ====================================================================== */

/* _Noreturn: Mark functions that never return. Enables compiler to:
 *   - Suppress false "control reaches end of non-void function" warnings
 *   - Optimize away dead code after noreturn function calls
 *   - Generate better stack traces
 *
 * Available in C11, but we support older standards via GCC __attribute__.
 * Use __attribute__((noreturn)) instead of _Noreturn for maximum portability,
 * as it works on both GCC and GCC-compatible compilers across all C standards.
 *
 * === r20 Audit (compat-layer) ===
 * Identified exit-only functions in source/SRC/:
 *   1. gameexit(char *t) - source/FUNCT.H:372, source/GAME.C:2189 (always exit(0))
 *   2. reportandexit(char *msg) - SRC/BUILD.H:352, SRC/CACHE1D.C:239 (always exit(0))
 *   3. error_fatal() - compat/compat.h:755 (already annotated)
 * No further candidates without callsite audit (all other exit() calls are inline).
 */
#ifndef _Noreturn
  #ifdef __GNUC__
    #define _Noreturn __attribute__((noreturn))
  #elif defined(__clang__)
    #define _Noreturn __attribute__((noreturn))
  #else
    /* Fallback: define as nothing for unsupported compilers */
    #define _Noreturn
  #endif
#endif

/* ======================================================================
 * Standard headers that replace DOS equivalents
 * ====================================================================== */

/* POSIX feature test macros - must precede all system includes */
#ifndef _WIN32
#ifndef _GNU_SOURCE
#define _GNU_SOURCE      /* FNM_CASEFOLD, etc. on glibc */
#endif
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE  /* usleep, etc. on glibc >= 2.19 */
#endif
#define _BSD_SOURCE      /* usleep on older glibc */
#endif

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
#include <ctype.h>
#include <signal.h>
#include <fcntl.h>      /* open, O_RDONLY, etc. */
#include <sys/types.h>  /* replaces sys\types.h */
#include <sys/stat.h>   /* replaces sys\stat.h */

/*
 * Validate fundamental C integer types across all platforms.
 * These assertions catch configuration errors early and ensure
 * that DOS/legacy code assumptions about type sizes hold true.
 */
_Static_assert(sizeof(int8_t) == 1, "int8_t must be exactly 1 byte");
_Static_assert(sizeof(uint8_t) == 1, "uint8_t must be exactly 1 byte");
_Static_assert(sizeof(int16_t) == 2, "int16_t must be exactly 2 bytes");
_Static_assert(sizeof(uint16_t) == 2, "uint16_t must be exactly 2 bytes");
_Static_assert(sizeof(int32_t) == 4, "int32_t must be exactly 4 bytes");
_Static_assert(sizeof(uint32_t) == 4, "uint32_t must be exactly 4 bytes");
_Static_assert(sizeof(int64_t) == 8, "int64_t must be exactly 8 bytes");
_Static_assert(sizeof(uint64_t) == 8, "uint64_t must be exactly 8 bytes");

/*
 * Validate pointer size: affects struct layouts and pointer arithmetic.
 * Game code assumes pointers fit in 32-bit or 64-bit consistently.
 */
_Static_assert((sizeof(void *) == 4) || (sizeof(void *) == 8), "pointer must be 4 or 8 bytes");

#ifdef _WIN32
  /* WIN32_LEAN_AND_MEAN prevents windows.h from including winsock.h,
     which conflicts with winsock2.h used in MMULTI.C networking code.
     It also excludes rpcndr.h which defines boolean as unsigned char. */
  #ifndef WIN32_LEAN_AND_MEAN
  #define WIN32_LEAN_AND_MEAN
  #endif
  #include <windows.h>
  #include <dbghelp.h>   /* StackWalk64 backtrace in the crash handler (E5) */
  /* With WIN32_LEAN_AND_MEAN, rpcndr.h is excluded so boolean is not
     defined. Define it here as int32_t to match the game convention. */
  #ifndef _BOOLEAN_DEFINED
  #define _BOOLEAN_DEFINED
  typedef int32_t boolean;
  #endif
  #include <direct.h>   /* _mkdir, _getcwd */
  #include <io.h>       /* filelength, tell, _findfirst, etc. */
  #ifdef _MSC_VER
    #include <BaseTsd.h>
    typedef SSIZE_T ssize_t;
    #include "msvc_unistd.h"
  #endif
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
#define FP_OFF(p)   ((intptr_t)(p))
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
            f->name[sizeof(f->name)-1] = 0;
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
        f->_pattern[sizeof(f->_pattern)-1] = 0;
        *slash = 0;
        strncpy(f->_path, dirpart, sizeof(f->_path)-1);
        f->_path[sizeof(f->_path)-1] = 0;
    } else {
        strncpy(f->_pattern, path, sizeof(f->_pattern)-1);
        f->_pattern[sizeof(f->_pattern)-1] = 0;
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

/** Precondition: buf size must be >= 22 bytes; behavior undefined otherwise.
 *  Returns 0 on malformed header.
 */
extern unsigned long voc_file_size(const unsigned char *buf);

/** Precondition: buf size must be >= 22 bytes; behavior undefined otherwise.
 *  Returns 0 on malformed header.
 */
extern unsigned long wav_file_size(const unsigned char *buf);

/* Timer (replaces PIT 8254 programming) */
extern void sdl_timer_init(void);
extern void sdl_timer_shutdown(void);
extern unsigned long sdl_timer_getticks(void);

/* Network (multiplayer support) */
extern short getpacket(short *other, char *bufptr); /* build-r16-lto-type: aligned to legacy K&R decl */

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

#ifdef __GNUC__
__attribute__((unused))
#endif
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
 * Startup logging — writes to duke3d_startup.log for debugging silent
 * crashes on Windows where -mwindows suppresses console output.
 * ====================================================================== */

extern FILE *_startup_log;

#ifdef COMPAT_STARTUP_LOG_OWNER
FILE *_startup_log = NULL;
#endif

static inline void startup_log_open(void)
{
    _startup_log = fopen("atomic_shell_startup.log", "w");
    if (_startup_log) {
        fprintf(_startup_log, "Atomic Shell startup log\n");
        fprintf(_startup_log, "(Build engine port — derived from Duke Nukem 3D codebase, Apogee/3D Realms 1996)\n");
        fprintf(_startup_log, "========================\n");
        fflush(_startup_log);
    }
}

static inline void startup_log(const char *fmt, ...)
{
    if (_startup_log) {
        va_list ap;
        va_start(ap, fmt);
        vfprintf(_startup_log, fmt, ap);
        va_end(ap);
        fprintf(_startup_log, "\n");
        fflush(_startup_log);
    }
}

static inline void startup_log_close(void)
{
    if (_startup_log) {
        fprintf(_startup_log, "Startup log closed (game running normally)\n");
        fclose(_startup_log);
        _startup_log = NULL;
    }
}

/* ======================================================================
 * Fatal error reporting — shows MessageBox on Windows, stderr on Linux
 * ====================================================================== */

static inline int startup_show_error_dialogs(void)
{
#ifdef _WIN32
    const char *silent_errors = getenv("DUKE3D_SILENT_ERRORS");
    if (silent_errors && silent_errors[0] && strcmp(silent_errors, "0") != 0)
        return 0;
    if (getenv("DUKE3D_HEADLESS"))
        return 0;
#endif
    return 1;
}

static inline _Noreturn void error_fatal(const char *title, const char *msg)
{
    startup_log("error_fatal: %s: %s", title, msg);
#ifdef _WIN32
    if (startup_show_error_dialogs())
        MessageBoxA(NULL, msg, title, MB_OK | MB_ICONERROR);
    else
        fprintf(stderr, "%s: %s\n", title, msg);
#else
    fprintf(stderr, "%s: %s\n", title, msg);
#endif
    exit(1);
}

#ifdef _WIN32
static LONG WINAPI crash_handler(EXCEPTION_POINTERS *ep)
{
    static volatile int in_crash_handler = 0;
    char buf[1024];
    DWORD code;
    void *addr;
    uintptr_t module_base;
    uintptr_t exception_rva;
    const char *access_type = "";
    char access_info[128] = "";

    /* Prevent re-entrant crashes from looping */
    if (in_crash_handler)
        return EXCEPTION_EXECUTE_HANDLER;
    in_crash_handler = 1;

    code = ep->ExceptionRecord->ExceptionCode;
    addr = ep->ExceptionRecord->ExceptionAddress;
    module_base = (uintptr_t)GetModuleHandleA(NULL);
    exception_rva = (uintptr_t)addr - module_base;

    if (code == 0xC0000005 && ep->ExceptionRecord->NumberParameters >= 2) {
        ULONG_PTR rw = ep->ExceptionRecord->ExceptionInformation[0];
        ULONG_PTR target = ep->ExceptionRecord->ExceptionInformation[1];
        access_type = (rw == 0) ? "READ" : (rw == 1) ? "WRITE" : "EXEC";
        snprintf(access_info, sizeof(access_info),
            "Access violation %s address %p",
            access_type, (void *)target);
    }

    snprintf(buf, sizeof(buf),
        "Atomic Shell crashed!\n\n"
        "Exception: 0x%08lX at %p (RVA 0x%llX)\n"
        "%s\n\n"
        "Check atomic_shell_startup.log for details.",
        (unsigned long)code, addr, (unsigned long long)exception_rva, access_info);

    if (_startup_log) {
        fprintf(_startup_log, "CRASH: Exception 0x%08lX at %p (module base %p, RVA 0x%llX)\n",
            (unsigned long)code, addr, (void *)module_base, (unsigned long long)exception_rva);
        if (access_info[0])
            fprintf(_startup_log, "CRASH: %s\n", access_info);
        fflush(_startup_log);   /* persist the fault line before the (possibly faulting) stack walk */
#if defined(_M_X64) || defined(_WIN64)
        /* E5: x64 register dump + StackWalk64 backtrace. Each frame logs the
         * module + RVA (symbolize duke3d.exe RVAs offline via the linker .map),
         * plus a symbol name when one is resolvable. Diagnostic-only. */
        {
            HANDLE proc = GetCurrentProcess();
            HANDLE thr  = GetCurrentThread();
            CONTEXT *ctx = ep->ContextRecord;
            STACKFRAME64 sf;
            char symbuf[sizeof(SYMBOL_INFO) + 256];
            SYMBOL_INFO *sym = (SYMBOL_INFO *)symbuf;
            int n;

            fprintf(_startup_log,
                "RIP=%016llX RSP=%016llX RBP=%016llX\n"
                "RAX=%016llX RBX=%016llX RCX=%016llX RDX=%016llX\n"
                "RSI=%016llX RDI=%016llX R8 =%016llX R9 =%016llX\n",
                (unsigned long long)ctx->Rip, (unsigned long long)ctx->Rsp, (unsigned long long)ctx->Rbp,
                (unsigned long long)ctx->Rax, (unsigned long long)ctx->Rbx, (unsigned long long)ctx->Rcx, (unsigned long long)ctx->Rdx,
                (unsigned long long)ctx->Rsi, (unsigned long long)ctx->Rdi, (unsigned long long)ctx->R8, (unsigned long long)ctx->R9);

            SymSetOptions(SYMOPT_DEFERRED_LOADS | SYMOPT_UNDNAME);
            SymInitialize(proc, NULL, TRUE);

            memset(&sf, 0, sizeof(sf));
            sf.AddrPC.Offset    = ctx->Rip; sf.AddrPC.Mode    = AddrModeFlat;
            sf.AddrFrame.Offset = ctx->Rbp; sf.AddrFrame.Mode = AddrModeFlat;
            sf.AddrStack.Offset = ctx->Rsp; sf.AddrStack.Mode = AddrModeFlat;

            fprintf(_startup_log, "CRASH: backtrace (x64):\n");
            for (n = 0; n < 48; n++) {
                DWORD64 pc, mbase, disp = 0;
                char modpath[MAX_PATH] = "";
                const char *modname;
                if (!StackWalk64(IMAGE_FILE_MACHINE_AMD64, proc, thr, &sf, ctx,
                        NULL, SymFunctionTableAccess64, SymGetModuleBase64, NULL))
                    break;
                pc = sf.AddrPC.Offset;
                if (pc == 0) break;
                mbase = SymGetModuleBase64(proc, pc);
                if (mbase) GetModuleFileNameA((HMODULE)(uintptr_t)mbase, modpath, sizeof(modpath));
                modname = strrchr(modpath, '\\');
                modname = modname ? modname + 1 : (modpath[0] ? modpath : "?");
                memset(symbuf, 0, sizeof(symbuf));
                sym->SizeOfStruct = sizeof(SYMBOL_INFO);
                sym->MaxNameLen = 255;
                if (SymFromAddr(proc, pc, &disp, sym))
                    fprintf(_startup_log, "  #%02d %s+0x%llX  [%s RVA 0x%llX]\n",
                        n, sym->Name, (unsigned long long)disp, modname,
                        (unsigned long long)(mbase ? pc - mbase : 0));
                else
                    fprintf(_startup_log, "  #%02d %016llX  [%s RVA 0x%llX]\n",
                        n, (unsigned long long)pc, modname,
                        (unsigned long long)(mbase ? pc - mbase : 0));
            }
            SymCleanup(proc);
            fflush(_startup_log);
        }
#endif
#ifdef _X86_
        {
            CONTEXT *ctx = ep->ContextRecord;
            fprintf(_startup_log, "EAX=%08lX EBX=%08lX ECX=%08lX EDX=%08lX\n",
                ctx->Eax, ctx->Ebx, ctx->Ecx, ctx->Edx);
            fprintf(_startup_log, "ESI=%08lX EDI=%08lX EBP=%08lX ESP=%08lX\n",
                ctx->Esi, ctx->Edi, ctx->Ebp, ctx->Esp);
            fprintf(_startup_log, "EIP=%08lX\n", ctx->Eip);
            /* Mini stack dump */
            fprintf(_startup_log, "Stack (ESP):");
            {
                unsigned long *sp = (unsigned long *)(uintptr_t)ctx->Esp;
                int i;
                for (i = 0; i < 16 && !IsBadReadPtr(sp+i, 4); i++)
                    fprintf(_startup_log, " %08lX", sp[i]);
            }
            fprintf(_startup_log, "\n");
        }
#endif
        fflush(_startup_log);
        fclose(_startup_log);
    }
    if (startup_show_error_dialogs())
        MessageBoxA(NULL, buf, "Atomic Shell - Crash", MB_OK | MB_ICONERROR);
    else
        fprintf(stderr, "%s\n", buf);
    /* Forcibly terminate — returning EXCEPTION_EXECUTE_HANDLER alone can
       leave the process alive if the CRT or another thread interferes. */
    ExitProcess(1);
    return EXCEPTION_EXECUTE_HANDLER; /* unreachable, satisfies compiler */
}
#endif

/* ======================================================================
 * Debug logging for stubbed functions (compat/log_stub.h)
 * =====================================================================
 * To enable debug logging for no-op stubs (Music_SetVolume, PlayMusic,
 * CONTROL_WaitRelease, CONTROL_Ack, FX_StopRecord, etc.):
 *
 *   make DUKE3D_STUB_LOG=1
 *   // or
 *   DUKE3D_STUB_LOG=1 make
 *
 * When enabled, each stub logs once to stderr with [STUB] prefix.
 * See compat/log_stub.h for full documentation.
 * ===================================================================== */

#endif /* COMPAT_H_ */
