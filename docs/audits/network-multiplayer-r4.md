# Network & Multiplayer Audit Report - Round 4

**Persona**: network-multiplayer  
**Timestamp**: 2025-05-20  
**Scope**: AUDIT-ONLY round 4 — Verify cycle-15 closures + audit for additional unvalidated wire-supplied indices  
**Status**: Cycles 12 & 15 CLOSED; 3 r3 HIGH items remain pending; 3 NEW medium-risk findings identified  

---

## EXECUTIVE SUMMARY - ROUND 4

### ✅ Cycle Verification

**Cycle 12 (Complete)**: Little-endian wire-format helpers (`mm_pack_u16_le`, `mm_unpack_u16_le`) successfully landed in SRC/MMULTI.C:111–120. All wire packet length fields now use explicit endianness-safe pack/unpack.

**Cycle 15 (Complete)**: Two CRITICAL security fixes confirmed:
1. **from_player bounds validation** (line 199–206): Wire-supplied player ID clamped to [0, MAXPLAYERS) before array use. Invalid packets silently dropped.
2. **sendpacket() OOB protection** (line 603–607): Destination index `other` validated before `player_sockets[other]` access. Invalid calls return without sending.

### ⏳ Open R3 Items (Still Pending, NOT Re-flagged)

| Item | Severity | Status | Notes |
|------|----------|--------|-------|
| net-r3-replay-protection | HIGH | Pending | No explicit sequence numbers; TCP ordering implicit. Design space: packet-level seq vs. game-layer movefifoend. |
| net-r3-ipv6-support | HIGH | Pending | IPv4-only (AF_INET hardcoded). No dual-stack or IPv6 socket support. Blocks cloud/mobile deployment. |
| net-r3-packet-loss-diagnostic | HIGH | Pending | Silent DROP-OLDEST queue policy; pq_dropped_packets counter never logged. Sender unaware of loss. |

### 🟡 Round 4 NEW FINDINGS

| # | Finding | Severity | File:Lines | Root Cause |
|---|---------|----------|-----------|-----------|
| 1 | Unvalidated packet type 250 | MEDIUM | source/GAME.C:635 | Wire-supplied `packbuf[0]` used as other index without explicit GAME.C-layer bounds check (relies on MMULTI.C `from_player` validation from cycle 15) |
| 2 | Sound ID index OOB (packet type 7) | MEDIUM | source/GAME.C:553 | `RTS_GetSound(packbuf[1]-1)` uses unvalidated wire-supplied byte as array index; RTS table bounds unknown |
| 3 | Packet type 9 (game state) incomplete | LOW | source/GAME.C:543–560 | Packet type 9 exists but partially documented; uses packbuf[] indices without explicit validation in dispatch |

---

## DETAILED FINDINGS

### Finding 1: Packet Type 250 (Player Ready Flag) — Unvalidated Array Access

**File**: source/GAME.C:635  
**Severity**: MEDIUM  
**Type**: Data Flow / Incomplete Validation  

**The Issue**:
```c
// source/GAME.C line 391-640 (simplified):
while ((packbufleng = getpacket(&other,packbuf)) > 0)
{
    switch(packbuf[0])
    {
        // ... types 0,1,4,5,6,7,8,9 ...
        
        case 250:
            playerreadyflag[other]++;  // ← Array access on 'other'
            break;
    }
}
```

**Analysis**:
- `other` is returned from `getpacket()` (SRC/MMULTI.C:637), which extracts it from `packet_queue[pq_head].from_player`
- Cycle 15 added bounds validation in SRC/MMULTI.C:199–206 before queuing → `from_player` is guaranteed in [0, MAXPLAYERS)
- Therefore, `other` received by GAME.C is already bounds-checked
- **However**: This defense-in-depth is implicit (requires reading MMULTI.C bounds check code)
- **Risk**: If future refactoring removes MMULTI.C validation, GAME.C code becomes vulnerable

