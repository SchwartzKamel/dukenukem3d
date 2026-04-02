/*
 * pragmas_gcc.h - GCC replacement for Watcom PRAGMAS.H
 *
 * Replaces ~183 Watcom "#pragma aux" inline assembly declarations with
 * portable static inline C functions. All wide multiplies use int64_t
 * to match the original 32x32→64 semantics of the x86 IMUL instruction.
 *
 * Parameters use "long" to match the original calling code (which uses
 * "long" everywhere). When compiled with -m32, long == 4 bytes.
 * Internally we cast to int64_t for 64-bit intermediate results.
 */

#ifndef PRAGMAS_GCC_H_
#define PRAGMAS_GCC_H_
#pragma once

#include <stdint.h>
#include <string.h>
#include <stdlib.h>

/* ======================================================================
 * Global used by divmod / moddiv
 * ====================================================================== */
extern long dmval;

/* ======================================================================
 * Core math
 * ====================================================================== */

static inline long sqr(long a)
{
    return a * a;
}

static inline long scale(long a, long b, long c)
{
    return (long)(((int64_t)a * b) / c);
}

static inline long mulscale(long a, long b, long c)
{
    return (long)(((int64_t)a * b) >> c);
}

/* ======================================================================
 * mulscale1 .. mulscale32
 * Each: mulscaleN(a, b) = (long)(((int64_t)a * b) >> N)
 * ====================================================================== */

static inline long mulscale1(long a, long b) { return (long)(((int64_t)a * b) >> 1); }
static inline long mulscale2(long a, long b) { return (long)(((int64_t)a * b) >> 2); }
static inline long mulscale3(long a, long b) { return (long)(((int64_t)a * b) >> 3); }
static inline long mulscale4(long a, long b) { return (long)(((int64_t)a * b) >> 4); }
static inline long mulscale5(long a, long b) { return (long)(((int64_t)a * b) >> 5); }
static inline long mulscale6(long a, long b) { return (long)(((int64_t)a * b) >> 6); }
static inline long mulscale7(long a, long b) { return (long)(((int64_t)a * b) >> 7); }
static inline long mulscale8(long a, long b) { return (long)(((int64_t)a * b) >> 8); }
static inline long mulscale9(long a, long b) { return (long)(((int64_t)a * b) >> 9); }
static inline long mulscale10(long a, long b) { return (long)(((int64_t)a * b) >> 10); }
static inline long mulscale11(long a, long b) { return (long)(((int64_t)a * b) >> 11); }
static inline long mulscale12(long a, long b) { return (long)(((int64_t)a * b) >> 12); }
static inline long mulscale13(long a, long b) { return (long)(((int64_t)a * b) >> 13); }
static inline long mulscale14(long a, long b) { return (long)(((int64_t)a * b) >> 14); }
static inline long mulscale15(long a, long b) { return (long)(((int64_t)a * b) >> 15); }
static inline long mulscale16(long a, long b) { return (long)(((int64_t)a * b) >> 16); }
static inline long mulscale17(long a, long b) { return (long)(((int64_t)a * b) >> 17); }
static inline long mulscale18(long a, long b) { return (long)(((int64_t)a * b) >> 18); }
static inline long mulscale19(long a, long b) { return (long)(((int64_t)a * b) >> 19); }
static inline long mulscale20(long a, long b) { return (long)(((int64_t)a * b) >> 20); }
static inline long mulscale21(long a, long b) { return (long)(((int64_t)a * b) >> 21); }
static inline long mulscale22(long a, long b) { return (long)(((int64_t)a * b) >> 22); }
static inline long mulscale23(long a, long b) { return (long)(((int64_t)a * b) >> 23); }
static inline long mulscale24(long a, long b) { return (long)(((int64_t)a * b) >> 24); }
static inline long mulscale25(long a, long b) { return (long)(((int64_t)a * b) >> 25); }
static inline long mulscale26(long a, long b) { return (long)(((int64_t)a * b) >> 26); }
static inline long mulscale27(long a, long b) { return (long)(((int64_t)a * b) >> 27); }
static inline long mulscale28(long a, long b) { return (long)(((int64_t)a * b) >> 28); }
static inline long mulscale29(long a, long b) { return (long)(((int64_t)a * b) >> 29); }
static inline long mulscale30(long a, long b) { return (long)(((int64_t)a * b) >> 30); }
static inline long mulscale31(long a, long b) { return (long)(((int64_t)a * b) >> 31); }
static inline long mulscale32(long a, long b) { return (long)(((int64_t)a * b) >> 32); }

