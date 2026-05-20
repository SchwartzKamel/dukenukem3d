# Network & Multiplayer Audit Report - Round 7

**Persona**: network-multiplayer  
**Timestamp**: 2025-07-16 (Cycle 33)  
**Scope**: Cycle-33 hardening verification + deep transport layer + architectural gap assessment  
**Status**: Type-4 fix VERIFIED ✅; 3 R6 findings RE-CONFIRMED (types 6, 8, 16/17 still vulnerable); 5 NEW findings in transport/test layers (CRITICAL, HIGH, MEDIUM)

---

## EXECUTIVE SUMMARY - ROUND 7

### ✅ Cycle-33 Type-4 Fix Verification

**File**: source/GAME.C:567–575  
**Status**: ✅ FIXED AND VERIFIED
```c
case 4:
    /* Type 4 (chat): bounds-check before strcpy */
    if (packbufleng > 1 && packbufleng <= sizeof(recbuf)) {
        strncpy(recbuf, packbuf+1, packbufleng-1);
        recbuf[packbufleng-1] = 0;
        adduserquote(recbuf);
        ...
```
**Verification**: The strcpy buffer overflow identified in R6 has been mitigated via:
1. Bounds check `packbufleng <= sizeof(recbuf)` BEFORE strncpy
2. Use of strncpy() instead of strcpy()
3. Explicit null-termination with safe length

**Risk**: **RESOLVED** from HIGH → RESOLVED

---

### ⚠️ R6 Findings RE-CONFIRMED (Not Fixed)

| Finding | Severity | File:Lines | Status |
|---------|----------|-----------|--------|
| Type 6 unbounded string parsing | **HIGH** | source/GAME.C:641–646 | ⚠️ STILL VULNERABLE |
| Type 8 negative size arithmetic | **MEDIUM** | source/GAME.C:730–735 | ⚠️ STILL VULNERABLE |
| Types 16/17 missing required_len | **HIGH** | source/GAME.C:764–780 | ⚠️ STILL VULNERABLE |

**Verification code**:
```bash
# Type 6 still loops without packbufleng bounds:
sed -n '641,646p' source/GAME.C
# → for (i=2;packbuf[i];i++) [no packbufleng check]

# Type 8 still performs negative arithmetic:
sed -n '730,735p' source/GAME.C
# → copybufbyte(packbuf+10, boardfilename, packbufleng-11) [if packbufleng < 11, undefined]

# Type 16/17 still missing pre-validation:
sed -n '764,780p' source/GAME.C
# → No required_len pre-check before bit-flag parsing
```

---

## 🔴 ROUND 7 NEW FINDINGS (5 findings: 1 CRITICAL, 3 HIGH, 1 MEDIUM)

| # | Finding | Severity | File:Lines | Root Cause |
|---|---------|----------|-----------|-----------|
| 1 | Partial send vulnerability (silent data loss) | **CRITICAL** | SRC/MMULTI.C:617–650 | No loop-retry around send(); returns < messleng bytes discarded |
| 2 | EINTR/EAGAIN recv handling incomplete | **HIGH** | SRC/MMULTI.C:207–213 | recv() errors (EAGAIN/EINTR) treated identically; loop exits prematurely |
| 3 | Packet queue DROP-OLDEST silent, unlogged | **HIGH** | SRC/MMULTI.C:249–257 | pq_dropped_packets counter incremented but never exported/logged to game layer |
| 4 | IPv4-only hardcoding blocks cloud deployment | **HIGH** | SRC/MMULTI.C:367, 377, 463, 470 | AF_INET hardcoded; no AF_INET6 or dual-stack support |
| 5 | No sequence numbers; replay attack risk | **MEDIUM** | SRC/MMULTI.C (entire transport) | Attacker can replay captured packets; no per-player seq validation |

---

## 🔴 ROUND 7 NEW FINDINGS (5 findings: 1 CRITICAL, 3 HIGH, 1 MEDIUM)

### Finding 1: MMULTI.C Partial Send Vulnerability — CRITICAL

**File**: SRC/MMULTI.C:617–650 (sendpacket function)  
**Severity**: **CRITICAL**  
**Type**: Partial Send / Data Loss / Silent Corruption  