**Assessment**: 
- **Not a direct vulnerability** (MMULTI.C validation is in place from cycle 15)
- **Code hygiene issue**: Defensive coding at both layers would catch refactoring bugs
- **Recommendation**: Add optional assert/comment in GAME.C documenting the MMULTI.C assumption

---

### Finding 2: Sound ID Array Index OOB (Packet Type 7 — RTS Sound)

**File**: source/GAME.C:553–557  
**Severity**: MEDIUM  
**Type**: Buffer Overflow / Unvalidated Index  

**The Issue**:
```c
// source/GAME.C case 7 (RTS sound broadcast):
case 7:
    if (SoundToggle == 0 || ud.lockout == 1 || FXDevice == NumSoundCards)
        break;
    rtsptr = (char *)RTS_GetSound(packbuf[1]-1);  // ← Wire-supplied index
    if (*rtsptr == 'C')
        FX_PlayVOC3D(rtsptr,0,0,0,255,-packbuf[1]);
    else
        FX_PlayWAV3D(rtsptr,0,0,0,255,-packbuf[1]);
```

**Analysis**:
- Packet type 7 carries a sound ID in `packbuf[1]` (1-byte from wire)
- `RTS_GetSound(packbuf[1]-1)` calls a lookup function with wire-supplied index
- **Unknown bounds**: RTS sound table size not documented; `RTS_GetSound()` implementation not visible in codebase
- **Risk**: Attacker sends `packbuf[1]=256` → `RTS_GetSound(255)` → potential out-of-bounds access if RTS table < 256 entries

**Defense Mechanism**: 
- If `RTS_GetSound()` has internal bounds checking, it's opaque to this code
- No explicit validation in GAME.C before calling

**Recommendation**:
- Define `MAX_RTS_SOUNDS` constant
- Add bounds check: `if (packbuf[1] < 1 || packbuf[1] > MAX_RTS_SOUNDS) break;`
- Validate before `RTS_GetSound()` call

---

### Finding 3: Packet Type 9 (Game State Updates) — Partial Documentation

**File**: source/GAME.C:543–560  
**Severity**: LOW  
**Type**: Documentation Gap  

**The Issue**:
```c
case 9:
    for (j=2; j < packbufleng; j++) {  // ← Dynamic payload parsing
        i = packbuf[j];
        // Unpacks level_number, volume_number, player_skill, etc.
    }
```

**Analysis**:
- Packet type 9 updates game settings (level, volume, skill, co-op flag, etc.)
- Payload format: `[type=9][payload_len][data[0..packbufleng-1]]`
- Dynamic iteration over `packbuf[j]` (j from 2 to packbufleng)
- **No explicit bounds validation** in the loop

**Current Risk Level**: LOW
- `packbufleng` comes from `getpacket()` which validates payload_len in MMULTI.C:209
- MAXPACKETSIZE = 2048, so packbufleng is bounded

**Recommendation** (advisory):
- Document packet type 9 format explicitly (expected field offsets, bounds)
- Consider versioning packet type 9 if new fields are added in future

---

## CYCLE-15 CLOSURE VERIFICATION (Detailed)

### ✅ Fix 1: from_player Bounds Validation

**File**: SRC/MMULTI.C:199–206  
**Evidence**:
```c
/* Validate from_player bounds (CRITICAL: from_player is wire-supplied, attacker-controlled) */
if (from_player < 0 || from_player >= MAXPLAYERS) {
    printf("NET: SECURITY: Invalid from_player=%d (out of bounds [0,%d)). Dropping packet.\n",
        from_player, MAXPLAYERS);
    recv_bufs[i].len -= NET_HEADER_SIZE;
    if (recv_bufs[i].len > 0)
        memmove(recv_bufs[i].buf, recv_bufs[i].buf + NET_HEADER_SIZE, recv_bufs[i].len);
    continue;
}
```
**Status**: ✅ LANDED  
**Impact**: Prevents cycle-15 CRITICAL finding #1 (from_player OOB)

