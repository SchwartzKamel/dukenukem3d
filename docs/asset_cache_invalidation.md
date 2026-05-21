# Asset Cache Invalidation Gap

**Status:** Documentation of current behavior + optional future enhancement
**Audience:** Asset pipeline engineers, CI maintainers
**Scope:** Texture and sprite cache invalidation in CI; distinction from audio manifest approach

---

## Current Behavior: Full Regeneration Every Build

The asset pipeline currently **regenerates ALL textures and sprites on every CI run**, regardless of whether the catalog (`TEXTURE_DEFS`, `SPRITE_DEFS`) has changed.

### How It Works (tools/generate_assets.py)

1. **Texture catalog definition** (lines 145–187):
   - `TEXTURE_DEFS`: 20 wall/floor/ceiling textures as tuples `(tile_num, width, height, description, flux_prompt)`
   - Defined as Python list literals in the source file
   - No timestamp or hash tracking in the source

2. **Sprite catalog definition** (lines 190–200):
   - `SPRITE_DEFS`: 10 item/sprite tiles as tuples `(tile_num, width, height, description)`
   - Similar list literal structure

3. **Procedural fallback map** (line 956):
   - `PROCEDURAL_MAP`: dict mapping tile_num → procedural generator function
   - Generators called by reference; no versioning

4. **Main pipeline execution** (lines 2135–2200):
   - CI runs: `python3 tools/generate_assets.py --no-ai` (`.github/workflows/build.yml` line 48)
   - Pipeline detects no cache key; **full regeneration occurs every time**
   - Textures parallelized across 8 workers (multiprocessing)
   - Sprites processed similarly
   - Font tiles (2048–2175) also regenerated
   - Total time: ~30–60 seconds on standard CI runners

---

## The Gap: No Dependency Tracking

### What's Missing

When a developer **edits `tools/generate_assets.py`** to change texture definitions (e.g., modify a `TEXTURE_DEFS` entry, adjust a procedural generator function, or update `PROCEDURAL_MAP`), the CI build system has **no way to detect this change** and trigger incremental regeneration.

### Why This Is a Gap

In a hypothetical advanced pipeline, you might want to:
- **Cache individual tile outputs** (per-tile .ART data blobs)
- **Detect definition changes** via checksum or manifest
- **Regenerate only affected tiles** instead of all 30 (20 textures + 10 sprites)
- **Reuse unchanged tiles** from a prior build

Currently, none of this is possible because:
- No manifest file records the definition state (tile_num, width, height, generator function)
- No hash or timestamp of `TEXTURE_DEFS` / `SPRITE_DEFS` is tracked
- Cache busting always happens (safe, but inefficient)

### Example Scenario

```python
# Hypothetical change in tools/generate_assets.py

# Developer changes tile 3 description:
TEXTURE_DEFS = [
    ...
    (3, 64, 64, "Neon circuit wall (UPDATED)",  # ← changed
     "seamless tileable dark wall panel with glowing cyan circuit traces..."),
    ...
]
```

**Result:** CI rebuilds **all 30 tiles** even though only tile 3 definition changed.

---

## Why We Don't Currently Care

This gap is **not a blocking issue** for three reasons:

### 1. **Deterministic & Fast**

- Asset generation is deterministic (no randomness in procedural functions, controlled RNG seeds via `random.Random(seed)`)
- All textures complete in ~30–60 seconds with parallelization
- GRP packing another ~10 seconds
- **Total CI impact:** <2 minutes, acceptable overhead

### 2. **No FLUX API Dependency in CI**

- CI uses `--no-ai` flag (line 48 of build.yml)
- No Azure FLUX.2-pro calls (no latency, no quota concerns, no API failures)
- Procedural fallbacks are lightweight CPU-bound tasks

### 3. **Binary Caching Not Cost-Effective**

- Per-tile caching would require:
  - Manifest sidecar file (`ASSET_MANIFEST.json`) with hash of each tile definition
  - Pre-built tile cache (disk storage or remote)
  - Complex invalidation logic (tile dependencies, palette changes)
  - ~1–2 days engineering effort for ~30 seconds CI savings
- **ROI:** Poor for a one-time per-build overhead

---

## The Precedent: Audio Manifest Pattern (Cycle 90)

For comparison, the **audio pipeline** implemented a **manifest schema** with integrity tracking:

### `tools/sound_manifest.py` Structure

From cycle 90 (commit 832b964), `SoundManifestEntry` Pydantic model (lines 13–131):

```python
class SoundManifestEntry(BaseModel):
    wav: str                    # Filename
    hash: Optional[str]         # SHA256 checksum
    size_bytes: Optional[int]   # File size for metadata
    engine_sound_id: str
    category: str
    # ... other fields
    schema_version: Literal['1.0']
```

### Why Audio Did This

- **Audio uses remote FLUX API** (potential latency, quota)
- **Manifest freshness tracking** considered (cycle 88, deferred per cycle 90 audit)
- **Integrity verification** useful (manifest checksums prevent corruption)
- Audio entries are sparse (~21 sounds) vs. dense texture generation (30 tiles)

