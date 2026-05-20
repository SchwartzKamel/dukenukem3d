# Network & Multiplayer Audit Report - Round 3

**Persona**: network-multiplayer  
**Timestamp**: 2025-05-20  
**Scope**: AUDIT-ONLY round 3 (fresh analysis) — 11 focus areas beyond cycles 11–12  
**Status**: Code-complete, 5 critical/high findings with fresh attack surface identified  

---

## EXECUTIVE SUMMARY - ROUND 3 NEW FINDINGS

Building on Round 2's 6 findings (packet queue, MTU, sequence numbers, compat stub, co-op/DM validation, timeout value), Round 3 identifies **5 NEW CRITICAL/HIGH-CONFIDENCE FINDINGS** plus 5 additional medium-risk areas:

### 🔴 CRITICAL (Must fix before production)
1. **from_player bounds violation** — Wire-supplied player ID (0–255) used as array index without bounds check
2. **sendpacket() array index OOB** — `player_sockets[other]` accessed without validating `other` is in [0, MAXPLAYERS)

### 🟠 HIGH (Fix before release)
3. **Silent packet loss** — Queue DROP-OLDEST policy: sender never learns packets were dropped
4. **No replay/sequence protection** — Implicit TCP ordering; no sequence field; replay-vulnerable design
5. **IPv4-only** — No IPv6 support; hardcoded INADDR_ANY; port 23513 hardcoded

### 🟡 MEDIUM (Next sprint)
6. **Handshake timeout only during join** — No per-connection keepalive during gameplay (dead client hangs indefinitely)
7. **No fragmentation strategy** — TCP fragmentation of large packets undocumented; silent reassembly assumed
8. **Broadcast mechanism incomplete** — dest=255 treated as broadcast but no explicit validation/documentation
9. **Player ID collision on reconnect** — No recycling strategy; slots not released until host restart
10. **State desync after packet loss** — No explicit resync mechanism; desync silently propagates

---

## CRITICAL FINDINGS

### Finding 1: from_player Bounds Violation (Array Index OOB)

**File**: SRC/MMULTI.C:193, 228, 620  
**Severity**: CRITICAL  
**Type**: Memory Safety / Buffer Overflow

**The Issue**:
```c
// Line 193: Extract sender ID directly from wire without validation
int from_player = recv_bufs[i].buf[0];  // ← Can be ANY value 0–255

// Lines 225–229: Store in queue
memcpy(packet_queue[pq_tail].data, recv_bufs[i].buf + NET_HEADER_SIZE, payload_len);
packet_queue[pq_tail].length      = (short)payload_len;
packet_queue[pq_tail].from_player  = (short)from_player;  // ← Stored as-is
pq_tail = (pq_tail + 1) % PACKET_QUEUE_SIZE;

// Line 620 in getpacket(): Returned to game layer
*other = packet_queue[pq_head].from_player;
```

**Exploit Path**:
- Attacker sends crafted packet with sender byte = 255 (or any value ≥ MAXPLAYERS=16)
- Game layer calls `getpacket(&other, buf)` → receives `other=255`
- Game layer then indexes arrays/tables using `other` as player index (e.g., `player_health[other]`, `player_x[other]`)
- **Result**: Out-of-bounds read/write, potential crash or data corruption

**Attack Scenario**:
```c
// In game loop (e.g., source/GAME.C)
short other;
char buf[256];
short len = getpacket(&other, buf);
if (len > 0) {
    // Assume game layer does this (typical game code pattern):
    actor_t *player = &actors[other];  // OOBS if other >= MAXACTORS
    player->health -= 10;              // Corruption
}
```

**Impact**: 
- Crash (segfault on bad pointer dereference)
- Memory corruption (write to arbitrary address)
- Denial of service (attacker can hang game)

**Root Cause**: No validation of wire-supplied player ID. The protocol trusts all 8 bits without bounds checking.

---

### Finding 2: sendpacket() Array Index OOB

