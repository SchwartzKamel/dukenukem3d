/*
 * a.c - C replacement for SRC/A.ASM
 *
 * Pure-C implementations of the BUILD engine's inner-loop rendering
 * routines (texture-mapped walls, floors, ceilings, sprites, translucency,
 * voxel slabs).  Correctness over speed: the original hand-tuned x86
 * assembly used self-modifying code and register tricks we cannot
 * replicate portably.
 */

#include <stdint.h>
#include <string.h>

/* ================================================================
 * External globals shared with the rest of the BUILD engine
 * (defined in ENGINE.C or similar)
 * ================================================================ */
extern long asm1, asm2, asm3, asm4;
extern long fpuasm;
extern long globalx3, globaly3;
extern long *ylookup;        /* scanline-offset table */
extern long vplce[4], vince[4];
extern long palookupoffse[4], bufplce[4];
extern long ebpbak, espbak;
extern char pow2char[16];
extern long pow2long[16];
extern long reciptable[2048];

/* ================================================================
 * Module-local rendering state (mirrors the self-modifying code in
 * A.ASM – setup functions store values here, drawing functions read)
 * ================================================================ */

/* Horizontal line state */
static long hl_logx, hl_logy;
static long hl_bufptr;
static long hl_xshift;           /* setuphlineasm4 */
static long hl_mask;             /* (1<<(logx+logy)) - 1 mask, etc. */

/* "pro" horizontal line state */
static long prohl_bufptr;
static long prohl_shru, prohl_shrv;
static long prohl_mask;

/* Vertical line state */
static long vl_shift;            /* setupvlineasm  (32-logy) */
static long vl_shift_pro;        /* prosetupvlineasm */
static long vl_bpl;              /* setvlinebpl */
static long vl_palookup;         /* setpalookupaddress */
static long vl_palookup_pro;     /* prosetpalookupaddress */

/* Masked vline state */
static long mvl_shift;           /* setupmvlineasm */

/* Translucent vline state */
static long tvl_shift;           /* setuptvlineasm */

/* Translucency table */
static char *trans_table = NULL;
static int   trans_reverse = 0;

/* Sprite state */
static long spr_palookup, spr_inc, spr_bufptr, spr_bpl;
static long mspr_palookup, mspr_inc, mspr_bufptr, mspr_bpl;
static long tspr_palookup, tspr_inc, tspr_bufptr, tspr_bpl;

/* m/thline shifts */
static long mhl_logx, mhl_logy;
static long thl_logx, thl_logy;

/* tvlineasm2 state */
static long tv2_shade, tv2_palookup;

/* slopevlin state */
static long slp_logylogx, slp_bufptr, slp_shade;
static long slp2_logylogx, slp2_bufptr, slp2_shade;

/* rh/rmh/qrh line state */
static long rhl_shift;
static long rmhl_shift;
static long qrhl_shift;

/* drawslab state */
static long dslab_shift;

/* ================================================================
 * Helper: pointer/integer conversion (BUILD freely casts long↔ptr)
 * ================================================================ */
static inline unsigned char *LP(long v) { return (unsigned char *)(intptr_t)v; }
static inline long PL(const void *p) { return (long)(intptr_t)p; }

/* ================================================================
 * Setup functions
 * ================================================================ */

void sethlinesizes(long logx, long logy, long bufptr)
{
    hl_logx   = logx;
    hl_logy   = logy;
    hl_bufptr = bufptr;
    /* mask for extracting texel index from combined bx/by */
    hl_mask = (1L << (logx + logy)) - 1;
}

void prosethlinesizes(long logx, long logy, long bufptr)
{
    prohl_bufptr = bufptr;
    prohl_shru   = 32 - logx - logy;
    prohl_shrv   = 32 - logy;
    prohl_mask   = ((~0UL) >> (32 - logx)) << logy;
}

void setvlinebpl(long bpl)
{
    vl_bpl = bpl;
}

void setpalookupaddress(long addr)
{
    vl_palookup = addr;
}

void prosetpalookupaddress(long addr)
{
    vl_palookup_pro = addr;
}