/* ======================================================================
 * dmulscale1 .. dmulscale32
 * Each: dmulscaleN(a, b, c, d) = (long)((((int64_t)a*b) + ((int64_t)c*d)) >> N)
 * ====================================================================== */

static inline long dmulscale1(long a, long b, long c, long d)  { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 1); }
static inline long dmulscale2(long a, long b, long c, long d)  { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 2); }
static inline long dmulscale3(long a, long b, long c, long d)  { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 3); }
static inline long dmulscale4(long a, long b, long c, long d)  { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 4); }
static inline long dmulscale5(long a, long b, long c, long d)  { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 5); }
static inline long dmulscale6(long a, long b, long c, long d)  { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 6); }
static inline long dmulscale7(long a, long b, long c, long d)  { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 7); }
static inline long dmulscale8(long a, long b, long c, long d)  { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 8); }
static inline long dmulscale9(long a, long b, long c, long d)  { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 9); }
static inline long dmulscale10(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 10); }
static inline long dmulscale11(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 11); }
static inline long dmulscale12(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 12); }
static inline long dmulscale13(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 13); }
static inline long dmulscale14(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 14); }
static inline long dmulscale15(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 15); }
static inline long dmulscale16(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 16); }
static inline long dmulscale17(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 17); }
static inline long dmulscale18(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 18); }
static inline long dmulscale19(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 19); }
static inline long dmulscale20(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 20); }
static inline long dmulscale21(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 21); }
static inline long dmulscale22(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 22); }
static inline long dmulscale23(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 23); }
static inline long dmulscale24(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 24); }
static inline long dmulscale25(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 25); }
static inline long dmulscale26(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 26); }
static inline long dmulscale27(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 27); }
static inline long dmulscale28(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 28); }
static inline long dmulscale29(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 29); }
static inline long dmulscale30(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 30); }
static inline long dmulscale31(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 31); }
static inline long dmulscale32(long a, long b, long c, long d) { return (long)((((int64_t)a * b) + ((int64_t)c * d)) >> 32); }

/* ======================================================================
 * tmulscale1 .. tmulscale32
 * Each: tmulscaleN(a,b,c,d,e,f) =
 *   (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> N)
 * ====================================================================== */

static inline long tmulscale1(long a, long b, long c, long d, long e, long f)  { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 1); }
static inline long tmulscale2(long a, long b, long c, long d, long e, long f)  { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 2); }
static inline long tmulscale3(long a, long b, long c, long d, long e, long f)  { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 3); }
static inline long tmulscale4(long a, long b, long c, long d, long e, long f)  { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 4); }
static inline long tmulscale5(long a, long b, long c, long d, long e, long f)  { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 5); }
static inline long tmulscale6(long a, long b, long c, long d, long e, long f)  { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 6); }
static inline long tmulscale7(long a, long b, long c, long d, long e, long f)  { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 7); }
static inline long tmulscale8(long a, long b, long c, long d, long e, long f)  { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 8); }
static inline long tmulscale9(long a, long b, long c, long d, long e, long f)  { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 9); }
static inline long tmulscale10(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 10); }
static inline long tmulscale11(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 11); }
static inline long tmulscale12(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 12); }
static inline long tmulscale13(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 13); }
static inline long tmulscale14(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 14); }
static inline long tmulscale15(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 15); }
static inline long tmulscale16(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 16); }
static inline long tmulscale17(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 17); }
static inline long tmulscale18(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 18); }
static inline long tmulscale19(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 19); }
static inline long tmulscale20(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 20); }
static inline long tmulscale21(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 21); }
static inline long tmulscale22(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 22); }
static inline long tmulscale23(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 23); }
static inline long tmulscale24(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 24); }
static inline long tmulscale25(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 25); }
static inline long tmulscale26(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 26); }
static inline long tmulscale27(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 27); }
static inline long tmulscale28(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 28); }
static inline long tmulscale29(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 29); }
static inline long tmulscale30(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 30); }
static inline long tmulscale31(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 31); }
static inline long tmulscale32(long a, long b, long c, long d, long e, long f) { return (long)((((int64_t)a*b) + ((int64_t)c*d) + ((int64_t)e*f)) >> 32); }

