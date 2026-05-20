# Network & Multiplayer Audit — Cycle 48 (r12)

## Executive Summary

Cycle 48 r12 audit verifies r11 closures (type-17 envelope pre-validate, disconnect memset, EAGAIN distinguish all LIVE and intact). Comprehensive packet-handler bounds matrix constructed: 15 active packet types enumerated with validation status. **NEW findings**: 2 bounds-check gaps (type-4, type-9), 1 large-scope pending (IPv6 getaddrinfo refactor still unblocked but scope needs clarification), 1 acceptance-criteria refinement for replay tracking, 3 supportability items (socket lifecycle audit, xdist isolation verification, unhandled packet types fallthrough). **Status**: Multiplayer NOT production-ready (3 HIGH/4 MEDIUM open items); dispatch 7 new todos for r12 grind.

**Findings Summary:**
- ✅ Type-17 envelope pre-validate VERIFIED INTACT (line 770)
- ✅ Disconnect memset VERIFIED INTACT (line 621)
- ✅ EAGAIN distinguish VERIFIED INTACT (lines 244, 250)
- ⚠️ Type-4 chat message: **MISSING pre-check** (HIGH)
- ⚠️ Type-9 weapon choice: **MINIMAL validation** (MEDIUM)
- 🟡 IPv6 getaddrinfo: Design ready, scope needs subtask breakdown (HIGH)
- 🟡 Replay sequence: Acceptance criteria underdefined (HIGH)
- 🟡 xdist parallel: recv_buf isolation under `-n auto` needs verification (MEDIUM)
- 🟡 Socket lifecycle: Error-path cleanup audit needed (MEDIUM)

---

## Section 1: Packet-Handler Bounds Matrix

**Comprehensive inventory of all active packet types in source/GAME.C packet switch (lines 397–819):**

| Type | Purpose | Location | Packbufleng Check | Status | Findings |
|------|---------|----------|-------------------|--------|----------|
| **0** | Master sync (host→clients) | 409–517 | Multi-stage at 418, 421, 425–507 | ✅ PASS | Extensive bounds validation per-field; SAFE |
| **1** | Slave sync (client→host) | 517–568 | Per-field checks lines 520, 530, 540, 555 | ✅ PASS | Field-by-field validation; SAFE |
| **4** | Chat message | 569–580 | **MISSING** (packbuf[1] read at 577 without pre-check) | 🔴 **FAIL** | **HIGH: OOB read on packbufleng < 2** |
| **5** | Game settings | 582–642 | 10 fields validated at lines 584–634 | ✅ PASS | Proper bounds per-field; SAFE |
| **6** | Player name exchange | 644–666 | Cycle-38 strncpy fixed; bounds at 660 | ✅ PASS | Bounded string copy; SAFE |
| **7** | RTS sound event | 678–700 | Sound ID range-checked at 687, MAX_RTS_SOUNDS bounds | ✅ PASS | Sound ID validation; SAFE |
| **8** | Host game settings | 702–763 | Cycle-42 pre-check at 752: `packbufleng < 11` | ✅ PASS | Type-17 envelope pre-validate verified; SAFE |
| **9** | Weapon choice | 668–676 | **MINIMAL** (packbuf[1] read at 676, no explicit bounds) | 🟡 **WEAK** | **MEDIUM: Assumed packbufleng >= 2, not verified** |
| **16** | Input sync init | 766–768 | Minimal; flag reset only | ✅ PASS | Initialization only; SAFE |
| **17** | Input sync (delta update) | 769–810 | Cycle-45 pre-check at 770: `packbufleng < 20` | ✅ PASS | **Envelope pre-validation LIVE** (r11 closure verified); field reads at 786–794 now protected |
| **125** | Reserved/Debug | 397–399 | No-op | ✅ N/A | No payload processing; SAFE |
| **126** | Load player / Ready | 401–407 | Single field; no overflow risk | ✅ PASS | Minimal payload; SAFE |
| **127** | No-op | 813–814 | No-op | ✅ N/A | No payload processing; SAFE |
| **250** | Player ready | 816–818 | Increment counter; no payload read | ✅ PASS | No bounds risk; SAFE |
| **255** | Exit game | 819–821 | No payload processing | ✅ N/A | Terminate; SAFE |
| **Unhandled** | Types 2–3, 10–15, 18–124, 128–249, 251–254 | N/A | Fall-through (safe) | ✅ PASS | **Unhandled types safely ignored**; no crash risk |