---

### ✅ Fix 2: sendpacket() Array Index Validation

**File**: SRC/MMULTI.C:602–607  
**Evidence**:
```c
/* Validate other is in bounds (CRITICAL: other used as array index for player_sockets) */
if (other < 0 || other >= MAXPLAYERS) {
    printf("NET: SECURITY: Invalid other=%d (out of bounds [0,%d)). Dropping packet.\n",
        other, MAXPLAYERS);
    return;
}
```
**Status**: ✅ LANDED  
**Impact**: Prevents cycle-15 CRITICAL finding #2 (sendpacket OOB)

---

### ✅ Cycle 12: Little-Endian Helpers

**File**: SRC/MMULTI.C:111–120  
**Evidence**:
```c
/* Little-endian u16 pack/unpack helpers (compile away to nothing on LE platforms) */
static inline void mm_pack_u16_le(unsigned char *buf, uint16_t val)
{
    buf[0] = (unsigned char)(val & 0xFF);
    buf[1] = (unsigned char)((val >> 8) & 0xFF);
}

static inline uint16_t mm_unpack_u16_le(const unsigned char *buf)
{
    return (uint16_t)(buf[0] | ((unsigned)buf[1] << 8));
}
```
**Status**: ✅ LANDED  
**Usage**: Used at line 195 (payload_len extraction), line 611 (header packing)  
**Impact**: Explicit endianness handling; future-proofs for big-endian ports

---

## ADDITIONAL OBSERVATIONS

### Wire-Supplied Indices Audit (Comprehensive Scan)

**Packet Type 0 (Host Sync)**:
- Line 415: `otherminlag = (long)((signed char)packbuf[j]);` — Signed char, no array index

**Packet Type 1 (Slave Sync)**:
- Line 470: `k = packbuf[1];` — Field selector (bit flags), no array indexing

**Packet Type 4 (Misc)**:
- Line 403: `multipos = packbuf[1];` — Position byte (no array access)

**Packet Type 5 & 8 (Game State)**:
- Lines 513–522: Level number, volume number, player skill, etc.
- These are stored directly in `ud.*` structures
- **No array indexing** (field assignment, not array subscript)

**Packet Type 6 (Version Check)**:
- Line 537: `if (packbuf[1] != BYTEVERSION)` — Version byte comparison
- Line 540: `ud.user_name[other][i-2] = packbuf[i];` — uses `other` (validated from cycle 15)

**Packet Type 7 (Sound)**: 
- **Finding 2 (above)** — `RTS_GetSound(packbuf[1]-1)`

**Packet Type 9 (Game State)**:
- **Finding 3 (above)** — Dynamic parsing, bounded by packbufleng

**Packet Type 250 (Ready Flag)**:
- **Finding 1 (above)** — uses `other` (validated from cycle 15)

**Packet Type 127 (No-op)**:
- Empty handler, no data access

**Packet Type 255 (Disconnect)**:
- Calls `gameexit()`, no data access

### New Packet Types Since R3

**Packet Type 250** (new):
- Player ready flag increment
- First seen in this audit (not documented in R3)

### Code Quality Notes

1. **No TODOs/FIXMEs in SRC/MMULTI.C** — Clean codebase, no dangling comments
2. **CRC Implementation** — Still dormant (lines 241–253 in MMULTI.C); functions exist but not used in packet send/receive
3. **Error Logging** — Cycle 15 fixes added diagnostic printf() for bounds violations (good for debugging)

---

## PACKET QUEUE METRICS

**Queue Size Increase** (since R3):
- R3 documented: PACKET_QUEUE_SIZE = 512
- **Current (R4)**: PACKET_QUEUE_SIZE = 1024 (line 82)
- **Impact**: Doubles buffer against DROP-OLDEST; burst protection improved

**Dropped Packet Counter**:
- `pq_dropped_packets` still never logged (open r3 item)
- Counter increments at line 230 but never examined