void setuphlineasm4(long shift)
{
    hl_xshift = shift;
}

void setupvlineasm(long neglogy)
{
    /* The assembly stores (32 - logy) variants; neglogy is what comes in.
     * In practice the caller passes "32 - logy" as the shift amount. */
    vl_shift = neglogy;
}

void prosetupvlineasm(long neglogy)
{
    vl_shift_pro = neglogy;
}

void setupmvlineasm(long neglogy)
{
    mvl_shift = neglogy;
}

void setuptvlineasm(long neglogy)
{
    tvl_shift = neglogy;
}

void setupspritevline(long palookup, long inc, long bufptr, long bpl)
{
    spr_palookup = palookup;
    spr_inc      = inc;
    spr_bufptr   = bufptr;
    spr_bpl      = bpl;
}

void msetupspritevline(long palookup, long inc, long bufptr, long bpl)
{
    mspr_palookup = palookup;
    mspr_inc      = inc;
    mspr_bufptr   = bufptr;
    mspr_bpl      = bpl;
}

void tsetupspritevline(long palookup, long inc, long bufptr, long bpl)
{
    tspr_palookup = palookup;
    tspr_inc      = inc;
    tspr_bufptr   = bufptr;
    tspr_bpl      = bpl;
}

void msethlineshift(long logx, long logy)
{
    mhl_logx = logx;
    mhl_logy = logy;
}

void tsethlineshift(long logx, long logy)
{
    thl_logx = logx;
    thl_logy = logy;
}

void setuptvlineasm2(long shade, long palookup)
{
    tv2_shade    = shade;
    tv2_palookup = palookup;
}

void setupslopevlin(long logylogx, long bufptr, long shade)
{
    slp_logylogx = logylogx;
    slp_bufptr   = bufptr;
    slp_shade    = shade;
}

void setupslopevlin2(long logylogx, long bufptr, long shade)
{
    slp2_logylogx = logylogx;
    slp2_bufptr   = bufptr;
    slp2_shade    = shade;
}

void setuprhlineasm4(long shift)  { rhl_shift  = shift; }
void setuprmhlineasm4(long shift) { rmhl_shift = shift; }
void setupqrhlineasm4(long shift) { qrhl_shift = shift; }

void setupdrawslab(long shift)
{
    dslab_shift = shift;
}

void fixtransluscence(long transptr)
{
    trans_table = (char *)(intptr_t)transptr;
}

void settransnormal(void)
{
    trans_reverse = 0;
}

void settransreverse(void)
{
    trans_reverse = 1;
}

/* ================================================================
 * Vertical-line renderers
 * ================================================================ */

/*
 * prevlineasm1 – draw a single pixel (degenerate case when cnt==0
 * in the caller).  Some callers rely on this returning vplc.
 */
long prevlineasm1(long vinc, long shade, long cnt, long vplc,
                  long bufptr, long destptr)
{
    unsigned char *buf  = LP(bufptr);
    unsigned char *pal  = LP(shade);
    unsigned char *dest = LP(destptr);

    (void)cnt; /* typically 0 */
    unsigned char texel = buf[(unsigned long)vplc >> vl_shift];
    *dest = pal[texel];
    vplc += vinc;
    return vplc;
}

/*
 * vlineasm1 – textured vertical column (walls).
 * Parameters follow Watcom register calling convention:
 *   eax=vinc, ebx=shade(=palookup+offset), ecx=cnt, edx=vplc,
 *   esi=bufptr, edi=destptr
 */
long vlineasm1(long vinc, long shade, long cnt, long vplc,
               long bufptr, long destptr)
{
    unsigned char *buf  = LP(bufptr);
    unsigned char *pal  = LP(shade);
    unsigned char *dest = LP(destptr);
    long bpl = vl_bpl;
    long shift = vl_shift;

    for (long i = cnt; i >= 0; i--) {
        *dest = pal[buf[(unsigned long)vplc >> shift]];
        dest += bpl;
        vplc += vinc;
    }
    return vplc;
}

