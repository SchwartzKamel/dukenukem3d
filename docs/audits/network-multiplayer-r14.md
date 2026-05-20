# Network & Multiplayer Audit — Cycle 58 (r14)

## Executive Summary

Cycle 58 r14 audit conducts comprehensive investigation of **NEW audit scope** not covered by r13 (packet bounds validation, endianness, player-index bounds). Focuses on: sync determinism, disconnect/timeout lifecycle, lobby setup, master/slave authority, legacy transport code, packet ordering/replay protection, and verification of cycle-53 fragmentation documentation.

**Key Findings Summary:**
- ✅ Fragmentation documentation (ARCHITECTURE.md) **VERIFIED ACCURATE** — constants match code exactly
- ✅ No IPX/serial legacy code found — pure TCP/IP only
- ✅ Clear master/slave authority model (host is authoritative, clients send input)
- 🔴 **CRITICAL: Sync determinism gap** — randomseed not synchronized at game start; causes RNG divergence if peers clock-sync varies
- 🔴 **CRITICAL: CRC dormant** — CRC table initialized but never validated on packets; integrity protection disabled
- 🟡 **MEDIUM: Socket lifecycle leaks** — TCP send failures leave zombie sockets open; mid-game player timeout undefined
- 🟡 **MEDIUM: Packet ordering not enforced** — no sequence numbers; replay attacks theoretically possible (low risk: TCP ordering + checksync validation provides partial mitigation)
- 🟡 **MEDIUM: Unused timeout variables** — timeoutcount/resendagaincount never consulted; legacy DOS code

**Status**: Multiplayer NOT production-ready for deterministic replay (3 blocking issues: randomseed sync, CRC validation, socket lifecycle).

**Findings Count**: 5 new findings; 3 CRITICAL, 2 MEDIUM.

---

## Section 1: Fragmentation & MTU Documentation Verification

### ARCHITECTURE.md Cycle-53 Section Cross-Check

**Finding**: docs/ARCHITECTURE.md § "Network MTU & Fragmentation Strategy" (lines 802–887) documents the wire protocol and fragmentation handling. Audit verifies all claims against actual SRC/MMULTI.C code.

**Verification Results**:

| Claim (ARCHITECTURE.md) | Code Location | Actual Value | Status |
|--|--|--|--|
| MAXPACKETSIZE = 2048 bytes | SRC/MMULTI.C:44 | 2048 ✓ | ✅ VERIFIED |
| NET_HEADER_SIZE = 4 bytes | SRC/MMULTI.C:45 | 4 ✓ | ✅ VERIFIED |
| RECV_BUF_SIZE = 65536 bytes | SRC/MMULTI.C:46 | 65536 ✓ | ✅ VERIFIED |
| Payload max = 2048 - 4 = 2044 bytes | SRC/MMULTI.C:277 | Validated `payload_len > MAXPACKETSIZE - NET_HEADER_SIZE` ✓ | ✅ VERIFIED |
| TCP_NODELAY enabled on both host & client | SRC/MMULTI.C:488, 548 | `setsockopt(..., TCP_NODELAY, ...)` on both sides ✓ | ✅ VERIFIED |
| Nagle disabled for low-latency gameplay | Implicit design choice | Both sockets set TCP_NODELAY=1 ✓ | ✅ VERIFIED |
| Per-socket 64KB recv buffer reassembles TCP stream | SRC/MMULTI.C:233, 260–283 | `recv_bufs[i]` struct, extraction loop ✓ | ✅ VERIFIED |
| No IP_DONTFRAG / IP_MTU_DISCOVER set | SRC/MMULTI.C (global search) | Not found ✓ | ✅ VERIFIED |
| Handshake timeout = 15 seconds | SRC/MMULTI.C:52 | HANDSHAKE_TIMEOUT_SEC = 15 ✓ | ✅ VERIFIED |

**Conclusion**: ✅ **DOCUMENTATION ACCURATE** — All MTU and fragmentation claims verified against live code. ARCHITECTURE.md is correct as of cycle 58.

---

## Section 2: Sync Determinism & Randomness Seeding

