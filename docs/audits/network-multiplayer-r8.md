# Network & Multiplayer Audit Report - Round 8

**Persona**: network-multiplayer  
**Timestamp**: 2025-07-17 (Cycle 37)  
**Scope**: Cycle-37 hardening verification (timeout fixes, send retry) + status of R7 todos + remaining packet handler gaps  
**Status**: ✅ Cycle-37 accept/send fixes verified; ⚠️ recv loop EAGAIN handling INCOMPLETE; 🔴 type-6 unbounded loop STILL OPEN; 5 R7 todos reviewed (2 partially done, 3 blocked)

---

## EXECUTIVE SUMMARY - ROUND 8

### ✅ Cycle-37 Timeout & Retry Fixes — VERIFIED

**Accept-Side (host)**:
- `NET_HOST_ACCEPT_TIMEOUT_SEC` = 10 seconds (SRC/MMULTI.C:55) ✅
- `net_accept_timeout()` uses `select()` with timeout before `accept()` (lines 173–192) ✅
- Prevents zombie client connections from blocking host indefinitely ✅

**Send-Side (both host & clients)**:
- New `net_send_all()` loop (lines 145–170) implements **8-attempt retry for EINTR/EAGAIN** ✅
- Handles both POSIX (`EAGAIN`, `EWOULDBLOCK`, `EINTR`) and Windows (`WSAEWOULDBLOCK`, `WSAEINTR`) ✅
- Backoff via `net_sleep(1)` between retries ✅
- **Eliminates R7 Finding 1 (partial send vulnerability)** ✅

**Risk Status**: ✅ RESOLVED (accept timeout + send retry both operational)

---

### ⚠️ Cycle-37 Recv-Loop EAGAIN Handling — INCOMPLETE

**File**: SRC/MMULTI.C:233–238  
**Status**: ⚠️ PARTIAL (timeout exists, but EAGAIN/EINTR not distinguished)

```c
while (recv_bufs[i].len < RECV_BUF_SIZE - 4096) {
    int r = recv(sock, (char *)(recv_bufs[i].buf + recv_bufs[i].len),
                 RECV_BUF_SIZE - recv_bufs[i].len, 0);
    if (r <= 0) break;  // ← Exits loop on EAGAIN (r = -1) without retry
    recv_bufs[i].len += r;
}
```

**Finding**: The recv() loop treats EAGAIN the same as ECONNRESET (both return r < 0, both trigger `break`). This means:
- Non-blocking socket returns EAGAIN (no data available) → loop exits **prematurely**
- Cannot drain pipelined packets in single poll cycle
- Latency impact: game tick must wait 16ms for next poll to read queued data
- **R7 Finding 2 (EINTR/EAGAIN recv handling incomplete) NOT FIXED**

**Recommendation**: Add error classification before break:
```c
if (r < 0) {
    int err = errno;
    if (err == EAGAIN || err == EWOULDBLOCK) break;  // Expected, retry next poll
    if (err == EINTR) continue;  // Signal interrupted, retry immediately
    // Fatal error: ECONNRESET, EPIPE, etc.
    recv_bufs[i].len = 0;
    break;
}
```

**Risk Status**: ⚠️ HIGH — Not blocking, but impacts latency on high-packet-rate networks (game tick stalls waiting for next poll)

---

### 🔴 Packet Handler Type-6 (Player Name Exchange) — STILL VULNERABLE

**File**: source/GAME.C:644–649  
**Status**: 🔴 STILL OPEN (unchecked string buffer loop)

```c
case 6:
    if (packbuf[1] != BYTEVERSION)
        gameexit("\nYou cannot play Duke with different versions.");
    for (i=2;packbuf[i];i++)  // ← NO BOUNDS CHECK ON i
        ud.user_name[other][i-2] = packbuf[i];
    ud.user_name[other][i-2] = 0;
    break;
```

**Vulnerability**: Loop continues until `packbuf[i] == 0` **without checking packbufleng**:
- Attacker sends: `packbuf = [6, BYTEVERSION, 'A', 'A', ... (1000 A's) ..., 0]` with `packbufleng = 1010`
- Loop reads past buffer bounds, treats uninitialized memory as player name
- **Buffer overflow: ud.user_name[other][]** (defined in DUKE3D.H, typically 32 bytes per player)
- Overwrites adjacent player roster memory

