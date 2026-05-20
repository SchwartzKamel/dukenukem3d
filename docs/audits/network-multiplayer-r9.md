# Network & Multiplayer Audit Report - Round 9

**Persona**: network-multiplayer  
**Timestamp**: 2025-07-18 (Cycle 39)  
**Scope**: Cycle-38 closure verification (type-6 packet handler), net-r8 backlog reassessment, packet handler matrix, net-r3 architectural HIGHs restated, MMULTI.C re-verification  
**Status**: ✅ Cycle-38 type-6 fix VERIFIED; ⚠️ net-r8 backlog items reassessed (2 resolved, 3 escalated); 🟡 16 packet handler types reviewed; 🔴 3 R3 HIGHs remain architectural work

---

## EXECUTIVE SUMMARY - ROUND 9

### ✅ Cycle-38 Type-6 Handler Closure — VERIFIED COMPLETE

**File**: source/GAME.C:644–667  
**Status**: ✅ FIXED (all 4 criteria met)

**Findings Confirmed**:
1. **Player-index bound is unsigned-compare** ✅
   - Line 646: `if ((unsigned)other >= MAXPLAYERS)` uses unsigned comparison
   - Prevents negative index traversal attacks

2. **packbufleng bound applies inside loop** ✅
   - Line 654: Loop condition `i < packbufleng && i - 2 < MAXPLAYERNAMELENGTH`
   - Double-guarded: packet bounds AND string length bounds
   - Prevents out-of-bounds read from packet buffer

3. **Name length truncation explicitly null-terminates** ✅
   - Lines 659–660: Normal case: `ud.user_name[other][i-2] = 0;`
   - Lines 663–665: Overflow case: `ud.user_name[other][MAXPLAYERNAMELENGTH-1] = 0;`
   - Both paths guarantee null termination (no buffer overflow into adjacent memory)

4. **No signed/unsigned mix** ✅
   - Loop counter `i` is int (signed)
   - Comparison uses unsigned cast of `other`
   - String buffer destination is char array (implicitly signed for comparison, but safe due to bounds)

**R8 Finding Closure**: Type-6 unbounded loop vulnerability (flagged R6, re-confirmed R8) is **FULLY RESOLVED** ✅

**Cross-Reference**: Resolves `net-r8-type-6-bounds` and eliminates re-confirmation flag from `test-r12-packet-type-6-null-term`

---

## NET-R8 BACKLOG RE-ASSESSMENT

### Status Update on R8 Todo Items

| R8 Todo | Current Status | Finding | Recommendation |
|---------|---|---------|---|
| **net-r8-type-6-player-name-bounds** | ✅ **RESOLVED** | Cycle-38 fix verified (4 criteria passed) | **MARK DONE** — Type-6 handler bounds-safe |
| **net-r8-recv-eagain-distinguish** | ⚠️ **INCOMPLETE** | Lines 233–238 still exit on EAGAIN without retry | Escalate to net-r9: HIGH priority (latency impact on real networks) |
| **net-r8-type-8-packbufleng-precheck** | ⚠️ **INCOMPLETE** | Line 752: `copybufbyte(packbuf+10, boardfilename, packbufleng-11)` has no pre-check for packbufleng ≥ 11 | Escalate to net-r9: Dangerous underflow if packbufleng < 11 → huge unsigned length |
| **net-r8-type-17-field-length-validate** | ⚠️ **INCOMPLETE** | Line 784–792: Fields decoded (fvel, svel, avel, bits, horz) without pre-envelope validation | Escalate to net-r9: Out-of-bounds read if packet truncated |
| **net-r8-ipv6-getaddrinfo-design** | ❌ **OPEN** | AF_INET still hardcoded (lines 413, 510 MMULTI.C); no getaddrinfo() refactor | Remains open; architectural work for cycle 40+ |

**Key Insight**: Cycle-38 focused exclusively on type-6 fix (1 of 5 R8 items). The remaining 4 R8 items remain actionable and exposed.

---

## CYCLE-38 CLOSURE VERIFICATION — DETAILED WALK-THROUGH