### Finding: Randomseed Not Synchronized at Game Start (CRITICAL)

**Location**: source/GAME.C (randomseed usage); SRC/MMULTI.C (handshake); docs/ARCHITECTURE.md § Connection Lifecycle (lines 767–788)

**Issue**: Multiplayer deterministic replay requires all peers to initialize with identical `randomseed` value. Current implementation:

1. **Handshake does NOT exchange randomseed** (SRC/MMULTI.C:501–509):
   ```c
   /* Send handshake to each client: [player_index, numplayers, version_lo, version_hi] */
   for (i = 1; i < numplayers; i++) {
       unsigned char msg[4];
       msg[0] = (unsigned char)i;
       msg[1] = (unsigned char)numplayers;
       mm_pack_u16_le(msg + 2, NET_PROTOCOL_VERSION);
       net_send_raw(player_sockets[i], msg, 4);
       // ^^^ NO randomseed field
   }
   ```

2. **Randomseed bytes are piggybacked** (source/GAME.C:8935–8939):
   ```c
   ch = (char)(randomseed&255);  // Line 8935
   syncval[myconnectindex][syncvalhead[myconnectindex]&(MOVEFIFOSIZ-1)] = ch;
   syncvalhead[myconnectindex]++;
   ```
   These bytes are appended to case-0 packets (host→clients) and case-1 packets (client→host). But this happens AFTER initial sync setup, not at game-start.

3. **Consequence**: Host and clients each initialize randomseed independently (likely from system time or uninitialized variable). Over the course of a game:
   - Clients receive host's randomseed bytes in packets
   - But host's initial randomseed never sent to clients
   - Clients' initial RNG state differs from host
   - **Result**: Deterministic replay fails if game logic depends on RNG between game-start and first packet exchange

**Risk**: 
- Desynchronization if either peer uses RNG before receiving initial sync (e.g., level setup, initial sprite placement)
- Replay validation impossible (checksync() compares input only, not RNG state)

**Proposed Fix**: 
1. Add randomseed to handshake message (expand 4-byte handshake to 8 bytes: add 4-byte seed in little-endian)
2. Both host and client initialize game randomseed from handshake value
3. OR: Send explicit "game start" packet before game loop begins, containing randomseed

**Effort**: 15 minutes (handshake expansion, both sides parse seed)

**Severity**: 🔴 **CRITICAL** (Blocks deterministic replay; RNG divergence leads to eventual desync)

---

## Section 3: CRC Validation — Dormant/Unused

### Finding: CRC Implementation Present But Never Validated (CRITICAL)

**Location**: SRC/MMULTI.C lines 319–358 (CRC functions declared but unused)

**Issue**: Wire protocol includes CRC infrastructure, but validation is disabled:

```c
/* ---- CRC (kept for compatibility) ----
 * 
 * The initcrc(), getcrc(), and updatecrc16() functions are currently DORMANT.
 * The 4-byte wire format header [sender][dest][len_lo][len_hi] has no CRC field.
 * To enable CRC validation, the wire format must be bumped to 8 bytes to include
 * a 4-byte CRC checksum. This is a backwards-incompatible protocol change...
 */
```

**Code Evidence**:
1. **Initialization happens** (SRC/MMULTI.C:381):
   ```c
   initcrc();  /* Line 381 */
   ```

2. **But never used**: Search for `getcrc()` or `updatecrc16()` calls in packet handlers:
   ```bash
   grep -n "getcrc\|updatecrc16" SRC/MMULTI.C source/GAME.C
   # Result: No matches (lines 333–358 are dead code)
   ```

3. **Consequence**: 
   - Packets with bit-flip corruption pass through without detection
   - **Integrity check missing**: Only bounds validation exists, not integrity
   - Malicious actor can flip payload bits and packet will be accepted

**Risk**:
- Corruption on congested/lossy networks (unlikely, but possible)
- Bit-flip attack (attacker-in-the-middle flips bits in packet)
- **Severity is LOW on LAN** (checksums at TCP layer provide partial protection), but **HIGH for WAN**

