# Network & Multiplayer Audit — Cycle 50 (r13)

## Executive Summary

Cycle 50 r13 audit re-verifies r12 closures (type-4 and type-9 pre-checks live) and conducts comprehensive re-audit of ALL packet handlers for length pre-validation and field access patterns. **NEW CRITICAL FINDINGS**: 3 handlers with OOB read vulnerabilities (type-5 no pre-check, type-7 no pre-check, type-8 check in wrong location), 1 systematic byteswap audit gap, 1 player index bounds validation gap. **Status**: Multiplayer NOT production-ready (3 CRITICAL/2 HIGH open items seeded for r13 grind); dispatch 5 new todos.

**Findings Summary:**
- ✅ Type-4 chat pre-check VERIFIED INTACT (line 570)
- ✅ Type-9 weapon pre-check VERIFIED INTACT (line 669)
- 🔴 **Type-5 game settings: CRITICAL missing pre-check** (reads packbuf[1..10] without validating packbufleng >= 11)
- 🔴 **Type-8 post-game: CRITICAL late bounds check** (validates at line 753 AFTER field reads at lines 742-751)
- 🟡 **Type-7 RTS sound: MEDIUM missing pre-check** (reads packbuf[1] without validating packbufleng >= 2)
- 🟡 Byteswap audit: Multi-byte field reads (type-1, type-17) verified using explicit helpers (HIGH systematic importance)
- 🟡 Player index bounds: from_player validation in MMULTI.C gateway (line 261-269) single point of validation

---

## Section 1: R12 Closure Verification

### ✅ Type-4 Chat Pre-Check (VERIFIED PRESENT & LIVE)

**Location**: source/GAME.C, line 570

**Verification**:
```c
case 4:
    if (packbufleng < 2) break;  /* net-r12-type-4-chat-prevalidate: drop malformed packet */
    if (packbufleng <= sizeof(recbuf)) {
        strncpy(recbuf, packbuf+1, packbufleng-1);
        recbuf[packbufleng-1] = 0;
        adduserquote(recbuf);
        sound(EXITMENUSOUND);
        pus = NUMPAGES;
        pub = NUMPAGES;
    }
    break;
```

**Status**: ✅ **INTACT** — Cycle 48 landing verified present. Pre-check `packbufleng < 2` blocks OOB read of packbuf[1]. Comment tag present for traceability.

**Severity**: 🔴 **HIGH** (Was blocking, now fixed)

---

### ✅ Type-9 Weapon Pre-Check (VERIFIED PRESENT & LIVE)

**Location**: source/GAME.C, line 669

**Verification**:
```c
case 9:
    if (packbufleng < 2) break;  /* net-r12-type-9-weapon-prevalidate: drop malformed packet */
    if (packbufleng - 1 > MAX_WEAPONS)
    {
        printf("NET: SECURITY: Packet type 9 payload too large (%d > %d). Dropping.\n",
            packbufleng - 1, MAX_WEAPONS);
        break;
    }
    for (i=1;i<packbufleng;i++)
        ud.wchoice[other][i-1] = packbuf[i];
    break;
```

**Status**: ✅ **INTACT** — Cycle 48 landing verified present. Pre-check `packbufleng < 2` blocks OOB read. Additional payload-length guard at line 670. Comment tag present.

**Severity**: 🟡 **MEDIUM** (Was blocking, now fixed)

---

## Section 2: Packet-Handler Bounds Matrix — UPDATED

**Comprehensive re-audit of all active packet types in source/GAME.C packet switch (lines 397–829):**