**Key Observations:**
- **2 NEW FAILS**: Type-4 (chat), Type-9 (weapon) lack pre-validation
- **15 Active types**: 13 PASS/N/A, 2 WEAK/HIGH severity
- **Type-17 closure verified**: Envelope pre-validation at line 770 blocks OOB multi-byte field reads (lines 786–794)
- **Unhandled types**: Safe fallthrough; no dispatcher loop infinite-loop risk

---

## Section 2: R11 Closure Verification

### ✅ Type-17 Envelope Pre-Validation (VERIFIED COMPLETE)

**Location**: source/GAME.C, line 770

**Finding**: Pre-validation gate blocks OOB reads on multi-byte fields:

```c
case 17:
    if (packbufleng < 20) break;  /* net-r11-type-17-envelope-prevalidate */
    j = 1;
    // ... field reads at lines 786-794 now protected ...
```

**Status**: ✅ **INTACT** — Cycle 45 landing verified present. Envelope minimum 20 bytes enforced before j++ loop at lines 786–794 (k-field flag reads).

**Severity**: HIGH — Without this gate, j++ index could exceed packbufleng on malformed packet.

---

### ✅ Disconnect Memset (VERIFIED COMPLETE)

**Location**: SRC/MMULTI.C, line 621

**Finding**: Recv buffer explicitly zeroed on socket close:

```c
for (i = 0; i < MAXPLAYERS; i++) {
    if (player_sockets[i] != INVALID_SOCKET) {
        /* net-r11-player-disconnect-memset */
        memset(&recv_bufs[i], 0, sizeof(recv_bufs[i]));
        net_close(player_sockets[i]);
        player_sockets[i] = INVALID_SOCKET;
    }
}
```

**Status**: ✅ **INTACT** — Cycle 45 landing verified present. Comment tag present for traceability.

**Severity**: MEDIUM — Prevents stale recv buffer data from leaking to reconnecting players (future concern if session keys added).

---

### ✅ EAGAIN Distinction (VERIFIED COMPLETE)

**Location**: SRC/MMULTI.C, lines 244–253

**Finding**: Transient recv errors distinguished from fatal errors:

```c
// Line 240-254 (net_poll_sockets)
} else {
    int err;
#ifdef _WIN32
    err = WSAGetLastError();
    if (err == WSAEWOULDBLOCK || err == WSAEINTR) {
        /* net-r9-recv-eagain-distinguish: transient, retry */
        continue;
    }
#else
    err = errno;
    if (err == EAGAIN || err == EWOULDBLOCK || err == EINTR) {
        /* net-r9-recv-eagain-distinguish: transient, retry */
        continue;
    }
#endif
    break;
}
```

**Status**: ✅ **INTACT** — Cycle 41 landing verified present. Both POSIX (EAGAIN, EWOULDBLOCK, EINTR) and Windows (WSAEWOULDBLOCK, WSAEINTR) codes handled correctly.

**Severity**: HIGH — Without distinction, WiFi transient errors would cause immediate socket drop, breaking LAN play.

---

## Section 3: Packet-Handler Gaps — NEW FINDINGS

### 🔴 **HIGH: Type-4 Chat Message — Missing Pre-Check**

**Location**: source/GAME.C, line 569–577

**Issue**: Type-4 handler reads packbuf[1] without validating packbufleng >= 2:

```c
case 4:
    // NO BOUNDS CHECK HERE
    // ...
    if(j+packbuf[1]<=packbufleng) {  // Line 577: reads packbuf[1] BEFORE checking bounds
        copybufbyte(&packbuf[j],msg,packbuf[1]);
    }
```

**Vulnerability**: Malformed packet with packbufleng == 1 causes OOB read of packbuf[1].

**Proposed Fix**: Add pre-check at case 4 entry:
```c
case 4:
    if (packbufleng < 2) break;  /* pre-validate before packbuf[1] read */
    // ... rest of handler ...
```

**Effort**: 5 minutes

**Severity**: 🔴 **HIGH** (OOB read, information leak, potential crash)

---

### 🟡 **MEDIUM: Type-9 Weapon Choice — Minimal Validation**

**Location**: source/GAME.C, line 668–676