---

## RECOMMENDATIONS (Tiered by Scope)

### Blocking R4 (No Action Required — Cycles 12 & 15 Complete)
- ✅ from_player bounds validation
- ✅ sendpacket() OOB protection
- ✅ Little-endian helpers documented

### High Priority (R3 Open Items — Not Re-Flagged Here)
- [ ] **net-r3-replay-protection** — Add sequence numbers (HIGH, open from R3)
- [ ] **net-r3-ipv6-support** — Add AF_INET6 socket support (HIGH, open from R3)
- [ ] **net-r3-packet-loss-diagnostic** — Log dropped packets, expose counter API (HIGH, open from R3)

### Medium Priority (R4 New Findings)
- [ ] **Bounds-check RTS sound ID** (Finding 2) — Add MAX_RTS_SOUNDS constant + validation at source/GAME.C:553
- [ ] **Document packet type 9 format** (Finding 3) — Add comment block specifying expected field offsets
- [ ] **Add assert/comment in packet type 250** (Finding 1) — Document MMULTI.C `from_player` validation dependency

### Nice-to-Have
- [ ] Reduce CONNECT_TIMEOUT_SEC from 60s to 10s (R3 MEDIUM)
- [ ] Implement keepalive timeout during gameplay (R3 MEDIUM)
- [ ] Enable CRC checksums on packets (protocol bump required)

---

## SUMMARY TABLE

| Round | CRITICAL | HIGH | MEDIUM | LOW | Status |
|-------|----------|------|--------|-----|--------|
| **R1** | 3 | 4 | 2 | 1 | Baseline (11 findings) |
| **R2** | 1 | 4 | 3 | 0 | +6 findings (packet queue, compat layer) |
| **R3** | 2 | 3 | 5 | 0 | +10 findings (from_player OOB, sendpacket OOB, replay vuln, IPv4-only, etc.) |
| **R4** | 0 | 0 | 3 | 0 | +3 findings (type 250 implicit validation, sound ID OOB, type 9 incomplete doc) |
| **CUMULATIVE** | **6** | **11** | **13** | **1** | **31 total findings** |

---

## VERIFICATION CHECKLIST

- [x] Cycle 12 closure verified: `mm_pack_u16_le` / `mm_unpack_u16_le` at SRC/MMULTI.C:111–120
- [x] Cycle 15 closure verified: `from_player` bounds-check at SRC/MMULTI.C:199–206
- [x] Cycle 15 closure verified: `sendpacket()` bounds-check at SRC/MMULTI.C:603–607
- [x] R3 open items verified as still pending (no re-flagging):
  - net-r3-replay-protection (HIGH) — No sequence field, TCP ordering implicit
  - net-r3-ipv6-support (HIGH) — AF_INET hardcoded, no dual-stack
  - net-r3-packet-loss-diagnostic (HIGH) — Silent DROP-OLDEST, counter never logged
- [x] Comprehensive wire-supplied index audit completed (packet types 0–9, 127, 250, 255)
- [x] No pre-existing TODOs/FIXMEs in SRC/MMULTI.C

---

## CONCLUSION

**Cycle 15 security fixes are confirmed LANDED** (from_player bounds, sendpacket OOB). The multiplayer core is now more robust against malicious wire-supplied player IDs.

Round 4 audit identified **3 new medium-to-low risk findings**, all related to game-layer packet handling:
1. **Implicit validation** in packet type 250 (not a bug, but fragile)
2. **Unvalidated sound ID** in packet type 7 (requires MAX_RTS_SOUNDS bounds check)
3. **Incomplete documentation** of packet type 9 format

The **3 HIGH-severity items from R3 remain pending** (replay protection, IPv6, packet loss diagnostics). These are architectural and require protocol-level redesign or compat-layer work, not simple fixes.

**Production readiness**: MMULTI.C is now sufficiently hardened for LAN testing. Recommend multiplayer integration tests before release.