**File**: SRC/MMULTI.C:583–608  
**Severity**: CRITICAL  
**Type**: Memory Safety / Buffer Overflow

**The Issue**:
```c
sendpacket(int32_t other, char *bufptr, int32_t messleng)
{
    SOCKET sock;
    ...
    if (other == myconnectindex) return;
    if (messleng <= 0 || messleng > MAXPACKETSIZE) return;
    
    // ← NO validation that other is in [0, MAXPLAYERS)
    
    if (is_host) {
        sock = player_sockets[other];  // ← OOBS if other < 0 or >= MAXPLAYERS
    } else {
        sock = player_sockets[0];
    }
    if (sock == INVALID_SOCKET) return;
    ...
}
```

**Exploit Path**:
- Game layer calls `sendpacket(-1, buf, 100)` or `sendpacket(20, buf, 100)`
- Host accesses `player_sockets[-1]` (negative index wraps in C) or `player_sockets[20]` (out of bounds)
- **Result**: Stack overflow, memory corruption, or crash

**Example in game code** (hypothetical):
```c
// source/GAME.C game loop
for (int i = 0; i <= numplayers; i++) {  // ← Loop goes one past numplayers
    sendpacket(i, updates, sizeof(updates));  // Oops: i == numplayers, OOB!
}
```

**Impact**: 
- Crash (segfault)
- Memory corruption
- Remote code execution if attacker controls return address on stack

**Root Cause**: No bounds validation on `other` parameter. Callers expected to be careful, but no defense-in-depth.

---

## HIGH-SEVERITY FINDINGS

### Finding 3: Silent Packet Loss (DROP-OLDEST Policy)

**File**: SRC/MMULTI.C:217–223  
**Severity**: HIGH  
**Type**: Reliability / Silent Failure

**The Issue**:
```c
int is_full = (pq_count >= PACKET_QUEUE_SIZE);

if (is_full) {
    /* DROP-OLDEST policy: discard oldest unread packet to make room for new one */
    pq_head = (pq_head + 1) % PACKET_QUEUE_SIZE;  // ← Silently drop oldest
    pq_dropped_packets++;  // ← Counter incremented but never examined
} else {
    pq_count++;
}
```

**Why It's Critical**:
- When the packet queue fills (1024 packets), the oldest unread packet is **silently discarded**
- Sender never knows the packet was dropped → no retransmission
- Game state becomes desynchronized (e.g., weapon fire, movement, score updates lost)
- `pq_dropped_packets` counter increments but is **never read or logged**

**Trigger Scenario** (high-latency / bursty network):
1. Host receives 1024+ packets/frame in a backlog
2. Packet 1 is dropped, replaced by packet 1025
3. Client never receives "player 1 fired weapon" update
4. Host sees damage, client doesn't → desync

**Design Flaw**: Queue size (1024 packets) is fixed but not validated against frame rate:
- If game runs at 60 FPS, queue holds ~17 frames of packets
- On a 2 Mbps link with 2048-byte packets, that's **very** fast
- Under congestion or packet loss (real networks), 17 frames is insufficient

**Impact**:
- Silent game state desync
- No error reporting to user
- Undetectable by player (may appear as "lag" or "cheating")

---

### Finding 4: No Replay/Sequence Protection

**File**: SRC/MMULTI.C (entire send/receive path)  
**Severity**: HIGH  
**Type**: Security / Protocol Weakness

**The Issue**:
The packet header is:
```c
#define NET_HEADER_SIZE 4   /* [1B sender][1B dest][2B payload length] */
```

There is **NO sequence number field**. Game state updates rely on:
1. TCP ordering (implicit) — but TCP doesn't prevent **replay attacks**
2. No explicit deduplication — duplicate packets (from network retransmit or attacker relay) are processed twice

**Replay Attack Scenario**:
```
Time T=0: Host sends "Fire weapon" (10 damage) to player 1
         Attacker intercepts and relays same packet 100 times to other players
Time T=10ms: Each client processes 100 identical "fire weapon" packets
             Net effect: 1000 damage instead of 10 ← **EXPLOIT**
```