/* Masked vertical line – skip texel 255 (transparent) */
long mvlineasm1(long vinc, long shade, long cnt, long vplc,
                long bufptr, long destptr)
{
    unsigned char *buf  = LP(bufptr);
    unsigned char *pal  = LP(shade);
    unsigned char *dest = LP(destptr);
    long bpl = vl_bpl;
    long shift = mvl_shift;

    for (long i = cnt; i >= 0; i--) {
        unsigned char texel = buf[(unsigned long)vplc >> shift];
        if (texel != 255)
            *dest = pal[texel];
        dest += bpl;
        vplc += vinc;
    }
    return vplc;
}

/* Translucent + masked vertical line */
long tvlineasm1(long vinc, long shade, long cnt, long vplc,
                long bufptr, long destptr)
{
    unsigned char *buf  = LP(bufptr);
    unsigned char *pal  = LP(shade);
    unsigned char *dest = LP(destptr);
    long bpl = vl_bpl;
    long shift = tvl_shift;

    for (long i = cnt; i >= 0; i--) {
        unsigned char texel = buf[(unsigned long)vplc >> shift];
        if (texel != 255) {
            unsigned char src_col = pal[texel];
            unsigned char dst_col = *dest;
            if (trans_table) {
                if (trans_reverse)
                    *dest = (unsigned char)trans_table[(dst_col << 8) | src_col];
                else
                    *dest = (unsigned char)trans_table[(src_col << 8) | dst_col];
            } else {
                *dest = src_col;
            }
        }
        dest += bpl;
        vplc += vinc;
    }
    return vplc;
}

/* ================================================================
 * 4-column vertical-line renderers
 * ================================================================ */

/*
 * vlineasm4 – render 4 wall columns simultaneously.
 * Uses global arrays: vplce[], vince[], palookupoffse[], bufplce[].
 * cnt = number of rows, destptr = start of first destination pixel.
 */
void vlineasm4(long cnt, long destptr)
{
    unsigned char *dest = LP(destptr);
    long shift = vl_shift;
    long bpl = vl_bpl;

    long p0 = vplce[0], p1 = vplce[1], p2 = vplce[2], p3 = vplce[3];
    long i0 = vince[0], i1 = vince[1], i2 = vince[2], i3 = vince[3];
    unsigned char *b0 = LP(bufplce[0]), *b1 = LP(bufplce[1]);
    unsigned char *b2 = LP(bufplce[2]), *b3 = LP(bufplce[3]);
    unsigned char *l0 = LP(palookupoffse[0]), *l1 = LP(palookupoffse[1]);
    unsigned char *l2 = LP(palookupoffse[2]), *l3 = LP(palookupoffse[3]);

    for (long i = cnt; i >= 0; i--) {
        dest[0] = l0[b0[(unsigned long)p0 >> shift]];
        dest[1] = l1[b1[(unsigned long)p1 >> shift]];
        dest[2] = l2[b2[(unsigned long)p2 >> shift]];
        dest[3] = l3[b3[(unsigned long)p3 >> shift]];
        dest += bpl;
        p0 += i0; p1 += i1; p2 += i2; p3 += i3;
    }

    vplce[0] = p0; vplce[1] = p1; vplce[2] = p2; vplce[3] = p3;
}

/* "pro" variant – identical algorithm, uses pro shift */
void provlineasm4(long cnt, long destptr)
{
    unsigned char *dest = LP(destptr);
    long shift = vl_shift_pro;
    long bpl = vl_bpl;

    long p0 = vplce[0], p1 = vplce[1], p2 = vplce[2], p3 = vplce[3];
    long i0 = vince[0], i1 = vince[1], i2 = vince[2], i3 = vince[3];
    unsigned char *b0 = LP(bufplce[0]), *b1 = LP(bufplce[1]);
    unsigned char *b2 = LP(bufplce[2]), *b3 = LP(bufplce[3]);
    unsigned char *l0 = LP(palookupoffse[0]), *l1 = LP(palookupoffse[1]);
    unsigned char *l2 = LP(palookupoffse[2]), *l3 = LP(palookupoffse[3]);

    for (long i = cnt; i >= 0; i--) {
        dest[0] = l0[b0[(unsigned long)p0 >> shift]];
        dest[1] = l1[b1[(unsigned long)p1 >> shift]];
        dest[2] = l2[b2[(unsigned long)p2 >> shift]];
        dest[3] = l3[b3[(unsigned long)p3 >> shift]];
        dest += bpl;
        p0 += i0; p1 += i1; p2 += i2; p3 += i3;
    }

    vplce[0] = p0; vplce[1] = p1; vplce[2] = p2; vplce[3] = p3;
}