### Type-6 Handler: End-to-End Code Path

```c
case 6:
    /* net-r8-type-6-bounds: packet field validation */
    if ((unsigned)other >= MAXPLAYERS)                    // ✅ CRITERION 1: Unsigned bound
    {
        printf("NET: SECURITY: Packet type 6 invalid player index...");
        break;
    }
    if (packbuf[1] != BYTEVERSION)
        gameexit("\nYou cannot play Duke with different versions.");
    
    for (i=2; i < packbufleng && i - 2 < MAXPLAYERNAMELENGTH; i++)  // ✅ CRITERION 2: Bounds inside loop
    {
        if (packbuf[i] == 0) break;
        ud.user_name[other][i-2] = packbuf[i];
    }
    
    if (i - 2 < MAXPLAYERNAMELENGTH)                      // ✅ CRITERION 3a: Normal null-term
        ud.user_name[other][i-2] = 0;
    else
    {
        printf("NET: SECURITY: Packet type 6 player name too long...");
        ud.user_name[other][MAXPLAYERNAMELENGTH-1] = 0;  // ✅ CRITERION 3b: Overflow null-term
    }
    break;                                                 // ✅ CRITERION 4: No signed/unsigned mix
```

**Vulnerability Analysis**:
- **Before Cycle-38**: Loop at line 656 (old R7 code) read `for (i=2; packbuf[i]; i++)` — **exits on null terminator WITHOUT checking packbufleng**, allowing attacker to overflow into uninitialized/adjacent memory
- **After Cycle-38**: Loop exits on BOTH `i >= packbufleng` (hard stop) AND `packbuf[i] == 0` (natural terminator), AND on string length limit (3 guards)
- **Null-Termination**: Both normal (short name) and overflow (long name) paths guarantee zero-byte at destination

**Risk Downgrade**: 🔴 HIGH (R8) → ✅ RESOLVED (cycle-38)

---

## PACKET HANDLER MATRIX — RE-SWEEP

### Enumeration of All `switch(packbuf[0])` Cases (0–255)

| Type | Handler Purpose | Location | Validation Status | Reachable from Untrusted | Severity |
|------|---------|----------|---------|---------|---|
| **0** | Master sync (host→clients) | source/GAME.C:409–517 | ✅ Multi-stage bounds (lines 418, 439, 452, 457, 464, 471, 477, 483, 489, 495, 503, 509) | Yes | ✅ SAFE |
| **1** | Slave sync (client→host) | source/GAME.C:517–570 | ✅ Per-field checks during decode (lines 522–567) | Yes | ✅ SAFE |
| **4** | Chat message | source/GAME.C:569–582 | ✅ packbufleng > 1 pre-check (line 571) | Yes | ✅ SAFE |
| **5** | Game settings | source/GAME.C:582–643 | ✅ 10 fields validated (packbuf[1] through packbuf[10]) | Yes | ✅ SAFE |
| **6** | Player name exchange | source/GAME.C:644–667 | ✅✅ Cycle-38 fix: unsigned index, loop bounds, null-term | Yes | ✅ RESOLVED |
| **7** | RTS sound event | source/GAME.C:678–701 | ✅ Sound ID range-checked (lines 695–700) | Yes | ✅ SAFE |
| **8** | Host game settings | source/GAME.C:702–763 | ⚠️ **INCOMPLETE**: Field values validated (packbuf[1] through packbuf[10]) but no pre-check before `copybufbyte(packbuf+10, boardfilename, packbufleng-11)` at line 752 | Yes | 🔴 **HIGH (underflow)** |
| **9** | Weapon choice | source/GAME.C:668–677 | ✅ packbufleng > 1 pre-check (line 669) | Yes | ✅ SAFE |
| **16** | Input sync init | source/GAME.C:765–767 | ⚠️ MINIMAL: Only resets movefifoend counter; no field validation | Yes | ⚠️ MEDIUM |
| **17** | Input sync (delta update) | source/GAME.C:768–810 | ⚠️ **INCOMPLETE**: Fields decoded (lines 785–792) without pre-validation; final bounds check only prints warning (line 801–802) | Yes | 🔴 **HIGH (OOB read)** |
| **125** | Reserved/Debug | source/GAME.C:397–399 | ✅ No-op (cp = 0) | — | ✅ N/A |
| **126** | Load player / Ready flag | source/GAME.C:401–408 | ✅ multipos = packbuf[1] (single field, natural bounds from loadplayer function) | Yes | ✅ SAFE |
| **127** | No-op | source/GAME.C:811–812 | ✅ No-op (break) | — | ✅ N/A |
| **250** | Player ready | source/GAME.C:814–816 | ✅ Increment playerreadyflag[other]; simple counter (no buffer) | Yes | ✅ SAFE |
| **255** | Exit game | source/GAME.C:817–819 | ✅ gameexit() terminates connection | — | ✅ N/A |
| **Unhandled (2–3, 10–15, 18–124, 128–249, 251–254)** | — | — | ✅ Fall-through (no action) | Yes | ✅ SAFE |

