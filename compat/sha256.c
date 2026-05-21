/* sha256.c -- Minimal public-domain SHA-256 / HMAC-SHA256 / HKDF-SHA256
 *
 * net-r17-hmac: SHA-256 core + HMAC + HKDF for MMULTI.C player authentication.
 *
 * SHA-256 core based on Brad Conte's public-domain implementation
 * (https://github.com/B-Con/crypto-algorithms, commit 2b8c40c).
 * HMAC construction: RFC 2104.
 * HKDF construction: RFC 5869.
 *
 * Compile with -std=gnu11 (compat layer) or -std=gnu89 (engine layer).
 * No dynamic allocation.  No external dependencies beyond <string.h>.
 *
 * This file is placed in the public domain.
 */

#include "sha256.h"
#include <string.h>

/* ============================================================
 * SHA-256 core
 * ============================================================ */

/* Round constants: first 32 bits of the fractional parts of the
 * cube roots of the first 64 prime numbers (FIPS 180-4 §4.2.2). */
static const uint32_t K256[64] = {
    0x428a2f98UL, 0x71374491UL, 0xb5c0fbcfUL, 0xe9b5dba5UL,
    0x3956c25bUL, 0x59f111f1UL, 0x923f82a4UL, 0xab1c5ed5UL,
    0xd807aa98UL, 0x12835b01UL, 0x243185beUL, 0x550c7dc3UL,
    0x72be5d74UL, 0x80deb1feUL, 0x9bdc06a7UL, 0xc19bf174UL,
    0xe49b69c1UL, 0xefbe4786UL, 0x0fc19dc6UL, 0x240ca1ccUL,
    0x2de92c6fUL, 0x4a7484aaUL, 0x5cb0a9dcUL, 0x76f988daUL,
    0x983e5152UL, 0xa831c66dUL, 0xb00327c8UL, 0xbf597fc7UL,
    0xc6e00bf3UL, 0xd5a79147UL, 0x06ca6351UL, 0x14292967UL,
    0x27b70a85UL, 0x2e1b2138UL, 0x4d2c6dfcUL, 0x53380d13UL,
    0x650a7354UL, 0x766a0abbUL, 0x81c2c92eUL, 0x92722c85UL,
    0xa2bfe8a1UL, 0xa81a664bUL, 0xc24b8b70UL, 0xc76c51a3UL,
    0xd192e819UL, 0xd6990624UL, 0xf40e3585UL, 0x106aa070UL,
    0x19a4c116UL, 0x1e376c08UL, 0x2748774cUL, 0x34b0bcb5UL,
    0x391c0cb3UL, 0x4ed8aa4aUL, 0x5b9cca4fUL, 0x682e6ff3UL,
    0x748f82eeUL, 0x78a5636fUL, 0x84c87814UL, 0x8cc70208UL,
    0x90befffaUL, 0xa4506cebUL, 0xbef9a3f7UL, 0xc67178f2UL
};

#define ROTR32(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
#define S0(x) (ROTR32((x), 2)  ^ ROTR32((x), 13) ^ ROTR32((x), 22))
#define S1(x) (ROTR32((x), 6)  ^ ROTR32((x), 11) ^ ROTR32((x), 25))
#define s0(x) (ROTR32((x), 7)  ^ ROTR32((x), 18) ^ ((x) >> 3))
#define s1(x) (ROTR32((x), 17) ^ ROTR32((x), 19) ^ ((x) >> 10))
#define CH(x, y, z)  (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))

static void sha256_transform(sha256_ctx_t *ctx, const uint8_t *blk)
{
    uint32_t a, b, c, d, e, f, g, h, t1, t2;
    uint32_t w[64];
    int i;

    /* Load message schedule (big-endian 32-bit words) */
    for (i = 0; i < 16; i++) {
        w[i] = ((uint32_t)blk[i * 4    ] << 24)
             | ((uint32_t)blk[i * 4 + 1] << 16)
             | ((uint32_t)blk[i * 4 + 2] <<  8)
             | ((uint32_t)blk[i * 4 + 3]      );
    }
    for (i = 16; i < 64; i++) {
        w[i] = s1(w[i - 2]) + w[i - 7] + s0(w[i - 15]) + w[i - 16];
    }

    /* Initialise working variables */
    a = ctx->state[0]; b = ctx->state[1];
    c = ctx->state[2]; d = ctx->state[3];
    e = ctx->state[4]; f = ctx->state[5];
    g = ctx->state[6]; h = ctx->state[7];

    /* 64 rounds */
    for (i = 0; i < 64; i++) {
        t1 = h + S1(e) + CH(e, f, g) + K256[i] + w[i];
        t2 = S0(a) + MAJ(a, b, c);
        h = g;  g = f;  f = e;  e = d + t1;
        d = c;  c = b;  b = a;  a = t1 + t2;
    }

    ctx->state[0] += a; ctx->state[1] += b;
    ctx->state[2] += c; ctx->state[3] += d;
    ctx->state[4] += e; ctx->state[5] += f;
    ctx->state[6] += g; ctx->state[7] += h;
}