/* Masked 4-column vertical line – skip texel 255 */
void mvlineasm4(long cnt, long destptr)
{
    unsigned char *dest = LP(destptr);
    long shift = mvl_shift;
    long bpl = vl_bpl;

    long p0 = vplce[0], p1 = vplce[1], p2 = vplce[2], p3 = vplce[3];
    long i0 = vince[0], i1 = vince[1], i2 = vince[2], i3 = vince[3];
    unsigned char *b0 = LP(bufplce[0]), *b1 = LP(bufplce[1]);
    unsigned char *b2 = LP(bufplce[2]), *b3 = LP(bufplce[3]);
    unsigned char *l0 = LP(palookupoffse[0]), *l1 = LP(palookupoffse[1]);
    unsigned char *l2 = LP(palookupoffse[2]), *l3 = LP(palookupoffse[3]);

    for (long i = cnt; i >= 0; i--) {
        unsigned char t;
        t = b0[(unsigned long)p0 >> shift]; if (t != 255) dest[0] = l0[t];
        t = b1[(unsigned long)p1 >> shift]; if (t != 255) dest[1] = l1[t];
        t = b2[(unsigned long)p2 >> shift]; if (t != 255) dest[2] = l2[t];
        t = b3[(unsigned long)p3 >> shift]; if (t != 255) dest[3] = l3[t];
        dest += bpl;
        p0 += i0; p1 += i1; p2 += i2; p3 += i3;
    }

    vplce[0] = p0; vplce[1] = p1; vplce[2] = p2; vplce[3] = p3;
}

/* ================================================================
 * Horizontal-line renderers (floor / ceiling spans)
 * ================================================================ */

/*
 * hlineasm4 – textured horizontal span.
 * cnt = number of pixels - 1 (drawn right-to-left).
 * bx,by = texture coordinates (fixed-point).
 * shade = palookup + shade offset, pal unused (it is shade).
 */
void hlineasm4(long cnt, long shade, long pal, long bx, long by,
               long destptr)
{
    unsigned char *buf  = LP(hl_bufptr);
    unsigned char *lut  = LP(shade);
    unsigned char *dest = LP(destptr);
    long logx = hl_logx;
    long logy = hl_logy;
    long xinc = asm1;   /* stored by caller */
    long yinc = asm2;

    (void)pal; /* shade already incorporates palette */

    for (long i = cnt; i >= 0; i--) {
        unsigned long tx = ((unsigned long)bx >> (32 - logx)) & ((1 << logx) - 1);
        unsigned long ty = ((unsigned long)by >> (32 - logy)) & ((1 << logy) - 1);
        unsigned long idx = (tx << logy) + ty;
        *dest = lut[buf[idx]];
        dest--;
        bx -= xinc;
        by -= yinc;
    }
}

/* "pro" horizontal line – uses progressive shift state */
void prohlineasm4(long cnt, long shade, long pal, long bx, long by,
                  long destptr)
{
    unsigned char *buf  = LP(prohl_bufptr);
    unsigned char *lut  = LP(shade);
    unsigned char *dest = LP(destptr);
    long xinc = asm1;
    long yinc = asm2;

    (void)pal;

    for (long i = cnt; i >= 0; i--) {
        unsigned long combined = (unsigned long)(bx) >> prohl_shru;
        unsigned long idx = combined & prohl_mask;
        idx |= ((unsigned long)(by) >> prohl_shrv);
        *dest = lut[buf[idx]];
        dest--;
        bx -= xinc;
        by -= yinc;
    }
}

/* ================================================================
 * Sprite vertical-line renderers
 * ================================================================ */

