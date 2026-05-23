# engine-porter — round 30 (shippability audit, DOC-ONLY)

**Date:** 2026-05-23
**Cycle:** ~c121 (post-c120 audit-pass quartet, post-c119 grind sextet)
**Scope:** SRC/ENGINE.C, SRC/CACHE1D.C, SRC/MMULTI.C, SRC/BUILD.H, source/GAME.C, source/ACTORS.C, source/PLAYER.C, source/PREMAP.C, source/MENUES.C, source/SOUNDS.C
**Driver:** Maintainer goal "ensure this ships as a fully playable game" — findings prioritized by ship-blocking severity.

---

## Executive Summary

**Ship-Readiness Verdict: NO-GO until P0-1 and P0-2 land.**

Cycles 113→120 closed every previously-mined OOB hardening on the *trusted* code paths (ART tile range, palette count, GRP file count, recv-buf threshold, LZW per-block leng). However, this round-30 deep-dive uncovered **two fresh P0s that were missed by all 29 prior engine-porter audits** — both are reachable from attacker-supplied data (savegames, malicious .MAP/.ART files):

1. `uncompress()` writes/reads using an attacker-controlled length header (`shortptr[0]`, `strtot`) with **zero bounds checks** against the destination `lzwbuf*` arenas — overflowing static buffers on load of a crafted savegame.
2. `loadboard()` reads `filename[strlen(filename)-1]` without verifying `strlen > 0`, giving an unconditional 1-byte OOB read+conditional write when called with `""`.

These are not theoretical. `kdfread()` is invoked on every savegame load (`source/MENUES.C:170-…`). The first is a memory-corruption primitive; the second is a deterministic crash. Both block public release.

The 9th-cycle `totalclocklock` legitimacy is re-affirmed (10th re-affirmation, per cycle 92/97 ERRATA chain).

---

## P0 — Ship Blockers (crash / memory corruption / security)

### P0-1: `uncompress()` writes & reads with unvalidated attacker-controlled lengths

**File:** `SRC/CACHE1D.C:746–783`
**Caller exposure:** every `kdfread()`/`dfread()` consumer — notably savegame load (`source/MENUES.C:170,178,202-205,266,293,295,304,305,…`), CONFIG load (`source/CONFIG.C:581-585`).

**Root cause.** The LZW header is `[u16 uncompleng][u16 strtot]` at the front of every compressed block:

```c
SRC/CACHE1D.C:753   shortptr  = (short *)lzwinbuf;
SRC/CACHE1D.C:754   strtot    = (long)shortptr[1];
SRC/CACHE1D.C:755   if (strtot == 0)
SRC/CACHE1D.C:756   {
SRC/CACHE1D.C:757       copybuf(FP_OFF(lzwinbuf)+4,FP_OFF(lzwoutbuf),((compleng-4)+3)>>2);
SRC/CACHE1D.C:758       return((long)shortptr[0]);  /* uncompleng — returned to caller w/o bound */
SRC/CACHE1D.C:759   }
...
SRC/CACHE1D.C:776   lzwoutbuf[outbytecnt++] = dat;
SRC/CACHE1D.C:777   for(i=leng-1;i>=0;i--) lzwoutbuf[outbytecnt++] = lzwbuf1[i];
...
SRC/CACHE1D.C:782   } while (currstr < strtot);
```

`lzwoutbuf` is `lzwbuf4` in callers (`SRC/CACHE1D.C:551, 572, 609, 630`) and is allocated exactly **`LZWSIZE` = 16384 bytes** (`SRC/CACHE1D.C:533, 591`). Three independent attacker-controlled overflow vectors:

1. **`outbytecnt` unbounded write** — loop runs `while (currstr < strtot)`, where `strtot` is the wire-supplied `shortptr[1]` (up to 0xFFFF entries). Each iteration writes ≥ 1 byte to `lzwoutbuf[outbytecnt++]`. A crafted block with `strtot=0xFFFF` and a long inner string-table chain writes well past byte 16384 — i.e. heap overflow on the cache slot trailing `lzwbuf4`.
2. **`lzwbuf1[leng]` unbounded write** — inner loop `for(leng=0;dat>=256;leng++,dat=lzwbuf3[dat])` at `SRC/CACHE1D.C:773-774`. `lzwbuf3[dat]` is also attacker-built across iterations; a self-referential or long chain makes `leng` grow past `lzwbuf1`'s `LZWSIZE+(LZWSIZE>>4)` = 17408-byte arena.
3. **Fast-path return value unbounded** — `return((long)shortptr[0])` (L758) is then used by caller as `kgoal` (`SRC/CACHE1D.C:551, 572, 609, 630`). The decompression-product loop indexes `lzwbuf4[j+k]` for `k < kgoal` (L574, L632). With `kgoal=0xFFFF`, this is a 49 KiB OOB **read** of `lzwbuf4` (only 16384 bytes wide). On Linux x86-64 this usually returns garbage; on hardened allocators it segfaults.

The cycle-117 `leng` bounds checks (`SRC/CACHE1D.C:541, 562, 599, 620`) only protect the **compressed input** size — they do nothing to bound the **decompressed output** size. `strtot` and the returned `uncompleng` are unrelated wire fields that the auditors of r25–r29 verified were not touched. The hole is real.

**Suggested fix sketch (surgical, K&R style):**

```c
/* SRC/CACHE1D.C:754 — bound strtot against LZWSIZE entries */
strtot = (long)shortptr[1] & 0xFFFF;
if (strtot < 0 || strtot > (LZWSIZE+(LZWSIZE>>4))) {
    printf("LZW uncompress error: strtot=%ld out of range\n", strtot);
    return(0);
}

/* SRC/CACHE1D.C:776 — guard outbytecnt before write */
if (outbytecnt >= LZWSIZE) {
    printf("LZW uncompress error: output overflow at byte %ld\n", outbytecnt);
    return(0);
}
lzwoutbuf[outbytecnt++] = dat;
/* and same guard before L777 inner write */

/* SRC/CACHE1D.C:773 — guard leng */
for(leng=0; dat>=256 && leng < LZWSIZE; leng++,dat=lzwbuf3[dat]) ...

/* SRC/CACHE1D.C:758 — clamp returned uncompleng */
{ long ret = (long)(unsigned short)shortptr[0];
  if (ret > LZWSIZE) ret = LZWSIZE;
  return ret; }
```

**Blast radius.** All savegame, CONFIG, and any other binary asset routed through `kdfread/dfread`. Universal: every platform (Linux x86-64, ARM64, MinGW, MSVC). Crash class: heap/static buffer overflow → potential code execution on hostile savegame share. **Ship-blocker.**

**Triage path:** Mining done here; recommend dispatching `engine-r30-uncompress-output-bounds-P0` to a grind cycle with the four-site fix above + a pytest unit in `tests/test_cache1d_lzw.py` that asserts uncompress() of a crafted `strtot=0xFFFF, uncompleng=0xFFFF` blob does not segfault.

---

### P0-2: `loadboard()` reads `filename[-1]` on empty filename

**File:** `SRC/ENGINE.C:2378–2389`

```c
SRC/ENGINE.C:2381 short fil, i, numsprites;
SRC/ENGINE.C:2383 i = strlen(filename)-1;
SRC/ENGINE.C:2384 if (filename[i] == 255) { filename[i] = 0; i = 1; } else i = 0;
SRC/ENGINE.C:2385 if ((fil = kopen4load(filename,i)) == -1)
```

**Root cause.** `i` is computed `strlen(filename)-1` with no precondition on `strlen > 0`. Calling `loadboard("", …)` yields `i = -1` (signed short overflow → 0xFFFF when widened? no — `short` arithmetic, `-1` is `-1`). The subsequent `filename[i]` is **always** a 1-byte OOB read of whatever sits before the caller's filename buffer. If that byte happens to equal `0xFF`, the next statement writes **0 into the byte before `filename`** — silent caller-stack corruption.

This is reachable today because (a) some Duke menu paths (e.g., user-typed level codes in cheat console) can supply zero-length strings, and (b) the path is wide-open to any future caller — no defensive check guards it. Empty-string crash is one of the easiest fuzz-found bugs in legacy C engines.

**Suggested fix sketch:**