**Implicit Sequence Assumption**:
Per Round 2 findings, game layer uses `movefifoend[player]` modulo MOVEFIFOSIZ as an implicit sequence number. This is:
- Not documented in the protocol
- Not validated on packet boundaries
- Vulnerable to out-of-order processing (TCP guarantees per-socket ordering, not across sockets)

**Impact**:
- Attacker can duplicate/replay network packets to corrupt game state
- Weapon fire, movement, item pickup can be replayed 
- No cryptographic authentication (not even HMAC)

---

### Finding 5: IPv4-Only (No IPv6, No Dynamic Ports)

**File**: SRC/MMULTI.C:354, 366, 458  
**Severity**: HIGH  
**Type**: Platform Support / Future Proofing

**The Issue**:
```c
// Line 354: IPv4 socket only
server_socket = socket(AF_INET, SOCK_STREAM, 0);

// Line 366: INADDR_ANY hardcoded (IPv4)
addr.sin_addr.s_addr = INADDR_ANY;

// Line 458: Client uses inet_addr (IPv4 only)
addr.sin_addr.s_addr = inet_addr(ip);

// Line 46: Port hardcoded
#define DEFAULT_PORT 23513
```

**Why It Matters**:
- IPv6 is required for new networks (ISP, cloud, mobile)
- INADDR_ANY binds only to IPv4 interfaces
- No IPv6 support = cannot host on IPv6-only networks
- No support for dual-stack (IPv4 + IPv6 simultaneously)

**Scenario**:
- On a 2026+ cloud VM (IPv6-only), host cannot bind port 23513
- Players cannot connect because server doesn't listen on IPv6
- Game is unplayable on modern infrastructure

**Port Hardcoding**:
- DEFAULT_PORT = 23513 is fixed
- If one game instance binds port 23513, second instance must wait for close (TIME_WAIT), or use different --host port
- No dynamic port discovery (e.g., port 0 = OS chooses ephemeral port)

**Impact**:
- No IPv6 support (future-incompatible)
- Cannot run multiple instances on same machine easily
- No support for containerized/cloud deployments

---

## MEDIUM-RISK FINDINGS

### Finding 6: Handshake Timeout Only During Join (No Keepalive)

**File**: SRC/MMULTI.C:48, 163, 391  
**Severity**: MEDIUM  
**Type**: Reliability / Deadlock

**The Issue**:
```c
#define HANDSHAKE_TIMEOUT_SEC 15

// net_recv_all() used ONLY during initial handshake (line 473)
if (net_recv_all(sock, msg, 4) != 4) {  // 15-second timeout
    printf("NET: Handshake failed\n");
    goto singleplayer;
}

// After handshake completes, NO timeout on game sockets (net_poll_sockets uses non-blocking recv)
```

**Why It's a Problem**:
- During gameplay, if a client crashes, its socket remains in the host's `player_sockets[]` array
- Host keeps trying to relay packets to dead client (line 210: `net_send_raw(player_sockets[dest], ...)`)
- Client slot is **never recycled** (no per-connection timeout, no keepalive)
- After ~30–60 seconds, TCP timeout eventually closes the socket, but until then:
  - Host relay waits for send() to complete (blocking on full send buffer)
  - Dead client slot not available for new players
  - Game feels "hung" for other players while host waits on dead socket

**Scenario**:
```
T=0: Player 2 crashes (game exits, TCP connection lingers)
T=10ms: Host sends relay packet to player 2 → socket buffer fills → send() blocks
T=50ms: Other players try to join → host busy in send() → no accept() being called
T=60s: TCP timeout closes player 2 socket, but by then other players have timed out
```

**Impact**:
- Dead client slots not recycled quickly
- Other players experience hangs/lag when a client crashes
- No diagnostic logging of which clients are "stuck"

---