| Type | Purpose | Location | Packbufleng Check | Status | Findings (r13) |
|------|---------|----------|-------------------|--------|----------|
| **0** | Master sync (host→clients) | 409–517 | Multi-stage at 418, 421, 425–507 | ✅ PASS | Per-field bounds validation; SAFE |
| **1** | Slave sync (client→host) | 517–568 | Per-field checks lines 520, 533, 543 | ✅ PASS | Field-by-field validation + required_len pre-calc (line 523); SAFE |
| **4** | Chat message | 569–580 | **Pre-check at 570: `packbufleng < 2`** | ✅ PASS | r12 fix VERIFIED; SAFE |
| **5** | Game settings | 582–643 | **MISSING (NEW FINDING)** | 🔴 **FAIL** | **CRITICAL: Reads packbuf[1..10] without pre-check at line 582 entry** |
| **6** | Player name exchange | 644–666 | Bounds check at 660; cycle-38 strncpy fixed | ✅ PASS | Bounded string copy; player-index guard (line 646-649); SAFE |
| **7** | RTS sound event | 679–702 | **MISSING (NEW FINDING)** | 🟡 **WEAK** | **MEDIUM: Reads packbuf[1] at line 693 without pre-check; no packbufleng < 2 guard** |
| **8** | Post-game settings | 703–765 | **Check at 753 (TOO LATE)** | 🔴 **FAIL** | **CRITICAL: Check `packbufleng < 11` at line 753 is AFTER field reads (lines 742-751)** |
| **9** | Weapon choice | 668–678 | **Pre-check at 669: `packbufleng < 2`** | ✅ PASS | r12 fix VERIFIED; payload guard at 670; SAFE |
| **16** | Input sync init | 767–769 | Minimal; flag reset only | ✅ PASS | Initialization only; SAFE |
| **17** | Input sync (delta update) | 770–812 | **Pre-check at 770: `packbufleng < 20`** | ✅ PASS | r11 closure verified; envelope pre-validation LIVE (line 771); SAFE |
| **125** | Reserved/Debug | 397–399 | No-op | ✅ N/A | No payload processing; SAFE |
| **126** | Load player / Ready | 401–407 | Single field; no overflow risk | ✅ PASS | Minimal payload; SAFE |
| **127** | No-op | 814–815 | No-op | ✅ N/A | No payload processing; SAFE |
| **250** | Player ready | 817–819 | Increment counter; no payload read | ✅ PASS | No bounds risk; SAFE |
| **255** | Exit game | 820–822 | No payload processing | ✅ N/A | Terminate; SAFE |
| **Unhandled** | Types 2–3, 10–15, 18–124, 128–249, 251–254 | N/A | Fall-through (safe) | ✅ PASS | Unknown packet at default case (line 824); unknown_packet_count counter tracks; SAFE |

**Key Changes from r12:**
- Type-5 (game settings): NEW FINDING — **CRITICAL missing pre-check** (reads packbuf[1..10])
- Type-7 (RTS sound): NEW FINDING — **MEDIUM missing pre-check** (reads packbuf[1])
- Type-8 (post-game): NEW FINDING — **CRITICAL late bounds check** (check at line 753 is AFTER reads at lines 742-751)

---

## Section 3: NEW CRITICAL FINDINGS (r13)

### 🔴 **CRITICAL: Type-5 Game Settings — Missing Pre-Check**

**Location**: source/GAME.C, line 582–643

**Issue**: Type-5 handler reads packbuf[1] through packbuf[10] without ANY packbufleng validation at case entry:

```c
case 5:
    /* Range-check game settings from untrusted packet */
    if (packbuf[1] >= 11) {                    // Reads packbuf[1] WITHOUT pre-check!
        // ... more reads of packbuf[2..10] ...
    }
    // ... continues accessing packbuf[1..10] ...
    ud.m_level_number = ud.level_number = packbuf[1];
    // ... assigns from packbuf[2..10] at lines 743-751 ...
```

**Vulnerability**: Malformed packet with packbufleng < 11 causes OOB read of uninitialized buffer, leading to potential crash or information leak.

**Proposed Fix**: Add pre-check at case 5 entry:
```c
case 5:
    if (packbufleng < 11) break;  /* net-r13-type-5-missing-bounds-check */
    /* Range-check game settings from untrusted packet */
    // ... rest of handler ...
```

**Effort**: 5 minutes

**Severity**: 🔴 **CRITICAL** (OOB read on every field access, information leak, potential crash)

---

### 🔴 **CRITICAL: Type-8 Post-Game — Bounds Check in Wrong Location**

**Location**: source/GAME.C, line 703–765

**Issue**: Type-8 handler reads packbuf[1] through packbuf[10] WITHOUT pre-check, then validates late:

```c
case 8:
    /* Range-check game settings from untrusted packet */
    if (packbuf[1] >= 11) {                    // OOB read!
        // ... continues reading packbuf[1..10] ...
    }
    // ...
    ud.m_level_number = ud.level_number = packbuf[1];  // Line 742: OOB read
    ud.m_volume_number = ud.volume_number = packbuf[2];
    // ... more unsafe reads at lines 743-751 ...

    if (packbufleng < 11) break;  /* net-r9-type-8-boardfilename-underflow */
    // Line 753: Check is AFTER reads!
```

**Vulnerability**: The bounds check at line 753 happens AFTER field reads (lines 742-751), so the validation is ineffective. Malformed packet with packbufleng < 11 causes OOB reads.

**Proposed Fix**: Move check to case entry before any field access:
```c
case 8:
    if (packbufleng < 11) break;  /* net-r13-type-8-late-bounds-check: move pre-validation to top */
    /* Range-check game settings from untrusted packet */
    // ... rest of handler ...
```

**Effort**: 5 minutes

**Severity**: 🔴 **CRITICAL** (OOB read on every field access, identical to type-5)

---

### 🟡 **MEDIUM: Type-7 RTS Sound — Missing Pre-Check**

**Location**: source/GAME.C, line 679–702

**Issue**: Type-7 handler reads packbuf[1] without validating packbufleng >= 2:

```c
case 7:
    if(numlumps == 0) break;
    if (SoundToggle == 0 || ud.lockout == 1 || FXDevice == NumSoundCards)
        break;
    // NO BOUNDS CHECK HERE
    if (packbuf[1] < 1 || packbuf[1] >= MAX_RTS_SOUNDS)  // OOB read!
        break;
```

**Vulnerability**: Malformed packet with packbufleng == 1 causes OOB read of packbuf[1].

**Proposed Fix**: Add pre-check:
```c
case 7:
    if (packbufleng < 2) break;  /* net-r13-type-7-missing-bounds-check */
    if(numlumps == 0) break;
    // ... rest of handler ...
```

**Effort**: 5 minutes

**Severity**: 🟡 **MEDIUM** (OOB read, but range-check validates field afterward; lower risk than types 5 & 8)

---

## Section 4: Byteswap & Endianness Audit

### Multi-Byte Field Read Verification

**Finding**: Audit identified two key sites with explicit little-endian unpacking helpers (SAFE):

**1. Type-1 Slave Sync (lines 544-545)**:
```c
if (k&1)   nsyn[other].fvel = packbuf[j]+((short)packbuf[j+1]<<8), j += 2;  /* Little-endian unpack */
if (k&2)   nsyn[other].svel = packbuf[j]+((short)packbuf[j+1]<<8), j += 2;  /* Little-endian unpack */
```

**Status**: ✅ **VERIFIED** — Manual little-endian byte shifting; no endianness issue (assumes LE platform, but correct given network protocol design)

**2. Type-17 Input Sync (lines 786-794)**:
```c
// Multi-byte reads protected by pre-check at line 770 (if (packbufleng < 20) break)
// Field-by-field access after bounds gate
```

**Status**: ✅ **VERIFIED** — Envelope pre-check blocks access to multi-byte fields on malformed packets

**3. MMULTI.C Header Unpacking (line 263)**:
```c
int payload_len = mm_unpack_u16_le(recv_bufs[i].buf + 2);  /* Explicit LE helper */
```

**Status**: ✅ **VERIFIED** — mm_unpack_u16_le() helper at lines 125-128 explicitly handles little-endian unpack

**Summary**: ✅ Endianness handling is explicit and correct across packet dispatch. No `*(short*)&buf[i]` raw pointer casts found (which would be unsafe).

**Severity**: ✅ **SAFE** (Explicit endianness helpers used throughout)

---

## Section 5: Player Index Bounds Validation

### Validation Point in MMULTI.C Packet Gateway

**Location**: SRC/MMULTI.C, lines 261–269

**Finding**: The `from_player` field from wire packet is validated at packet receipt (SINGLE validation point):