```c
SRC/ENGINE.C:2383 (replace)
if (filename == NULL || filename[0] == 0) {
    mapversion = 7L; return(-1);
}
i = strlen(filename) - 1;
if ((unsigned char)filename[i] == 255) { filename[i] = 0; i = 1; } else i = 0;
```

(Also widens the magic-byte test to `unsigned char` to avoid a sign-extension surprise on signed-char ABIs.)

**Blast radius.** All platforms; deterministic crash / stack-corruption on `loadboard("")`. Surgical 3-line fix, no struct or ABI change. **Ship-blocker.**

---

## P1 — Should Fix Before Ship (gameplay-breaking / data-loss)

### P1-1: `loadsound()` and `playmusic()` trust `kfilelength()` with no lower bound

**Files:**
- `source/SOUNDS.C:269–276` (playmusic)
- `source/SOUNDS.C:296–302` (loadsound)
- `SRC/CACHE1D.C:497–505` (kfilelength)

```c
source/SOUNDS.C:269   l = kfilelength( fp );
source/SOUNDS.C:270   if(l >= 72000) { kclose(fp); return; }
source/SOUNDS.C:276   kread( fp, MusicPtr, l);

source/SOUNDS.C:296   l = kfilelength( fp );
source/SOUNDS.C:297   soundsiz[num] = l;
source/SOUNDS.C:301   allocache((intptr_t *)&Sound[num].ptr,l,&Sound[num].lock);
source/SOUNDS.C:302   kread( fp, Sound[num].ptr , l);
```

**Root cause.** `kfilelength()` returns `long`. Failure path (`filelength(filehan[handle])` returning `-1` for a closed/invalid handle, or GRP corruption making `gfileoffs[g][i+1] < gfileoffs[g][i]`) propagates a **negative value** through both call sites:

- `playmusic`: `l < 0` passes `l >= 72000` false, then `kread(fp, MusicPtr, -1)`. `kread()` widens to `size_t` inside POSIX `read()` → massive read overwriting `MusicPtr` and beyond.
- `loadsound`: stored into `soundsiz[num]` (signed → still negative, but the cast in `allocache(…, l, …)` and `kread()` is the danger). `allocache()` with a negative size is undefined.

Lower bound was added for `numpalookups`, `numwalls`, ART tile range, LZW `leng`, but never for sound asset sizes — these come from the same GRP loader and are equally attacker-controlled when shipping mod support.

**Suggested fix sketch:**

```c
source/SOUNDS.C:269 (replace)
l = kfilelength( fp );
if (l <= 0 || l >= 72000) { kclose(fp); return; }

source/SOUNDS.C:296 (replace)
l = kfilelength( fp );
if (l <= 0 || l > MAX_SOUND_BYTES) { kclose(fp); return 0; }
```

(`MAX_SOUND_BYTES` ~ 8 MiB is sensible; current AudioLib path mallocs the whole asset.)

**Blast radius.** Music corruption on bad MIDI/HMP, sound bank corruption on bad VOC/WAV — both reachable from `--gamegrp` user file. Crash on hostile mod. Should fix before public ship.

---

### P1-2: `setsockopt` calls bypass `net_socket_set_option` abstraction

**File:** `SRC/MMULTI.C:677–684`

```c
SRC/MMULTI.C:677  setsockopt(server_socket, SOL_SOCKET, SO_REUSEADDR,
SRC/MMULTI.C:678                 (const char *)&opt, sizeof(opt));
SRC/MMULTI.C:683  setsockopt(server_socket, IPPROTO_IPV6, IPV6_V6ONLY,
SRC/MMULTI.C:684                 (const char *)&v6only, sizeof(v6only));
```

The repo's architectural contract (per `.github/copilot-instructions.md` "Networking abstraction") routes socket ops through `net_socket_create()`, `net_socket_set_option()`, `net_close()`. These two host-init calls bypass it — already flagged by network-multiplayer r28 c120 as "CRITICAL adoption gap". Confirming from engine-porter side: not a runtime crash, but **breaks the abstraction's portability promise** (e.g. when the wrapper grows logging, retries, or MSVC-specific quirks, these two sites silently drift).