**Issue**: Type-9 handler reads packbuf[1] as weapon ID without explicit pre-check:

```c
case 9:
    // NO EXPLICIT PRE-CHECK
    ud.m_wchoice[packbuf[1]]=ud.wchoice[packbuf[1]];
```

**Vulnerability**: Implicit assumption that packbufleng >= 2. Malformed packet could cause OOB read.

**Proposed Fix**: Add pre-check:
```c
case 9:
    if (packbufleng < 2) break;  /* net-r12-type-9-weapon-overread: pre-validate */
    ud.m_wchoice[packbuf[1]]=ud.wchoice[packbuf[1]];
```

**Effort**: 5 minutes

**Severity**: 🟡 **MEDIUM** (OOB read, but weapon ID field is known-safe range due to m_wchoice bounds)

---

## Section 4: IPv6 Dual-Stack Status

**Current State**: 
- SRC/MMULTI.C line 518: `inet_addr(host_string)` (IPv4-only, deprecated)
- No `getaddrinfo()` anywhere in codebase
- Blocks IPv6 support per r10 design spec

**R11 Audit Assessment**: "Large, likely still pending"

**R12 Reassessment**:

**Gap**: R11 did not clarify **why** IPv6 is large or **what breakpoints** exist.

**Analysis**:
1. **Socket creation**: Single `socket(AF_INET, ...)` at line 413 — refactor to `getaddrinfo()` + loop for both AF_INET and AF_INET6
2. **Address handling**: Hardcoded `sockaddr_in` structure — switch to `sockaddr_storage` or union
3. **Handshake**: Protocol version negotiation needed for backward compatibility (r10 design: version 0x0001 → 0x0002)
4. **Test impact**: All existing tests IPv4-only; new IPv6 tests needed

**Proposed Subtasks**:
- `net-r12-ipv6-getaddrinfo-refactor-stage1`: Replace inet_addr() with getaddrinfo() + single-socket dual-stack (AF_INET6 + IPV6_V6ONLY=0)
- `net-r12-ipv6-dual-stack-test-matrix`: IPv4→IPv4, IPv6→IPv6, IPv4-mapped IPv6 tests

**Severity**: 🔴 **HIGH** (Blocks future IPv6 support; design ready, implementation split into stages)

---

## Section 5: Replay Sequence Tracking

**Current State**:
- No sequence numbers on packets
- Each packet processed on arrival without idempotency check
- Vulnerable to replay attacks (attacker re-sends captured packet)

**R10 Design Spec**: Complete (documented in network-multiplayer-r10.md)

**R11 Status**: "Still pending; restate with sharper acceptance criteria"

**R12 Sharper Criteria**:

**Acceptance Test Matrix**:
1. **Monotonic sequence**: Host increments seq counter on each outgoing packet; seq != 0
2. **Replay rejection (per peer)**: If `seq <= last_seq[peer_id]`, drop packet with log `[NET] Replay detected: peer %d seq %u <= last %u`
3. **Multi-peer independence**: Replay on peer A should NOT affect peer B (separate last_seq tracking)
4. **Protocol version handshake**: Version 0x0001 (old, no seq) → 0x0002 (new, with seq); old clients rejected by new hosts with log message
5. **Backward compat**: Old hosts (0x0001) still accept old clients (graceful degradation)
6. **Sequence wrap**: seq counter wraps at 32-bit boundary; wrap handled correctly (seq > last_seq with wrap-around logic)

**Effort**: 2–3 cycles (200–250 LOC changes + test suite extension)

**Severity**: 🔴 **HIGH** (Enables LAN replay defense; design complete, acceptance criteria now sharp)

---

## Section 6: Recv Buffer Isolation Under xdist

**Current State** (Cycle 46):
- pytest.ini: `addopts = -n auto --dist loadscope` (parallel xdist enabled)
- conftest.py: filelock-based singleton for generated_audio_artifacts (one per session)
- **Question**: Are multiplayer network tests isolated per worker, or do they share global state?

**Finding**: SRC/MMULTI.C static globals:
- `recv_bufs[MAXPLAYERS]` — per-socket buffers, **GLOBAL STATE**
- `packet_queue[PACKET_QUEUE_SIZE]` — queue of buffered packets, **GLOBAL STATE**
- `player_sockets[MAXPLAYERS]` — socket FDs, **GLOBAL STATE**