void sha256_init(sha256_ctx_t *ctx)
{
    ctx->datalen  = 0;
    ctx->bitlen   = 0;
    /* Initial hash values: first 32 bits of fractional parts of
     * square roots of the first 8 primes (FIPS 180-4 §5.3.3). */
    ctx->state[0] = 0x6a09e667UL;
    ctx->state[1] = 0xbb67ae85UL;
    ctx->state[2] = 0x3c6ef372UL;
    ctx->state[3] = 0xa54ff53aUL;
    ctx->state[4] = 0x510e527fUL;
    ctx->state[5] = 0x9b05688cUL;
    ctx->state[6] = 0x1f83d9abUL;
    ctx->state[7] = 0x5be0cd19UL;
}

void sha256_update(sha256_ctx_t *ctx, const uint8_t *data, size_t len)
{
    size_t i;
    for (i = 0; i < len; i++) {
        ctx->data[ctx->datalen] = data[i];
        ctx->datalen++;
        if (ctx->datalen == 64) {
            sha256_transform(ctx, ctx->data);
            ctx->bitlen += 512;
            ctx->datalen = 0;
        }
    }
}

void sha256_final(sha256_ctx_t *ctx, uint8_t digest[SHA256_DIGEST_SIZE])
{
    uint32_t rem;  /* remaining bytes in current block */
    uint32_t i;

    rem = ctx->datalen;

    /* Pad: 1-bit followed by zeros, then 64-bit big-endian bit count */
    ctx->data[rem++] = 0x80;
    if (rem <= 56) {
        while (rem < 56)
            ctx->data[rem++] = 0x00;
    } else {
        while (rem < 64)
            ctx->data[rem++] = 0x00;
        sha256_transform(ctx, ctx->data);
        memset(ctx->data, 0, 56);
    }

    /* Total bit count (big-endian 64-bit) */
    ctx->bitlen += (uint64_t)ctx->datalen * 8ULL;
    ctx->data[56] = (uint8_t)(ctx->bitlen >> 56);
    ctx->data[57] = (uint8_t)(ctx->bitlen >> 48);
    ctx->data[58] = (uint8_t)(ctx->bitlen >> 40);
    ctx->data[59] = (uint8_t)(ctx->bitlen >> 32);
    ctx->data[60] = (uint8_t)(ctx->bitlen >> 24);
    ctx->data[61] = (uint8_t)(ctx->bitlen >> 16);
    ctx->data[62] = (uint8_t)(ctx->bitlen >>  8);
    ctx->data[63] = (uint8_t)(ctx->bitlen      );
    sha256_transform(ctx, ctx->data);

    /* Write digest (big-endian 32-bit words) */
    for (i = 0; i < 4; i++) {
        digest[i     ] = (uint8_t)(ctx->state[0] >> (24 - i * 8));
        digest[i +  4] = (uint8_t)(ctx->state[1] >> (24 - i * 8));
        digest[i +  8] = (uint8_t)(ctx->state[2] >> (24 - i * 8));
        digest[i + 12] = (uint8_t)(ctx->state[3] >> (24 - i * 8));
        digest[i + 16] = (uint8_t)(ctx->state[4] >> (24 - i * 8));
        digest[i + 20] = (uint8_t)(ctx->state[5] >> (24 - i * 8));
        digest[i + 24] = (uint8_t)(ctx->state[6] >> (24 - i * 8));
        digest[i + 28] = (uint8_t)(ctx->state[7] >> (24 - i * 8));
    }
}

void sha256_oneshot(const uint8_t *data, size_t len,
                    uint8_t digest[SHA256_DIGEST_SIZE])
{
    sha256_ctx_t ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, data, len);
    sha256_final(&ctx, digest);
}

/* ============================================================
 * HMAC-SHA256 (RFC 2104)
 * ============================================================ */