/* ======================================================================
 * divscale1 .. divscale32
 * Each: divscaleN(a, b) = (long)(((int64_t)a << N) / b)
 * ====================================================================== */

static inline long divscale1(long a, long b)  { return (long)(((int64_t)a << 1) / b); }
static inline long divscale2(long a, long b)  { return (long)(((int64_t)a << 2) / b); }
static inline long divscale3(long a, long b)  { return (long)(((int64_t)a << 3) / b); }
static inline long divscale4(long a, long b)  { return (long)(((int64_t)a << 4) / b); }
static inline long divscale5(long a, long b)  { return (long)(((int64_t)a << 5) / b); }
static inline long divscale6(long a, long b)  { return (long)(((int64_t)a << 6) / b); }
static inline long divscale7(long a, long b)  { return (long)(((int64_t)a << 7) / b); }
static inline long divscale8(long a, long b)  { return (long)(((int64_t)a << 8) / b); }
static inline long divscale9(long a, long b)  { return (long)(((int64_t)a << 9) / b); }
static inline long divscale10(long a, long b) { return (long)(((int64_t)a << 10) / b); }
static inline long divscale11(long a, long b) { return (long)(((int64_t)a << 11) / b); }
static inline long divscale12(long a, long b) { return (long)(((int64_t)a << 12) / b); }
static inline long divscale13(long a, long b) { return (long)(((int64_t)a << 13) / b); }
static inline long divscale14(long a, long b) { return (long)(((int64_t)a << 14) / b); }
static inline long divscale15(long a, long b) { return (long)(((int64_t)a << 15) / b); }
static inline long divscale16(long a, long b) { return (long)(((int64_t)a << 16) / b); }
static inline long divscale17(long a, long b) { return (long)(((int64_t)a << 17) / b); }
static inline long divscale18(long a, long b) { return (long)(((int64_t)a << 18) / b); }
static inline long divscale19(long a, long b) { return (long)(((int64_t)a << 19) / b); }
static inline long divscale20(long a, long b) { return (long)(((int64_t)a << 20) / b); }
static inline long divscale21(long a, long b) { return (long)(((int64_t)a << 21) / b); }
static inline long divscale22(long a, long b) { return (long)(((int64_t)a << 22) / b); }
static inline long divscale23(long a, long b) { return (long)(((int64_t)a << 23) / b); }
static inline long divscale24(long a, long b) { return (long)(((int64_t)a << 24) / b); }
static inline long divscale25(long a, long b) { return (long)(((int64_t)a << 25) / b); }
static inline long divscale26(long a, long b) { return (long)(((int64_t)a << 26) / b); }
static inline long divscale27(long a, long b) { return (long)(((int64_t)a << 27) / b); }
static inline long divscale28(long a, long b) { return (long)(((int64_t)a << 28) / b); }
static inline long divscale29(long a, long b) { return (long)(((int64_t)a << 29) / b); }
static inline long divscale30(long a, long b) { return (long)(((int64_t)a << 30) / b); }
static inline long divscale31(long a, long b) { return (long)(((int64_t)a << 31) / b); }
static inline long divscale32(long a, long b) { return (long)(((int64_t)a << 32) / b); }

/* ======================================================================
 * boundmulscale - clamped mulscale
 * ====================================================================== */

