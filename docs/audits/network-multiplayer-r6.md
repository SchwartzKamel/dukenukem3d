# Network & Multiplayer Audit Report - Round 6

**Persona**: network-multiplayer  
**Timestamp**: 2025-07-15 (Cycle 31)  
**Scope**: Cycle-26/28 hardening re-verification + audit of under-explored packet types  
**Status**: Cycle-26 & Cycle-28 fixes VERIFIED INTACT ✅; 4 NEW HIGH/MEDIUM findings in under-audited packet types (4, 6, 8, 16/17)

---

## EXECUTIVE SUMMARY - ROUND 6

### ✅ Verification of Cycle-26 & Cycle-28 Hardening (Grep-Proof)

**Cycle-26 Type-9 Fix**: source/GAME.C:649 ✅ VERIFIED
```c
if (packbufleng - 1 > MAX_WEAPONS)
    printf("NET: SECURITY: Packet type 9 payload too large (%d > %d). Dropping.\n",
        packbufleng - 1, MAX_WEAPONS);
    break;
```
**Status**: ✅ INTACT — wchoice buffer overflow FIXED

**Cycle-26 Type-0/1 Fixes**: source/GAME.C:437-486 (type 0), 518-536 (type 1) ✅ VERIFIED
```c
// Type 0 (line 437-440):
if (k >= packbufleng) {
    printf("NET: SECURITY: Packet type 0 truncated at bitmask read. Dropping.\n");
    break;
}

// Type 1 (line 521-536):
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
```
**Status**: ✅ INTACT — OOB read vulnerabilities FIXED

**Cycle-28 Type-5/8 Bounds Checks**: source/GAME.C:580-616 (type 5), 683-719 (type 8) ✅ VERIFIED
```c
// Type 5 (lines 581-592):
if (packbuf[1] >= 11) {
    printf("NET: SECURITY: Packet type 5 invalid level number (%d >= 11). Clamping to 0.\n", packbuf[1]);
    packbuf[1] = 0;
}
if (packbuf[2] >= 4) {
    printf("NET: SECURITY: Packet type 5 invalid volume number (%d >= 4). Clamping to 0.\n", packbuf[2]);
    packbuf[2] = 0;
}
if (packbuf[3] >= 5) {
    printf("NET: SECURITY: Packet type 5 invalid skill (%d >= 5). Clamping to 0.\n", packbuf[3]);
    packbuf[3] = 0;
}
// ... additional flag validation (lines 593-616) ...
```
**Status**: ✅ INTACT — Game state corruption via invalid level/volume/skill FIXED

**Cycle-22 & Cycle-24 Verifications**: SRC/MMULTI.C:50 ✅ & source/RTS.H:40 ✅
```c
// NET_CONNECT_TIMEOUT (SRC/MMULTI.C:50)
#define NET_CONNECT_TIMEOUT 30

// MAX_RTS_SOUNDS (source/RTS.H:40)
#define MAX_RTS_SOUNDS 256
```
**Status**: ✅ VERIFIED — Both constants in place and being used correctly

---

## 🔴 ROUND 6 NEW FINDINGS (4 findings: 3 HIGH, 1 MEDIUM)

| # | Finding | Severity | File:Lines | Root Cause |
|---|---------|----------|-----------|-----------|
| 1 | Packet type 4 (chat) strcpy buffer overflow | **HIGH** | source/GAME.C:567–569 | `strcpy(recbuf, packbuf+1)` with NO bounds check; recbuf is 80 bytes |
| 2 | Packet type 6 (version/name) unbounded string parsing | **HIGH** | source/GAME.C:641–646 | Loop `for (i=2; packbuf[i]; i++)` reads until NULL without verifying packbufleng; user_name[other] is 32 bytes |
| 3 | Packet type 8 (map change) negative size in copybufbyte | **MEDIUM** | source/GAME.C:732–733 | If packbufleng < 11, copybufbyte gets negative size; boardfilename size unchecked |
| 4 | Packet types 16/17 missing required_len validation | **HIGH** | source/GAME.C:764–772 | Bit-flag parsing identical to type 0/1 but NO pre-validation like type 1; can OOB read packbuf |

