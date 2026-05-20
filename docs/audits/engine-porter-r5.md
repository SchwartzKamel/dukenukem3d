# Engine Porter — Round 5

Scope: `SRC/*.C/H`, `source/*.C/H`. Focus on changes landed since round 4
(SE40_Draw status-list rewrite in `source/GAME.C`, `allocache` quick-path
in `SRC/CACHE1D.C`, `MMULTI.C` net hygiene, `ENGINE.C` getzsofslope sig,
unchecked file I/O in MENUES.C).

This file is a thin reconstruction. The round-5 sub-agent's full-length
markdown ghosted in the persistence regression that hit cycle 11; the SQL
inserts for the new todos survived, and the agent's returned summary is
restated here so the index is accurate.

## Findings

### CRITICAL — allocache quick-path

Two correctness bugs discovered in the candidate-cache speedup that
landed in commit `2925d51` (`SRC/CACHE1D.C` lines 86–113):

- **Stale candidate state.** `lastCandidateBesto` /
  `lastCandidateBestz` / `lastCandidateSize` are static and are written
  at the end of every `allocache` call. However, the "Suck things out"
  block immediately below (lines 145+) coalesces and shifts entries in
  `cac[]` as part of every allocation. Between calls, the slot indexed
  by `lastCandidateBestz` may refer to an entirely different memory
  region or block layout. The guard `lastCandidateBestz < cacnum` is a
  bounds check, not a *validity* check.
- **Loop-iteration index.** The inner walk
  `for(i=cand_o1,zz=lastCandidateBestz;i<cand_o2;i+=cac[zz++].leng)`
  reuses the canonical BUILD engine cache-walk idiom, but combined
  with the stale-state bug above, it can read lock values from blocks
  that are no longer at the slot we believed they were at.

**Resolution this cycle**: the quick-path was reverted (cycle 11). The
perf goal is reopened as `perf-cache-allocation` with a description
mandating either (a) invalidating `lastCandidate*` at the end of
`allocache` after the suck step, or (b) recomputing the offset by
walking `cac[]` before trusting the cached slot, plus a unit test.

### CRITICAL (pre-existing) — `fix-engine-unchecked-file-io`

158 unchecked `kdfread` / `dfwrite` / `dfread16` / `dfwrite16` / `kread`
call sites in `source/MENUES.C`. On a truncated or corrupt save file
the engine silently uses uninitialized memory. Verified still open at
start of cycle 11; round 1 of the cleanup landed in commit `26117d6`
(14 critical save/load sites). Remaining 145 sites tracked as
`fix-engine-unchecked-file-io-r2`.

### CRITICAL (pre-existing) — `fix-engine-labelcode-corruption`

`source/GAME.C:7118` initializes `labelcode = (long *)&sector[0]`,
allowing the script compiler in `GAMEDEF.C` to overwrite the sector
array. If `labelcnt` exceeds `sizeof(sectortype) * MAXSECTORS / 4`,
gameplay-critical state is corrupted. Still open.

### Verified safe (no regression)

- `SRC/ENGINE.C` pow2-mask wallscan/ceilscan/florscan optimization
  (commit `1c73e5f`): preserves bit-identical output for power-of-two
  tiles; bound checks remain in place for non-pow2.
- `SRC/ENGINE.C` `getzsofslope` `ceilz`/`florz` widened to `int32_t*`
  (commit `5e3f54c`): matches `sectortype` field width; no aliasing.
- `source/GAME.C` SE40_Draw status-list walk (commit `2925d51`): every
  `statnum` reachable from the old `MAXSPRITES` linear scan is also
  reachable via `headspritestat[]` / `nextspritestat[]`. Behaviour
  bit-identical, 5–12% faster on populated maps.
- `SRC/MMULTI.C` cycle-10/11 net work: platform types, handshake
  timeout, bounds-before-relay, ring buffer rewrite, graceful
  disconnect, payload-length cast. All gnu89-clean.

## New todos seeded

| id | severity |
|----|----------|
| `fix-engine-allocache-off-by-one` | CRITICAL — closed in cycle 11 revert |
| `fix-engine-allocache-stale-candidate` | CRITICAL — closed in cycle 11 revert |
| `audit-engine-allocache-correctness` | MEDIUM — add unit test for the redesigned quick-path |
| `fix-engine-unchecked-file-io-priority` | reminder — closed by round-1 file-I/O work |
