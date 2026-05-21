# GRP CRC Enhancement: Future Design & Compatibility Analysis
**Cycle:** 87  
**Asset Pipeline Engineer** — Document optional CRC field for GRP (future enhancement)  
**Status:** DESIGN PHASE (DEFER — manifest checksum sufficient)  
**Date:** 2025-05-21

---

## Executive Summary

This document proposes a forward-looking enhancement to the Duke Nukem 3D GRP archive format to optionally include per-file **CRC32 integrity checks**. The analysis concludes that this enhancement should be **DEFERRED** because:

1. **Current KenSilverman spec** (12-byte "KenSilverman" magic, 4-byte file count, per-entry 12-byte name + 4-byte size) is correct and stable.
2. **SHA256 manifest** (`GRP_MANIFEST.json`) in `tools/generate_assets.py` already provides **content-addressable integrity** at the bundle and per-file level.
3. **Backward compatibility** with original DUKE3D loader is a hard constraint—any change risks breaking legacy consumers.
4. **Implementation cost** (1–3 developer-days) exceeds the benefit when existing checksums are production-ready.

**Recommendation:** Document this as a potential v2 extension (with fallback compatibility) and revisit only if:
- GRP files are distributed over unreliable channels (CRC catches single-bit flips in transit).
- Performance analysis shows SHA256 verification is a bottleneck.
- Legacy loader integration becomes infeasible.

---

## Section 1: KenSilverman GRP Format (Current)

### Header Layout

```
Bytes 0–11:    "KenSilverman" (12-byte ASCII magic)
Bytes 12–15:   num_files (uint32, little-endian)
```

### File Directory

For each of `num_files` entries:
```
Bytes N+0–N+11:    Filename (12 bytes, null-padded ASCII, uppercase)
Bytes N+12–N+15:   File size (uint32, little-endian)
```

Total directory size: `num_files × 16` bytes.

### File Data

All file data concatenated in directory order (no gaps or padding between entries).

### Example Structure

For a GRP with 3 files (TILES000.ART, PALETTE.DAT, TABLES.DAT):

```
Offset  Content
0       "KenSilverman" (12 bytes)
12      0x03000000 (3 files, little-endian uint32)
16      "TILES000.ART\0" + size (16 bytes)
32      "PALETTE.DAT\0" + size (16 bytes)
48      "TABLES.DAT\0" + size (16 bytes)
64      [TILES000.ART data]
...     [PALETTE.DAT data]
...     [TABLES.DAT data]
```

---

## Section 2: Why No CRC in Current Design

### 2.1 Content-Addressable via SHA256 Manifest

The **GRP_MANIFEST.json** sidecar (produced by `_emit_grp_manifest()` in `tools/generate_assets.py`) provides full integrity coverage:

```json
{
  "schema_version": "1.0",
  "generated_at": "2025-05-21T10:30:00Z",
  "grp_checksum": "abc123def456...",    // SHA256 of entire DUKE3D.GRP
  "members": {
    "TILES000.ART": "sha256_hex_...",
    "PALETTE.DAT": "sha256_hex_...",
    "TABLES.DAT": "sha256_hex_..."
  },
  "manifest_checksum": "xyz789..."      // SHA256 of manifest (excl. this field)
}
```

**Advantages:**
- **Cryptographic strength:** SHA256 is collision-resistant; CRC32 is not (designed for single-bit error detection, not security).
- **Per-member verification:** Load-time validation of each asset without re-computing entire GRP hash.
- **Decoupled from archive format:** Manifest can be updated independently; no breaking changes to GRP reader.
- **Distribution flexibility:** Manifest can be served separately (e.g., via CDN checksum endpoint) for incremental downloads.

### 2.2 Original Spec Design Decision

Ken Silverman's GRP format (1996) was intentionally minimal:
- No redundancy fields (CRC, magic trailer, format version).
- No padding or alignment overhead.
- Simple sequential file data for fast streaming access on 1990s hardware.

Adding CRC would:
- Break the 16-byte directory entry structure (would require 20+ bytes per entry).
- Force re-reading the GRP to calculate CRC on every load (performance cost on slow drives).
- Not align with the "stream-friendly" design philosophy.

### 2.3 Current Assurance Mechanism

For generated assets, `tools/generate_assets.py`:
1. Generates all textures, maps, palettes, and tables procedurally.
2. Packs into a **single, deterministic GRP** (sorted filenames ensure reproducibility).
3. **Emits SHA256 checksums** in `GRP_MANIFEST.json` (schema v1.0).
4. Can **re-generate and verify checksums** in CI/CD without storing the GRP.

This is sufficient for:
- **Integrity assurance:** SHA256 detects any bit corruption in transit or storage.
- **Reproducibility:** Identical inputs → identical SHA256 output.
- **Auditability:** Manifest is human-readable JSON; easy to sign (e.g., GPG, RSA).

---

## Section 3: Future Enhancement Sketch

If GRP integrity in the archive itself becomes necessary, two options exist:

### Option A: Sidecar CRC32 File (`.grp.crc`)