**Risk**: If two multiplayer tests run in parallel under xdist:
- Test A initializes host on port 23513
- Test B also initializes host on port 23513 → `bind()` fails OR port already in use
- Tests interfere, flaky failures

**Current Test Isolation**:
- test_multiplayer_protocol.py: Unit tests only, no sockets created → OK
- test_engine_net_hardening_regressions.py: Static analysis only, no runtime execution → OK

**Verdict**: ✅ **Current test suite is safe** (no real sockets created in tests). However, **if future tests spawn multiplayer instances**, must add `@pytest.mark.serial` or use per-test port allocation.

**Recommendation**: Document in test suite that spawned multiplayer processes must use distinct ports (e.g., `23513 + worker_id`).

**Severity**: 🟡 **MEDIUM** (Potential issue for future integration tests; current suite safe)

---

## Section 7: Socket Lifecycle & Resource Leak Audit

**Scope**: Verify socket cleanup on all error paths (connect timeout, handshake timeout, send failures, recv errors).

**Key Paths**:

1. **Connect timeout (NET_CONNECT_TIMEOUT = 30s)**:
   - SRC/MMULTI.C line 518–540 (connect loop with timeout)
   - Verified: Socket properly closed on timeout break; no leak

2. **Handshake timeout (HANDSHAKE_TIMEOUT_SEC = 15s)**:
   - SRC/MMULTI.C line ~550 (handshake read loop)
   - Verified: No explicit timeout logic present; relies on underlying socket timeout
   - **Gap**: No explicit handshake timeout enforcement; zombie connection if client never sends handshake

3. **Send failures (tcp_send_failures counter)**:
   - SRC/MMULTI.C line 145–173 (net_send_raw retry loop, 8 attempts)
   - Verified: After 8 failures, sends up, logs error, continues
   - **Gap**: Socket not closed on send failure; connection remains open; may re-attempt on next tick

4. **Recv errors (fatal, non-transient)**:
   - SRC/MMULTI.C line 240–256 (distinguish EAGAIN from fatal recv errors)
   - Verified: Fatal recv errors break loop and trigger socket drop

**Findings**:
- ✅ Connect timeout: Safe
- 🟡 Handshake timeout: No explicit enforcement (relax on system socket timeout)
- 🟡 Send failures: Socket not closed; connection remains zombie until next error
- ✅ Recv errors: Safe

**Severity**: 🟡 **MEDIUM** (Minor leak on send failures; handshake zombie connections possible under network attack)

---

## Section 8: Mock Harness & Test Coverage

**Current Test Coverage**:

| Test File | Coverage | Isolation |
|-----------|----------|-----------|
| test_multiplayer_protocol.py | Unit: CRC, packet struct, header | ✅ Mocked (no real sockets) |
| test_engine_net_hardening_regressions.py | Static: bounds checks, guards | ✅ Static analysis (no execution) |

**Gaps**:
- **No integration tests**: No spawned multiplayer processes, no real TCP sockets, no end-to-end game state sync
- **No fuzzing**: No malformed packet injection tests (type-4, type-9 type-check OOB scenarios)
- **No stress tests**: No many-client connection storm, no rapid disconnect/reconnect, no packet loss simulation

**Mock Harness Status**: ✅ Adequate for current static validation; integration tests needed for production readiness.

---

## NEW FINDINGS & TODOS (r12)

**7 NEW TODOS** — prioritized HIGH/MEDIUM:

| ID | Title | Severity | Scope | Effort |
|----|-------|----------|-------|--------|
| **net-r12-type-4-chat-underflow** | Type-4 chat message bounds OOB read | 🔴 HIGH | Add pre-check `packbufleng < 2` at case 4 entry | 5 min |
| **net-r12-type-9-weapon-overread** | Type-9 weapon choice malformed packet | 🟡 MEDIUM | Add pre-check `packbufleng < 2` at case 9 entry | 5 min |
| **net-r12-getaddrinfo-ipv6-status-reassess** | Reassess IPv6 getaddrinfo refactor | 🔴 HIGH | Break into stage-1 (single socket dual-stack) + stage-2 (full IPv6 support) | 2–3 cycles |
| **net-r12-replay-sequence-tracking-acceptance-criteria** | Refine replay detection acceptance criteria | 🔴 HIGH | Define acceptance test matrix (6 scenarios); enable grind dispatch | 1 cycle design |
| **net-r12-recv-buffer-isolation-xdist** | Verify recv_buf state isolation under xdist | 🟡 MEDIUM | Document per-worker port allocation; verify no global state races | 1 cycle |
| **net-r12-socket-lifecycle-leak-audit** | Audit socket cleanup on error paths | 🟡 MEDIUM | Inspect connect, handshake, send, recv error paths; implement handshake timeout | 1–2 cycles |
| **net-r12-packet-type-unhandled-sentinel** | Add unhandled packet types fallthrough audit | 🟡 MEDIUM | Verify types 2–3, 10–15, 18–124, etc. safely ignored; no dispatcher loop risk | 1 cycle |