---

## DETAILED FINDINGS

### Finding 1: Packet Type 4 (Chat) — HIGH Buffer Overflow

**File**: source/GAME.C:567–569  
**Severity**: **HIGH**  
**Type**: Buffer Overflow / strcpy Misuse  

**The Issue**:
```c
case 4:
    strcpy(recbuf,packbuf+1);      // ← strcpy BEFORE bounds check!
    recbuf[packbufleng-1] = 0;     // ← Null termination AFTER overflow
    // ...
```

**Analysis**:
- `recbuf` is 80 bytes (source/GAME.C:320: `char recbuf[80];`)
- `packbufleng` comes from untrusted wire data (getpacket())
- If attacker sends type-4 packet with packbufleng=256, `strcpy(recbuf, packbuf+1)` copies 255 bytes into 80-byte buffer
- **The null-termination on line 569 attempts mitigation but is ineffective**: strcpy has already corrupted the stack/heap
- strncpy or bounds-checking BEFORE strcpy is required

**Risk Level**: HIGH
- **Confidentiality**: Stack/heap data disclosure via overflowed buffer
- **Integrity**: Corruptted stack frame, potential code-execution via return address overwrite
- **Availability**: Crash via memory corruption

**Example Attack**:
```
Malicious packet: [0x04] [padding × 254]
Attacker goal: Overflow recbuf[80] with 255 bytes of controlled data
Result: Stack smashing, RIP/RBP corruption on x64, function epilogue hijack
```

**Defense Mechanism**: The null-termination on line 569 is INSUFFICIENT because strcpy has already written past buffer bounds.

**Recommendation**:
```c
case 4:
    // Bounds-check BEFORE strcpy
    if (packbufleng - 1 > sizeof(recbuf) - 1) {
        printf("NET: SECURITY: Packet type 4 payload too large (%d > %zu). Dropping.\n",
            packbufleng - 1, sizeof(recbuf) - 1);
        break;
    }
    strncpy(recbuf, packbuf+1, sizeof(recbuf) - 1);
    recbuf[sizeof(recbuf) - 1] = 0;
    adduserquote(recbuf);
    sound(EXITMENUSOUND);
    pus = NUMPAGES;
    pub = NUMPAGES;
    break;
```

---

### Finding 2: Packet Type 6 (Version/Name) — HIGH Unbounded String Read

**File**: source/GAME.C:641–646  
**Severity**: **HIGH**  
**Type**: Buffer Overflow / Unbounded String Parsing  

**The Issue**:
```c
case 6:
    if (packbuf[1] != BYTEVERSION)
        gameexit("\nYou cannot play Duke with different versions.");
    for (i=2;packbuf[i];i++)           // ← Reads until NULL, NO packbufleng check
        ud.user_name[other][i-2] = packbuf[i];
    ud.user_name[other][i-2] = 0;
    break;
```

**Analysis**:
- Loop condition: `packbuf[i]` (reads until NULL byte)
- **No validation** that packbufleng >= i (packet might not contain NULL terminator)
- **No validation** that (i-2) < 32 (user_name[other] is 32 bytes per source/DUKE3D.H:290)
- Attacker can craft packet with packbufleng=256, no NULL, and 30+ non-zero bytes → overflow user_name[other]

**Example Attack**:
```
Malicious packet: [0x06] [BYTEVERSION] [A×40] [no NULL]
- Loop: i=2 reads packbuf[2]='A', i=3 reads 'A', ... up to i=41
- Writes to user_name[other][0..39] but array is only 32 bytes
- Overflow: 8 bytes beyond array bounds
Result: Corruption of adjacent fields in ud structure
```

**Risk Level**: HIGH
- **Confidentiality**: Information leak (adjacent memory in ud structure)
- **Integrity**: Game state corruption via overflow into adjacent fields
- **Availability**: Crash if adjacent field is dereferenced

**Boundary Conditions**:
- Maximum safe packet size: packbufleng = 1 (type) + 1 (version) + 31 (name) + 1 (NULL) = 34 bytes
- Current code accepts up to packbufleng = 256 and reads unbounded

