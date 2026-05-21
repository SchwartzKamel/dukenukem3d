# Allocache Quick-Path Thread-Safety Investigation

**Ticket**: `engine-r20-carry-r19-allocache-race` (MED)  
**Audit Date**: Cycle 85  
**Investigator**: Engine Porter  
**Status**: Investigation Complete  

---

## 1. Function Description

**Location**: `SRC/CACHE1D.C:67-186` (`allocache()`)

### Purpose
`allocache()` is the primary cache block allocation function in the BUILD engine's linear cache management system. It allocates memory from a pre-initialized global cache buffer (initialized by `initcache()`) and maintains a descriptor table (`cac[]` array) to track allocated regions.

### Quick-Path Optimization (Lines 95-122)
The function includes a performance optimization that avoids expensive full-cache scanning for allocation requests of similar size. This optimization:

1. **Caches the last successful allocation candidate** in three static variables:
   - `lastCandidateBesto` — offset of the last candidate block
   - `lastCandidateBestz` — index in the cache descriptor array
   - `lastCandidateSize` — size of the last allocated request

2. **Fast-path logic** (lines 96-122):
   - If a new allocation request has size within 256 bytes of the last candidate:
     ```c
     if (lastCandidateSize > 0 && lastCandidateSize <= newbytes + 256)
     ```
   - Use the candidate block's offset and index directly without full scan
   - Compute cost for that region only (lines 103-109)
   - If cost is acceptable, skip full scan and goto `cachealloc_found` (line 118)

3. **Candidate update** (lines 144-146):
   - After allocation decision, update all three static variables:
   ```c
   lastCandidateBesto = besto;
   lastCandidateBestz = bestz;
   lastCandidateSize = newbytes;
   ```

### Allocation Path
After finding a candidate (fast or slow path):
- Evict locks blocking the region (lines 155-156)
- Consolidate cache descriptors (lines 159-160)
- Mark new block as allocated (lines 161-165)
- Maintain free bytes counter (lines 164, 170)
- Merge adjacent free blocks if necessary (lines 172-185)

---

## 2. Caller Analysis: Which Threads Call allocache?

### Current Codebase: Single-Threaded Only

**Threading Search Results**:
- Grep for `pthread`, `_beginthread`, `CreateThread`, `thread`, `Thread` in `source/` and `SRC/`: **0 matches**
- No mutex, critical section, or synchronization primitives found
- SDL2 library (included) supports threading, but the game code does not use it

### Callers of allocache (Confirmed Locations)

All calls are from **main game loop context** during initialization or gameplay:

1. **Sound Loading**:
   - `source/SOUNDS.C:301` — Load sound effect into cache (main loop)
   - `source/PREMAP.C:254` — Pre-cache level sounds (map loading, main loop)

2. **Texture/Tile Loading**:
   - `source/MENUES.C:207, 324, 3972` — Load menu graphics (main loop)
   - `source/GAME.C:3104, 3113` — Load background tiles (main loop)

3. **RTS Resource Loading**:
   - `source/RTS.C:231` — Load RTS sound lumps (game initialization / main loop)

4. **Compression Buffer Allocation** (LZW):
   - `SRC/CACHE1D.C:516-520, 552-556, 588-592` — Allocate LZW compression buffers (called from file load functions, which are main-loop-only)

### Call Pattern
- No calls from audio playback callbacks
- No calls from network threads
- No calls from interrupt handlers
- All callers are **synchronous**, running in the main game loop thread

### Threat Model: Does allocache Need Protection?

**Current Reality**: Single-threaded, no threat.

**Hypothetical Future Scenario**: If Duke3D were refactored to support:
- Asynchronous sound loading on a background thread
- Network asset streaming on a dedicated thread
- Audio engine callbacks (e.g., `SDL_AudioCallback`)

Then `allocache()` **would have race conditions** in its quick-path optimization.

---

## 3. Shared State Inventory

### Global Variables Accessed by allocache

**Quick-Path Cache** (Updated lines 144-146):
- `static long lastCandidateBesto` — candidate block offset
- `static long lastCandidateBestz` — candidate descriptor index
- `static long lastCandidateSize` — candidate size threshold
- **Synchronization**: NONE. Read at line 96 without barrier.