**Format:**
```
.grp.crc (text file):
DUKE3D.GRP: <crc32_hex>
TILES000.ART: <crc32_hex>
PALETTE.DAT: <crc32_hex>
TABLES.DAT: <crc32_hex>
```

**Pros:**
- Zero changes to GRP file structure.
- Original DUKE3D loader works unmodified.
- Easy to generate with `zlib.crc32()` in Python.
- Can be distributed alongside GRP (single download bundle or two separate URLs).

**Cons:**
- Requires distributors to maintain two files (GRP + .crc).
- Sidecar may be lost in transit or file transfers.
- No standardization; custom loading code required per platform.
- Weaker than SHA256 (CRC32 is vulnerable to deliberate collisions).

**Implementation Effort:** ~1 day (Python `zlib.crc32()`, C/Rust reader for sidecar).

### Option B: Embedded Extension Format (v2 Magic with Backward Fallback)

**Concept:** New GRP v2 magic ("KenSilverman2" or length-encoded variant) with optional CRC extension.

**Layout:**
```
Bytes 0–11:     "KenSilverman" (existing magic)
Bytes 12–15:    num_files (uint32, little-endian)
Bytes 16–31:    OPTIONAL: v2 extension header
                  - 4 bytes: "EXT2" magic (if present, triggers v2 parsing)
                  - 4 bytes: num_extended_entries (uint32)
                  - 8 bytes: reserved
...
```

**Pros:**
- Fully backward compatible: old loader sees existing format, ignores extension.
- New loader can optionally parse CRC32 entries for integrity.
- Future-proof: can add other metadata (timestamps, compression hints, etc.).

**Cons:**
- More complex parser logic: old reader must skip unknown extensions.
- Risk of parser bugs: straying into data section if extension header is malformed.
- Increases GRP file size (16+ bytes overhead).
- Requires version negotiation logic in dual-mode readers.

**Implementation Effort:** ~2–3 days (new struct packing, compatibility layer in C/Rust reader).

### Option C: Ignore and Use External Checksums (Recommended Status Quo)

Continue relying on:
- **GRP_MANIFEST.json** for generated assets.
- **Cryptographic signatures** (GPG, RSA) on manifest for distribution trust.
- **CI/CD reproducibility:** Regenerate and checksum in automated builds.

**Pros:**
- Zero GRP file changes; no compatibility risk.
- Scales to all asset types (ART, PALETTE, TABLES, MAP files).
- Easier to audit (checksums are standalone, not embedded).

**Cons:**
- Requires manifest alongside GRP; extra file to track.
- Not suitable for direct GRP file distribution without manifest (loose coupling).

---

## Section 4: Compatibility Constraints

### Hard Constraint: Original DUKE3D Loader Must Work

The original BUILD engine loader (and any derivative using unmodified KenSilverman parsing) must **never** fail due to our enhancements:

```c
// Pseudo-code: original loader (must remain compatible)
fread(magic, 12, 1, fp);
if (memcmp(magic, "KenSilverman", 12) != 0) error("Invalid GRP");
fread(&num_files, 4, 1, fp);
for (int i = 0; i < num_files; i++) {
    fread(filename, 12, 1, fp);
    fread(&size, 4, 1, fp);
    // ... load file data
}
```

**Constraint:** Any v2 extension **must not alter** the directory offset or file data positions. The first `12 + 4 + (num_files × 16)` bytes must remain identical in layout.

**Implication:** CRC fields cannot be embedded **within** the directory entries themselves (would shift all subsequent data). CRC must be:
1. **After** file data (sidecar file, or appended with a trailer magic).
2. **Optional** (reader skips gracefully if absent).

---

## Section 5: Implementation Effort Estimate

| Scenario | Effort | Rationale |
|----------|--------|-----------|
| **Sidecar CRC32 (.grp.crc)** | 1 day | Add `_emit_grp_crc()` to `generate_assets.py`; Python `zlib.crc32()`. Update DUKE3D loader C code to optionally read `.crc` file (5–10 lines). |
| **Embedded v2 Extension** | 2–3 days | Design extension header format; implement struct packing; dual-mode parser (old magic → stop; new magic → parse extension). Edge-case testing. |
| **Manifest + GPG Signing** | ~4 hours | Use `gpg` CLI or Python `gnupg` module; sign `GRP_MANIFEST.json`; document verification workflow. |
| **Documentation & Testing** | 1–2 days | Write format spec; add pytest tests for packing/unpacking; integration test with DUKE3D loader. |
| **Total (Sidecar Path)** | **2–3 days** | Single weekend sprint. |
| **Total (Embedded Path)** | **4–5 days** | Two-day task + review/iteration. |

---

## Section 6: Risk Analysis

### Risk: Parser Complexity

**Embedded v2 adds branching logic:**
```c
// Old loader (simple)
if (magic != "KenSilverman") error();
// ...load files...

// New dual-mode loader (complex)
if (magic == "KenSilverman") {
    // Could be v1 or v2 (if extension header follows)
    if (peek_next_4_bytes == "EXT2") {
        // Parse extension
    } else {
        // Treat as v1
    }
}
```