### Why Textures Didn't Adopt It

- No external API overhead (procedural is local)
- Texture generation is **already fast**
- Manifest sidecar adds file I/O burden without ROI

---

## Optional Future: Manifest-Hashing Strategy

**If** asset caching becomes a bottleneck (CI >10 min per build, or many contributors), this pattern could be adopted:

### 1. **Create Asset Manifest**

```python
# File: generated_assets/ASSET_MANIFEST.json

{
  "schema_version": "1.0",
  "generated_at": "2026-05-21T10:30:00Z",
  "texture_defs_hash": "sha256:abc123...",
  "sprite_defs_hash": "sha256:def456...",
  "tiles": {
    "0": {
      "tile_num": 0,
      "width": 64,
      "height": 64,
      "description": "Dark steel wall panel",
      "hash": "sha256:tile_0_hash_here",
      "generated_at": "..."
    },
    "1": { ... },
    ...
  }
}
```

### 2. **Hash Definition Tuples**

In `tools/generate_assets.py`:
```python
import hashlib

def hash_texture_defs():
    """Hash TEXTURE_DEFS + SPRITE_DEFS tuples for cache invalidation."""
    content = str(TEXTURE_DEFS) + str(SPRITE_DEFS)
    return hashlib.sha256(content.encode()).hexdigest()
```

### 3. **Incremental Cache Check**

```python
def load_cache_manifest(manifest_path):
    """Load prior manifest; return dict of cached tile hashes."""
    if not os.path.exists(manifest_path):
        return {}
    with open(manifest_path) as f:
        data = json.load(f)
    return {t['tile_num']: t['hash'] for t in data['tiles'].values()}

def regenerate_if_changed(tile_num, prior_hash):
    """Compare cached hash with new definition; regenerate if mismatch."""
    new_hash = hash_single_tile_def(tile_num)
    if new_hash == prior_hash:
        print(f"  Tile {tile_num} unchanged; using cached version")
        return load_from_cache(tile_num)
    else:
        print(f"  Tile {tile_num} changed; regenerating")
        return generate_tile(tile_num)
```

### 4. **CI Integration**

```bash
# .github/workflows/build.yml (hypothetical future)
- name: Generate assets (incremental)
  run: python3 tools/generate_assets.py --no-ai --use-cache
```

---

## Trade-Offs: Why Not Implement Now?

| Aspect | Cost | Benefit | Decision |
|--------|------|---------|----------|
| **Implementation** | 1–2 days | 30–60 sec CI savings | Not worth (1% of build time) |
| **Maintenance** | Manifest versioning, migration tests | Documentation value only | Deferred |
| **Correctness risk** | Cache invalidation bugs (correctness hazard) | None (already fast) | Avoid risk |
| **Scalability** | Linear with tile count (N tiles → N hash checks) | Sublinear savings (amortized per decade) | Not needed |

**Recommendation:** Implement **only if**:
1. Asset generation exceeds 5 minutes per build, **and**
2. Multiple developers frequently modify texture definitions, **and**
3. You adopt the audio `SoundManifestEntry` Pydantic pattern (for schema forward-compat)

---

## References

### Source Files (Read-Only)

- **tools/generate_assets.py**
  - Lines 145–187: `TEXTURE_DEFS` catalog
  - Lines 190–200: `SPRITE_DEFS` catalog
  - Line 956: `PROCEDURAL_MAP` dict
  - Lines 2135–2200: `main()` generation logic
  - Line 2148: Multiprocessing pool (8 workers)

- **.github/workflows/build.yml**
  - Line 48: `python3 tools/generate_assets.py --no-ai` (CI entry point)
  - Line 26–27: pip cache (not asset cache)
  - Line 92–102: SDL2 MinGW cache (unrelated to textures)

- **tools/sound_manifest.py**
  - Lines 13–131: `SoundManifestEntry` Pydantic model (cycle 90 precedent)
  - Lines 28–38: `hash` + `size_bytes` fields (optional but structured)

### Historical Context

- **Cycle 90** (commit 832b964): Audio manifest schema with hash + size_bytes fields; manifest freshness tracking considered then **deferred** (cycle 88 decision reaffirmed)
- **Cycle 88–89:** Manifest freshness analysis determined caching not cost-effective for audio; similar logic applies to textures
- **Asset pipeline audit** (r22, cycle 90): Cache invalidation gap flagged as **INFORMATIONAL** (not CRITICAL/HIGH)

---

## Summary

The asset pipeline regenerates textures fully every build because there's no dependency tracking between source code (`TEXTURE_DEFS`) and build outputs. This is **safe and fast enough** that caching is not justified. A manifest-hashing strategy is **documented as optional**, following the audio pipeline precedent (cycle 90), but should be deferred unless asset generation becomes a measurable bottleneck.

**Current Status:** ✅ Safe, ✅ Fast, ✅ Deterministic | ❌ Not Cached | ✅ Not Worth Caching Now

---

**Document Version:** 1.0  
**Last Updated:** Cycle 90  
**Next Review:** Cycle 95 (if CI times exceed 10 min)
