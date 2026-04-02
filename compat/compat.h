/*
 * compat.h - Master compatibility header for Duke Nukem 3D
 *
 * Replaces all DOS/Watcom-specific includes for GCC/Linux + SDL2 builds.
 * Include this instead of dos.h, conio.h, io.h, i86.h, bios.h, etc.
 */

#ifndef COMPAT_H_
#define COMPAT_H_
#pragma once

/* ======================================================================
 * Standard headers that replace DOS equivalents
 * ====================================================================== */

#define _DEFAULT_SOURCE  /* usleep, etc. on glibc >= 2.19 */
#define _BSD_SOURCE      /* usleep on older glibc */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <strings.h>    /* strcasecmp */
#include <unistd.h>     /* read, write, close, lseek, usleep */
#include <fcntl.h>      /* open, O_RDONLY, etc. */
#include <sys/types.h>  /* replaces sys\types.h */
#include <sys/stat.h>   /* replaces sys\stat.h */
#include <errno.h>
#include <ctype.h>
#include <signal.h>

/* ======================================================================
 * Watcom compiler keyword stubs
 * ====================================================================== */

/* #pragma aux is handled by -include or by wrapping; these keywords
   must become no-ops in GCC. */
#define __interrupt
#define __far
#define __pascal
#define __cdecl
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

/* filelength(fd) - return the size of an open file descriptor */
static inline long filelength(int fd)
{
    struct stat st;
    if (fstat(fd, &st) == -1) return -1L;
    return (long)st.st_size;
}

/* tell(fd) - return current file position */
static inline long tell(int fd)
{
    return (long)lseek(fd, 0, SEEK_CUR);
}

/* Watcom's sopen() - just map to open(), ignoring share flags */
#define sopen(path, oflag, shflag, ...)  open((path), (oflag), ##__VA_ARGS__)

/* ======================================================================
 * String function mappings
 * ====================================================================== */

#ifndef stricmp
#define stricmp  strcasecmp
#endif

#ifndef strcmpi
#define strcmpi  strcasecmp
#endif

#ifndef strnicmp
#define strnicmp strncasecmp
#endif

#ifndef strlwr
static inline char *strlwr(char *s)
{
    char *p = s;
    while (*p) { *p = tolower((unsigned char)*p); p++; }
    return s;
}
#endif

#ifndef strupr
static inline char *strupr(char *s)
{
    char *p = s;
    while (*p) { *p = toupper((unsigned char)*p); p++; }
    return s;
}
#endif

/* itoa / ltoa - non-standard but used in the original code */
#ifndef itoa
static inline char *itoa(int val, char *buf, int radix)
{
    if (radix == 10) { sprintf(buf, "%d", val); return buf; }
    if (radix == 16) { sprintf(buf, "%x", val); return buf; }
    if (radix == 8)  { sprintf(buf, "%o", val); return buf; }
    sprintf(buf, "%d", val);
    return buf;
}
#endif

#ifndef ltoa
static inline char *ltoa(long val, char *buf, int radix)
{
    if (radix == 10) { sprintf(buf, "%ld", val); return buf; }
    if (radix == 16) { sprintf(buf, "%lx", val); return buf; }
    if (radix == 8)  { sprintf(buf, "%lo", val); return buf; }
    sprintf(buf, "%ld", val);
    return buf;
}
#endif

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

/* inp / outp - x86 port I/O (no-ops on modern Linux userspace) */
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
static inline void delay(unsigned int ms)
{
    usleep((unsigned int)ms * 1000u);
}

/* clock tick / timing */
#define CLOCKS_PER_SEC_DOS 18.2

/* getenv is already POSIX - no mapping needed */

/* ======================================================================
 * Path separator handling
 * ====================================================================== */

#ifndef PATH_SEP_CHAR
#define PATH_SEP_CHAR '/'
#endif

#ifndef PATH_SEP_STR
#define PATH_SEP_STR "/"
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

#endif /* COMPAT_H_ */