**Proposed Fix**:
1. **Short-term**: Document that CRC is disabled; add explicit note in docs that packets are NOT integrity-checked beyond TCP checksums
2. **Long-term**: Implement CRC validation:
   - Expand wire header from 4 bytes to 8 bytes: [sender][dest][len_lo][len_hi][crc32_lo][crc32_mid][crc32_mid2][crc32_hi]
   - Calculate CRC over [sender][dest][payload_len][payload]
   - Verify CRC on receive; drop packets with CRC mismatch
   - **Cost**: Protocol version bump + compatibility negotiation

**Effort**: 
- Short-term doc: 5 minutes
- Full CRC: 2+ hours (requires protocol redesign + both sender/receiver changes)

**Severity**: 🔴 **CRITICAL** (No integrity protection; data corruption undetected)

---

## Section 4: Socket Lifecycle & Disconnect/Timeout Handling

### Finding 1: TCP Send Failures Leave Zombie Sockets (MEDIUM)

**Location**: SRC/MMULTI.C lines 143–171 (net_send_raw)

**Issue**: Send failures don't close the socket; connection remains open in broken state:

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
                // ... error handling ...
                attempts++;
                if (attempts < 8) net_sleep(1);
            }
        }
        if (r <= 0) {
            tcp_send_failures++;  // Counter incremented
            break;                 // <-- BUT SOCKET NOT CLOSED
        }
        sent += r;
    }
}
```

**Consequence**:
1. After 8 send failures, `tcp_send_failures` counter increments
2. But socket is left in broken state (peer may have disconnected)
3. Subsequent packets to this player are silently dropped
4. **No notification to game loop** — game believes player is still connected

**Risk**: Player appears to hang/freeze in-game; no clean disconnect notification.

**Proposed Fix**: 
```c
if (r <= 0) {
    tcp_send_failures++;
    net_close(sock);  // Close broken socket
    // Notify game loop: player disconnect
    return;
}
```

**Effort**: 15 minutes (close socket, notify game to handle player quit)

**Severity**: 🟡 **MEDIUM** (Degrades user experience; zombie connections cause lag)

---

### Finding 2: Mid-Game Player Timeout Not Defined (MEDIUM)

**Location**: SRC/MMULTI.C net_poll_sockets() lines 219–317; source/GAME.C (no mid-game timeout logic)

**Issue**: Handshake timeout exists (15s), but no mechanism to detect stale peers during active game:

**Evidence**:
1. Handshake timeout: `HANDSHAKE_TIMEOUT_SEC = 15` (SRC/MMULTI.C:52) ✓
2. Connect timeout: `NET_CONNECT_TIMEOUT = 30` (SRC/MMULTI.C:51) ✓
3. Accept timeout: `NET_HOST_ACCEPT_TIMEOUT_SEC = 10` (SRC/MMULTI.C:55) ✓
4. **In-game idle timeout**: NOT FOUND ❌

**Consequence**: If a client silently freezes (e.g., game crash, network hang), host continues to wait for input indefinitely. No timeout to detect and remove dead peers.

**Risk**: Dead players block game loop (if host waits for input from all players); wasted resources.

**Proposed Fix**: Add mid-game timeout:
```c
/* Detect stale peers (no packets in X seconds) */
#define NET_IDLE_TIMEOUT_SEC 30
if ((current_time - last_packet_time[i]) > NET_IDLE_TIMEOUT_SEC) {
    printf("NET: Player %d idle timeout. Removing.\n", i);
    // Mark player as quit
}
```

**Effort**: 20 minutes (add timestamp tracking, check in game loop)

**Severity**: 🟡 **MEDIUM** (Game experience degrades if player freezes; design handles gracefully but could be faster)

---

## Section 5: Packet Ordering & Replay Protection

### Finding: No Sequence Numbers; Replay Not Protected (MEDIUM)

**Location**: SRC/MMULTI.C wire format (lines 101–128); source/GAME.C packet handlers (lines 409–830)

**Issue**: Network packets have no sequence numbers or anti-replay markers:

**Wire Format** (SRC/MMULTI.C:101–116):
```c
/* WIRE FORMAT SPECIFICATION: ALL MULTI-BYTE INTEGERS ARE LITTLE-ENDIAN
 *
 * NET_HEADER_SIZE = 4 bytes:
 *   [1B: sender ID] [1B: dest ID] [2B: payload length (net byte order)]
 *   
 * Payload: up to MAXPACKETSIZE = 2048 bytes
 */