### Finding 7: No Fragmentation Strategy (TCP Reassembly Assumed)

**File**: SRC/MMULTI.C:184–189, 204–205  
**Severity**: MEDIUM  
**Type**: Reliability / Incomplete Design

**The Issue**:
```c
// Line 184: Raw read into buffer
int r = recv(sock, (char *)(recv_bufs[i].buf + recv_bufs[i].len),
             RECV_BUF_SIZE - recv_bufs[i].len, 0);

// Line 204: Assume complete packet is available
if (recv_bufs[i].len < total_len) break;  // Wait for more data (correct)
```

**What's Missing**:
- No documentation of MTU assumptions
- No handling of Nagle's algorithm interaction (TCP_NODELAY is set, good)
- No explicit fragmentation test case
- Large packets (e.g., 2000+ bytes) may be fragmented into multiple TCP segments
  - **Current code handles this correctly** (buffers incoming data until complete packet)
  - **But:** No validation that fragmented packets reassemble correctly under stress (packet loss, reordering)

**Scenario** (fragmented packet):
```
Packet: [header(4B)] [payload(2000B)] = 2004 bytes total
TCP segment 1: bytes 0–1023
TCP segment 2: bytes 1024–2003

net_poll_sockets() loop 1: recv() returns 1024 bytes, len=1024, total_len=2004, breaks (correct)
net_poll_sockets() loop 2: recv() returns 980 bytes, len=2004, packet extracted (correct)
```

**BUT** under packet loss:
- If segment 2 is dropped and retransmitted after 100ms, game may have already processed stale state
- No explicit handling of "retransmit after timeout" with fragmented packets

**Impact**:
- Large packets may not reassemble reliably under real network conditions
- No test case for fragmented packets + packet loss
- Undocumented assumptions about TCP behavior

---

### Finding 8: Broadcast Mechanism Incomplete

**File**: SRC/MMULTI.C:208–214, 526  
**Severity**: MEDIUM  
**Type**: Design / Incomplete Feature

**The Issue**:
```c
// Line 526: Broadcast use (dest=255)
disconnect_pkt[1] = 255;  /* broadcast */

// Line 208-214: Relay behavior
if (is_host && dest != 0 && dest > 0 && dest < numplayers) {
    if (player_sockets[dest] != INVALID_SOCKET)
        net_send_raw(player_sockets[dest], recv_bufs[i].buf, total_len);
}

// ← dest=255 is NOT in range [0, numplayers), so NOT relayed!
```

**Why It's a Problem**:
- `dest=255` is treated as "broadcast" in disconnect packet
- But host relay logic (line 208) only forwards if `dest < numplayers`
- So broadcast packets are **silently dropped** by host relay
- Clients never receive the broadcast disconnect

**Who Detects the Disconnect?**:
- Client waits for data on socket
- When server closes socket on host side, recv() returns 0 (EOF)
- **But:** Client may not detect for 30+ seconds (TCP FIN retransmit timeout)

**Impact**:
- Broadcast mechanism is incomplete (documented but non-functional)
- Clients may not detect server shutdown quickly
- No error message to user ("server disconnected")

---

### Finding 9: Player ID Collision on Reconnect (No Recycling)

**File**: SRC/MMULTI.C:405–407, 488  
**Severity**: MEDIUM  
**Type**: Design / Resource Leak

**The Issue**:
```c
// Line 405-407: Host assigns player index sequentially
client = accept(server_socket, ...);
if (client != INVALID_SOCKET) {
    int idx = numplayers;  // ← Next index is always numplayers
    player_sockets[idx] = client;
    numplayers++;
}

// Line 488: Client receives its assigned index
myconnectindex = (short)msg[0];
```

