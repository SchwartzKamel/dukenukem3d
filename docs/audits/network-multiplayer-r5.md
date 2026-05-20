# Network & Multiplayer Audit Report - Round 5

**Persona**: network-multiplayer  
**Timestamp**: 2025-06-01  
**Scope**: Cycle-20–24 closures + audit for unvalidated wire-supplied payload parsing  
**Status**: Cycle-22 (NET_CONNECT_TIMEOUT) & Cycle-24 (RTS MAX_RTS_SOUNDS) VERIFIED; 2 NEW HIGH-severity findings; 3 r3 items remain pending  

---

## EXECUTIVE SUMMARY - ROUND 5

### ✅ Cycle Verification (Since R4)

**Cycle 22 (Complete)**: NET_CONNECT_TIMEOUT reduced from 60s → 30s  
- Evidence: SRC/MMULTI.C:50 `#define NET_CONNECT_TIMEOUT 30`
- Impact: LAN multiplayer now times out faster, reducing zombie-connection footprint
- Status: ✅ VERIFIED

**Cycle 24 (Complete)**: RTS sound ID bounds fixed  
- Evidence: source/GAME.C:561–562 bounds check + source/RTS.H:40 `#define MAX_RTS_SOUNDS 256`
- Impact: Packet type 7 now validates `packbuf[1] < 1 || packbuf[1] >= MAX_RTS_SOUNDS`
- Status: ✅ VERIFIED (r4 Finding 2 resolved)

### ⏳ Open R3 Items (Still Pending, NOT Re-flagged)

| Item | Severity | Status | Notes |
|------|----------|--------|-------|
| net-r3-replay-protection | HIGH | Pending | No explicit sequence numbers; TCP ordering implicit |
| net-r3-ipv6-support | HIGH | Pending | IPv4-only (AF_INET hardcoded) |
| net-r3-packet-loss-diagnostic | HIGH | Pending | Silent DROP-OLDEST; pq_dropped_packets never logged |

### 🔴 Round 5 NEW FINDINGS (2 HIGH-severity)

| # | Finding | Severity | File:Lines | Root Cause |
|---|---------|----------|-----------|-----------|
| 1 | Packet type 9 buffer overflow (wchoice) | **CRITICAL** | source/GAME.C:543–546 | Loop writes `packbuf[i]` to `ud.wchoice[other][i-1]` without validating packbufleng ≤ MAX_WEAPONS+1 (12 bytes) |
| 2 | Packet types 0/1 out-of-bounds read | **HIGH** | source/GAME.C:434–440, 476–482 | Payload parsing reads `packbuf[j±1]` based on bit flags WITHOUT pre-validating sufficient data in packet |
| 3 | Packet types 5/8 unsafe bounds (level number, volume number) | MEDIUM | source/GAME.C:513–514, 572–573 | Wire-supplied level/volume directly assigned to ud.level_number, ud.volume_number; no range check |
| 4 | Packet type 250 implicit validation | MEDIUM | source/GAME.C:645–646 | Still relies on MMULTI.C from_player bounds (r4 Finding 1 unresolved) |

---

## DETAILED FINDINGS

### Finding 1: Packet Type 9 (Weapon Choice) — CRITICAL Buffer Overflow

**File**: source/GAME.C:543–546  
**Severity**: **CRITICAL**  
**Type**: Buffer Overflow / Unvalidated Array Write  

**The Issue**:
```c
case 9:
    for (i=1;i<packbufleng;i++)
        ud.wchoice[other][i-1] = packbuf[i];  // ← No bounds validation
    break;
```

**Analysis**:
- `ud.wchoice[MAXPLAYERS][MAX_WEAPONS]` is defined in source/DUKE3D.H:297 with MAX_WEAPONS=12 (source/DUKE3D.H:183)
- Loop bounds: `i` ranges from 1 to `packbufleng-1`, writing to `ud.wchoice[other][i-1]`
- **No validation** that `packbufleng - 1 <= MAX_WEAPONS` (12 bytes)
- Attacker sends packet type 9 with packbufleng=256 → writes 255 bytes into 12-byte array → **heap/stack corruption**

**Example Attack**:
```
Malicious packet: [0x09] [padding × 254] (packbufleng=255)
Result: Writes packbuf[1..254] into wchoice[other][0..253]
Expected: wchoice[other] is only 12 elements (48 bytes on 32-bit, 96 bytes on 64-bit)
Overflow: ✓ 203 bytes beyond array bounds
```

**Risk Level**: CRITICAL
- **Confidentiality**: Attacker can read adjacent memory via crafted packets
- **Integrity**: Attacker can corrupt playerstate, playerai, or other adjacent fields
- **Availability**: Crash via invalid memory write

**Defense Mechanism**: None. No pre-check, no runtime bounds validation.