**Main Cache State** (Accessed throughout):
- `cactype cac[MAXCACHEOBJECTS]` — cache descriptor array
  - Contains: `long *hand`, `long leng`, `char *lock` per block
  - Modifications at lines 156, 160, 161-163, 175-176, 183-185
  - **Synchronization**: NONE.

- `long cacnum` — count of descriptors in use
  - Read/modified at lines 124, 159, 174, 182
  - **Synchronization**: NONE.

- `long cachesize` — total cache size (immutable after init)
  - Read-only in allocache (line 80, 127)
  - **Synchronization**: Safe (immutable).

- `long cache1d_free_bytes` — free space counter
  - Read at line 194 (not in allocache, but in suckcache)
  - Modified at lines 164, 170
  - **Synchronization**: NONE.

### Lock Pointers
- Function reads `*cac[zz].lock` values at lines 105, 132
- These are **caller-provided** pointers to lock counters (e.g., `&Sound[num].lock`)
- Not synchronized; callers control lock lifetime

### Other Shared State
- `agecount` — used by `agecache()` to rotate eviction preference
- `cachestart` — immutable after init
- `cachecount` — statistics counter
- `zerochar` — sentinel zero byte used as "unlocked" marker

---

## 4. Hazard Assessment

### A. Quick-Path Candidate Cache Race Condition

**Type**: **Read-then-act** (TOCTOU)

**Scenario**:
```
Thread A (main):           Thread B (hypothetical async):
--                         --
allocache(handle1, 1000)
  line 96: read lastCandidateSize (=500)
  line 96-100: enter fast path
  line 103: loop with lastCandidateBestz (=2)
  ...
                           allocache(handle2, 2000)
                             line 144: lastCandidateBesto = 0x1000
                             line 145: lastCandidateBestz = 1
                             line 146: lastCandidateSize = 2000
  
  line 112: use stale lastCandidateBestz (=2)
  line 113: evaluate cost with wrong descriptor
  Result: Allocate to wrong region or crash reading cac[2]
```

**Root Cause**:
- `lastCandidateBesto`, `lastCandidateBestz`, `lastCandidateSize` are **non-atomic**, **not locked**
- Fast path reads them without checking for concurrent writers
- Between line 96 (check) and line 103 (use), values can change

**Severity If Multi-Threaded**:
- **CRITICAL**: Could corrupt cache state, allocate overlapping regions, invalidate pointers
- Silent memory corruption (not caught by assertions)
- Likely to cause crashes on large allocations

### B. Main Cache State Races

**Affected Variables**: `cac[]`, `cacnum`, `cache1d_free_bytes`

**Scenarios**:
- Thread A evicts block X (line 156) while Thread B reads its descriptor (line 105)
- Thread A increments `cacnum` (line 174) while Thread B iterates `cacnum` (line 124)
- Thread A updates `cache1d_free_bytes` (line 164) while Thread B reads it (suckcache)

**Severity**: CRITICAL for concurrent access

### C. Single-Thread Invariant Verification

**Current Code**: Assumes allocache is called only from **single thread** (main loop).

**Evidence**:
- No synchronization primitives anywhere in the codebase
- All callers are synchronous, main-loop-only
- No async callbacks trigger allocache
- No network threads call cache functions

**Conclusion**: The single-thread invariant **IS CURRENTLY VALID** and **NOT DOCUMENTED**. This is a latent vulnerability—refactoring for async will miss this.

---

## 5. Hazard Classification

| Aspect | Assessment |
|--------|-----------|
| **Actual Race Condition** | NO — Code is single-threaded. |
| **Theoretical Race Condition** | YES — Quick-path uses non-atomic static variables. |
| **Severity if Multi-Threaded** | CRITICAL — Unprotected writes to candidate cache + shared state. |
| **Exploitability** | Hard to trigger in practice (requires exact timing), but semantically unsound. |
| **Root Cause** | Performance optimization assumes single-thread; not future-proof. |

---

## 6. Recommendation

### Option 1: Document Single-Thread Invariant (PREFERRED for v1.1)
**Approach**: Explicit documentation of thread-safety contract.

**Action**:
- Add comment block above `allocache()`:
  ```c
  /*
   * allocache() is NOT thread-safe. It must be called only from the main
   * game loop thread. The fast-path optimization (lastCandidateBesto, etc.)
   * uses unprotected static variables. If Duke3D is refactored to support
   * async sound loading or network streaming, allocache() must be protected
   * by a global mutex or atomic operations.
   */
  ```