**Example Attack**:
```
Client 1 sends malformed type-6 packet:
- packbuf[0] = 6 (type)
- packbuf[1] = BYTEVERSION
- packbuf[2..66] = 'X' (65 bytes)
- No null terminator in first 65 bytes
→ ud.user_name[other][0..63] = corrupted (buffer is 32 bytes)
→ Adjacent memory (player colors, ready flags) overwritten
```

**R6 Re-Confirmation**: This finding was flagged in R6 (line 641–646 in prior code), not fixed in cycle-33.

**Risk Status**: 🔴 HIGH — Buffer overflow, arbitrary memory write, cheating vector

---

### ⚠️ Packet Handlers Types 16/17 (Input Sync) — Partial Pre-Check Only

**File**: source/GAME.C:755–800  
**Status**: ⚠️ INCOMPLETE VALIDATION (final bounds check exists, but no per-field pre-check)

```c
case 17:
    j = 1;
    // ... (skip some code) ...
    k = packbuf[j++];
    if (k&1)   nsyn[other].fvel = packbuf[j]+((short)packbuf[j+1]<<8), j += 2;  // ← j not checked < packbufleng
    if (k&2)   nsyn[other].svel = packbuf[j]+((short)packbuf[j+1]<<8), j += 2;
    if (k&4)   nsyn[other].avel = (signed char)packbuf[j++];
    if (k&8)   nsyn[other].bits = ((nsyn[other].bits&0xffffff00)|((long)packbuf[j++]));
    // ... (more fields) ...

    if (j > packbufleng)
        printf("INVALID GAME PACKET!!! (%ld too many bytes)\n",j-packbufleng);  // ← Only prints, doesn't stop
```

**Issue**: The final check `if (j > packbufleng)` only **prints a warning** after reading out-of-bounds. Does not prevent subsequent array access.

**Attack Scenario**:
```
Malformed type-17 packet with packbufleng = 5:
- packbuf[0] = 17 (type)
- packbuf[1] = k = 0xFF (all flags set)
- packbuf[2..4] = data (only 3 bytes available)
→ Loop reads packbuf[5], packbuf[6], etc. (uninitialized/stack)
→ printf("INVALID...") fires, but nsyn[other] already corrupted
```

**Recommendation**: Pre-validate required_len before entering field decode:
```c
int required_len = 2 + (popcount(k) * 2) + (k&128 ? 1 : 0);  // Estimate
if (j + required_len > packbufleng) {
    printf("NET: SECURITY: Type 17 packet too short (need %d, have %d)\n", 
           j + required_len, packbufleng);
    break;
}
```

**Risk Status**: ⚠️ MEDIUM/HIGH — Out-of-bounds read, input struct corruption

---

## R7 TODOS REASSESSMENT

| R7 Todo | Status | Severity | Cycle-37 Impact | Recommendation |
|---------|--------|----------|-----------------|-----------------|
| **net-r7-eintr-eagain-handling** | 🟡 PARTIAL | HIGH | Send-side FIXED ✅ (net_send_all loop); recv-side INCOMPLETE (line 236 still exits on EAGAIN) | Split: mark send-side DONE, create `net-r8-recv-eagain-distinguish` for recv loop |
| **net-r7-partial-send-retry** | ✅ DONE | CRITICAL | Fixed in cycle-37 (net_send_all loop, 8-attempt retry) | **MARK DONE** — net_send_all verified working |
| **net-r7-ipv6-dual-stack** | ⚠️ OPEN | HIGH | No progress in cycle-37; AF_INET still hardcoded (lines 367, 463, etc.) | Still requires getaddrinfo() refactor (estimated 2 cycles) |
| **net-r7-queue-drop-logging** | ⚠️ OPEN | HIGH | No progress; pq_dropped_packets counter still exported but not logged/warned | Requires API export + printf logging (1-2 cycles) |
| **net-r7-seq-number-design** | ⚠️ OPEN | MEDIUM | No progress; replay attack protection still pending | Requires wire format v2 design + integration (2–3 cycles) |