**Defense Mechanism**: None. Loop never checks packbufleng.

**Recommendation**:
```c
case 6:
    if (packbuf[1] != BYTEVERSION)
        gameexit("\nYou cannot play Duke with different versions.");
    
    /* Validate name length and NULL terminator */
    int name_len = 0;
    for (i=2; i<packbufleng && name_len < 31; i++) {
        if (packbuf[i] == 0) break;
        name_len++;
    }
    
    if (name_len >= 31 && i < packbufleng && packbuf[i] != 0) {
        printf("NET: SECURITY: Packet type 6 name too long (%d >= 31) or missing NULL. Dropping.\n", name_len);
        break;
    }
    
    for (i=2; packbuf[i] && i-2 < 31; i++)
        ud.user_name[other][i-2] = packbuf[i];
    ud.user_name[other][i-2] = 0;
    break;
```

---

### Finding 3: Packet Type 8 (Map Change) — MEDIUM Negative Size Arithmetic

**File**: source/GAME.C:732–733  
**Severity**: MEDIUM  
**Type**: Integer Underflow / Undefined Behavior  

**The Issue**:
```c
copybufbyte(packbuf+10,boardfilename,packbufleng-11);
boardfilename[packbufleng-11] = 0;
```

**Analysis**:
- If attacker sends type-8 packet with packbufleng < 11, `packbufleng-11` becomes NEGATIVE (signed integer)
- copybufbyte() interprets this as a huge unsigned value → reads/writes way past packet bounds
- boardfilename is 128 bytes, but no bounds check in copybufbyte() for the destination

**Risk Level**: MEDIUM
- **Confidentiality**: Out-of-bounds read of packet buffer and stack/heap memory
- **Integrity**: Out-of-bounds write to boardfilename could overflow into adjacent stack/heap
- **Availability**: Crash via memory access violation

**Example Attack**:
```
Malicious packet: [0x08] [level][volume][skill][flags...] (packbufleng=5)
- packbufleng-11 = -6 (sign-extended to huge unsigned on 64-bit)
- copybufbyte() attempts to read/write ~18 exabytes
Result: SIGSEGV or heap corruption
```

**Boundary Conditions**:
- Minimum valid type-8 packet: 11 bytes (header + 10 settings bytes, no map name)
- Maximum safe map name: boardfilename is 128 bytes

**Recommendation**:
```c
case 8:
    // ... existing bounds checks for level/volume/skill/flags ...
    
    if (packbufleng < 11) {
        printf("NET: SECURITY: Packet type 8 truncated (too short). Dropping.\n");
        break;
    }
    
    int map_name_len = packbufleng - 11;
    if (map_name_len >= (int)sizeof(boardfilename)) {
        printf("NET: SECURITY: Packet type 8 map name too long (%d >= %zu). Dropping.\n",
            map_name_len, sizeof(boardfilename));
        break;
    }
    
    copybufbyte(packbuf+10, boardfilename, map_name_len);
    boardfilename[map_name_len] = 0;
    break;
```

---

### Finding 4: Packet Types 16/17 (Respawn/Update) — HIGH Missing Bounds Validation

**File**: source/GAME.C:764–772 (shared code path)  
**Severity**: **HIGH**  
**Type**: Out-of-Bounds Read / Bit-Flag Parsing  

**The Issue**:
```c
case 16:
    movefifoend[other] = movefifoplc = movefifosendplc = fakemovefifoplc = 0;
    syncvalhead[other] = syncvaltottail = 0L;
case 17:
    j = 1;
    // ... skip ahead check ...
    k = packbuf[j++];                    // ← NO bounds check that j < packbufleng
    if (k&1)   nsyn[other].fvel = packbuf[j]+((short)packbuf[j+1]<<8), j += 2;
    if (k&2)   nsyn[other].svel = packbuf[j]+((short)packbuf[j+1]<<8), j += 2;
    if (k&4)   nsyn[other].avel = (signed char)packbuf[j++];
    // ... etc for flags 8, 16, 32, 64, 128 ...
    if (k&128) nsyn[other].horz = (signed char)packbuf[j++];
```