---

## PRODUCTION READINESS CHECKPOINT

**Multiplayer NOT production-ready**:
- ✅ Type-0, 1, 5–8, 16–17 bounds-validated (cycles 38–45)
- ❌ **Type-4 MISSING pre-check** (NEW HIGH finding)
- ❌ **Type-9 MINIMAL validation** (NEW MEDIUM finding)
- ✅ EAGAIN distinction working (cycle 41)
- ✅ Type-17 envelope pre-validate LIVE (cycle 45)
- ✅ Disconnect memset LIVE (cycle 45)
- ❌ IPv6 not supported (design ready, implementation split needed)
- ❌ Replay protection not implemented (design ready, acceptance criteria now sharp)
- ❌ Packet-loss telemetry not exported
- 🟡 Socket lifecycle minor leaks (handshake zombie connections possible)
- 🟡 Integration tests missing (unit tests only)

**Recommended Next Cycle (Cycle 49)**:
1. **Dispatch** `net-r12-type-4-chat-underflow` (5 min, HIGH)
2. **Dispatch** `net-r12-type-9-weapon-overread` (5 min, MEDIUM)
3. **Dispatch** `net-r12-getaddrinfo-ipv6-status-reassess` (refactor strategy + stage-1 planning)
4. **Dispatch** `net-r12-replay-sequence-tracking-acceptance-criteria` (design + test plan)
5. **Dispatch** `net-r12-recv-buffer-isolation-xdist` (verify test safety)

This would unblock **LAN alpha testing** (types 0–9, 16–17 validated).

---

## OBSERVATIONS & SYNTHESIS

### Cycle-45 Impact Verified ✅
- Type-17 envelope pre-validation LIVE and effective
- Disconnect memset LIVE (future-proofing for session tokens)
- EAGAIN distinction enables WiFi reliability

### Type-4 & Type-9 Gaps (NEW)
- Type-4 chat and Type-9 weapon choice lack explicit pre-validation
- Both require simple 2-byte minimum checks (5 min each)
- Likely low-probability in practice (chat/weapon messages rarely malformed) but HIGH severity per audit contract

### IPv6 Status Clarified
- R11 "large, pending" now broken into:
  - Stage 1: Single AF_INET6 socket with dual-stack (simpler, blocks no IPv6 upgrade)
  - Stage 2: Full multi-socket IPv4 + IPv6 support (larger, future enhancement)

### Replay Tracking Acceptance Sharpened
- 6 test scenarios defined: monotonic seq, per-peer isolation, protocol negotiation, wrap-around, backward compat, old-host graceful degradation
- Enables grind dispatch with clear acceptance gates

### xdist Parallel Safety
- Current test suite is safe (unit + static analysis only)
- Future integration tests must add serial markers or per-worker port allocation

---

## FILES REFERENCED IN THIS AUDIT

- **SRC/MMULTI.C** (736 lines) — Network transport, socket management, recv buffer lifecycle
- **source/GAME.C** (10,100 lines) — Packet dispatch (types 0–17, 125–127, 250, 255)
- **tests/test_multiplayer_protocol.py** — Unit tests (CRC, packet struct, header)
- **tests/test_engine_net_hardening_regressions.py** — Regression tests (static bounds checks)
- **docs/audits/network-multiplayer-r11.md** — Previous audit (r11 closures, IPv6/replay design specs)
- **docs/audits/GRIND_LOG.md** — Cycle 45 grind log (r11 closures verified)
- **pytest.ini** — xdist configuration (addopts = -n auto --dist loadscope)

---

**Sentinel**: `net-r12-audit-complete: 9 findings 7 todos`