void spritevline(long bx, long cnt, long destptr)
{
    unsigned char *pal  = LP(spr_palookup);
    unsigned char *buf  = LP(spr_bufptr);
    unsigned char *dest = LP(destptr);
    long inc = spr_inc;
    long bpl = spr_bpl;

    for (long i = 0; i < cnt; i++) {
        unsigned char texel = buf[(unsigned long)bx >> 16];
        *dest = pal[texel];
        dest += bpl;
        bx += inc;
    }
}

void mspritevline(long bx, long cnt, long destptr)
{
    unsigned char *pal  = LP(mspr_palookup);
    unsigned char *buf  = LP(mspr_bufptr);
    unsigned char *dest = LP(destptr);
    long inc = mspr_inc;
    long bpl = mspr_bpl;

    for (long i = 0; i < cnt; i++) {
        unsigned char texel = buf[(unsigned long)bx >> 16];
        if (texel != 255)
            *dest = pal[texel];
        dest += bpl;
        bx += inc;
    }
}

void tspritevline(long bx, long cnt, long destptr)
{
    unsigned char *pal  = LP(tspr_palookup);
    unsigned char *buf  = LP(tspr_bufptr);
    unsigned char *dest = LP(destptr);
    long inc = tspr_inc;
    long bpl = tspr_bpl;

    for (long i = 0; i < cnt; i++) {
        unsigned char texel = buf[(unsigned long)bx >> 16];
        if (texel != 255) {
            unsigned char src_col = pal[texel];
            unsigned char dst_col = *dest;
            if (trans_table) {
                if (trans_reverse)
                    *dest = (unsigned char)trans_table[(dst_col << 8) | src_col];
                else
                    *dest = (unsigned char)trans_table[(src_col << 8) | dst_col];
            } else {
                *dest = src_col;
            }
        }
        dest += bpl;
        bx += inc;
    }
}

/* ================================================================
 * Masked / translucent horizontal-line renderers
 * ================================================================ */

static void mhline_inner(long bufptr, long bx, long cnt, long by,
                          long destptr, long logx, long logy)
{
    unsigned char *buf  = LP(bufptr);
    unsigned char *pal  = LP(asm3);   /* shade/palette offset */
    unsigned char *dest = LP(destptr);
    long xinc = asm1;
    long yinc = asm2;

    for (long i = cnt; i >= 0; i--) {
        unsigned long tx = ((unsigned long)bx >> (32 - logx)) & ((1 << logx) - 1);
        unsigned long ty = ((unsigned long)by >> (32 - logy)) & ((1 << logy) - 1);
        unsigned long idx = (tx << logy) + ty;
        unsigned char texel = buf[idx];
        if (texel != 255)
            *dest = pal[texel];
        dest++;
        bx += xinc;
        by += yinc;
    }
}

void mhline(long bufptr, long bx, long cnt, long by, long destptr)
{
    mhline_inner(bufptr, bx, cnt >> 16, by, destptr, mhl_logx, mhl_logy);
}

void mhlineskipmodify(long bufptr, long bx, long cnt, long by, long destptr)
{
    mhline_inner(bufptr, bx, cnt >> 16, by, destptr, mhl_logx, mhl_logy);
}

static void thline_inner(long bufptr, long bx, long cnt, long by,
                          long destptr, long logx, long logy)
{
    unsigned char *buf  = LP(bufptr);
    unsigned char *pal  = LP(asm3);
    unsigned char *dest = LP(destptr);
    long xinc = asm1;
    long yinc = asm2;

    for (long i = cnt; i >= 0; i--) {
        unsigned long tx = ((unsigned long)bx >> (32 - logx)) & ((1 << logx) - 1);
        unsigned long ty = ((unsigned long)by >> (32 - logy)) & ((1 << logy) - 1);
        unsigned long idx = (tx << logy) + ty;
        unsigned char texel = buf[idx];
        if (texel != 255) {
            unsigned char src_col = pal[texel];
            unsigned char dst_col = *dest;
            if (trans_table) {
                if (trans_reverse)
                    *dest = (unsigned char)trans_table[(dst_col << 8) | src_col];
                else
                    *dest = (unsigned char)trans_table[(src_col << 8) | dst_col];
            } else {
                *dest = src_col;
            }
        }
        dest++;
        bx += xinc;
        by += yinc;
    }
}