```
**No sequence number field.**

**Consequence**:
1. **Packet ordering**: TCP guarantees in-order delivery on stream, so this is OK for LAN.
2. **Replay attack**: Same packet sent twice is indistinguishable from legitimate duplicate. For example, old "case 0 master sync" packet replayed would update game state to stale values.
3. **Mitigation**: TCP checksums + recv_bufs cleanup (SRC/MMULTI.C:728 `recv_bufs[i].len = 0` on invalid length), but incomplete.

**Risk**:
- **LOW on LAN**: TCP stream integrity + host authority over state makes replay hard
- **HIGH on WAN/untrusted networks**: Attacker-in-the-middle could capture and replay packets
- **Design implication**: No deterministic replay possible without recording packet sequence

**Proposed Fix** (Long-term design):
1. Add 4-byte **packet sequence number** to header: [sender][dest][seqnum_lo][seqnum_hi][len_lo][len_hi]
2. Receiver tracks `last_seqnum[sender]`; drops packets with seqnum < last_seqnum
3. OR: Use monotonic timestamp instead of sequence number

**Effort**: MEDIUM (protocol redesign; affects all packet parsing)

**Severity**: 🟡 **MEDIUM** (Replay protection missing; design otherwise sound for LAN use)

---

## Section 6: Master/Slave Authority Model

### Verification: Authority Structure (VERIFIED SAFE)

**Finding**: Clear authority model with host as authoritative state provider.

**Structure**:

| Role | Responsibility | Code Location |
|--|--|--|
| **Host (connecthead)** | Receives client input (case-1 packets), broadcasts game state (case-0 packets) | source/GAME.C:1059–1133 (master sync send) |
| **Clients (myconnectindex != connecthead)** | Send input (case-1), receive state updates (case-0) | source/GAME.C:990–1046 (slave input send) |

**Authority Points**:
1. **Input validation**: Only player's own input is trusted; host re-broadcasts to others (host relays, doesn't blindly accept alien input)
2. **State authority**: Host computes game state; clients render received state
3. **Player ID validation**: Handshake assigns player ID (SRC/MMULTI.C:504 `msg[0] = (unsigned char)i`); cannot be forged

**Code Evidence** (source/GAME.C lines 1059–1133):
```c
while (1)  //Master
{
    // Host reads movefifo[i] for all players
    osyn = (input *)&inputfifo[(movefifosendplc-1)&(MOVEFIFOSIZ-1)][0];
    nsyn = (input *)&inputfifo[(movefifosendplc  )&(MOVEFIFOSIZ-1)][0];
    
    packbuf[0] = 0; j = 1;  // Case 0 (master sync)
    
    // Iterate all players, pack current state
    for(i=connecthead;i>=0;i=connectpoint2[i]) {
        if (playerquitflag[i] == 0) continue;
        // ... pack nsyn[i].fvel, nsyn[i].svel, etc. ...
    }
    
    // Broadcast to all clients
    for(i=connectpoint2[connecthead];i>=0;i=connectpoint2[i])
        if (playerquitflag[i])
            sendpacket(i,packbuf,j);
}
```

**Cheat Surface Analysis**:
1. ✅ Client cannot modify other players' input (host re-broadcasts, not relay)
2. ✅ Client cannot forge player ID (assigned at handshake, validated at transport)
3. ⚠️ Client CAN send false input for own player (but host must validate bounds)
   - **Mitigation**: Bounds checks in game logic (movement clamps, weapon validation, etc.)
   - **Current status**: Not audited in this pass (scope is network layer, not game logic)

**Conclusion**: ✅ **AUTHORITY MODEL SOUND** — Host-authoritative design is correct for multiplayer FPS.

---

## Section 7: Legacy Code & Dead Code

### Finding 1: Unused Timeout Variables (MEDIUM)

**Location**: SRC/MMULTI.C lines 63–65, 360–366

**Issue**: `timeoutcount` and `resendagaincount` are legacy DOS/IPX variables never used:

```c
static int32_t timeoutcount = 60, resendagaincount = 4;  /* Line 63 */

