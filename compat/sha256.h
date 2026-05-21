/* sha256.h -- Minimal public-domain SHA-256 / HMAC-SHA256 / HKDF-SHA256
 *
 * net-r17-hmac: HMAC-SHA256 + HKDF for per-session player authentication.
 * HKDF context: "AUTH_SPOOFING_V1" (RFC 5869, no pre-shared secret).
 *
 * Based on Brad Conte's public-domain SHA-256 (B-Con/crypto-algorithms).
 * HMAC: RFC 2104.  HKDF: RFC 5869.
 *
 * C89-compatible declarations (no C99 designated initialisers, no inline).
 * sha256.c is compiled as gnu11 (compat layer); this header is safe to
 * include from gnu89 translation units (SRC/MMULTI.C).
 *
 * This file is placed in the public domain.
 */

#ifndef SHA256_H
#define SHA256_H

#include <stdint.h>   /* uint8_t, uint32_t, uint64_t -- available in GCC gnu89 */
#include <stddef.h>   /* size_t */

#ifdef __cplusplus
extern "C" {
#endif

/* ---- Sizes ---- */
#define SHA256_BLOCK_SIZE  64
#define SHA256_DIGEST_SIZE 32
#define HMAC_SHA256_SIZE   32

/* ---- SHA-256 context ---- */
typedef struct {
    uint8_t  data[64];
    uint32_t datalen;   /* bytes buffered in current (incomplete) block */
    uint64_t bitlen;    /* total bits hashed so far (complete blocks only) */
    uint32_t state[8];
} sha256_ctx_t;

/* ---- SHA-256 ---- */
void sha256_init   (sha256_ctx_t *ctx);
void sha256_update (sha256_ctx_t *ctx, const uint8_t *data, size_t len);
void sha256_final  (sha256_ctx_t *ctx, uint8_t digest[SHA256_DIGEST_SIZE]);

/* One-shot convenience wrapper */
void sha256_oneshot(const uint8_t *data, size_t len,
                    uint8_t digest[SHA256_DIGEST_SIZE]);

/* ---- HMAC-SHA256 (RFC 2104) ---- */
void hmac_sha256(const uint8_t *key,  size_t key_len,
                 const uint8_t *msg,  size_t msg_len,
                 uint8_t        out[HMAC_SHA256_SIZE]);

/* ---- HKDF-SHA256 (RFC 5869) ---- */
/*
 * HKDF-Extract then HKDF-Expand.
 * salt    : optional (pass NULL / 0 for HashLen-zeros default per RFC 5869 §2.2)
 * ikm     : input keying material
 * info    : context / application-specific binding string
 * okm     : output buffer of exactly okm_len bytes
 * okm_len : requested output length, must be <= 255 * HMAC_SHA256_SIZE
 */
void hkdf_sha256(const uint8_t *salt,    size_t salt_len,
                 const uint8_t *ikm,     size_t ikm_len,
                 const uint8_t *info,    size_t info_len,
                 uint8_t       *okm,     size_t okm_len);

/* ---- Constant-time comparison ---- */
/*
 * Returns 0 iff the first `len` bytes of `a` and `b` are identical.
 * Timing is independent of the content of `a` and `b` (no early exit).
 */
int hmac_sha256_verify_ct(const uint8_t *a, const uint8_t *b, size_t len);

#ifdef __cplusplus
}
#endif

#endif /* SHA256_H */