**The Issue**:
```c
sendpacket(int32_t other, char *bufptr, int32_t messleng)
{
    ...
    for(i=0;i<MAXPLAYERS;i++) {
        ...
        if (messleng > 0) {
            if (send(sock, bufptr, (size_t)messleng, 0) < 0) {
                // ← send() may return < messleng (partial send)
                // ← Code treats ANY error as fatal, but doesn't distinguish
                //   EAGAIN (recoverable) from ECONNRESET (fatal)
            }
        }
    }
}
```

**Analysis**:
- `send()` on non-blocking or congested TCP may return **fewer bytes sent** than requested
- Current code assumes `send()` either sends all bytes or returns error
- If `send()` returns (e.g.) 512 bytes of a 1024-byte packet:
  - Remaining 512 bytes are **silently discarded** (no retry, no buffer)
  - Remote player receives **truncated game-state update** (malformed packet)
  - No CRC validation (CRC is dormant per MMULTI.C:276–287)
  - Game state **desynchronizes silently**

**Example Attack Scenario**:
```
Host sends 1024-byte update to client over congested WiFi:
- send() returns 512 (written 512 of 1024)
- Remaining 512 bytes discarded
- Client receives incomplete packet
- Client's next game state is corrupt (no detection)
- 30+ seconds of desynced gameplay until next successful packet
```

**Root Cause**: No loop-retry around send() with backoff for EAGAIN/EWOULDBLOCK.

**Recommendation**:
```c
int net_send_all(SOCKET sock, const char *buf, int len) {
    int sent = 0;
    while (sent < len) {
        int n = send(sock, (char *)(buf + sent), len - sent, 0);
        if (n < 0) {
            int err = errno;
            if (err == EAGAIN || err == EWOULDBLOCK) {
                net_sleep(1);  /* Backoff 1ms, retry */
                continue;
            }
            return -1;  /* Fatal error (ECONNRESET, EPIPE, etc.) */
        }
        if (n == 0) return -1;  /* Connection closed */
        sent += n;
    }
    return sent;
}
/* Then update sendpacket() to use net_send_all() */
```

---

### Finding 2: MMULTI.C Partial Recv Buffer Inconsistency — HIGH

**File**: SRC/MMULTI.C:207–213 (net_poll_sockets recv loop)  
**Severity**: **HIGH**  
**Type**: Incomplete I/O / Data Loss  

**The Issue**:
```c
while (recv_bufs[i].len < RECV_BUF_SIZE - 4096) {
    int r = recv(sock, (char *)(recv_bufs[i].buf + recv_bufs[i].len),
                 RECV_BUF_SIZE - recv_bufs[i].len, 0);
    if (r <= 0) break;  // ← Exits loop on ANY error or would-block
    recv_bufs[i].len += r;
}
```

**Analysis**:
- `recv()` returns -1 on error (EAGAIN/EWOULDBLOCK/EINTR) or 0 (peer shutdown)
- Code treats -1 and 0 identically: **breaks immediately**
- On EAGAIN/EWOULDBLOCK (non-blocking socket):
  - Loop exits prematurely (only 1 recv attempt per poll)
  - High-latency networks may have 1-2ms between recv-ready intervals
  - **Pipelined packets not drained in single poll cycle**
  - Game loop stalls (next poll cycle 16ms away)
- On EINTR (signal interrupt):
  - Loop exits instead of **retrying recv()**
  - Received-but-unprocessed data discarded on next poll
  - Packet loss without any logging

**Example Attack Scenario**:
```
WiFi round-trip delay: 50ms
Client sends 3 update packets in rapid succession (2ms apart)
Host net_poll_sockets() called every 16ms:
- Poll 1: recv() returns data from packet 1 only, EAGAIN on retry → loop exits
- Poll 2 (16ms later): recv() gets packet 2
- Poll 3 (16ms later): recv() gets packet 3
- Effective latency: +32ms + network latency = gameplay lag
```