void thline(long bufptr, long bx, long cnt, long by, long destptr)
{
    thline_inner(bufptr, bx, cnt >> 16, by, destptr, thl_logx, thl_logy);
}

void thlineskipmodify(long bufptr, long bx, long cnt, long by, long destptr)
{
    thline_inner(bufptr, bx, cnt >> 16, by, destptr, thl_logx, thl_logy);
}

/* ================================================================
 * Dual translucent vertical line (tvlineasm2)
 *
 * Renders two interleaved translucent columns: column 0 at dest[0],
 * column 1 at dest[1], advancing by vl_bpl each row.
 * ================================================================ */

void tvlineasm2(long cnt, long destptr)
{
    unsigned char *dest = LP(destptr);
    long bpl = vl_bpl;
    unsigned char *pal = LP(tv2_palookup);

    long p0 = vplce[0], p1 = vplce[1];
    long i0 = vince[0], i1 = asm1;
    unsigned char *b0 = LP(bufplce[0]), *b1 = LP(bufplce[1]);
    long shift = tvl_shift;

    for (long i = cnt; i >= 0; i--) {
        unsigned char t0 = b0[(unsigned long)p0 >> shift];
        unsigned char t1 = b1[(unsigned long)p1 >> shift];

        if (t0 != 255) {
            unsigned char src = pal[t0];
            unsigned char dst_col = dest[0];
            if (trans_table) {
                if (trans_reverse)
                    dest[0] = (unsigned char)trans_table[(dst_col << 8) | src];
                else
                    dest[0] = (unsigned char)trans_table[(src << 8) | dst_col];
            } else {
                dest[0] = src;
            }
        }
        if (t1 != 255) {
            unsigned char src = pal[t1];
            unsigned char dst_col = dest[1];
            if (trans_table) {
                if (trans_reverse)
                    dest[1] = (unsigned char)trans_table[(dst_col << 8) | src];
                else
                    dest[1] = (unsigned char)trans_table[(src << 8) | dst_col];
            } else {
                dest[1] = src;
            }
        }
        dest += bpl;
        p0 += i0;
        p1 += i1;
    }

    asm1 = p0;   /* store updated positions for caller */
    asm2 = p1;
}

/* ================================================================
 * Slope renderers (perspective-correct floor/ceiling)
 * ================================================================ */

void slopevlin(long destptr, long cnt, long *slopalptr, long shade)
{
    unsigned char *dest = LP(destptr);
    unsigned char *pal  = LP(shade);
    long bpl = vl_bpl;
    long logy = slp_logylogx & 0xFFFF;
    long logx = (slp_logylogx >> 16) & 0xFFFF;
    unsigned char *buf = LP(slp_bufptr);

    for (long i = 0; i < cnt; i++) {
        long sx = slopalptr[i * 2 + 0];
        long sy = slopalptr[i * 2 + 1];
        unsigned long tx = ((unsigned long)sx >> (32 - logx)) & ((1 << logx) - 1);
        unsigned long ty = ((unsigned long)sy >> (32 - logy)) & ((1 << logy) - 1);
        unsigned long idx = (tx << logy) + ty;
        *dest = pal[buf[idx]];
        dest += bpl;
    }
}

void slopevlin2(long destptr, long cnt, long *slopalptr, long shade)
{
    unsigned char *dest = LP(destptr);
    unsigned char *pal  = LP(shade);
    long bpl = vl_bpl;
    long logy = slp2_logylogx & 0xFFFF;
    long logx = (slp2_logylogx >> 16) & 0xFFFF;
    unsigned char *buf = LP(slp2_bufptr);

    for (long i = 0; i < cnt; i++) {
        long sx = slopalptr[i * 2 + 0];
        long sy = slopalptr[i * 2 + 1];
        unsigned long tx = ((unsigned long)sx >> (32 - logx)) & ((1 << logx) - 1);
        unsigned long ty = ((unsigned long)sy >> (32 - logy)) & ((1 << logy) - 1);
        unsigned long idx = (tx << logy) + ty;
        *dest = pal[buf[idx]];
        dest += bpl;
    }
}