- Add sentinel comment at lines 144-146:
  ```c
  /* Non-atomic update of quick-path candidate. Single-thread invariant. */
  ```

**Pros**: Minimal code change, preserves performance, clear contract
**Cons**: Fragile if threading is added later; must be enforced in code review

### Option 2: Add Atomic Operations (FUTURE)
**Approach**: Atomic loads/stores for quick-path variables.

**Pseudo-code**:
```c
#include <stdatomic.h>  /* Requires C11 */
static _Atomic(long) lastCandidateBesto = 0;
static _Atomic(long) lastCandidateBestz = 0;
static _Atomic(long) lastCandidateSize = 0;

/* In allocache, line 96: */
if (atomic_load(&lastCandidateSize) > 0 && 
    atomic_load(&lastCandidateSize) <= newbytes + 256) { ... }

/* Lines 144-146: */
atomic_store(&lastCandidateBesto, besto);
atomic_store(&lastCandidateBestz, bestz);
atomic_store(&lastCandidateSize, newbytes);
```

**Pros**: Futureproof, standards-compliant
**Cons**: Requires C11 (current code is gnu89); may affect embedded targets

### Option 3: Instrument with ThreadSanitizer (TESTING)
**Approach**: Enable TSAN to detect races during development.

**Action**:
- Build with `-fsanitize=thread` flag
- Run game for several minutes with mixed sound/texture loading
- TSAN will report races if code is refactored to use threads

**Pros**: Catches races automatically during refactoring
**Cons**: Runtime overhead; only detects races that are actually triggered

### Option 4: Add Mutex (CONSERVATIVE)
**Approach**: Global cache lock protecting all allocache operations.

**Pseudo-code**:
```c
static pthread_mutex_t cache_lock = PTHREAD_MUTEX_INITIALIZER;

void allocache(...) {
    pthread_mutex_lock(&cache_lock);
    /* ... existing code ... */
    pthread_mutex_unlock(&cache_lock);
}
```

**Pros**: Maximum safety
**Cons**: Performance hit; requires pthreads; overkill for current single-threaded code

---

## 7. Recommended Action (v7 Contract)

**Immediate (This Cycle)**:
- [x] Investigation complete — hazard identified and documented
- [ ] Next cycle: Add explicit single-thread invariant comment to allocache()
- [ ] Follow-up todo: `engine-r20-allocache-document-invariant` (LOW, 1 hour)

**If Threading is Added**:
- Re-evaluate. Consider Option 2 (atomics) or Option 4 (mutex) based on performance profile
- Add to TSAN regression tests

**No Code Changes Required This Cycle** (Investigation only, per v7 contract)

---

## 8. References

- **Primary Function**: `SRC/CACHE1D.C:67-186` (allocache)
- **Candidates**: `SRC/CACHE1D.C:49` (static variables)
- **Fast Path**: `SRC/CACHE1D.C:95-122`
- **Update**: `SRC/CACHE1D.C:144-146`
- **Helper Functions**: `SRC/CACHE1D.C:188-237` (suckcache, agecache)
- **Callers**: source/GAME.C, source/SOUNDS.C, source/PREMAP.C, source/RTS.C, source/MENUES.C
- **Build System**: No threading configuration found; single-threaded by design

---

## 9. Verification

**Grep Confirmation** (all zero):
```bash
$ grep -r "pthread\|_beginthread\|CreateThread" source/ SRC/
# No output
```

**Caller Context** (all main-loop):
```bash
$ grep -B5 allocache source/SOUNDS.C
    # All calls in synchronous file-load functions (main loop context)
```

**Static Variable Risk** (confirmed):
- `lastCandidateBesto`, `lastCandidateBestz`, `lastCandidateSize` are read without synchronization (line 96)
- Updated without synchronization (lines 144-146)
- No fence or memory barrier

---

## Conclusion

The **quick-path optimization in allocache() is NOT thread-safe**, but this is **not a bug in the current codebase** because all callers are single-threaded (main game loop). The hazard becomes **critical only if the code is refactored to support async operations** (network threads, audio callbacks, etc.).

**Recommendation**: Document the single-thread invariant explicitly in code comments. Plan for atomics or mutex if threading is added.

---

*End of Report*