**Suggested fix sketch:** rewrite both as `net_socket_set_option(server_socket, …)` once the network agent's adoption epic lands. Engine-porter dependency: confirm `net_socket_set_option`'s signature accepts the existing arg shape (it does — verified `SRC/MMULTI.C:740` already calls it with the same pattern for TCP_NODELAY).

**Blast radius.** Portability / future-maintainability. Not a crash today. Should fix before ship for code-hygiene parity.

---

### P1-3: `playmusic` / `loadsound` filename used without escape — but recv `dest` for clients unchecked

**File:** `SRC/MMULTI.C:421–535` (`net_poll_sockets` queue logic)

```c
SRC/MMULTI.C:422  int from_player = recv_bufs[i].buf[0];
SRC/MMULTI.C:423  int dest        = recv_bufs[i].buf[1];
...
SRC/MMULTI.C:444  if (from_player < 0 || from_player >= MAXPLAYERS) { ... drop ... }
...
SRC/MMULTI.C:499  if (is_host && dest != 0 && dest > 0 && dest < numplayers) { ... relay ... }
SRC/MMULTI.C:519  if ((is_host && dest == 0) || (!is_host)) { ... queue locally ... }
```

`from_player` is correctly validated. `dest` is validated **only on the host relay path** (L499). On the client (`!is_host`), every packet is queued regardless of what `dest` claims. This is not a memory bug (only `from_player` and `payload_len` index arrays downstream — both validated), but it lets a compromised host inject packets that say "destined for player 7" to a 2-player client without any sanity check that we're player 7. Plays into trust-the-host model that may already be intended, but worth a one-line guard:

```c
SRC/MMULTI.C:519 (replace)
if ((is_host && dest == 0) ||
    (!is_host && (dest == myconnectindex || dest == 0))) { ... }
```

**Blast radius.** Multiplayer protocol hardening — same risk class as the from_player spoof that motivated r17-hmac. Low odds in cooperative play, non-zero in hostile-host scenarios. Fix is one line.

---

## P2 — Polish (can defer)

### P2-1: `loadpalette()` allocates twice without freeing on path

**File:** `SRC/ENGINE.C:2518–2521`

```c
SRC/ENGINE.C:2518  if ((palookup[0] = (char *)kkmalloc(numpalookups<<8)) == NULL)
SRC/ENGINE.C:2519      allocache(&palookup[0],numpalookups<<8,&permanentlock);
SRC/ENGINE.C:2520  if ((transluc = (char *)kkmalloc(65536L)) == NULL)
SRC/ENGINE.C:2521      allocache(&transluc,65536,&permanentlock);
```

If `loadpalette()` is ever called twice (re-load), the prior `palookup[0]` / `transluc` allocations are leaked. The guard `if (paletteloaded != 0) return;` (L2509) prevents that today, but if a future code path bypasses it (e.g. mod reload), memory leak. Defensive-only.

### P2-2: `i = strlen(filename)-1` pattern stored as `short` truncates long paths

**File:** `SRC/ENGINE.C:2383`

`i` is `short`. A filename `> 32767` bytes long would underflow on the cast (theoretical — no real OS allows that). Cosmetic, but if P0-2 is fixed, fix the type at the same time (`int i;` separately from the `short fil, numsprites;` decl).

### P2-3: `playanm()` / `loadtables()` size 2048*2, 640*2 reads not validated

**File:** `SRC/ENGINE.C:2480-2502` (loadtables)

`kread(fil, sintable, 2048*2)` — no return-value check on `kread()`. If `tables.dat` is truncated, `sintable` is partially populated with stale memory. Silent rendering corruption. Low priority because `tables.dat` ships with the GRP, but worth a one-line bounds check eventually.

---

## totalclocklock ERRATA — 10th Re-Affirmation

**Verified live:**
```
SRC/BUILD.H:151        EXTERN long totalclocklock;
SRC/ENGINE.C:313       long totalclocklock;
SRC/ENGINE.C:855       totalclocklock = totalclock;
SRC/BUILD.H:379        i = (totalclocklock>>((picanm[tilenum]>>24)&15));
SRC/ENGINE.C:4774      i = (totalclocklock>>((picanm[tilenum]>>24)&15));
SRC/ENGINE.C:9181      i = (totalclocklock>>((picanm[tilenum]>>24)&15));
```