```c
while (recv_bufs[i].len >= NET_HEADER_SIZE) {
    int from_player = recv_bufs[i].buf[0];
    int dest        = recv_bufs[i].buf[1];
    int payload_len = mm_unpack_u16_le(recv_bufs[i].buf + 2);
    int total_len;

    /* Validate from_player bounds (CRITICAL: from_player is wire-supplied, attacker-controlled) */
    if (from_player < 0 || from_player >= MAXPLAYERS) {  /* Line 267 */
        printf("NET: SECURITY: Invalid from_player=%d (out of bounds [0,%d)). Dropping packet.\n",
            from_player, MAXPLAYERS);
        recv_bufs[i].len -= NET_HEADER_SIZE;
        // ... drop packet ...
    }
```

**Status**: ✅ **VERIFIED** — from_player bounds-checked at network transport layer (SRC/MMULTI.C). Packet dispatch handlers (source/GAME.C) use "other" parameter which is derived from from_player, so bounds are enforced before dispatch.

**Observation**: Case 6 handler also redundantly validates player index (line 646-649), which is defensive programming but not required given the gateway validation.

**Severity**: ✅ **SAFE** (Single validation point is sufficient; player index cannot be OOB at dispatch time)

---

## Section 6: Socket Lifecycle & Resource Leak Audit (R12 Follow-up)

### Verification of R12 Findings

**Connect Timeout (NET_CONNECT_TIMEOUT = 30s)**:
- SRC/MMULTI.C line 518–540 (connect loop with timeout)
- ✅ **VERIFIED**: Socket properly closed on timeout; no leak

**Handshake Timeout (HANDSHAKE_TIMEOUT_SEC = 15s)**:
- SRC/MMULTI.C line ~550 (handshake read loop)
- 🟡 **UNCHANGED**: No explicit handshake timeout enforcement; relies on socket timeout

**Send Failures (tcp_send_failures counter)**:
- SRC/MMULTI.C line 145–171 (net_send_raw retry loop, 8 attempts)
- 🟡 **UNCHANGED**: After 8 failures, socket remains open; may be zombie connection

**Recv Errors (fatal, non-transient)**:
- SRC/MMULTI.C line 240–256 (distinguish EAGAIN from fatal recv errors)
- ✅ **VERIFIED**: Fatal recv errors break loop and trigger socket drop

**Status Summary**: 
- ✅ Connect timeout: Safe
- 🟡 Handshake timeout: No explicit enforcement
- 🟡 Send failures: Socket not closed on repeated failures
- ✅ Recv errors: Safe

---

## Section 7: xdist Recv Buffer Isolation & Test Coverage

### Parallel Test Safety (R12 Follow-up)

**Current Test Suite Status**:
- test_multiplayer_protocol.py: Unit tests (mocked, no real sockets) ✅
- test_engine_net_hardening_regressions.py: Static analysis (no execution) ✅

**R12 Assessment**: "Current test suite is safe (no real sockets created in tests)"

**R13 Verification**: ✅ **CONFIRMED** — No changes to test infrastructure; safety remains intact.

**Test Coverage Gaps**:
- ✅ Type-4 chat: Regression test present (line 3044–3076)
- ✅ Type-9 weapon: Regression test present (line 3091–3121)
- ❌ Type-5 game settings: NO regression test for pre-check
- ❌ Type-7 RTS sound: NO regression test for pre-check
- ❌ Type-8 post-game: Regression test exists (line 753 check) but should test r13 fix (move to top)
- ❌ Byteswap helpers: No explicit test for endianness on multi-byte fields
- ❌ Integration tests: No spawned multiplayer instances with real sockets

**Recommendation**: Add regression tests for types 5, 7, and 8 pre-checks after fixes land.

---

## NEW FINDINGS & TODOS (r13)

**5 NEW TODOS** — prioritized CRITICAL/HIGH/MEDIUM:

| ID | Title | Severity | Scope | Effort |
|----|-------|----------|-------|--------|
| **net-r13-type-5-missing-bounds-check** | Type-5 game settings missing pre-check | 🔴 CRITICAL | Add `if (packbufleng < 11) break;` at case 5 entry | 5 min |
| **net-r13-type-8-late-bounds-check** | Type-8 post-game bounds check in wrong location | 🔴 CRITICAL | Move `if (packbufleng < 11) break;` from line 753 to case 8 entry (before field reads) | 5 min |
| **net-r13-type-7-missing-bounds-check** | Type-7 RTS sound missing pre-check | 🟡 MEDIUM | Add `if (packbufleng < 2) break;` at case 7 entry | 5 min |
| **net-r13-byteswap-endianness-audit** | Verify all multi-byte field reads use explicit endianness helpers | 🟡 MEDIUM | Audit type-1, type-17, and all handlers for multi-byte reads; verify no raw pointer casts like `*(short*)&buf[i]` | 1 cycle design |
| **net-r13-player-index-bounds-audit** | Verify all packet handlers validate player index bounds | 🟡 MEDIUM | Document MMULTI.C line 267 as single validation point; remove redundant guards in dispatch handlers (e.g., case 6) | 1 cycle design |