**Mitigation:** Sidecar approach avoids this entirely. GRP file remains immutable; CRC is separate concern.

### Risk: Distribution Complexity

**Sidecar requires coordination:**
- Packagers must bundle both GRP and .crc.
- If .crc is lost, loader warns but still works (graceful fallback).

**Mitigation:** Document clearly; add checksum to release notes.

### Risk: Manifest Signature Loss

**If GRP_MANIFEST.json + GPG signature are lost**, users cannot verify integrity.

**Mitigation:** Embed manifest checksum in release announcement (printed in console at startup, or in README). Example:
```
DUKE3D.GRP verified: sha256=abc123... (see release v0.6 notes)
```

---

## Section 7: Current KenSilverman Spec Validation

Per `tools/grp_format.py` (lines 1–42), the **current implementation is correct**:

✅ **12-byte "KenSilverman" magic** — correct  
✅ **4-byte file count (uint32, little-endian)** — correct  
✅ **Per-entry 12-byte filename + 4-byte size** — correct  
✅ **File data concatenated in sorted order** — correct  
✅ **Deterministic output** (sorted filenames) — correct  

**No bugs found. Spec is faithful to Ken Silverman's original design.**

---

## Section 8: Recommendation

### Primary Path: DEFER Embedded CRC

**Status:** Archive spec is mature and stable. SHA256 manifest is sufficient for current distribution models.

**When to revisit:**
1. **If files are served over UDP/unreliable channels** (CRC catches single-bit corruption; SHA256 requires re-downloading entire file on mismatch).
2. **If GRP distribution without manifest becomes mandatory** (e.g., read-only FAT32 USB stick, or HTTP-only mirrors).
3. **If performance analysis shows SHA256 verification as CPU bottleneck** (CRC32 is ~10× faster; unlikely on modern hardware).

### Secondary Path: Adopt Sidecar CRC32 (Low-Risk, High-Compatibility)

If CRC is deemed necessary:
- **Implement sidecar `.grp.crc` file** (Option A).
- Zero impact on GRP format; legacy loader unaffected.
- Add `_emit_grp_crc()` to `tools/generate_assets.py` (~10 lines Python).
- Update DUKE3D loader to optionally read and verify `.crc` (~5–10 lines C).
- Document in ARCHITECTURE.md § Asset Pipeline.

**Effort:** 1 day (implementation + testing).

### Tertiary Path: GPG Sign Manifest (Recommended for Distributable Assets)

For assets shipped publicly:
1. **Generate manifest** (already done in `_emit_grp_manifest()`).
2. **Sign manifest with GPG**: `gpg --detach-sign GRP_MANIFEST.json`.
3. **Distribute as bundle**: GRP + manifest + `.asc` signature.
4. **Loader verifies**: `gpg --verify GRP_MANIFEST.json.asc`.

**Effort:** ~4 hours (GPG integration + documentation).

---

## Section 9: Architecture.md Integration

When this enhancement moves from design to implementation, update **docs/ARCHITECTURE.md** § Asset Pipeline:

```markdown
### GRP Archive Integrity

- **Current:** SHA256 checksums in `GRP_MANIFEST.json` (per-file + bundle-level).
- **Future (deferred):** Optional CRC32 sidecar (`.grp.crc` file) for CRC validation during load.
  - Does not alter GRP format; fully backward compatible.
  - See `docs/audits/RUN_grp_crc_future_cycle87.md` for design analysis.
- **Crypto signing:** GPG-signed manifest for trusted distribution (roadmap v1.0).
```

---

## Section 10: Related Issues & Tickets

- **`asset-r16-grp-manifest-emit`**: Manifest generation is DONE (SHA256 per-file checksums).
- **`build-system` audit**: Ensure GRP reproducibility in CI (already validated).
- **Future**: `asset-r5-grp-crc-future` — Design phase; implementation deferred pending upstream requirements.

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-05-21 | DEFER CRC; recommend external checksums | SHA256 manifest sufficient; embedded CRC adds complexity; sidecar preferred if needed. |
| 2025-05-21 | Validate KenSilverman spec | Confirmed correct per original design; no breaking changes proposed. |
| 2025-05-21 | Document v2 extension path | Sketched as low-risk future option; not blocking current pipeline. |

---

## Conclusion

The KenSilverman GRP format is **correct, stable, and sufficient** for current asset delivery. SHA256 checksums via `GRP_MANIFEST.json` provide:

- **Integrity assurance** (cryptographic strength).
- **Decoupled metadata** (manifest independent of archive).
- **Forward compatibility** (can evolve without GRP changes).

**Embedding CRC within the archive itself adds complexity and risk** without commensurate benefit. The **sidecar CRC32 option** remains a low-cost future enhancement if distribution assurance requirements change.

**Final Recommendation:** DEFER embedded CRC. Rely on external SHA256 manifest and GPG signing for production releases.

---

**Sentinel:** `grp-crc-doc-c2f1a8e7`