static inline long boundmulscale(long a, long b, long c)
{
    int64_t r = ((int64_t)a * b) >> c;
    if (r > 0x7fffffffLL) return 0x7fffffffL;
    if (r < (-0x7fffffffLL - 1)) return (long)(-0x80000000LL);
    return (long)r;
}

/* ======================================================================
 * Utility functions
 * ====================================================================== */

static inline long klabs(long a) { return (a < 0) ? -a : a; }
static inline long ksgn(long a)  { return (a > 0) ? 1 : ((a < 0) ? -1 : 0); }

static inline long kmin(long a, long b)
{
    return (a < b) ? a : b;
}

static inline long kmax(long a, long b)
{
    return (a > b) ? a : b;
}

static inline unsigned long umin(unsigned long a, unsigned long b)
{
    return (a < b) ? a : b;
}

static inline unsigned long umax(unsigned long a, unsigned long b)
{
    return (a > b) ? a : b;
}

/* ======================================================================
 * Multiply helpers
 * ====================================================================== */

static inline long mul3(long a) { return a * 3; }
static inline long mul5(long a) { return a * 5; }
static inline long mul9(long a) { return a * 9; }

/* ======================================================================
 * divmod / moddiv
 * ====================================================================== */

static inline long divmod(long a, long b)
{
    extern long dmval;
    dmval = a % b;
    return a / b;
}

static inline long moddiv(long a, long b)
{
    extern long dmval;
    dmval = a / b;
    return a % b;
}

/* ======================================================================
 * Memory / buffer operations
 *
 * copybuf:      copy N dwords (4*N bytes)
 * copybufbyte:  copy N bytes
 * copybufreverse: copy N bytes in reverse order from source
 * clearbuf:     fill N dwords with a 32-bit value
 * clearbufbyte: fill N bytes (approximate: original fills dword pattern)
 * ====================================================================== */

static inline void copybuf(void *src, void *dst, long n)
{
    memcpy(dst, src, (size_t)n * 4);
}

static inline void copybufbyte(void *src, void *dst, long n)
{
    memcpy(dst, src, (size_t)n);
}

static inline void copybufreverse(void *src, void *dst, long n)
{
    const char *s = (const char *)src;
    char *d = (char *)dst;
    long i;
    for (i = 0; i < n; i++)
        d[i] = s[-i];
}

static inline void clearbuf(void *dst, long n, long val)
{
    int32_t *d = (int32_t *)dst;
    /* If all 4 bytes are identical, use memset (GCC vectorizes this) */
    unsigned long uv = (unsigned long)val;
    if ((uv & 0xFF) == ((uv >> 8) & 0xFF) &&
        (uv & 0xFF) == ((uv >> 16) & 0xFF) &&
        (uv & 0xFF) == ((uv >> 24) & 0xFF)) {
        memset(d, (int)(uv & 0xFF), (size_t)n * 4);
    } else {
        long i;
        for (i = 0; i < n; i++)
            d[i] = (int32_t)val;
    }
}

static inline void clearbufbyte(void *dst, long n, long val)
{
    /* Original fills with a repeating dword pattern.
       For the common case val < 256 this is equivalent to memset. */
    if ((val & 0xFFFFFF00L) == 0 || val == -1L) {
        memset(dst, (int)(val & 0xFF), (size_t)n);
    } else {
        /* Fill dwords, then remaining bytes */
        int32_t *d32 = (int32_t *)dst;
        int32_t val32 = (int32_t)val;
        long ndwords = n >> 2;
        long rem = n & 3;
        long i;
        for (i = 0; i < ndwords; i++)
            d32[i] = val32;
        if (rem > 0) {
            char *tail = (char *)&d32[ndwords];
            char *vp = (char *)&val32;
            for (i = 0; i < rem; i++)
                tail[i] = vp[i];
        }
    }
}

/* ======================================================================
 * Pixel operations
 * ====================================================================== */

static inline void drawpixel(void *addr, char val)
{
    *(char *)addr = val;
}

