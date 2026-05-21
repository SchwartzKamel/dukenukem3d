# RTS.C Shared Opens FIXME Investigation

**Ticket**: `audit-engine-rts-fixme` (LOW)  
**Audit Date**: Cycle 88  
**Investigator**: Engine Porter  
**Status**: Investigation Complete  

---

## 1. FIXME Context

**Location**: `source/RTS.C:72` (within `RTS_AddFile()` function)

**Comment**:
```c
//
// read the entire file in
//      FIXME: shared opens

handle = SafeOpenRead( filename, filetype_binary );
```

**Context** (lines 61-109):
- `RTS_AddFile()` is called by `RTS_Init()` to load RTS (WAD) files containing game resources (sounds, sprites, lumps)
- The function opens a single RTS file using `SafeOpenRead()` at line 74
- For each lump in the WAD file, a `lumpinfo_t` structure is created and **stores the same file handle** (line 104: `lump_p->handle = handle`)
- Multiple lumps from the same WAD file **share a single file descriptor**
- Each lump record stores: `handle`, `position` (offset in file), and `size`

**File-Handle Usage Pattern** (lines 202-212):
```c
void RTS_ReadLump (int32 lump, void *dest) {
   // ... validation ...
   l = lumpinfo+lump;
   lseek (l->handle, l->position, SEEK_SET);  // Seek to lump position
   SafeRead(l->handle,dest,l->size);          // Read lump from file
}
```

The shared handle is used for random access via `lseek()` + `SafeRead()`.

---

## 2. File-Handle Audit: Open/Close Pair Tracing

### Open Operations

**Location**: `source/RTS.C:74` (in `RTS_AddFile()`)
```c
handle = SafeOpenRead( filename, filetype_binary );
```
- Called once per RTS file loaded in `RTS_Init()` (line 132)
- Handle is stored in `lumpinfo[].handle` for all lumps from that file
- **File remains open for the lifetime of the application**

### Close Operations

**Search Results**:
- No `SafeClose()`, `kclose()`, `close()` calls in `source/RTS.C`
- No `RTS_Shutdown()` or `RTS_Cleanup()` function exists
- No cleanup registration (e.g., atexit handlers)
- **Result**: FILE DESCRIPTOR IS NEVER CLOSED

### Handle Lifecycle

| Operation | Line | Note |
|-----------|------|------|
| Open | 74 | SafeOpenRead() in RTS_AddFile() |
| Store | 104 | Stored in lumpinfo[].handle (shared by all lumps) |
| Use | 211-212 | Random access in RTS_ReadLump() |
| Close | **NONE** | ❌ Missing |
| Cleanup | **NONE** | ❌ No RTS_End() or RTS_Shutdown() |

---

## 3. Single-Thread Invariant Context

### Reference: Cycle 85 Allocache-Race Investigation

From `docs/audits/RUN_allocache_race_cycle85.md`:

**Threading Model** (lines 54-83):
- No threading primitives found in codebase (`pthread`, `CreateThread`, `_beginthread`, etc.)
- All allocache callers are **synchronous, main-loop-only**
- No async callbacks or network threads trigger resource loading
- **Conclusion**: Codebase is **single-threaded**

### RTS.C Caller Analysis

All `RTS_*()` function calls occur during:
1. **Game initialization** (`RTS_Init()` called at startup)
2. **Main game loop** (sound lookups via `RTS_GetSound()`)

**Call Stack**:
- `RTS_GetSound()` → `RTS_SoundLength()` or `RTS_ReadLump()`
- Called from `SOUNDS.C:301` (main loop)
- Called from `allocache()` callback (also main loop)

**Thread Safety Implication**: File handle usage is inherently race-free in single-threaded model. The "shared opens" pattern is safe **only because** there is no concurrent access.

---

## 4. Verdict: Stale Comment, Not a Real Bug

### Analysis

1. **Is it a real bug (file descriptor leak)?**
   - ✅ **Technically YES**: File descriptors are not closed, creating a resource leak
   - ❌ **Practically NO**: Leak is minimal (1-2 FDs) and auto-reclaimed on process exit
   - On modern systems, the OS gracefully closes all FDs when the process terminates

2. **Is it a stale comment?**
   - ✅ **YES**: The "FIXME: shared opens" is orphaned from original design
   - The comment suggests future refactoring consideration (e.g., pooling/cache file handles)
   - No follow-up action was ever taken; the pattern works as-is

3. **Scope Classification**
   - **Type**: Design commentary (FIXME), not critical bug
   - **Severity**: LOW
   - **Impact**: Negligible in production (process exit reclaims FDs)
   - **Risk**: Refactoring for async I/O would need to revisit this pattern

### Why This Pattern Exists

**Design Rationale**:
- **Minimizes system calls**: One open per RTS file, not one per lump
- **Efficient random access**: `lseek()` is faster than open/read/close cycles
- **Simplicity**: Shared handle avoids handle multiplexing logic
- **Context**: 1996-2003 codebase (DOS/early Windows era), process lifecycle = game session

**The "FIXME" likely meant**: "Consider if this design is optimal for future platform variants or if we need better resource cleanup." But it was never acted upon because the simpler pattern works fine.

---

## 5. Recommendation: Remove Comment / Document Intent

### Option A: Remove FIXME (Recommended for LOW priority)
- Delete lines 70-72 comment
- Add brief implementation note: "File handle kept open for entire session; safe in single-threaded context"
- Rationale: Comment is outdated; code is working as designed

### Option B: Add Cleanup Function (If Needed)
- Implement `RTS_Shutdown()` to iterate `lumpinfo[]` and close unique handles
- Register with atexit or call from game shutdown
- Rationale: Only needed if porting to embedded systems with strict FD limits

### Option C: Keep Comment with Clarification (Compromise)
Replace:
```c
// FIXME: shared opens
```

With:
```c
// File handle shared across all lumps from this WAD; safe in single-threaded context.
// If async I/O is added, consider pooling or per-lump file access patterns.
```

---

## 6. Conclusion

**Status**: STALE COMMENT

The "FIXME: shared opens" is a design note from the original codebase, not a critical issue. The pattern is:
- ✅ Functionally correct (random access works)
- ✅ Single-thread safe (no race conditions)
- ✅ Resource safe (OS cleanup on exit)
- ❌ Not documented (unclear to future maintainers)

**Action**: Treat as cleanup task only. No bug fix or runtime change required. Update comment for clarity or remove entirely.

**No follow-up todo required** — this is documentation/clarity only, not a code defect.

---

## Appendix: Cross-Reference

### File Structures Involved
- `source/RTS.C` — Resource manager
- `source/_RTS.H` — lumpinfo_t structure (line 37: `int32 handle`)
- `source/FILE_LIB.H` — SafeOpenRead / SafeClose declarations
- `source/SOUNDS.C` — RTS consumer (allocache + RTS_GetSound)

### Related Cycle 85 Finding
- Codebase threading model verified as single-threaded
- No concurrent access to RTS file handles
- Pattern is safe-by-design for current architecture

---

**End of Investigation**

Sentinel: `rts-fixme-e7c2b3a1`