**High-Risk Gaps**:
1. **Type 8 (line 752)**: `copybufbyte(packbuf+10, boardfilename, packbufleng-11)` — If packbufleng < 11, length wraps to huge unsigned value
2. **Type 17 (lines 785–792)**: Reads fvel, svel, avel, bits (multi-byte fields) without pre-validation of envelope

---

## NET-R3 ARCHITECTURAL ITEMS — RESTATED WITH DESIGN DOC TODOS

### Background

Three critical architectural items remain open since R3. These are **systemic design gaps**, not implementation bugs. They require design docs before dispatch to implementation cycles.

### 1. Replay Attack Protection (net-r3-replay-protection)

**Current Status**: ❌ **DESIGN PHASE — NOT STARTED**

**Problem Statement**:
- Current packet format has no sequence numbers or timestamp validation
- Attacker can record a packet (e.g., "player 0 fires at position X,Y,Z") and replay it indefinitely
- No defense against replay; host accepts duplicate fire events

**Design Requirements**:
- Add 4-byte sequence number to every game packet (type 0, 1, 17)
- Track last-seen sequence from each peer; reject if seq ≤ last_seq
- Handle legitimate out-of-order (rare on LAN, common on WiFi) with small reorder window (e.g., seq within [last_seq-16, last_seq+100])

**Estimated Effort**: 2–3 cycles (design + wire format update + integration test)

**Design Doc Todo**: `net-r9-replay-design-doc` (HIGH)

---

### 2. IPv6 Dual-Stack Support (net-r3-ipv6-support)

**Current Status**: ❌ **NOT STARTED**

**Problem Statement**:
- AF_INET hardcoded in 2 locations (MMULTI.C:413, 510)
- inet_addr() doesn't support IPv6
- No support for dual-stack (AF_INET6 with IPV6_V6ONLY=0)
- Lab testing on IPv4-only; real deployment may need IPv6

**Design Requirements**:
- Replace inet_addr() with getaddrinfo() (handles both IPv4 and IPv6)
- Create socket as AF_INET6 with IPV6_V6ONLY=0 for dual-stack
- Store results in sockaddr_in6 (or union of both)
- Update client connection logic to try all returned addresses (not just first)

**Estimated Effort**: 2–3 cycles (design + socket layer refactor + cross-platform test)

**Design Doc Todo**: `net-r9-ipv6-design-doc` (HIGH)

---

### 3. Packet-Loss Diagnostics (net-r3-packet-loss-diagnostic)

**Current Status**: ❌ **PARTIAL** (counter exists, not exported)

**Problem Statement**:
- MMULTI.C:99 exports `pq_dropped_packets` counter
- No API to read counter; not logged on disconnect
- Players can't diagnose high packet loss during network issues

**Design Requirements**:
- Export getpacket_dropped() function to query counter
- Log dropped packet count on graceful disconnect (host/client close)
- Add telemetry option: `printf("NET: Dropped %d packets during session\n", getpacket_dropped())`