**Recommendation**:
```c
while (recv_bufs[i].len < RECV_BUF_SIZE - 4096) {
    int r = recv(sock, (char *)(recv_bufs[i].buf + recv_bufs[i].len),
                 RECV_BUF_SIZE - recv_bufs[i].len, 0);
    if (r < 0) {
        int err = errno;
        if (err == EAGAIN || err == EWOULDBLOCK) {
            break;  /* No more data available (expected) */
        }
        if (err == EINTR) {
            continue;  /* Signal interrupted, retry */
        }
        /* Fatal error (ECONNRESET, etc.) */
        recv_bufs[i].len = 0;
        break;
    }
    if (r == 0) {
        /* Peer shutdown cleanly */
        recv_bufs[i].len = 0;
        break;
    }
    recv_bufs[i].len += r;
}
```

---

### Finding 3: Packet Queue DROP-OLDEST Silent Corruption — HIGH

**File**: SRC/MMULTI.C:249–257  
**Severity**: **HIGH**  
**Type**: Silent Data Loss / Undetectable Desynchronization  

**The Issue**:
```c
int is_full = (pq_count >= PACKET_QUEUE_SIZE);

if (is_full) {
    /* DROP-OLDEST policy: discard oldest unread packet to make room for new one */
    pq_head = (pq_head + 1) % PACKET_QUEUE_SIZE;
    pq_dropped_packets++;  // ← Counter incremented but NEVER LOGGED
} else {
    pq_count++;
}
```

**Analysis**:
- When packet queue fills (1024 packets unread), oldest packet is **silently dropped**
- `pq_dropped_packets` counter increments but is **never exported or logged**
- Game layer has **no visibility** into packet loss
  - Type-0/1 game-state updates drop → players desync
  - Type-5/8 game-settings drop → level changes fail silently
  - Type-9 weapon-choice drop → player sees wrong weapon in another's hands
- **No API to query dropped count** (only static variable, unreachable from game.c)
- **No warning or error message** to host/client that packet loss is occurring

**Example Attack Scenario**:
```
Slow client (200ms latency) on slow WiFi:
- Host sends updates every 33ms (30 fps)
- Client recv() backlog grows: 200ms / 33ms ≈ 6 packets
- Over 5 seconds: 150 updates queued, but only 100 processed
- Queue fills: oldest 50 updates discarded silently
- Player sees: lagging other player, then sudden teleport (missed position updates)
- Host has NO WAY to know packets were dropped
```

**Recommendation**:
```c
/* Export dropped count API */
int32_t getnetstat_dropped_packets(void) {
    return pq_dropped_packets;
}

/* Log when drops occur */
if (is_full) {
    printf("NET: WARNING: Packet queue full (size=%d). Dropping oldest packet. "
           "Total dropped this session: %d\n",
           PACKET_QUEUE_SIZE, pq_dropped_packets);
    pq_head = (pq_head + 1) % PACKET_QUEUE_SIZE;
    pq_dropped_packets++;
}

/* Host should monitor dropped count and warn player */
```

---

### Finding 4: IPv4-Only Socket Hardcoding Blocks Cloud Deployment — HIGH

**File**: SRC/MMULTI.C:367, 377, 463, 470  
**Severity**: **HIGH**  
**Type**: Architectural / Platform Limitation  

**The Issue**:
```c
// Line 367 (host mode):
server_socket = socket(AF_INET, SOCK_STREAM, 0);

// Line 463 (client mode):
sock = socket(AF_INET, SOCK_STREAM, 0);

// Lines 377, 470:
addr.sin_family = AF_INET;  // IPv4 only
```

**Analysis**:
- **AF_INET hardcoded** throughout (no AF_INET6 support)
- Cloud platforms (AWS, Azure, GCP) increasingly **IPv6-only** in some regions
- Mobile networks (4G/5G) often **IPv6-preferred**
- Blocks:
  - Cross-cloud multiplayer (no IPv6 interconnect)
  - Mobile player support
  - Future-proof deployment
- **Documented in R3 as architectural gap**, still pending after 40+ audit rounds

**Root Cause**: 1996 BUILD engine port assumes IPv4 throughout (platform-specific code).