---

## R3 ARCHITECTURAL ITEMS — STATUS UNCHANGED

| Item | Severity | Last Update | Status | Estimated Work |
|------|----------|------------|--------|-----------------|
| **net-r3-replay-protection** | HIGH | R7 | Still pending (sequence numbers) | 2–3 cycles |
| **net-r3-ipv6-support** | HIGH | R7 | Still pending (AF_INET hardcoded) | 2–3 cycles |
| **net-r3-packet-loss-diagnostic** | HIGH | R7 | Still pending (export + logging) | 1–2 cycles |

---

## REMAINING UNCHECKED FIELDS IN PACKET HANDLERS (Types 1–17)

### Comprehensive Scan Results

| Type | Handler | Fields Checked | Remaining Gaps | Severity |
|------|---------|-----------------|-----------------|----------|
| 0 | Master sync | ✅ All validated (R7 hardening) | None detected | ✅ SAFE |
| 1 | Slave sync | ✅ All validated (R7 hardening) | None detected | ✅ SAFE |
| 4 | Chat | ✅ packbufleng bounds-checked (cycle-33 fix) | None detected | ✅ SAFE |
| 5 | Game settings | ✅ All 10 fields validated (cycle-33 fix) | None detected | ✅ SAFE |
| **6** | **Player name** | ❌ String parsing unbounded | **Loop exits on null terminator without packbufleng check** | 🔴 HIGH |
| 7 | RTS sound | ✅ Bounds validated (sound ID checked) | None detected | ✅ SAFE |
| 8 | Game settings (host) | ✅ All 10 fields validated (cycle-33 fix) | `copybufbyte(packbuf+10, boardfilename, packbufleng-11)` — needs packbufleng ≥ 11 pre-check | ⚠️ MEDIUM |
| 9 | Weapon choice | ✅ packbufleng bounds-checked (cycle-33 fix) | None detected | ✅ SAFE |
| **16** | **Input sync init** | ⚠️ movefifoend reset only | No per-field checks | ⚠️ MEDIUM |
| **17** | **Input sync** | ⚠️ Final `j > packbufleng` check only | No pre-field validation; reads fvel, svel, avel, bits, horz without bounds | 🔴 HIGH/MEDIUM |

---

## SUMMARY TABLE

| Category | Count | Status |
|----------|-------|--------|
| **CRITICAL** | 0 | All cycle-37 CRITICAL items (partial send) verified FIXED ✅ |
| **HIGH** | 2 | Type-6 unbounded loop (NEW re-confirmation), type-17 OOB read (re-confirmed R7) |
| **MEDIUM** | 2 | Recv EAGAIN handling incomplete, type-8 packbufleng pre-check missing |
| **R7 Todos Closed** | 1 | net-r7-partial-send-retry (cycle-37 net_send_all) |
| **R7 Todos Open** | 4 | eintr-eagain (partial), ipv6, queue-drop, seq-numbers |

---

## OBSERVATIONS

### Cycle-37 Momentum
- **Partial Send Fix**: Excellent — net_send_all() loop with 8-attempt EINTR/EAGAIN retry is production-quality
- **Accept Timeout**: Excellent — 10-second cap on accept() prevents zombie connections
- **Recv Loop Gap**: recv-side EAGAIN handling incomplete; the send-side fix is asymmetric with recv-side

### Type-6 Vulnerability — Not Fixed Since R6
- **Flagged**: R6 (line 641–646), re-confirmed R7
- **NOT fixed in cycle-33**
- **Status R8**: Still vulnerable, buffer overflow risk
- **Suggests**: Selective backporting or incomplete audit coverage of packet handlers

### Latency Risk (Medium Priority)
- Recv loop exits on EAGAIN without retry → game loop stalls 16ms waiting for next poll
- High-packet-rate networks (WiFi, high-fps multiplayer) exposed
- Not blocking (TCP guarantees eventual delivery) but impacts gameplay smoothness

### R7 Partial Closure
- 1 of 5 R7 todos definitively closed (net-r7-partial-send-retry)
- 1 of 5 partially addressed (eintr-eagain: send fixed, recv incomplete)
- 3 of 5 remain open (ipv6, queue-drop, seq-numbers — architectural work)