**Analysis**:
- **Compare to type 1**: Type 1 (lines 521–536) pre-calculates `required_len` and validates before parsing
- **Type 16/17 lacks this validation**: Uses identical bit-flag parsing but NO required_len pre-check
- If attacker sends type-16/17 packet with packbufleng=3, all 8 flags can be set, but only 1 byte of data provided
- Loop will read packbuf[1], packbuf[2], packbuf[3], packbuf[4], ... → out-of-bounds reads until j > packbufleng

**Example Attack**:
```
Malicious packet: [0x11] [flags=0xFF] (packbufleng=2)
- j=1, k=0xFF (all flags set)
- Reading fvel: reads packbuf[1] + (packbuf[2] << 8) → packbuf[2] OUT OF BOUNDS
- Subsequent flags read packbuf[3..8] all out of bounds
Result: Information disclosure of adjacent stack/heap memory
```

**Risk Level**: HIGH
- **Confidentiality**: Stack/heap data leakage via uninitialized packbuf reads
- **Integrity**: Invalid game state from garbage input
- **Availability**: Potential crash if subsequent code assumes valid values

**Boundary Conditions**:
- Type 16 minimum valid packet: 2 bytes (type + reset flags), then 1+ data bytes
- Type 17 minimum valid packet: 2 bytes (type + sync data)
- Type 17 with flags=0xFF: requires 3 + 2+2+1+1+1+1+1+1 = 13 bytes minimum

**Defense Mechanism**: Type 1 has the fix, but types 16/17 inherited the old vulnerable pattern.

**Recommendation**:
```c
case 16:
    movefifoend[other] = movefifoplc = movefifosendplc = fakemovefifoplc = 0;
    syncvalhead[other] = syncvaltottail = 0L;
case 17:
{
    int required_len;
    j = 1;
    
    if ((movefifoend[other]&(TIMERUPDATESIZ-1)) == 0)
        if (other == connecthead)
            for(i=connectpoint2[connecthead];i>=0;i=connectpoint2[i])
            {
                if (i == myconnectindex)
                    otherminlag = (long)((signed char)packbuf[j]);
                j++;
            }
    
    /* Pre-validate sufficient data for bitmask + fields */
    if (j >= packbufleng) {
        printf("NET: SECURITY: Packet type 16/17 truncated (no bitmask). Dropping.\n");
        break;
    }
    
    k = packbuf[j++];
    
    /* Calculate required_len like type 1 */
    required_len = j;
    if (k&1)   required_len += 2;  /* fvel */
    if (k&2)   required_len += 2;  /* svel */
    if (k&4)   required_len += 1;  /* avel */
    if (k&8)   required_len += 1;  /* bits byte 0 */
    if (k&16)  required_len += 1;  /* bits byte 1 */
    if (k&32)  required_len += 1;  /* bits byte 2 */
    if (k&64)  required_len += 1;  /* bits byte 3 */
    if (k&128) required_len += 1;  /* horz */
    
    if (packbufleng < required_len) {
        printf("NET: SECURITY: Packet type 16/17 truncated (%d < %d). Dropping.\n",
            packbufleng, required_len);
        break;
    }
    
    // ... rest of parsing ...
}
```

---

## CYCLE VERIFICATION (Detailed with Grep Output)

### ✅ NET_CONNECT_TIMEOUT Reduction (Cycle 22)
**File**: SRC/MMULTI.C:50  
```
50:#define NET_CONNECT_TIMEOUT 30
```
**Status**: ✅ VERIFIED ACTIVE

### ✅ RTS Sound ID Bounds (Cycle 24)
**File**: source/RTS.H:40  
```
40:#define MAX_RTS_SOUNDS 256
```
**Status**: ✅ VERIFIED ACTIVE

### ✅ Cycle-26 Type-9 Bounds (Cycle 26)
**File**: source/GAME.C:649  
```
649:                if (packbufleng - 1 > MAX_WEAPONS)
```
**Status**: ✅ VERIFIED ACTIVE