void hmac_sha256(const uint8_t *key,  size_t key_len,
                 const uint8_t *msg,  size_t msg_len,
                 uint8_t        out[HMAC_SHA256_SIZE])
{
    uint8_t k_ipad[SHA256_BLOCK_SIZE]; /* K XOR ipad */
    uint8_t k_opad[SHA256_BLOCK_SIZE]; /* K XOR opad */
    uint8_t inner[SHA256_DIGEST_SIZE];
    sha256_ctx_t ctx;
    size_t i;

    /* 1. Normalise key */
    if (key_len > SHA256_BLOCK_SIZE) {
        /* Keys longer than block size are hashed first */
        sha256_ctx_t kctx;
        sha256_init(&kctx);
        sha256_update(&kctx, key, key_len);
        sha256_final(&kctx, k_ipad);
        memset(k_ipad + SHA256_DIGEST_SIZE, 0,
               SHA256_BLOCK_SIZE - SHA256_DIGEST_SIZE);
    } else {
        memcpy(k_ipad, key, key_len);
        memset(k_ipad + key_len, 0, SHA256_BLOCK_SIZE - key_len);
    }
    memcpy(k_opad, k_ipad, SHA256_BLOCK_SIZE);

    /* 2. Build ipad and opad */
    for (i = 0; i < SHA256_BLOCK_SIZE; i++) {
        k_ipad[i] ^= 0x36;
        k_opad[i] ^= 0x5c;
    }

    /* 3. Inner hash: H((K XOR ipad) || msg) */
    sha256_init(&ctx);
    sha256_update(&ctx, k_ipad, SHA256_BLOCK_SIZE);
    sha256_update(&ctx, msg, msg_len);
    sha256_final(&ctx, inner);

    /* 4. Outer hash: H((K XOR opad) || inner) */
    sha256_init(&ctx);
    sha256_update(&ctx, k_opad, SHA256_BLOCK_SIZE);
    sha256_update(&ctx, inner, SHA256_DIGEST_SIZE);
    sha256_final(&ctx, out);
}

/* ============================================================
 * HKDF-SHA256 (RFC 5869)
 * ============================================================ */

void hkdf_sha256(const uint8_t *salt,    size_t salt_len,
                 const uint8_t *ikm,     size_t ikm_len,
                 const uint8_t *info,    size_t info_len,
                 uint8_t       *okm,     size_t okm_len)
{
    /* Per RFC 5869 §2 the maximum OKM length is 255 * HashLen bytes */
    uint8_t prk[SHA256_DIGEST_SIZE];      /* pseudo-random key from Extract */
    uint8_t zero_salt[SHA256_DIGEST_SIZE]; /* used when no salt supplied */
    uint8_t t_prev[SHA256_DIGEST_SIZE];    /* T(i-1) in Expand */
    /* Expand buffer: T(i-1)[32] + info[<=255] + counter[1] = up to 288 bytes */
    uint8_t expand_buf[SHA256_DIGEST_SIZE + 255 + 1];
    const uint8_t *actual_salt;
    size_t actual_salt_len;
    size_t done;
    uint8_t counter;

    /* ---- Extract ---- */
    if (salt == NULL || salt_len == 0) {
        /* RFC 5869 §2.2: if salt not provided, use HashLen zeros */
        memset(zero_salt, 0, SHA256_DIGEST_SIZE);
        actual_salt     = zero_salt;
        actual_salt_len = SHA256_DIGEST_SIZE;
    } else {
        actual_salt     = salt;
        actual_salt_len = salt_len;
    }
    /* PRK = HMAC-SHA256(salt, IKM) */
    hmac_sha256(actual_salt, actual_salt_len, ikm, ikm_len, prk);

    /* ---- Expand ---- */
    /* T(0)  = "" (empty)
     * T(i)  = HMAC(PRK, T(i-1) || info || i)
     * OKM   = T(1) || T(2) || ... */
    done    = 0;
    counter = 1;
    memset(t_prev, 0, SHA256_DIGEST_SIZE); /* T(0) is empty – treated as 0-len */

    while (done < okm_len) {
        size_t buf_len = 0;
        size_t copy_len;
        uint8_t t_cur[SHA256_DIGEST_SIZE];
        size_t safe_info_len;

        /* Clamp info to 255 bytes to fit the expand_buf */
        safe_info_len = (info_len > 255) ? 255 : info_len;

        if (counter > 1) {
            memcpy(expand_buf, t_prev, SHA256_DIGEST_SIZE);
            buf_len += SHA256_DIGEST_SIZE;
        }
        if (info != NULL && safe_info_len > 0) {
            memcpy(expand_buf + buf_len, info, safe_info_len);
            buf_len += safe_info_len;
        }
        expand_buf[buf_len] = counter;
        buf_len++;

        hmac_sha256(prk, SHA256_DIGEST_SIZE, expand_buf, buf_len, t_cur);
        memcpy(t_prev, t_cur, SHA256_DIGEST_SIZE);

        copy_len = okm_len - done;
        if (copy_len > SHA256_DIGEST_SIZE)
            copy_len = SHA256_DIGEST_SIZE;
        memcpy(okm + done, t_cur, copy_len);
        done += copy_len;
        counter++;
    }
}

/* ============================================================
 * Constant-time comparison
 * ============================================================ */

int hmac_sha256_verify_ct(const uint8_t *a, const uint8_t *b, size_t len)
{
    /* XOR all byte differences into `diff`.  The loop always runs exactly
     * `len` iterations regardless of content, preventing timing side-channels. */
    unsigned char diff = 0;
    size_t i;
    for (i = 0; i < len; i++)
        diff |= a[i] ^ b[i];
    /* Cast to int; 0 == equal, non-zero == different */
    return (int)diff;
}