/* ================================================================
 * Non-power-of-2 / reverse horizontal line renderers
 * ================================================================ */

void rhlineasm4(long cnt, long destptr)
{
    unsigned char *dest = LP(destptr);
    unsigned char *buf  = LP(asm3);
    unsigned char *pal  = LP(vl_palookup);
    long bx = asm1, by = asm2;
    long xinc = globalx3, yinc = globaly3;
    long shift = rhl_shift;

    for (long i = cnt; i >= 0; i--) {
        unsigned long idx = (unsigned long)(bx + by) >> shift;
        *dest = pal[buf[idx]];
        dest--;
        bx += xinc;
        by += yinc;
    }
}

void rmhlineasm4(long cnt, long destptr)
{
    unsigned char *dest = LP(destptr);
    unsigned char *buf  = LP(asm3);
    unsigned char *pal  = LP(vl_palookup);
    long bx = asm1, by = asm2;
    long xinc = globalx3, yinc = globaly3;
    long shift = rmhl_shift;

    for (long i = cnt; i >= 0; i--) {
        unsigned long idx = (unsigned long)(bx + by) >> shift;
        unsigned char texel = buf[idx];
        if (texel != 255)
            *dest = pal[texel];
        dest--;
        bx += xinc;
        by += yinc;
    }
}

void qrhlineasm4(long cnt, long destptr)
{
    unsigned char *dest = LP(destptr);
    unsigned char *buf  = LP(asm3);
    unsigned char *pal  = LP(vl_palookup);
    long bx = asm1, by = asm2;
    long xinc = globalx3, yinc = globaly3;
    long shift = qrhl_shift;

    for (long i = cnt; i >= 0; i--) {
        unsigned long idx = (unsigned long)(bx + by) >> shift;
        *dest = pal[buf[idx]];
        dest--;
        bx += xinc;
        by += yinc;
    }
}

/* ================================================================
 * Voxel slab renderer
 * ================================================================ */

void drawslab(long dx, long vplc, long vinc, long destptr, long cnt)
{
    unsigned char *pal  = LP(asm3);
    unsigned char *buf  = LP(asm1);
    unsigned char *dest = LP(destptr);
    long bpl = vl_bpl;

    for (long row = 0; row < cnt; row++) {
        unsigned char texel = buf[(unsigned long)vplc >> dslab_shift];
        unsigned char color = pal[texel];
        /* Fill dx pixels horizontally */
        memset(dest, color, (size_t)dx);
        dest += bpl;
        vplc += vinc;
    }
}

/* ================================================================
 * Stretched horizontal line (for voxels / scaled sprites)
 * ================================================================ */

void stretchhline(long srcptr, long dest, long cnt, long xfrac, long xinc)
{
    unsigned char *src = LP(srcptr);
    unsigned char *dst = LP(dest);
    unsigned char *pal = LP(asm3);

    for (long i = 0; i < cnt; i++) {
        unsigned char texel = src[(unsigned long)xfrac >> 16];
        *dst = pal[texel];
        dst++;
        xfrac += xinc;
    }
}

/* ================================================================
 * Stubs / no-ops
 * ================================================================ */

void mmxoverlay(void)
{
    /* MMX detection/overlay – not needed in C port */
}

/* ================================================================
 * Watcom-register-convention aliases
 *
 * The BUILD engine calls these with trailing underscores (Watcom
 * name mangling).  We provide both names.
 * ================================================================ */