---

## NEW R8 TODOS (5 items)

| ID | Title | Severity | Est. Work | Depends |
|-----|-------|----------|-----------|---------|
| **net-r8-type-6-player-name-bounds** | Fix unbounded player name string loop (type-6 handler) | HIGH | 30 min | — |
| **net-r8-recv-eagain-distinguish** | Distinguish EAGAIN from fatal recv errors; avoid loop exit on EAGAIN | HIGH | 1 hour | — |
| **net-r8-type-8-packbufleng-precheck** | Add packbufleng ≥ 11 check before copybufbyte() in type-8 handler | MEDIUM | 30 min | — |
| **net-r8-type-17-field-length-validate** | Pre-validate required packet length before decoding type-17 input fields | MEDIUM | 1 hour | — |
| **net-r8-ipv6-getaddrinfo-design** | Design getaddrinfo() refactor for dual-stack (AF_INET/AF_INET6) support | MEDIUM | 2–3 hours | — |

---

## CYCLE-37 FIXES VERIFIED

### ✅ NET_HOST_ACCEPT_TIMEOUT_SEC (10 seconds)
**File**: SRC/MMULTI.C:55, 173–192, 461–463  
**Status**: ✅ VERIFIED
- Define constant at line 55
- Function `net_accept_timeout()` implements select() timeout (lines 173–192)
- Called in host loop with timeout parameter (lines 461–463)
- Prevents indefinite blocking on accept()

### ✅ net_send_all() with EINTR/EAGAIN Retry
**File**: SRC/MMULTI.C:145–170  
**Status**: ✅ VERIFIED
- Loop retries up to 8 times on EAGAIN/EWOULDBLOCK/EINTR
- Backoff via net_sleep(1)
- Handles both POSIX and Windows error codes
- Eliminates partial-send vulnerability (R7 Finding 1)

---

## CONCLUSION

**Round 8 verifies cycle-37's critical timeout/retry fixes and identifies remaining gaps in packet validation and recv handling.**

### Key Points

1. **Cycle-37 Made Real Progress**: Accept timeout + send retry are solid. Eliminates R7 Finding 1 (partial send).

2. **Recv Loop Gap**: EAGAIN handling on recv-side still incomplete. Not blocking, but latency impact on WiFi.

3. **Type-6 Still Open**: Unbounded player name loop not fixed since R6. Easy 30-minute fix that should have been done in cycle-33.

4. **Type-17 Exposure**: No pre-field bounds validation; final check only prints warning.

5. **R7 Partial Closure**: 1 todo definitively closed, 1 partially (send-side done, recv-side incomplete), 3 remain architectural work.

### Production Readiness

**Multiplayer still NOT production-ready**:
- ✅ Timeout/retry fixes verified (cycle-37)
- 🔴 **Type-6 buffer overflow still open** (HIGH)
- 🔴 **Type-17 OOB read still open** (HIGH/MEDIUM)
- ⚠️ Recv EAGAIN latency gap (MEDIUM)
- ⚠️ 3 R3 architectural items pending (IPv6, replay, diagnostics)
- ⚠️ Integration test suite still missing

### Recommended Next Cycle

**Phase 1 (Immediate, single cycle)**:
1. Fix type-6 unbounded loop (30 min)
2. Fix recv EAGAIN handling (1 hour)
3. Pre-validate type-17 field lengths (1 hour)
4. Type-8 packbufleng pre-check (30 min)

This would close all R6/R7/R8 packet handler gaps and unlock Phase 2 (IPv6, replay, diagnostics).

---

## FILES REFERENCED IN THIS AUDIT

- **SRC/MMULTI.C** (567 lines) — Transport layer, timeout/retry functions
- **source/GAME.C** (10,065 lines) — Packet type dispatch, handlers 0–17
- **docs/audits/network-multiplayer-r7.md** — R7 findings (5 findings, 3 still open)
- **docs/audits/network-multiplayer-deep.md** — Original deep audit (first audit, 8 CRITICAL findings identified)

---

**Sentinel**: `audit-round-8-network-multiplayer-cycle-37-verify-20250717-COMPLETE`