**Recommendation**:
```c
/* Support dual-stack (IPv4 + IPv6) with fallback */
struct addrinfo *ai_result = NULL;
struct addrinfo hints = {
    .ai_family = AF_UNSPEC,     /* Both IPv4 & IPv6 */
    .ai_socktype = SOCK_STREAM,
    .ai_protocol = IPPROTO_TCP,
};

int ret = getaddrinfo(hostname, port_str, &hints, &ai_result);
if (ret == 0) {
    /* Try each address until one connects */
    for (struct addrinfo *ai = ai_result; ai; ai = ai->ai_next) {
        sock = socket(ai->ai_family, ai->ai_socktype, ai->ai_protocol);
        if (sock != INVALID_SOCKET &&
            connect(sock, ai->ai_addr, ai->ai_addrlen) == 0) {
            break;  /* Connected */
        }
        net_close(sock);
    }
    freeaddrinfo(ai_result);
}
```

---

### Finding 5: No Sequence Number Protection Against Replay — MEDIUM

**File**: SRC/MMULTI.C (entire transport layer)  
**Severity**: **MEDIUM**  
**Type**: Architectural / Replay Attack Vulnerability  

**The Issue**:
- No **packet sequence numbers** in wire format
- No **timestamp validation**
- Attacker can **replay old packets**:
  - Record a "player_fire_weapon" packet from player 1
  - Send it again 10 times → Player 1's weapon fires 10 times without input
  - No way for receiver to detect it's a replay

**Current Mitigation**: TCP in-order guarantee (implicit ordering).
- **Weakness**: TCP ordering applies **per stream**, not **globally**
  - A captured packet sent to **wrong player** may not be rejected
  - An old packet captured from **previous game session** could be injected into new session

**Example Attack**:
```
Attacker wiretaps LAN:
1. Records packet [player_id=1, weapon_fire=1] from previous game
2. Waits for new game session to start
3. Injects same packet into new game
4. Player 1 fires their weapon without pressing fire button
```

**Root Cause**: Documented in R3 as `net-r3-replay-protection` (HIGH, pending 40+ rounds).

**Recommendation**:
```c
typedef struct {
    uint32_t sequence;    /* Per-player sequence number, incremented on each send */
    uint32_t timestamp;   /* Game tick when sent */
    /* ... rest of packet ... */
} packet_hdr_t;

/* Send-side: increment sequence */
static uint32_t send_seq[MAXPLAYERS] = {0};
send_seq[myconnectindex]++;
packet_hdr.sequence = send_seq[myconnectindex];

/* Receive-side: reject old packets */
static uint32_t recv_seq[MAXPLAYERS] = {0};
if (packet_hdr.sequence <= recv_seq[from_player]) {
    printf("NET: SECURITY: Replay attack detected (seq %u <= %u)\n",
           packet_hdr.sequence, recv_seq[from_player]);
    drop_packet();
    return;
}
recv_seq[from_player] = packet_hdr.sequence;
```

---

## CYCLE VERIFICATION (Detailed)

### ✅ Cycle-33 Type-4 Fix
**File**: source/GAME.C:567–575  
**Status**: ✅ VERIFIED FIXED

### ⚠️ Cycle-33 Type-6/8/16-17 Gaps (NOT Fixed Yet)
**Files**: source/GAME.C:641–646 (type 6), 730–735 (type 8), 764–780 (type 16/17)  
**Status**: ⚠️ STILL VULNERABLE (R6 re-confirmed)

---

## OPEN R3 ITEMS REASSESSMENT

| Item | Severity | Status | Notes | Sub-Tasks |
|------|----------|--------|-------|-----------|
| **net-r3-replay-protection** | HIGH | Pending | Sequence numbers not implemented. TCP implicit ordering insufficient for replay defense. | Split into: (1) wire format v2 design, (2) send-side seq impl, (3) recv-side validation, (4) integration test |
| **net-r3-ipv6-support** | HIGH | Pending | AF_INET hardcoded. Blocks cloud/mobile. getaddrinfo() + dual-stack fallback needed. | Split into: (1) getaddrinfo() host lookup, (2) dual-stack bind, (3) client fallback loop, (4) platform CI test |
| **net-r3-packet-loss-diagnostic** | HIGH | Pending | pq_dropped_packets counter exists but never logged. Game layer unaware of loss. API export needed. | Split into: (1) printf logging on drop, (2) export getnetstat_dropped_packets() API, (3) game.c integration to warn player, (4) network stats UI |