**Estimated Effort**: 1–2 cycles (simple logging + API export)

**Design Doc Todo**: `net-r9-packet-loss-design-doc` (MEDIUM)

---

## MMULTI.C CYCLE-36/37 LANDINGS RE-VERIFICATION

### ✅ Partial-Send Retry Loop (lines 145–170)

**Status**: ✅ INTACT AND VERIFIED

```c
static void net_send_raw(SOCKET sock, const unsigned char *data, int len)
{
    int sent = 0;
    while (sent < len) {
        int attempts = 0;
        int r = -1;
        /* Retry loop for send(): handle EINTR and EAGAIN up to 8 attempts */
        while (attempts < 8 && r < 0) {
            r = send(sock, (const char *)(data + sent), len - sent, 0);
            if (r < 0) {
                int err;
#ifdef _WIN32
                err = WSAGetLastError();
                if (err != WSAEWOULDBLOCK && err != WSAEINTR) break;
#else
                err = errno;
                if (err != EAGAIN && err != EWOULDBLOCK && err != EINTR) break;
#endif
                attempts++;
                if (attempts < 8) net_sleep(1);
            }
        }
        if (r <= 0) {
            tcp_send_failures++;
            break;
        }
        sent += r;
    }
}
```

**Verification**:
- ✅ 8-attempt retry cap prevents infinite loop
- ✅ Handles POSIX (EAGAIN, EWOULDBLOCK, EINTR) and Windows (WSAEWOULDBLOCK, WSAEINTR)
- ✅ Backoff via net_sleep(1) between retries
- ✅ tcp_send_failures counter incremented on final failure (diagnostic)
- ✅ Eliminates R7 Finding 1 (partial send vulnerability)

**Test Gap from R12**: `test-r12-host-accept-timeout-behavior` — validates 10-second timeout before resend retry kicks in (not yet verified)

---

### ✅ NET_HOST_ACCEPT_TIMEOUT_SEC (10 seconds)

**Status**: ✅ INTACT AND VERIFIED

**Definition**: Line 55 (MMULTI.C)
```c
#define NET_HOST_ACCEPT_TIMEOUT_SEC 10
```

**Function**: Lines 173–192 (MMULTI.C)
```c
static SOCKET net_accept_timeout(SOCKET server_sock, struct sockaddr_in *client_addr,
                                 socklen_t *client_len, int timeout_sec)
{
    SOCKET client;
    fd_set readfds;
    struct timeval tv;

    FD_ZERO(&readfds);
    FD_SET(server_sock, &readfds);
    tv.tv_sec = timeout_sec;
    tv.tv_usec = 0;

    if (select((int)server_sock + 1, &readfds, NULL, NULL, &tv) <= 0) {
        return INVALID_SOCKET;
    }

    client = accept(server_sock, (struct sockaddr *)client_addr, client_len);
    return client;
}
```

**Usage**: Lines 461–463 (MMULTI.C)
```c
client = net_accept_timeout(server_socket,
                            (struct sockaddr *)&client_addr, &client_len,
                            NET_HOST_ACCEPT_TIMEOUT_SEC);
```

**Verification**:
- ✅ select() timeout enforced before accept()
- ✅ Prevents zombie connections from blocking host indefinitely
- ✅ 10-second cap balances responsiveness (LAN) vs. retry mechanism

**Test Gap from R12**: `test-r12-host-accept-timeout-behavior` — validates that accept timeout fires and host continues loop (not yet verified)

---

## NEW R9 NET-R8 ESCALATIONS (4 items)

Cycle-38 closed type-6. The remaining 4 R8 todos require escalation to R9 with refined descriptions based on code re-verification.