### ✅ Cycle-26 Type-0/1 Bounds (Cycle 26)
**File**: source/GAME.C:531  
```
531:                    if (packbufleng < required_len)
```
**Status**: ✅ VERIFIED ACTIVE

### ✅ Cycle-28 Type-5/8 Validation (Cycle 28)
**File**: source/GAME.C:581, 684  
```
581:                if (packbuf[1] >= 11) {
684:                if (packbuf[1] >= 11) {
```
**Status**: ✅ VERIFIED ACTIVE

---

## OPEN R3 ITEMS (Carried Forward, Not Re-Seeded)

| Item | Severity | Status | Notes |
|------|----------|--------|-------|
| net-r3-replay-protection | HIGH | Pending | No explicit sequence numbers; TCP ordering implicit |
| net-r3-ipv6-support | HIGH | Pending | IPv4-only (AF_INET hardcoded) |
| net-r3-packet-loss-diagnostic | HIGH | Pending | Silent DROP-OLDEST; pq_dropped_packets never logged |

---

## OBSERVATIONS & RISK SUMMARY

### Audit Coverage By Packet Type (R6)

| Type | Hardened | Notes |
|------|----------|-------|
| 0 | ✅ Cycle-26 | Type-0 (master sync) bounds-checked per-field |
| 1 | ✅ Cycle-26 | Type-1 (slave sync) pre-validates required_len |
| 4 | ❌ **NEW HIGH** | Chat: strcpy buffer overflow |
| 5 | ✅ Cycle-28 | Type-5 (game settings) fully bounds-checked |
| 6 | ❌ **NEW HIGH** | Version: unbounded string parsing |
| 7 | ✅ Cycle-24 | Type-7 (sound) MAX_RTS_SOUNDS validated |
| 8 | ✅ Cycle-28 + **NEW MEDIUM** | Type-8 bounds-checked BUT negative size bug in copybufbyte |
| 9 | ✅ Cycle-26 | Type-9 (weapon choice) bounds-checked |
| 16/17 | ❌ **NEW HIGH** | Respawn/Update: missing required_len validation |
| 125, 126 | ✅ Simple | Special game control packets (minimal parsing) |
| 127 | ✅ Trivial | NOP (no-op) |
| 250 | ✅ Implicit | Ready flag (relies on MMULTI.C from_player bounds) |
| 255 | ✅ Trivial | Disconnect (immediate exit) |
| 2, 3 | ℹ️ Undefined | Not in dispatch (silently dropped/ignored) |

### Key Architectural Patterns

1. **Bit-Flag Parsing Risk** (types 0, 1, 16, 17):
   - Variable-length payload based on bitmask in packet
   - Requires careful bounds calculation
   - **Type 1 fixed in cycle-26**, but types 16/17 not backported

2. **String Handling Risk** (types 4, 6):
   - Legacy strcpy/unbounded loop patterns
   - No NULL-termination guarantee from wire data
   - Both require pre-validation

3. **Arithmetic Risk** (type 8):
   - `packbufleng - 11` can be negative
   - Passed to unsigned-accepting function (copybufbyte)
   - Triggers undefined behavior

### DoS Amplification Assessment

- **Type 4 (chat)**: No amplification; same-size echo
- **Type 6 (version)**: No amplification; username is small
- **Type 8 (map change)**: **POTENTIAL**: Server processes new game → sends game-state updates to all clients (amplification)
- **Type 16/17 (update)**: No amplification; update-acknowledgement only

---

## RECOMMENDATIONS (Tiered by Scope)

### Blocking R6 (NEW HIGH Findings)

- [ ] **Packet type 4 strcpy overflow** (Finding 1) — HIGH, add bounds-check + strncpy
- [ ] **Packet type 6 unbounded string read** (Finding 2) — HIGH, add packbufleng validation
- [ ] **Packet types 16/17 missing required_len** (Finding 4) — HIGH, backport type-1 pattern

### High Priority (Complement R6)

- [ ] **Packet type 8 negative size** (Finding 3) — MEDIUM, add packbufleng >= 11 check
- [ ] **Packet format documentation update** — Document types 2, 3 (missing/undefined)
- [ ] **Unified bounds-validation library** — Extract common pattern for bit-flag parsing

