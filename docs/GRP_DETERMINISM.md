# GRP Archive Determinism Contract

This document defines the **determinism guarantee** for Duke3D GRP archive generation. Given identical inputs (asset set, content bytes, and sort order), the resulting `DUKE3D.GRP` binary must be **bit-identical** across runs and platforms. This contract ensures reproducible builds and enables cryptographic verification via SHA256 checksums. For an overview of how this section fits into the contributor workflow, see [CONTRIBUTING.md](../CONTRIBUTING.md).

## Overview

This section documents the **determinism guarantee** for GRP archive generation: given identical inputs (asset set, content bytes, and sort order), the resulting `DUKE3D.GRP` binary must be **bit-identical** across runs and platforms. This contract ensures reproducible builds and enables cryptographic verification via SHA256 checksums.

## GRP Binary Format

The GRP archive follows the KenSilverman format as specified in `tools/grp_format.py` (lines 2–9, 14–41):

```
[Header: 16 bytes]
├─ Magic (12 bytes): "KenSilverman"
└─ File count (4 bytes): uint32 little-endian

[Directory: N entries × 16 bytes per entry]
├─ Filename (12 bytes): uppercase ASCII, null-padded to 12 bytes
└─ Size (4 bytes): uint32 little-endian

[Data payload: sum of all file sizes]
└─ File contents concatenated in directory order
```

**Verified by tests**: `tests/test_grp_format.py` (lines 6–55) validates magic, file count, filename padding (12 bytes), size encoding, and payload concatenation.

## Determinism Invariants

To guarantee bit-identical output, the following invariants are strictly enforced:

1. **File Insertion Order (Alphabetical)**  
   Files are sorted by name using `sorted(files_dict.keys())` (`tools/grp_format.py`, line 32). This ensures the directory order is deterministic regardless of dictionary insertion order or platform.

2. **File Count Limit**  
   File count is a 4-byte unsigned integer (uint32 LE). Maximum: 4,294,967,295 files. Current GRP archives contain ~4–10 files (maps, textures, audio), well below the limit.

3. **Header Byte Format**  
   - Magic: literal bytes `"KenSilverman"` (ASCII, not null-terminated within the header)
   - File count: `struct.pack("<I", num_files)` (little-endian unsigned 32-bit integer)

4. **Per-Entry Filename Padding**  
   Each filename is padded to exactly 12 bytes with null bytes (`\x00`). Filenames longer than 12 characters are rejected with a `ValueError` (`tools/grp_format.py`, line 35–36).

5. **Per-Entry Size (4 bytes, little-endian)**  
   Each file's size is encoded as `struct.pack("<I", len(data))`. No size field padding or alignment.

## Inputs That Affect Output

These inputs must be controlled for deterministic GRP generation:

- **Asset list**: The set of files to pack (must be the same)
- **File content bytes**: The binary content of each file (must be identical)
- **Sort order**: Filenames are sorted alphabetically (ascending ASCII order). This is automatic via `sorted()`.

## Inputs That MUST NOT Affect Output

These external factors must be excluded from the GRP to maintain determinism:

- **Filesystem metadata (mtime, ctime, atime)**: Ignored; only file content matters
- **Hostname or machine identity**: Not encoded in the GRP
- **Process PID**: Not embedded
- **Random seeds or non-deterministic RNG**: Not used in GRP packing
- **Time-of-day or wall-clock timestamps**: Only used in the manifest (e.g., `GRP_MANIFEST.json`'s `generated_at` field), not in the GRP binary itself
- **Locale or collation order**: Filenames use Python's default string comparison (lexicographic ASCII order), which is platform-independent

## Verification: Checking Determinism Locally

To verify that GRP generation is deterministic:

```bash
# Generate assets twice in succession
python3 tools/generate_assets.py --no-ai
sha256sum DUKE3D.GRP > checksum1.txt

python3 tools/generate_assets.py --no-ai
sha256sum DUKE3D.GRP > checksum2.txt

# Both checksums must be identical
diff checksum1.txt checksum2.txt  # Should show no difference
```

If the checksums differ, investigate:
1. **Stale cached textures**: Delete `generated_assets/` and regenerate
2. **Code changes to packing logic**: Review `tools/grp_format.py` and `tools/generate_assets.py`
3. **Manifest changes**: Manifest JSON (`GRP_MANIFEST.json`) embeds `generated_at` timestamps and may differ; verify the GRP binary itself with `hexdump` or binary comparison

## Atomic Write Guarantee (Cycle 70 Reference)

GRP files are written via `_atomic_write_bytes()` (`tools/generate_assets.py`, lines 238–258):

```python
def _atomic_write_bytes(path: str, data: bytes) -> None:
    tmp_path = path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)  # POSIX atomic rename
```

**Guarantee**: If the process is interrupted mid-write, the original GRP file (or none) remains intact; no partial or corrupted archives are ever left on disk. This ensures that all observed GRP files are either complete and correct or absent.

## Manifest Integrity & Checksums

The GRP manifest (`GRP_MANIFEST.json`, emitted by `tools/generate_assets.py` lines 282–334) records:

- **SHA256 of the GRP file**: Computed over the entire GRP binary
- **SHA256 of each member file**: Individual checksums for auditing
- **Member metadata**: Name, size, and order
- **Manifest checksum**: SHA256 computed over the manifest itself (excluding the `manifest_checksum` field)

Manifest integrity is verified on load (`tools/manifest_verification.py`) to catch any tampering or corruption. See `tests/test_grp_manifest.py` for verification tests (lines 123–249).

## Testing & Continuous Verification

- **Unit tests**: `tests/test_grp_format.py` (56 lines) validates GRP structure, magic, file counts, and filename padding
- **Integration tests**: `tests/test_grp_manifest.py` (282 lines) validates deterministic emission, checksums, and manifest integrity
- **CI/CD**: The build system regenerates GRP archives from source on every commit and verifies checksums against the manifest
- **Parametrization contracts**: See `tests/PARAMETRIZATION_CONTRACTS.md` for canonical test parametrization patterns and guidelines

This ensures that any unintended deviation from the determinism contract is caught immediately.