| ID | Title | Severity | Scope | Est. Work | Depends |
|----|-------|----------|-------|-----------|---------|
| **net-r9-recv-eagain-distinguish** | Distinguish EAGAIN from fatal recv() errors; avoid loop exit on EAGAIN | HIGH | SRC/MMULTI.C:233–238 | 1 hour | — |
| **net-r9-type-8-boardfilename-underflow** | Add packbufleng ≥ 11 pre-check before copybufbyte() in type-8 handler | HIGH | source/GAME.C:752 | 30 min | — |
| **net-r9-type-17-envelope-prevalidate** | Pre-validate packet length before decoding type-17 input fields (fvel, svel, avel, bits, horz) | HIGH | source/GAME.C:784–792 | 1 hour | — |
| **net-r9-ipv6-design-doc** | Design doc: getaddrinfo() refactor for IPv6 dual-stack (AF_INET + AF_INET6) | HIGH | SRC/MMULTI.C:410, 517 | 2 hours | — |

---

## NET-R3 DESIGN DOC TODOS (3 items)

| ID | Title | Severity | Est. Design Effort | Depends |
|----|-------|----------|-------------------|---------|
| **net-r9-replay-design-doc** | Design doc: Sequence numbers + replay window (detect & reject duplicate packets) | HIGH | 1–2 hours | — |
| **net-r9-packet-loss-design-doc** | Design doc: Packet-loss telemetry API + logging (export pq_dropped_packets counter) | MEDIUM | 30 min | — |
| **net-r9-ipv6-design-doc** | Design doc: IPv6 dual-stack via getaddrinfo() + socket creation refactor | HIGH | 1–2 hours | — |

Note: `net-r9-ipv6-design-doc` appears in both R8 escalation and R3 todo lists (design must precede implementation).

---

## OBSERVATIONS

### Cycle-38 Impact
- **Focused fix**: Type-6 vulnerability eliminated with comprehensive bounds validation and null-termination
- **Partial momentum**: Only 1 of 5 R8 items resolved; 4 remain in full backlog

### Type-8 & Type-17 Risks
- **Type-8 boardfilename**: Dangerous underflow vulnerability (packbufleng-11 wraps to huge unsigned if packbufleng < 11)
- **Type-17 envelope**: Post-check only (prints warning after OOB read); pre-validation missing

### MMULTI.C Stability
- ✅ Partial-send and accept-timeout fixes intact and verified
- ⚠️ recv() loop still lacks EAGAIN error classification (latency risk on WiFi)

### IPv6 Readiness
- ❌ Still not addressed; architectural design required before cycle 40

### R3 Architectural Items
- Remain open; require design docs before implementation dispatch
- Prioritize replay protection + IPv6 (both HIGH)

---

## PRODUCTION READINESS CHECKPOINT

**Multiplayer NOT production-ready**:
- ✅ Type-6 bounds-safe (cycle-38)
- 🔴 **Type-8 underflow (NEW HIGH)** — blocks release
- 🔴 **Type-17 OOB read (CONFIRMED HIGH)** — blocks release
- ⚠️ Recv EAGAIN latency gap (MEDIUM) — impacts WiFi gameplay
- ❌ IPv6 not supported (blocks multi-region deployment)
- ❌ Replay protection not implemented (blocks tournament/competitive mode)
- ❌ Integration test suite missing

**Recommended Next Cycle (Cycle 40)**:
1. Fix type-8 boardfilename underflow (30 min)
2. Fix type-17 envelope pre-validation (1 hour)
3. Fix recv EAGAIN distinction (1 hour)
4. Dispatch net-r9-ipv6-design-doc to documentation-curator or architecture review

This would unblock multiplayer alpha testing on LAN.

---

## FILES REFERENCED IN THIS AUDIT

- **SRC/MMULTI.C** (715 lines) — Transport layer, socket management, packet queue
- **source/GAME.C** (10,086 lines) — Packet dispatch (switch at line 395), handlers types 0–17, 125–127, 250, 255
- **docs/audits/network-multiplayer-r8.md** — R8 findings (5 net-r8 todos, type-6 re-confirmation)
- **docs/audits/network-multiplayer-r3.md** — R3 architectural items (replay, IPv6, diagnostics)

---

**Sentinel**: `audit-round-9-network-multiplayer-cycle-39-verify-r8-escalate-20250718-COMPLETE`