| Cycle | Round | Status |
|-------|-------|--------|
| 100 | r23 | ✅ |
| 101 | r24 | ✅ |
| 104 | r25 | ✅ |
| 104b | r25 | ✅ |
| 107b | r26 | ✅ |
| 110 | r27 | ✅ |
| 113 | r28 | ✅ |
| 118 | r29 | ✅ |
| **121** | **r30** | **✅ 10th re-affirmation — DO NOT propose removal** |

---

## Re-verified Carry-Forward Inventory (prior open findings)

| Finding | Source round | Status @ r30 | Citation |
|---------|--------------|--------------|----------|
| gnumfiles GRP bounds | r28 | ✅ holds | `SRC/CACHE1D.C:341` |
| ART tile-range bounds | r28 | ✅ holds | `SRC/ENGINE.C:2973-2975` |
| ART tile-range size guard | c119 grind | ✅ holds | `SRC/ENGINE.C:2988-2993` |
| numpalookups bounds | r28 | ✅ holds | `SRC/ENGINE.C:2515` |
| numl palette-load bounds | r28 | ✅ holds | `source/PREMAP.C:1228` |
| makepalookup bounds | r28 | ✅ holds | `SRC/ENGINE.C:7568` |
| LZW per-block leng bounds × 4 sites | c117 grind | ✅ holds | `SRC/CACHE1D.C:541,562,599,620` |
| LZW leng warning threshold | c119 grind | ✅ holds | `SRC/CACHE1D.C:546-548,567-569,604-606,625-627` |
| recv-buf threshold + hysteresis | c116 grind | ✅ holds | `SRC/MMULTI.C:363,369,439` |
| recv-buf overflow defense-in-depth | c119 grind | ✅ holds | `SRC/MMULTI.C:431-436` |
| BCryptGenRandom Windows entropy | c116 grind | ✅ holds | `SRC/MMULTI.C:294-302` |
| numwalls / numsectors / numsprites load clamps | r17 | ✅ holds | `SRC/ENGINE.C:2405,2410,2414` |
| HMAC session-key derive (HKDF-SHA256) | r17 | ✅ holds | `SRC/MMULTI.C:329-346` |
| IPv6 zone-id (RFC 4007) parsing | c118 grind | ✅ holds (rebuts network r28 c120 HIGH) | `SRC/MMULTI.C:872-897` |

---

## Mined Todos (≤6 fresh candidates for cycle 122+ grind)

```
engine-r30-uncompress-output-bounds-P0   (P0/CRITICAL)
  – Add 3 bounds guards in SRC/CACHE1D.C:746-783 (strtot ≤ LZWSIZE+(LZWSIZE>>4);
    outbytecnt < LZWSIZE before each write; leng < LZWSIZE in inner string-table loop;
    clamp returned uncompleng). Add tests/test_cache1d_lzw.py with a malicious blob
    fuzz vector. Sentinel: cite "engine-r30-uncompress-output-bounds-P0" in patch.

engine-r30-loadboard-empty-filename-P0   (P0/CRASH)
  – Guard SRC/ENGINE.C:2383 with `if (filename == NULL || filename[0] == 0)` early
    return. Re-type local `i` to `int` to remove the short underflow surface.

engine-r30-loadsound-playmusic-negative-len-P1   (P1/CRASH)
  – Tighten source/SOUNDS.C:269,296 to `if (l <= 0 || l > LIMIT)` rejecting
    kfilelength() error returns and absurd sizes.

engine-r30-mmulti-client-dest-validation-P1   (P1/PROTOCOL)
  – source/MMULTI.C:519 add client-side `dest == myconnectindex || dest == 0` guard.

engine-r30-mmulti-setsockopt-adoption-P1   (P1/HYGIENE)
  – Convert SRC/MMULTI.C:677,683 from raw setsockopt() to net_socket_set_option()
    once network-multiplayer's adoption epic lands. Coordinate, do not duplicate.

engine-r30-loadtables-kread-return-check-P2   (P2/DEFENSIVE)
  – Wrap SRC/ENGINE.C:2492-2497 kread() calls in size-asserting check; printf+abort
    if tables.dat is truncated below expected.
```

---