**Recommendation**:
```c
case 9:
    if (packbufleng - 1 > MAX_WEAPONS) {
        printf("NET: SECURITY: Packet type 9 payload too large (%d > %d). Dropping.\n",
            packbufleng - 1, MAX_WEAPONS);
        break;
    }
    for (i=1;i<packbufleng;i++)
        ud.wchoice[other][i-1] = packbuf[i];
    break;
```

---

### Finding 2: Packet Types 0 & 1 (Master/Slave Sync) — HIGH Out-of-Bounds Read

**File**: source/GAME.C:434–440 (type 0), 476–482 (type 1)  
**Severity**: **HIGH**  
**Type**: Out-of-Bounds Read / Buffer Over-Read  

**The Issue**:
```c
// Type 0: Master sync (line 434)
if (l&1)   nsyn[i].fvel = packbuf[j]+((short)packbuf[j+1]<<8), j += 2;
if (l&2)   nsyn[i].svel = packbuf[j]+((short)packbuf[j+1]<<8), j += 2;
if (l&4)   nsyn[i].avel = (signed char)packbuf[j++];
if (l&8)   nsyn[i].bits = ((nsyn[i].bits&0xffffff00)|((long)packbuf[j++]));
// ... etc for l&16, l&32, l&64, l&128
```

**Analysis**:
- `k` (or `l` in type 0) is a bit-mask from `packbuf[1]` (or `packbuf[1]` in type 0)
- Each bit flag (1, 2, 4, 8, 16, 32, 64, 128) corresponds to a field that must be read from the payload
- **No validation** that `j + required_bytes <= packbufleng` before reading

**Example Attack** (Type 1):
```
Packet type 1: [0x01] [bitmask=0xFF] [1 byte of data]
- packbufleng = 3 (header + bitmask + 1 byte)
- j = 2, packbuf[1] = 0xFF (all flags set)
- First flag (l&1): reads packbuf[2] + (packbuf[3] << 8) → packbuf[3] is INVALID
- Subsequent flags read: packbuf[4], [5], [6], ... all out of bounds
Result: Information disclosure (uninitialized stack/heap) + undefined behavior
```

**Risk Level**: HIGH
- **Confidentiality**: Stack leaks, heap data disclosure via malformed packets
- **Integrity**: Invalid input written to player state (fvel, svel, avel, bits, horz)
- **Availability**: Unvalidated values may cause gameplay desync

**Boundary Conditions**:
- Type 1 minimum valid packet: `[marker][flags=0x00][data]` (3 bytes)
- Type 1 with flags=0x01: requires 5 bytes minimum (header + 2 bytes for fvel)
- Type 1 with flags=0xFF: requires 3+2+2+1+1+1+1+1+1 = 13 bytes minimum

**Defense Mechanism**: None. Loop exits when `j == packbufleng` (line 486/635) but reads happen BEFORE the check.

**Recommendation**:
```c
case 1:
    j = 2; k = packbuf[1];
    
    /* Validate sufficient data for declared fields */
    {
        int required_len = 2;  /* header + bitmask */
        if (k&1)   required_len += 2;  /* fvel (2 bytes) */
        if (k&2)   required_len += 2;  /* svel (2 bytes) */
        if (k&4)   required_len += 1;  /* avel (1 byte) */
        if (k&8)   required_len += 1;  /* bits byte 0 */
        if (k&16)  required_len += 1;  /* bits byte 1 */
        if (k&32)  required_len += 1;  /* bits byte 2 */
        if (k&64)  required_len += 1;  /* bits byte 3 */
        if (k&128) required_len += 1;  /* horz (1 byte) */
        
        if (packbufleng < required_len) {
            printf("NET: SECURITY: Packet type 1 truncated (%d < %d). Dropping.\n",
                packbufleng, required_len);
            break;
        }
    }
    
    // ... existing parse code ...
```

---

### Finding 3: Packet Types 5 & 8 (Game Settings) — MEDIUM Out-of-Range Field Assignment

**File**: source/GAME.C:513–514 (type 5), 572–573 (type 8)  
**Severity**: MEDIUM  
**Type**: Input Validation Gap / Game State Corruption  

**The Issue**:
```c
case 5:
    ud.m_level_number = ud.level_number = packbuf[1];
    ud.m_volume_number = ud.volume_number = packbuf[2];
    ud.m_player_skill = ud.player_skill = packbuf[3];
    // ... directly assigned from untrusted packbuf bytes ...
```

**Analysis**:
- Level, volume, skill, and flags are assigned directly from wire-supplied bytes
- **No validation** that `packbuf[1]` is a valid level number (e.g., 0–9 in PLUTOPAK)
- **No validation** that `packbuf[2]` is a valid volume (e.g., 0–3)
- **No validation** that `packbuf[3]` is a valid skill (e.g., 0–4 for difficulty levels)