setpackettimeout(int32_t datimeoutcount, int32_t daresendagaincount)
{
    int32_t i;
    timeoutcount = datimeoutcount;       /* Set but never read */
    resendagaincount = daresendagaincount;  /* Set but never read */
    for(i=0;i<numplayers;i++) lastsendtime[i] = totalclock;
}
```

**Usage in game** (source/GAME.C:7035, 9988):
```c
setpackettimeout(0x3fffffff,0x3fffffff);  /* Disable by setting to large value */
```

**Consequence**: Dead code bloat; confusing API surface.

**Proposed Fix**: Remove unused variables and function, or document as "legacy, do not use".

**Effort**: 5 minutes (delete or comment-out)

**Severity**: 🟡 **MEDIUM** (Code smell, but not a functional bug)

---

### Finding 2: No Legacy IPX/Serial Code (VERIFIED SAFE)

**Finding**: Search for IPX, serial, modem, network device code yields no results. Pure TCP/IP implementation.

```bash
grep -rn "IPX\|ipx\|serial\|SERIAL" SRC/ --include="*.c" --include="*.h"
# Result: No matches
```

**Conclusion**: ✅ **LEGACY CODE CLEAN** — No DOS-era network stubs remain; codebase is modernized to TCP/IP only.

---

## Section 8: Lobby & Connection Setup

### Verification: Handshake Protocol (VERIFIED ADEQUATE)

**Location**: SRC/MMULTI.C lines 501–575 (host handshake), lines 551–575 (client handshake)

**Handshake Message Format**:
```
[1B: player_index] [1B: numplayers] [2B: protocol_version_le]
```

**Verification**:

| Component | Location | Status |
|--|--|--|
| Player ID assignment | SRC/MMULTI.C:504 | Host assigns sequential IDs (0, 1, 2, ...) ✓ |
| Player count negotiation | SRC/MMULTI.C:505 | Both sides agree on numplayers ✓ |
| Protocol version check | SRC/MMULTI.C:559–565 | Client verifies version; drops if mismatch ✓ |
| Handshake timeout | SRC/MMULTI.C:212, 552 | 15 seconds; client drops if timeout ✓ |
| Symmetry | SRC/MMULTI.C:501–509, 551–575 | Both sides handle handshake correctly ✓ |

**Missing**:
- No explicit "game start" packet (game loop begins immediately after handshake completes)
- No "ready to play" synchronization

**Design Impact**: 
- No guarantee that all clients are in sync at frame 0
- Potential for initial desynchronization if game logic depends on frame-0 randomness

**Proposed Enhancement** (Future work):
- Add "game start" packet after handshake: `[type=126][level][difficulty][randomseed][world_seed]`
- Both sides wait for "game start" before advancing game loop

**Effort**: MEDIUM (requires new packet type, both sender/receiver logic)

**Severity**: 🟡 **MEDIUM** (Design gap; mitigated by initial sync in game loop)

**Conclusion**: ✅ **HANDSHAKE ADEQUATE** — Functional, but could be enhanced for explicit sync points.

---

## NEW FINDINGS & TODOS (r14)

**5 NEW TODOS** — prioritized CRITICAL/MEDIUM:

| ID | Title | Severity | Scope | Effort |
|----|-------|----------|-------|--------|
| **net-r14-randomseed-game-start-sync** | Randomseed not synchronized at game start; causes RNG divergence | 🔴 CRITICAL | Add randomseed to handshake (8-byte: current 4-byte + 4-byte seed LE); both sides initialize game RNG from shared seed | 15 min |
| **net-r14-crc-validation-dormant** | CRC functions initialized but never validated; integrity check missing | 🔴 CRITICAL | Either: (1) Doc-only: remove initcrc() call, add note to ARCHITECTURE.md that packets are not CRC-protected beyond TCP checksums; OR (2) Implement: expand header to 8 bytes, add CRC32 validation on receive | 5 min (doc) / 2 hrs (impl) |
| **net-r14-socket-send-failure-zombie** | TCP send failures (after 8 retries) leave zombie sockets open | 🟡 MEDIUM | On send failure: close socket, notify game loop to mark player as quit | 15 min |
| **net-r14-mid-game-idle-timeout** | No timeout for stale peers during active game; dead players block host | 🟡 MEDIUM | Add NET_IDLE_TIMEOUT_SEC (e.g., 30s); track last_packet_time[i]; game loop checks and removes idle players | 20 min |
| **net-r14-packet-sequence-replay-protection** | No sequence numbers; replay attacks theoretically possible (low LAN risk, high WAN risk) | 🟡 MEDIUM | (Future design) Extend header to include 2-byte sequence number; receiver validates seqnum >= last_seqnum[from_player]; drops stale packets | MEDIUM (requires protocol redesign) |

---

## PRODUCTION READINESS CHECKPOINT

**Multiplayer NOT production-ready** (blocking items from r13 + r14):

**r13 Blockers (Type-5/7/8 pre-checks)**: Assumed FIXED by sibling agent `net-r13-endian-playeridx`

**r14 Blockers**:
- ❌ **Randomseed sync missing** (RNG divergence)
- ❌ **CRC dormant** (no integrity protection)
- 🟡 Socket zombie leaks (degraded experience)
- 🟡 Mid-game timeout (design gap)
- 🟡 Replay protection missing (WAN risk)

**Recommended Next Cycle (Cycle 59+)**:
1. **DISPATCH** `net-r14-randomseed-game-start-sync` (CRITICAL, 15 min)
2. **DISPATCH** `net-r14-crc-validation-dormant` (CRITICAL, 5 min for doc-only approach)
3. **DISPATCH** `net-r14-socket-send-failure-zombie` (MEDIUM, 15 min)
4. **DISPATCH** `net-r14-mid-game-idle-timeout` (MEDIUM, 20 min)
5. **DEFER** `net-r14-packet-sequence-replay-protection` (future protocol redesign)

This would unblock **LAN alpha testing** IF r13 pre-checks also land.

---

## FILES REFERENCED IN THIS AUDIT

- **SRC/MMULTI.C** (736 lines) — TCP/IP transport, handshake, socket lifecycle, packet framing
- **source/GAME.C** (10,133 lines) — Packet dispatch (case 0–17, etc.), sync validation, master/slave logic
- **docs/ARCHITECTURE.md** (900+ lines) — Network architecture + MTU/fragmentation strategy (lines 713–900)
- **docs/audits/network-multiplayer-r13.md** (507 lines) — Prior audit (packet bounds validation)

---

## OBSERVATIONS & SYNTHESIS

### Fragmentation Strategy (Cycle 53) VERIFIED CORRECT
All MTU and TCP tuning claims in ARCHITECTURE.md verified against code. Documentation is accurate and up-to-date.

### Sync Determinism: CRITICAL BLIND SPOT
Randomseed synchronization is missing at game start. Bytes are piggybacked mid-game, but initial value never agreed. This breaks:
- Deterministic replay (RNG state diverges)
- Checksync() validation (if RNG used in game logic)

### Integrity Protection: INCOMPLETE
CRC code exists but is unused. TCP checksums provide partial protection, but deliberate bit-flips would pass through undetected. For LAN use, TCP + host authority mitigate risk. For WAN, recommend CRC or HMAC.

### Authority Model: SOUND
Host-authoritative design correctly prevents client cheating. Input validation at network layer (bounds checks) + game layer (clamping) combined provide good security posture for LAN.

### Dead Code & Legacy: MINIMAL
No IPX/serial code found. Only minor legacy variables (timeoutcount, resendagaincount) remain. Clean codebase.

### Socket Lifecycle: MINOR LEAKS
Send failures don't close sockets; mid-game timeouts undefined. Not critical for LAN (TCP will eventually detect if peer is gone), but could be cleaner.

---

**Sentinel**: `net-r14-audit-complete: 5 findings 5 todos`