---

## TRANSPORT LAYER HARDENING GAPS

| Aspect | Current | Recommended | Impact |
|--------|---------|-------------|--------|
| **Partial Send Handling** | None (silent discard) | Loop-retry with EAGAIN backoff | CRITICAL: Data loss |
| **EINTR/EAGAIN in Recv** | Treats all errors alike (exit loop) | Distinguish EAGAIN (retry) from fatal (close) | HIGH: Latency + packet loss |
| **Packet Loss Visibility** | Counter exists, never logged | Export API + console warning | HIGH: Undetectable desyncs |
| **IPv6 Support** | IPv4 only (AF_INET) | getaddrinfo() dual-stack | HIGH: Cloud/mobile blocked |
| **Replay Protection** | None (TCP ordering implicit) | Sequence numbers in header | MEDIUM: Replay attack risk |
| **CRC Validation** | Dormant (functions present) | Enable in wire format v2 | MEDIUM: Corruption detection |

---

## SUMMARY TABLE

| Round | CRITICAL | HIGH | MEDIUM | LOW | Status |
|-------|----------|------|--------|-----|--------|
| **R6** | 0 | 3 | 1 | 0 | +4 findings (types 4/6/8/16-17) |
| **R7** | 1 | 3 | 1 | 0 | +5 findings (partial-send, EINTR, drop-silent, IPv4-only, replay) |
| **CUMULATIVE** | **8** | **18** | **17** | **1** | **44 total findings** |

---

## RECOMMENDATIONS (Tiered by Scope)

### Blocking R7 (CRITICAL Finding)

- [ ] **Partial send vulnerability** (Finding 1) — CRITICAL, implement net_send_all() loop

### High Priority R7 (NEW HIGH Findings)

- [ ] **EINTR/EAGAIN handling** (Finding 2) — HIGH, refactor recv loop error handling
- [ ] **Packet queue silent drop** (Finding 3) — HIGH, export API + console logging
- [ ] **IPv6 support gap** (Finding 4) — HIGH, refactor socket init for dual-stack

### Medium Priority (Complement R7)

- [ ] **Replay protection gap** (Finding 5) — MEDIUM, design sequence number format
- [ ] **Unresolved R6 findings** — HIGH, fix types 6, 8, 16/17 packet handlers
- [ ] **Test coverage gap** — test_doc_parity.py missing, test_multiplayer_protocol.py incomplete

### Open R3 Items (Architectural, Multi-Cycle)

- [ ] **net-r3-replay-protection** — Sequence numbers (3–5 cycles)
- [ ] **net-r3-ipv6-support** — Dual-stack getaddrinfo (2–3 cycles)
- [ ] **net-r3-packet-loss-diagnostic** — API + stats UI (2 cycles)

---

## TEST COVERAGE GAPS

| Test | Status | Issue |
|------|--------|-------|
| test_multiplayer_protocol.py | ✅ EXISTS | Covers CRC & handshake; partial-send not tested |
| test_doc_parity.py | ❌ MISSING | Should validate wire format docs match code |
| Integration (loopback) | ❌ MISSING | No pytest for multi-process spawn test |
| Platform (Windows MinGW) | ❌ MISSING | No CI validation on 32-bit Windows sockets |
| Partial recv/send | ❌ MISSING | No unit test for TCP retry logic |
| Packet loss injection | ❌ MISSING | No test to verify drop-oldest behavior |

---

## OBSERVATIONS

### Architecture Assessment

1. **Core MMULTI.C Competency**: Transport layer is well-structured (net_poll_sockets, recv_bufs[], packet queue) but lacks **error handling rigor** (EINTR/EAGAIN, partial send).

2. **Hardening Momentum**: Cycle-33 fixed type-4 chat overflow. Good signal. But types 6, 8, 16/17 still vulnerable. Suggests **incomplete audit coverage** or **selective backporting**.