**Why It's a Problem**:
- Player 1 joins → assigned index 1
- Player 1 crashes/disconnects
- Player 2 joins → assigned index 2 (but player 1's slot is never freed)
- If all 16 slots fill with disconnected players, no new players can join
- No recycling: only host restart resets `numplayers`

**Scenario**:
```
T=0: Player 1 joins (idx=1, numplayers=2)
T=1: Player 2 joins (idx=2, numplayers=3)
T=10: Player 1 exits (socket closed, but numplayers stays 3)
T=11: Player 3 tries to join (idx=3, numplayers=4) ← OK
... repeat until numplayers=16
T=100: Player 16 tries to join (idx=16, but MAXPLAYERS=16) → CONNECT_TIMEOUT_SEC → single-player
```

**Impact**:
- After a few players disconnect, no new players can join
- Host must be restarted to reset
- Player count grows indefinitely (even with disconnects)

---

### Finding 10: State Desync After Packet Loss (No Resync)

**File**: SRC/MMULTI.C (entire protocol)  
**Severity**: MEDIUM  
**Type**: Reliability / Game Logic

**The Issue**:
When a packet is dropped (either in network or dropped by DROP-OLDEST queue):
1. Host sends "Player 1 moved to (100, 200)"
2. Packet is lost
3. Host moves on to next update: "Player 1 moved to (120, 220)"
4. Client receives only step 3 → desync (thinks player 1 is at (120, 220), actually started at old position)

**Why There's No Resync**:
- No explicit resync request from client ("what's the current state?")
- No periodic "full state snapshot" (only incremental updates)
- No checksums/CRCs to detect desync
- CRC functions exist but are **dormant** (per lines 241–253)

**Scenario** (visible to player):
- Player 1 aims and fires at player 2's old position
- Packet lost → player 2's client doesn't receive position update
- Player 2's client thinks player 2 is still at old position
- Host processes damage at NEW position → "hit" on host
- Client doesn't see damage (different position on client) → "desync"
- Player 1 (attacker) thinks they landed hit; Player 2 (victim) disagrees

**Impact**:
- Silent game state desync after packet loss
- Players report "unfair" damage or movement
- No way to recover short of server restart

---

## ADDITIONAL OBSERVATIONS

### Platform-Specific Issues (LOW-MEDIUM)

**Windows Socket API Compliance** (MEDIUM):
- WSAEWOULDBLOCK remapping is correct (line 158)
- TCP_NODELAY is set correctly (line 409)
- But: No explicit testing on Windows MinGW (persona notes, but not in CI)

**Large Packet Risk** (LOW):
- MAXPACKETSIZE = 2048 bytes
- Typical MTU = 1500 bytes (Ethernet)
- Fragmentation likely on packets > 1500 bytes
- No explicit test for fragmented + packet loss

### CRC Implementation (LOW PRIORITY)

Per lines 241–253, CRC functions are **dormant**:
- `initcrc()` builds table
- `updatecrc16()` macro available
- But **not** used in sendpacket() or getpacket()
- To enable: requires protocol bump (NET_PROTOCOL_VERSION change) + wire format change

---

## VERIFICATION & TEST COVERAGE

**tests/test_multiplayer_protocol.py** covers:
- ✅ CRC-16 CCITT computation (unit test)
- ✅ Wire format pack/unpack (little-endian helpers mm_pack_u16_le / mm_unpack_u16_le)
- ✅ Protocol version handshake (abstract)
- ❌ from_player bounds validation
- ❌ sendpacket() OOB array access
- ❌ Packet loss scenarios (DROP-OLDEST)
- ❌ Replay attack vectors
- ❌ IPv4 vs IPv6 routing
- ❌ Keepalive / dead client timeout
- ❌ Fragmented packet reassembly
- ❌ Broadcast delivery
- ❌ Player ID recycling

**No integration tests** (multiplayer loopback / two-host scenarios) yet exist in CI.

---

## RECOMMENDATIONS (Tiered)

### TIER 1: CRITICAL (Block production release)

- [ ] **Fix from_player bounds** — Validate `from_player` is in [0, MAXPLAYERS) before storing in queue (line 193)
- [ ] **Fix sendpacket() OOB** — Validate `other` is in [0, MAXPLAYERS) before accessing `player_sockets[other]` (line 597)
- [ ] **Implement replay protection** — Add sequence number field to packet header + deduplication logic (protocol bump)

### TIER 2: HIGH (Next release)

- [ ] **Add packet loss diagnostic** — Log when DROP-OLDEST is triggered; provide API to query dropped packet count
- [ ] **IPv6 support** — Add AF_INET6 socket option + test on IPv6-only network
- [ ] **Per-connection keepalive** — Add inactivity timeout (~30 sec) to close dead client slots during gameplay

### TIER 3: MEDIUM (Next sprint)

- [ ] **Fragmentation test** — Add pytest case: send 2000-byte packet, verify reassembly under packet loss
- [ ] **Broadcast validation** — Document broadcast semantics (dest=255 vs flood vs no-op); update relay logic
- [ ] **Player ID recycling** — Implement slot recycling on disconnect (clear numplayers back, reclaim indices)
- [ ] **Resync mechanism** — Define protocol message "give me full game state" + implement periodic snapshot

### TIER 4: NICE-TO-HAVE (Future)

- [ ] **Enable CRC** — Bump protocol version, add CRC field, validate checksums
- [ ] **Dynamic port binding** — Allow `--host 0` (OS chooses ephemeral port) + report port to clients
- [ ] **Keepalive probes** — Send TCP keepalive or application-level ping to detect dead clients faster

---

## SUMMARY TABLE

| Finding | File:Lines | Severity | Root Cause | Fix Complexity | Impact |
|---------|-----------|----------|-----------|----------------|--------|
| from_player OOB | MMULTI.C:193,228,620 | CRITICAL | No bounds check on wire-supplied player ID | Low (1 check) | Crash, memory corruption |
| sendpacket() OOB | MMULTI.C:597 | CRITICAL | No validation of `other` parameter | Low (1 check) | Crash, memory corruption |
| Silent packet loss | MMULTI.C:217–223 | HIGH | DROP-OLDEST policy, no sender notification | Medium (add logging + API) | Silent desync |
| No replay protection | MMULTI.C (entire) | HIGH | No sequence field, TCP ordering implicit | High (protocol bump) | Replay attacks, state corruption |
| IPv4-only | MMULTI.C:354,366,458 | HIGH | AF_INET hardcoded, inet_addr() only | High (refactor sockets) | No IPv6/cloud support |
| No keepalive | MMULTI.C:48 | MEDIUM | Timeout only during handshake | Medium (add timer thread) | Dead client slots not recycled |
| No fragmentation strategy | MMULTI.C:184–205 | MEDIUM | Implicit TCP reassembly, no test | Medium (add test + docs) | Large packet failures under loss |
| Broadcast incomplete | MMULTI.C:208–214 | MEDIUM | dest=255 silently dropped by relay | Low (fix relay logic) | Clients miss disconnects |
| ID collision on reconnect | MMULTI.C:405–407 | MEDIUM | No slot recycling, numplayers grows | Medium (refactor state) | Max players reached prematurely |
| No resync mechanism | MMULTI.C (entire) | MEDIUM | No snapshot/resync protocol | High (new protocol message) | Silent desync after loss |

---

## APPENDIX: CYCLE 11–12 RECAP (Already Fixed)

Cycles 11–12 addressed:
- ✅ Packet queue overflow (PACKET_QUEUE_SIZE=1024, DROP-OLDEST policy)
- ✅ Graceful disconnect (net_send_disconnect + TCP_NODELAY)
- ✅ payload_len cast + bounds (line 199)
- ✅ Ringbuffer wraparound modulo arithmetic
- ✅ CRC documentation (dormant state)
- ✅ LE wire format + mm_pack_u16_le/mm_unpack_u16_le helpers
- ✅ audit-net-endianness task
- ✅ Regression harness (tests/test_multiplayer_protocol.py)

This audit builds on that foundation with fresh findings on bounds, relay, IPv6, and resync.