**Risk Level**: MEDIUM
- **Integrity**: Invalid level/volume/skill can cause newgame() to index out-of-bounds maps/tile arrays
- **Availability**: Game crash if enterlevel() tries to load invalid map

**Example**:
```
Packet type 5: [0x05] [level=99] [volume=99] [skill=99] ...
Result: newgame(99, 99, 99) → attempts to load non-existent level → crash or undefined behavior
```

**Recommendation**:
```c
case 5:
    if (packbuf[1] >= MAXLEVELS || packbuf[2] >= MAXVOLUMES || packbuf[3] >= MAXSKILLS) {
        printf("NET: SECURITY: Invalid game settings. Dropping.\n");
        break;
    }
    ud.m_level_number = ud.level_number = packbuf[1];
    ud.m_volume_number = ud.volume_number = packbuf[2];
    // ... etc ...
```

---

### Finding 4: Packet Type 250 (Player Ready Flag) — MEDIUM Implicit Validation (Carryover from R4)

**File**: source/GAME.C:645–646  
**Severity**: MEDIUM  
**Type**: Defense-in-Depth Gap  

**The Issue**:
```c
case 250:
    playerreadyflag[other]++;  // ← Uses 'other' as array index
    break;
```

**Analysis**:
- `other` comes from `getpacket()`, which extracts `from_player` from the packet queue
- Cycle 15 added bounds validation in SRC/MMULTI.C:202–209 → `from_player` guaranteed in [0, MAXPLAYERS)
- **However**: This is an implicit dependency — if MMULTI.C validation is removed, GAME.C becomes vulnerable

**Risk Assessment**: Same as R4 Finding 1 — not a direct vulnerability, but fragile design.

**Status**: Documented from R4, no fix required, but recommend defensive assert (optional).

---

## CYCLE VERIFICATION (Detailed)

### ✅ NET_CONNECT_TIMEOUT Reduction (Cycle 22)

**File**: SRC/MMULTI.C:50  
**Evidence**:
```c
#define NET_CONNECT_TIMEOUT 30
```

**Usage**: SRC/MMULTI.C:404 — timeout check during host accept loop  
**Impact**: Reduces handshake stall from 60s to 30s, faster LAN responsiveness  
**Status**: ✅ VERIFIED  

### ✅ RTS Sound ID Bounds (Cycle 24)

**File**: source/GAME.C:561–562  
**Evidence**:
```c
if (packbuf[1] < 1 || packbuf[1] >= MAX_RTS_SOUNDS)
    break;
```

**Definition**: source/RTS.H:40 `#define MAX_RTS_SOUNDS 256`  
**Impact**: Packet type 7 OOB read FIXED (r4 Finding 2 resolved)  
**Status**: ✅ VERIFIED  

### ✅ Previous Cycle Fixes Still Valid

- Cycle 15: `from_player` bounds (SRC/MMULTI.C:202–209) — ✅ VERIFIED
- Cycle 15: `sendpacket()` bounds (SRC/MMULTI.C:602–607) — ✅ VERIFIED
- Cycle 12: Little-endian pack/unpack (SRC/MMULTI.C:114–123) — ✅ VERIFIED

---

## ADDITIONAL OBSERVATIONS

### Payload Format Parsing Risk (General)

The packet dispatch in source/GAME.C uses imperative byte-parsing (j += offsets based on bit flags) rather than declarative schema validation. This pattern is inherently error-prone:

- **Type 0/1**: Variable-length sync packets with bit-flag field selectors (very hard to validate without explicit field offsets)
- **Type 5/8**: Fixed-offset field assignment (easier to validate, but currently doesn't)
- **Type 9**: Unbounded array write with NO offset table (CRITICAL risk)

**Recommendation**: Document explicit packet formats and payload sizes for each type:

```c
/* Packet Format Specification */
enum PACKET_TYPE {
    PKT_HOST_SYNC = 0,  // [type][lag][flags×N][sync][input_fields...]
    PKT_SLAVE_SYNC = 1, // [type][flags][input_fields...] (variable)
    PKT_CHAT = 4,       // [type][message...] (null-terminated string)
    PKT_GAME_SETTINGS = 5, // [type][level][volume][skill][opt1..10] (11 bytes fixed)
    PKT_VERSION = 6,    // [type][version][name...] (variable)
    PKT_SOUND = 7,      // [type][sound_id] (2 bytes fixed)
    PKT_MAP_CHANGE = 8, // [type][level][volume][skill][opt1..10][map_name...] (≥11)
    PKT_WEAPON_CHOICE = 9, // [type][weapons[1..12]] (≤13 bytes fixed)
    PKT_RESPAWN = 16,   // [type][input_fields...] (variable, same as PKT_SLAVE_SYNC)
    PKT_UPDATE = 17,    // [type][input_fields...] (variable, same as PKT_SLAVE_SYNC)
    PKT_NOP = 127,      // [type] (1 byte)
    PKT_READY = 250,    // [type] (1 byte)
    PKT_DISCONNECT = 255 // [type] (1 byte)
};
```

---

## QUEUE & BUFFER METRICS (Since R4)

**Packet Queue Size**: Still PACKET_QUEUE_SIZE = 1024 (line 85, SRC/MMULTI.C) — unchanged since R4  
**Recv Buffer Size**: RECV_BUF_SIZE = 65536 (line 45, SRC/MMULTI.C) — unchanged  
**Dropped Packets Counter**: `pq_dropped_packets` still incremented at line 233, never logged (r3 item still pending)  
**TCP Header Size**: NET_HEADER_SIZE = 4 bytes [sender][dest][len_lo][len_hi] — unchanged  

---

## RECOMMENDATIONS (Tiered by Scope)

### Blocking R5 (NEW CRITICAL/HIGH Findings)

- [ ] **Packet type 9 buffer overflow** (Finding 1) — CRITICAL, requires bounds check before loop
- [ ] **Packet types 0/1 OOB read** (Finding 2) — HIGH, requires payload length pre-validation

### High Priority (Complement R5)

- [ ] **Packet types 5/8 range validation** (Finding 3) — Add level/volume/skill bounds checks
- [ ] **Packet format documentation** — Add formal spec for each type with payload sizes
- [ ] **Defensive programming** — Optional assert in type 250 for from_player validation

### Open R3 Items (NOT Re-Seeded)

- [ ] **net-r3-replay-protection** — Add sequence numbers (architectural change)
- [ ] **net-r3-ipv6-support** — Add AF_INET6 dual-stack support
- [ ] **net-r3-packet-loss-diagnostic** — Log dropped packets, expose counter API

---

## SUMMARY TABLE

| Round | CRITICAL | HIGH | MEDIUM | LOW | Status |
|-------|----------|------|--------|-----|--------|
| **R1** | 3 | 4 | 2 | 1 | Baseline (11 findings) |
| **R2** | 1 | 4 | 3 | 0 | +6 findings (packet queue, compat) |
| **R3** | 2 | 3 | 5 | 0 | +10 findings (from_player OOB, sendpacket OOB, etc.) |
| **R4** | 0 | 0 | 3 | 0 | +3 findings (type 250 implicit validation, sound ID OOB, type 9 doc gap) |
| **R5** | 1 | 1 | 2 | 0 | +4 findings (type 9 buffer overflow, types 0/1 OOB read, type 5/8 unsafe, type 250 implicit) |
| **CUMULATIVE** | **7** | **12** | **15** | **1** | **35 total findings** |

---

## VERIFICATION CHECKLIST

- [x] Cycle 22 closure verified: NET_CONNECT_TIMEOUT = 30 (SRC/MMULTI.C:50)
- [x] Cycle 24 closure verified: MAX_RTS_SOUNDS bounds check + constant (source/RTS.H:40, source/GAME.C:561)
- [x] Cycle 15 fixes re-verified: from_player bounds (SRC/MMULTI.C:202–209) and sendpacket bounds (SRC/MMULTI.C:602–607)
- [x] Comprehensive wire-supplied payload audit completed (packet types 0–9, 16–17, 127, 250, 255)
- [x] Buffer overflow in type 9 (wchoice) confirmed: NO bounds check before array write
- [x] OOB read in types 0/1 confirmed: NO pre-validation of payload length before field parsing
- [x] R3 open items re-verified as still pending (no new action)

---

## CONCLUSION

**Cycle-22 and Cycle-24 improvements verified successfully.** The multiplayer core is now more responsive (30s timeout) and sound-safe (MAX_RTS_SOUNDS bounds).

However, **Round 5 identified 2 NEW critical security vulnerabilities** in the game-layer packet dispatch:

1. **Packet Type 9 CRITICAL Buffer Overflow** — Attacker can overflow `wchoice[other]` array and corrupt adjacent memory
2. **Packet Types 0/1 HIGH Out-of-Bounds Read** — Attacker can craft truncated sync packets to leak uninitialized memory

Both require immediate mitigation before multiplayer release. The **3 HIGH-severity items from R3 remain pending** (replay protection, IPv6, packet-loss diagnostics); these are architectural and deferred.

**Production readiness**: MMULTI.C infrastructure is solid (bounds validation, timeouts, endianness handling), but source/GAME.C packet dispatch requires hardening before field deployment. Recommend code review + patch + regression tests before LAN testing resumes.