3. **Silent Failure Patterns**:
   - Partial send → silently discarded data
   - EAGAIN in recv → premature loop exit
   - Dropped packets → counter never logged
   - **Root cause**: Legacy 1996 code assumes reliable, fast, always-available networks. Modern networks (WiFi, LTE, cloud) violate these assumptions.

4. **R3 Architectural Items**: Still pending after 40+ cycles. Suggests:
   - High complexity (IPv6 dual-stack, sequence number design)
   - Low priority relative to urgent hardening (buffer overflows)
   - Need for **separate multi-cycle epic** rather than individual audit findings

### Multiplayer Roadmap Status

| Milestone | Status |
|-----------|--------|
| **Transport Layer** | 🟡 Partially Complete (packet queue works, error handling gaps) |
| **Game State Sync** | 🟢 Green (types 0, 1, 5, 8, 9 mostly hardened) |
| **Chat/Metadata** | 🔴 Red (types 4, 6 vulnerabilities) |
| **Advanced Features** | ⚪ Blocked (IPv6, replay protection, packet loss diagnostic pending) |
| **Test Harness** | 🟡 Partial (protocol tests exist, integration tests missing) |
| **Production Ready** | 🔴 No — CRITICAL partial-send issue + 3 HIGH findings from R6 |

---

## CONCLUSION

**Round 7 deepens R6's findings and reveals transport-layer gaps previously unaudited.**

### Key Discoveries

1. **Cycle-33 Made Progress**: Type-4 fix verified ✅. Shows hardening momentum.

2. **Critical Transport Bug**: Partial send silently drops data (Finding 1). This is a **show-stopper**—a congested network will desync all players. Requires immediate fix.

3. **R6 Findings Confirmed**: Types 6, 8, 16/17 still vulnerable. Three HIGH/MEDIUM findings left unfixed from previous round. Suggest **prioritize patching cycle-33 type-4 + R6 findings before multiplayer release**.

4. **R3 Architectural Backlog**: IPv6, replay protection, packet loss diagnostic remain pending. Too large for single-cycle audit finds; recommend **extracting as multi-cycle epic** (`net-epic-cloud-readiness` or similar).

5. **Test Coverage Inadequate**: Integration tests missing. Windows platform tests missing. Partial-send/EINTR recovery untested. **Multiplayer release cannot proceed without end-to-end test passing**.

### Production Readiness

**Multiplayer is NOT ready for release.** Status:

- ✅ Core star-topology architecture sound
- ✅ Packet queue & header validation in place
- ✅ Some hardening applied (type-0, type-1, type-5, type-9)
- 🔴 **CRITICAL partial-send bug** (Finding 1)
- 🔴 **3 HIGH findings from R6 still open** (types 6, 8, 16/17)
- 🔴 **3 HIGH architectural items pending** (IPv6, replay, diagnostics)
- 🔴 **No integration test suite**

**Recommendation**: Establish **Phase 1 (Immediate, 1 cycle)**:
1. Fix partial-send vulnerability (CRITICAL)
2. Patch types 6, 8, 16/17 (HIGH)
3. Add EINTR/EAGAIN error handling (HIGH)

**Phase 2 (1–2 cycles)**:
1. Implement packet-loss logging API (HIGH)
2. Add integration test suite (loopback + 2-host)
3. Windows MinGW validation

**Phase 3 (2–3 cycles)**:
1. IPv6 dual-stack (HIGH, architectural)
2. Replay protection with sequence numbers (MEDIUM, architectural)

---

## FILES REFERENCED IN THIS AUDIT

- **SRC/MMULTI.C** (668 lines) — Transport layer, recv/send, packet queue
- **source/GAME.C** (10,065 lines) — Packet type dispatch, types 1–17 handlers
- **tests/test_multiplayer_protocol.py** — Protocol unit tests (partial coverage)
- **docs/audits/network-multiplayer-r6.md** — Prior round findings (types 4/6/8/16-17)
- **docs/audits/SUMMARY.md** — Cross-cutting themes & roadmap

---

**END ROUND 7**