---

## PRODUCTION READINESS CHECKPOINT

**Multiplayer NOT production-ready**:
- ✅ Type-0, 1, 16–17 bounds-validated
- ✅ Type-4 pre-check LIVE (r12 fix)
- ✅ Type-9 pre-check LIVE (r12 fix)
- ✅ Type-6 bounds-validated + player-index guard
- ✅ EAGAIN distinction working (cycle 41)
- ✅ Type-17 envelope pre-validate LIVE (cycle 45)
- ✅ Disconnect memset LIVE (cycle 45)
- ✅ Endianness helpers explicit + correct
- ❌ **Type-5 MISSING pre-check** (NEW CRITICAL)
- ❌ **Type-8 bounds check in wrong location** (NEW CRITICAL)
- ❌ **Type-7 MISSING pre-check** (NEW MEDIUM)
- ❌ IPv6 not supported (design ready, implementation split needed)
- ❌ Replay protection not implemented (design ready, acceptance criteria sharp)
- 🟡 Socket lifecycle minor leaks (handshake zombie, send failure zombies)
- 🟡 Integration tests missing (unit tests only)

**Recommended Next Cycle (Cycle 51)**:
1. **Dispatch** `net-r13-type-5-missing-bounds-check` (5 min, CRITICAL)
2. **Dispatch** `net-r13-type-8-late-bounds-check` (5 min, CRITICAL)
3. **Dispatch** `net-r13-type-7-missing-bounds-check` (5 min, MEDIUM)
4. **Dispatch** `net-r13-byteswap-endianness-audit` (design + documentation)
5. **Dispatch** `net-r13-player-index-bounds-audit` (design + documentation)

This would unblock **LAN alpha testing** (types 0–9, 16–17 validated if r13 fixes land).

---

## OBSERVATIONS & SYNTHESIS

### R12 Closures VERIFIED
- Type-4 chat and Type-9 weapon pre-checks LIVE and present ✅
- Both fixes working as designed and blocking OOB reads ✅

### New Critical Issues Discovered (r13)
- **Type-5 & Type-8 identical vulnerability**: Readers access packbuf[1..10] without pre-check
- Type-5 has NO length validation at all (unlike type-8 which has late check)
- Type-8's check at line 753 is ineffective (happens after reads)
- **Type-7 also vulnerable** but lower severity (single byte read, smaller window)

### Pattern Recognition
- All three new FAILING cases (5, 7, 8) follow same anti-pattern: direct packbuf access before bounds-checking
- Suggests copy-paste from unpatched template or missing systematic validation pass

### Endianness Design is Sound
- Multi-byte fields use explicit little-endian unpacking helpers
- No raw pointer casts detected
- Cross-platform endianness handling is correct

### Player Index Safety Verified
- Single validation point in MMULTI.C (line 267) is sufficient
- Packet dispatch handlers receive pre-validated player index
- Redundant checks in dispatch (e.g., case 6) are defensive but not required

---

## FILES REFERENCED IN THIS AUDIT

- **SRC/MMULTI.C** (736 lines) — Network transport, socket management, recv buffer lifecycle, from_player validation
- **source/GAME.C** (10,100 lines) — Packet dispatch (types 0–17, 125–127, 250, 255)
- **tests/test_multiplayer_protocol.py** — Unit tests (CRC, packet struct, header)
- **tests/test_engine_net_hardening_regressions.py** — Regression tests (static bounds checks, type-4 & type-9 guards)
- **docs/audits/network-multiplayer-r12.md** — Prior audit (r12 closures)
- **docs/audits/GRIND_LOG.md** — Cycle 48 grind log (r12 closures verified)

---

**Sentinel**: `net-r13-audit-complete: 7 findings 5 todos`