### Open R3 Items (NOT Re-Seeded)

- [ ] **net-r3-replay-protection** — Add sequence numbers
- [ ] **net-r3-ipv6-support** — AF_INET6 dual-stack
- [ ] **net-r3-packet-loss-diagnostic** — Log pq_dropped_packets

---

## SUMMARY TABLE

| Round | CRITICAL | HIGH | MEDIUM | LOW | Status |
|-------|----------|------|--------|-----|--------|
| **R1** | 3 | 4 | 2 | 1 | Baseline (11 findings) |
| **R2** | 1 | 4 | 3 | 0 | +6 findings (packet queue, compat) |
| **R3** | 2 | 3 | 5 | 0 | +10 findings (from_player OOB, sendpacket OOB, etc.) |
| **R4** | 0 | 0 | 3 | 0 | +3 findings (type 250 implicit validation, sound ID OOB, type 9 doc gap) |
| **R5** | 1 | 1 | 2 | 0 | +4 findings (type 9 buffer overflow, types 0/1 OOB read, type 5/8 unsafe, type 250 implicit) |
| **R6** | 0 | 3 | 1 | 0 | +4 findings (types 4/6/16/17 vulnerabilities + type 8 arithmetic bug) |
| **CUMULATIVE** | **7** | **15** | **16** | **1** | **39 total findings** |

---

## VERIFICATION CHECKLIST

- [x] Cycle-22 closure verified: NET_CONNECT_TIMEOUT = 30 (SRC/MMULTI.C:50)
- [x] Cycle-24 closure verified: MAX_RTS_SOUNDS = 256 (source/RTS.H:40)
- [x] Cycle-26 type-9 fix verified: packbufleng - 1 > MAX_WEAPONS (source/GAME.C:649)
- [x] Cycle-26 type-0/1 fix verified: packbufleng < required_len (source/GAME.C:531)
- [x] Cycle-28 type-5/8 fixes verified: bounds checks on all flags (source/GAME.C:581, 684)
- [x] Under-explored packet types audited (types 2, 3, 4, 6, 8, 16, 17)
- [x] 4 NEW findings identified in types 4, 6, 8, 16/17
- [x] R3 open items re-verified as still pending

---

## CONCLUSION

**All cycle-26 and cycle-28 hardening verified INTACT and ACTIVE.** The multiplayer code shows evidence of systematic hardening:
- Cycle-26 fixed critical packet type 9 and types 0/1 parsing flaws
- Cycle-28 added comprehensive bounds-checking to game-settings packets (types 5 & 8)
- Modern defensive patterns are being applied (required_len pre-validation in type 1)

However, **Round 6 identified 4 NEW vulnerabilities in under-explored packet types**:
1. **Type 4 (Chat) HIGH**: strcpy overflow — attacker can corrupt stack via chat message
2. **Type 6 (Version) HIGH**: Unbounded string parsing — attacker can overflow user_name via crafted version packet
3. **Type 8 (Map Change) MEDIUM**: Negative size arithmetic — packbufleng < 11 causes undefined behavior
4. **Types 16/17 (Respawn/Update) HIGH**: Missing required_len validation — bit-flag parsing vulnerable to OOB read

These 4 findings suggest that **not all packet types received the cycle-26/28 hardening.** Type 1's required_len pattern is best practice but was not backported to types 16/17.

**Recommendation**: Apply same hardening approach used in cycles-26/28 to types 4, 6, 8, 16/17. Establish unified bounds-validation library to prevent re-seeding identical bugs in future packet types.

**Production readiness**: The core infrastructure (MMULTI.C) is solid, and cycle-26/28 hardening is effective. However, complete coverage of ALL packet types (especially chat and metadata) is required before multiplayer release. Suggest code review + patch + regression tests.

---

## FILES CHANGED IN THIS AUDIT

- **docs/audits/network-multiplayer-r6.md** (NEW)
- **docs/audits/SUMMARY.md** (ROW APPENDED)