static inline void drawpixels(void *addr, short val)
{
    *(short *)addr = val;
}

static inline void drawpixelses(void *addr, long val)
{
    *(long *)addr = val;
}

static inline char readpixel(void *addr)
{
    return *(char *)addr;
}

/* ======================================================================
 * Swap operations
 * ====================================================================== */

static inline void swapchar(void *a, void *b)
{
    char t = *(char *)a;
    *(char *)a = *(char *)b;
    *(char *)b = t;
}

static inline void swapshort(void *a, void *b)
{
    short t = *(short *)a;
    *(short *)a = *(short *)b;
    *(short *)b = t;
}

static inline void swaplong(void *a, void *b)
{
    long t = *(long *)a;
    *(long *)a = *(long *)b;
    *(long *)b = t;
}

static inline void swapchar2(void *a, void *b, long n)
{
    char *pa = (char *)a;
    char *pb = (char *)b;
    long i;
    for (i = 0; i < n; i++) {
        char t = pa[i];
        pa[i] = pb[i];
        pb[i] = t;
    }
}

static inline void swapbuf4(void *a, void *b, long n)
{
    int32_t *pa = (int32_t *)a;
    int32_t *pb = (int32_t *)b;
    long i;
    for (i = 0; i < n; i++) {
        int32_t t = pa[i];
        pa[i] = pb[i];
        pb[i] = t;
    }
}

static inline void swap64bit(void *a, void *b)
{
    char tmp[8];
    memcpy(tmp, a, 8);
    memcpy(a, b, 8);
    memcpy(b, tmp, 8);
}

/* ======================================================================
 * Interpolation
 *
 * qinterpolatedown16:      fill long buffer with 16.16 fixed-point ramp
 * qinterpolatedown16short: fill short buffer with 16.16 fixed-point ramp
 * ====================================================================== */

static inline void qinterpolatedown16(long *buf, long n, long val, long add)
{
    long i;
    for (i = 0; i < n; i++) {
        buf[i] = val >> 16;
        val += add;
    }
}

static inline void qinterpolatedown16short(short *buf, long n, long val, long add)
{
    long i;
    for (i = 0; i < n; i++) {
        buf[i] = (short)(val >> 16);
        val += add;
    }
}

/* ======================================================================
 * Port I/O stubs (no direct hardware access on modern Linux)
 * ====================================================================== */

static inline void koutp(int port, int val)  { (void)port; (void)val; }
static inline void koutpw(int port, int val) { (void)port; (void)val; }
static inline int  kinp(int port)            { (void)port; return 0; }

/* ======================================================================
 * Display stubs (replaced by SDL video driver)
 * ====================================================================== */

static inline void setvmode(int mode) { (void)mode; }
static inline void limitrate(void) { }
static inline void setcolor16(int col) { (void)col; }

static inline void drawpixel16(long offset) { (void)offset; }

static inline void fillscreen16(long *buf, long val, long n)
{
    clearbuf(buf, n, val);
}

static inline void vlin16(long addr, int cnt)
{
    (void)addr; (void)cnt;
}

static inline void vlin16first(long addr, int cnt)
{
    (void)addr; (void)cnt;
}

/* ======================================================================
 * Timer functions (will be implemented by SDL timer driver)
 * ====================================================================== */

extern void inittimer1mhz(void);
extern void uninittimer1mhz(void);
extern long gettime1mhz(void);
extern long deltatime1mhz(void);
extern long readtimer(void);

/* ======================================================================
 * Mouse functions (will be implemented by SDL input driver)
 * ====================================================================== */

extern int setupmouse(void);
extern void readmousexy(short *x, short *y);
extern void readmousebstatus(short *bstatus);

/* ======================================================================
 * Misc stubs
 * ====================================================================== */

static inline void chainblit(void) { }
static inline void redblueblit(char *src1, char *src2, long cnt) {
	(void)src1; (void)src2; (void)cnt;
}
static inline void int5(void) { }

#endif /* PRAGMAS_GCC_H_ */