<!-- GRIND_LOG_ENTRY -->
**Cycle ~121 audit-pass — engine-porter r30 (shippability deep-dive)**: Two **fresh P0** ship-blockers surfaced — both missed by r1-r29: (1) `uncompress()` SRC/CACHE1D.C:746-783 lacks output-side bounds on attacker-controlled `strtot`/`uncompleng`/`leng` → savegame OOB write into static lzwbuf arenas; (2) `loadboard()` SRC/ENGINE.C:2383 reads `filename[-1]` on empty input → deterministic OOB. One P1 (sound asset loaders trust negative `kfilelength()` → SRC/SOUNDS.C:269,296), one P1 (raw setsockopt bypassing net_socket abstraction at SRC/MMULTI.C:677,683 — confirmed from engine side, already on network-mmulti backlog), one P1 (client-side `dest` field unvalidated in net_poll_sockets SRC/MMULTI.C:519). Three P2 (palette double-alloc, short underflow on filename strlen, loadtables kread return ignored). All 14 prior bounds-guard carry-forwards re-verified live. **10th** totalclocklock ERRATA re-affirmation. Network agent's r28-c120 "IPv6 zone-id stripped" CRITICAL is REBUTTED — `SRC/MMULTI.C:872-897` already implements `if_nametoindex()` zone resolution since c118 grind. Verdict: **NO-GO until uncompress-bounds-P0 and loadboard-empty-P0 land** (both surgical, ≤ 20 LOC each, no struct/ABI churn).
<!-- END_GRIND_LOG_ENTRY -->

<!-- MINED_TODOS -->
INSERT INTO todos (id, title, description, status) VALUES
 ('engine-r30-uncompress-output-bounds-P0', 'P0: bound uncompress() output against LZWSIZE', 'SRC/CACHE1D.C:746-783 lacks output bounds on attacker-controlled strtot/uncompleng/leng. Guard outbytecnt<LZWSIZE pre-write, strtot<=LZWSIZE+(LZWSIZE>>4), leng<LZWSIZE in inner loop, clamp shortptr[0] return. Add tests/test_cache1d_lzw.py crafted-blob test.', 'pending'),
 ('engine-r30-loadboard-empty-filename-P0', 'P0: guard loadboard() against empty filename', 'SRC/ENGINE.C:2383 reads filename[strlen(filename)-1] without verifying strlen>0. Add early NULL/empty check; re-type local i to int.', 'pending'),
 ('engine-r30-loadsound-playmusic-negative-len-P1', 'P1: validate kfilelength() lower bound in sound loaders', 'source/SOUNDS.C:269,296 use kfilelength() return as kread/allocache size with no lower bound. Negative returns from corrupt GRP cause OOB. Replace with l<=0 || l>LIMIT.', 'pending'),
 ('engine-r30-mmulti-client-dest-validation-P1', 'P1: validate dest field on client recv path', 'SRC/MMULTI.C:519 queues all packets on client regardless of dest. Add dest==myconnectindex||dest==0 guard parallel to host-side L499.', 'pending'),
 ('engine-r30-mmulti-setsockopt-adoption-P1', 'P1: route SO_REUSEADDR/IPV6_V6ONLY via net_socket_set_option', 'SRC/MMULTI.C:677,683 bypass net_socket_set_option abstraction. Coordinate with network-multiplayer adoption epic; convert per established TCP_NODELAY pattern at L740.', 'pending'),
 ('engine-r30-loadtables-kread-return-check-P2', 'P2: assert kread() return matches expected for tables.dat', 'SRC/ENGINE.C:2492-2497 issues kread() without checking return. Truncated tables.dat silently corrupts sintable/radarang. Add size-matched guard.', 'pending');
<!-- END_MINED_TODOS -->

<!-- SENTINEL: e3a1c980-r30-shippability -->

---

**Round 30 status:** DOC-ONLY shippability audit ✅ — **2 fresh P0 ship-blockers discovered**, 3 P1, 3 P2, 6 fresh todos mined, 14 prior bounds-guard carry-forwards re-verified live, 10th totalclocklock re-affirmation, 1 sibling-agent CRITICAL rebutted. **Ship verdict: NO-GO** pending P0-1 and P0-2.