/* Setup functions */
void sethlinesizes_(long a, long b, long c) { sethlinesizes(a,b,c); }
void prosethlinesizes_(long a, long b, long c) { prosethlinesizes(a,b,c); }
void setvlinebpl_(long a) { setvlinebpl(a); }
void setpalookupaddress_(long a) { setpalookupaddress(a); }
void prosetpalookupaddress_(long a) { prosetpalookupaddress(a); }
void setuphlineasm4_(long a) { setuphlineasm4(a); }
void setupvlineasm_(long a) { setupvlineasm(a); }
void prosetupvlineasm_(long a) { prosetupvlineasm(a); }
void setupmvlineasm_(long a) { setupmvlineasm(a); }
void setuptvlineasm_(long a) { setuptvlineasm(a); }
void setupspritevline_(long a, long b, long c, long d) { setupspritevline(a,b,c,d); }
void msetupspritevline_(long a, long b, long c, long d) { msetupspritevline(a,b,c,d); }
void tsetupspritevline_(long a, long b, long c, long d) { tsetupspritevline(a,b,c,d); }
void msethlineshift_(long a, long b) { msethlineshift(a,b); }
void tsethlineshift_(long a, long b) { tsethlineshift(a,b); }
void setuptvlineasm2_(long a, long b) { setuptvlineasm2(a,b); }
void setupslopevlin_(long a, long b, long c) { setupslopevlin(a,b,c); }
void setupslopevlin2_(long a, long b, long c) { setupslopevlin2(a,b,c); }
void setuprhlineasm4_(long a) { setuprhlineasm4(a); }
void setuprmhlineasm4_(long a) { setuprmhlineasm4(a); }
void setupqrhlineasm4_(long a) { setupqrhlineasm4(a); }
void setupdrawslab_(long a) { setupdrawslab(a); }
void fixtransluscence_(long a) { fixtransluscence(a); }
void settransnormal_(void) { settransnormal(); }
void settransreverse_(void) { settransreverse(); }

/* Drawing functions */
long prevlineasm1_(long a, long b, long c, long d, long e, long f)
    { return prevlineasm1(a,b,c,d,e,f); }
long vlineasm1_(long a, long b, long c, long d, long e, long f)
    { return vlineasm1(a,b,c,d,e,f); }
long mvlineasm1_(long a, long b, long c, long d, long e, long f)
    { return mvlineasm1(a,b,c,d,e,f); }
long tvlineasm1_(long a, long b, long c, long d, long e, long f)
    { return tvlineasm1(a,b,c,d,e,f); }

void hlineasm4_(long a, long b, long c, long d, long e, long f)
    { hlineasm4(a,b,c,d,e,f); }
void prohlineasm4_(long a, long b, long c, long d, long e, long f)
    { prohlineasm4(a,b,c,d,e,f); }
void vlineasm4_(long a, long b) { vlineasm4(a,b); }
void provlineasm4_(long a, long b) { provlineasm4(a,b); }
void mvlineasm4_(long a, long b) { mvlineasm4(a,b); }
void tvlineasm2_(long a, long b) { tvlineasm2(a,b); }

void spritevline_(long a, long b, long c) { spritevline(a,b,c); }
void mspritevline_(long a, long b, long c) { mspritevline(a,b,c); }
void tspritevline_(long a, long b, long c) { tspritevline(a,b,c); }

void mhline_(long a, long b, long c, long d, long e) { mhline(a,b,c,d,e); }
void mhlineskipmodify_(long a, long b, long c, long d, long e) { mhlineskipmodify(a,b,c,d,e); }
void thline_(long a, long b, long c, long d, long e) { thline(a,b,c,d,e); }
void thlineskipmodify_(long a, long b, long c, long d, long e) { thlineskipmodify(a,b,c,d,e); }

void slopevlin_(long a, long b, long *c, long d) { slopevlin(a,b,c,d); }
void slopevlin2_(long a, long b, long *c, long d) { slopevlin2(a,b,c,d); }

void rhlineasm4_(long a, long b) { rhlineasm4(a,b); }
void rmhlineasm4_(long a, long b) { rmhlineasm4(a,b); }
void qrhlineasm4_(long a, long b) { qrhlineasm4(a,b); }

void drawslab_(long a, long b, long c, long d, long e) { drawslab(a,b,c,d,e); }
void stretchhline_(long a, long b, long c, long d, long e) { stretchhline(a,b,c,d,e); }
void mmxoverlay_(void) { mmxoverlay(); }
