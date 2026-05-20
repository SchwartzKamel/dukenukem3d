# Network & Multiplayer Deep Audit Report - Round 2
**Persona**: network-multiplayer  
**Timestamp**: 2025-05-20  
**Scope**: Follow-up audit (6 focus areas) — protocol assumptions, compat layer, multiplayer game paths, threat model, co-op/DM divergence, constant values  
**Status**: Code-complete, critical protocol gaps identified  

---

## EXECUTIVE SUMMARY - ROUND 2 NEW FINDINGS

Building on Round 1's 11 findings, Round 2 identifies **6 NEW high-confidence findings** across the 6 focus areas:

1. **CRITICAL**: Packet queue wraparound at 512 entries — no handling for bursts >512 packets/frame
2. **HIGH**: No MTU documentation or TCP fragmentation handling strategy documented
3. **HIGH**: Missing sequence number field in packet header (implicit movefifoend in game layer)
4. **HIGH**: compat/network_stub.c does not exist; SDL2 socket shim incomplete
5. **MEDIUM**: Co-op/DM mode bit-pack difference not validated on packet receive
6. **MEDIUM**: CONNECT_TIMEOUT_SEC = 60 seconds (line 46) — excessive for LAN handshake

---

## FOCUS AREA 1: SRC/MMULTI.C — Undocumented Protocol Assumptions

### Finding 1A: Implicit Sequence Numbers (No Explicit Sequence Field)

**File**: SRC/MMULTI.C:79-86, source/GAME.C:419-420, 462-463  
**Severity**: HIGH  
**Type**: Protocol Gap (architecture, not security)

```c
// MMULTI.C: packet_queue stores [data, length, from_player] — NO sequence number
typedef struct {
    char data[MAXPACKETSIZE];   // payload
    short length;               // length
    short from_player;          // sender
    // NO: uint32_t sequence;   // ← MISSING
} queued_packet_t;

// GAME.C line 419-420: Sequence implicit via movefifoend modulo MOVEFIFOSIZ
nsyn = (input *)&inputfifo[(movefifoend[connecthead])&(MOVEFIFOSIZ-1)][0];
```

**Impact**:
- No way to detect dropped packets mid-game (only detects stalls via movefifoend lag threshold at line 671)
- No replay protection — duplicate packet relayed twice would corrupt game state
- Out-of-order packet handling relies entirely on TCP ordering (implicit assumption)
- Desync recovery impossible without explicit sequence field

**Gap**: The packet header (NET_HEADER_SIZE = 4 bytes at line 43) is:
  - `[1B sender | 1B dest | 2B payload_len]`
  - **No sequence field**; compare to modern protocols (e.g., Valve's Source engine uses `uint32_t sequence`)

**Blockers for Production**: Game layer (GAME.C) assumes TCP in-order delivery; if TCP ever reorders (rare but possible on packet loss + retransmit), packets can corrupt game state without explicit sequencing.

---

### Finding 1B: Packet Queue Wraparound at 512 Entries (Buffer Pressure)

**File**: SRC/MMULTI.C:78-86, 179-186  
**Severity**: CRITICAL  
**Type**: DoS / Data Loss

```c
#define PACKET_QUEUE_SIZE 512

// Ring buffer with modulo wraparound (line 179-186):
pq_next = (pq_tail + 1) % PACKET_QUEUE_SIZE;
if (pq_next != pq_head) {
    // Queue packet
    pq_tail = pq_next;
}
// If pq_next == pq_head (queue full), packet is SILENTLY DISCARDED
```

**Burst Scenario**:
- Host receives 600+ packets in one poll cycle (e.g., client burst of input frames)
- First 512 packets queued
- Packets 513-600 **silently dropped** (line 180 condition fails, pq_tail not advanced)
- Game.C does not detect loss; client believes input was received
- **Data loss silent** — no error flag, no retry, no flow control

**Evidence**:
- Line 537: `if (pq_head == pq_tail) return 0;` — empty queue check only
- No queue overflow flag or backpressure signal

**Root Cause**: Fixed queue size designed for 30 FPS at 2-4 packets/frame = 8-16 packets/frame max; burst of 10+ players sending input simultaneously can exceed 512 in <30ms.

**Impact**: Multiplayer desync, lost weapon fire, position desyncs during network lag spikes.

---

### Finding 1C: TCP Fragmentation Handling Undocumented (Implicit Assumption)

**File**: SRC/MMULTI.C:100-108, 149-154  
**Severity**: HIGH  
**Type**: Protocol Gap (incomplete)

```c
// Line 100-108: Naive send (no MTU awareness)
static void net_send_raw(SOCKET sock, const unsigned char *data, int len)
{
    int sent = 0;
    while (sent < len) {
        int r = send(sock, (const char *)(data + sent), len - sent, 0);
        if (r <= 0) break;  // ← Incomplete: doesn't retry partial sends
        sent += r;
    }
}

// Line 149-154: Receive loop assumes TCP will bundle packets
while (recv_bufs[i].len < RECV_BUF_SIZE - 4096) {
    int r = recv(sock, (char *)(recv_bufs[i].buf + recv_bufs[i].len),
                 RECV_BUF_SIZE - recv_bufs[i].len, 0);
    if (r <= 0) break;
    recv_bufs[i].len += r;
}
```

**Issues**:
1. **No MTU documentation**: MAXPACKETSIZE = 2048 (line 42) assumes Ethernet MTU 1500 leaves 500B for headers/overhead, but documented nowhere
2. **TCP may fragment**: A 2048B payload + 4B header = 2052B payload sent. TCP will fragment across 1500B Ethernet frames. memmove() at line 192 handles concatenation, but no comment explaining this
3. **Incomplete send retry**: Line 105 breaks on partial send (r <= 0) without retrying; relies on TCP buffering. This is OK for non-blocking mode but not documented

**Impact**: On high-latency/lossy networks or wireless, fragmentation delays can cause game stalls. No protocol-level documentation for debugging.

---

## FOCUS AREA 2: compat/network_stub.c — What Needs to Land for SDL2/BSD Socket Port

**File**: compat/ directory inventory  
**Severity**: HIGH  
**Type**: Compat Layer Gap (incomplete)

Current compat/ structure:
```
compat/
  a.c                      # Unrelated
  audio_stub.c/.h          # Audio abstraction layer
  mact_stub.c              # Input abstraction layer  
  sdl_driver.c/.h          # SDL window/graphics driver
  compat.h                 # Platform defines
  pragmas_gcc.h            # Compiler pragmas
  hud.c/.h                 # HUD rendering
```

**Finding**: No `network_stub.c` or socket abstraction layer exists.

**Current Reality** (SRC/MMULTI.C:20-39):
- Platform detection via `#ifdef _WIN32` embedded in MMULTI.C
- Winsock2.h on Windows, sys/socket.h on Linux
- Error code remapping hardcoded in MMULTI.C

**What Needs to Land** (for clean SDL2 port):
1. **compat/net_socket.h** — Abstract socket API:
   ```c
   typedef struct net_socket_s *net_socket_t;
   net_socket_t net_socket_create(int family, int type, int proto);
   int net_socket_bind(net_socket_t, const char *ip, int port);
   int net_socket_listen(net_socket_t, int backlog);
   net_socket_t net_socket_accept(net_socket_t, char *peer_ip_out, int *peer_port_out);
   int net_socket_connect(net_socket_t, const char *ip, int port);
   int net_socket_send(net_socket_t, const void *data, int len);
   int net_socket_recv(net_socket_t, void *data, int len);
   void net_socket_close(net_socket_t);
   ```

2. **compat/net_socket_posix.c** — POSIX implementation (Linux/BSD)

3. **compat/net_socket_win32.c** — Windows implementation

4. **Error code mapping**:
   ```c
   #define NET_EAGAIN (platform-specific)
   #define NET_EWOULDBLOCK (platform-specific)
   // etc.
   ```

**Impact**: Without compat layer, MMULTI.C remains tightly coupled to platform socket APIs, hindering future ports to Web (WebSockets) or mobile (custom protocol).

---

## FOCUS AREA 3: source/GAME.C Multiplayer Code Paths

### Finding 3A: Missing Player Join/Leave Explicit Packets

**File**: source/GAME.C:404-406, 484-488, SRC/MMULTI.C:365-371  
**Severity**: MEDIUM  
**Type**: Protocol Gap (incomplete handshake)

**Current Join Flow** (implicit):
1. Host accepts TCP connection (MMULTI.C line 344)
2. Host sends 4-byte handshake [player_idx, numplayers, 0, 0] (line 365-371)
3. **No explicit join packet** from client acknowledging receipt
4. Client starts sending game packets immediately (GAME.C line 793)
5. Host assumes join is complete (no confirmation)

**Issue**: No three-way handshake. If client crashes after connecting but before first game packet, host slot remains allocated forever (Round 1 Finding 4: No Handshake Timeout).

**Current Leave Flow** (line 484-488):
```c
sendlogoff() {
    tempbuf[0] = 255;              // Magic value 255
    tempbuf[1] = myconnectindex;   // Player ID
    for(i=connecthead;i>=0;i=connectpoint2[i])
        if (i != myconnectindex)
            sendpacket(i,tempbuf,2L);  // Send to others
}
```

**Missing**: No host-side "player left" packet. Clients only detect peer disconnect via TCP connection drop or 30-60s timeout.

**Impact**: Inconsistent player roster during network lag; clients may not render correct player list immediately after disconnect.

---

### Finding 3B: Save-State Sync Lacks Sequence/CRC Validation

**File**: source/GAME.C:398-406, 536-575  
**Severity**: MEDIUM  
**Type**: Data Integrity Gap

**Current Save-State Sync**:
```c
// Packet type 5 (line 995-1011, sent by host):
tempbuf[0] = 5;
tempbuf[1] = ud.m_level_number;
tempbuf[2] = ud.m_volume_number;
// ... (7 more single-byte fields)
// Line 6009-6010: Send to all players
for(i=connecthead;i>=0;i=connectpoint2[i])
    sendpacket(i,tempbuf,11);

// Packet type 5 receive (line 513-535):
// Client unpacks directly into ud struct — NO CRC CHECK, NO SEQUENCE
ud.m_player_skill = ud.player_skill = packbuf[3];
ud.m_monsters_off = ud.monsters_off = packbuf[4];
// ...
```

**Issue**:
1. No CRC field in save-state packet (11B payload has no checksum)
2. No sequence number — packet out-of-order (unlikely on TCP, but not impossible) could cause state rollback
3. No version field — incompatible game versions silently desync
4. Type 8 also exists (line 560-575) — similar issue, less clear when each is used

**Also**: Packet type 126 calls loadplayer() (line 404) — no CRC validation before deserializing save file.

**Impact**: Corrupted packet causes silent game state corruption. Clients accept arbitrary state overwrite without validation.

---

### Finding 3C: Score Sync Not Explicitly Handled (Implicit via Game Loop)

**File**: source/GAME.C:725-800, 815-860  
**Severity**: LOW  
**Type**: Design gap (not a bug, but incomplete)

**Current Score Sync**:
- Score is part of player state `ps[i].fragcount`, `ps[i].deaths`, etc.
- No explicit score sync packet
- Scores updated implicitly via game events (player killed → fragcount incremented by all clients computing same physics)
- **Assumption**: All clients compute identical game physics → identical scores

**Issue**: If a client's game loop lags, it may compute scores out-of-sync with host. No explicit score sync packet to re-align.

**Evidence**:
- No packet type dedicated to score updates
- Packet types 0, 1 carry input frames, not score deltas

**Impact**: Low; most games tolerate score desync until next game reset. But tournament-grade gaming requires explicit score checksum (CRC of `ps[0..15].fragcount`).

---

## FOCUS AREA 4: Threat Model — Malicious Peer Packet Anatomy

**File**: SRC/MMULTI.C:158-175, source/GAME.C:393-405  
**Severity**: CRITICAL  
**Type**: Security (zero authentication)

### Smallest Set of Changes for LAN-Grade Safety

**Threat 1: Forged Player Index**
- Malicious client sends: `[sender=0x05, dest=0x00, len_lo=0x10, len_hi=0x00, payload...]`
- Packet claims to be from player 5, but client 2 sent it
- Host relays to all clients as if player 5 sent it

**Mitigation** (smallest change):
  - Host validates: `from_player` byte MUST match socket index of sender
  - At MMULTI.C line 158, instead of trusting `recv_bufs[i].buf[0]`, use `from_player = i`
  - **Cost**: 1 line change (line 158: `int from_player = i;` not `recv_bufs[i].buf[0]`)

**Threat 2: Packet Length Spoofing → OOB Relay**
- Malicious client sends: `[sender, dest, 0xFF, 0xFF, ...]` (length = 65535)
- Host relays `total_len = 4 + 65535 = 65539` bytes to victim
- **Not an OOB crash** (line 163 bounds check catches it), but relay could fail

**Mitigation**: Already present (line 163).

**Threat 3: Queue Overflow DoS**
- Malicious client sends 512+ frames of input instantly
- Packet queue fills, legitimate packets dropped
- **No mitigation** beyond per-socket rate limiting

**Mitigation** (hardest):
  - Track bytes/sec per socket, drop if exceed 100KB/s
  - Add exponential backoff on malicious sockets
  - **Cost**: 20-30 lines

**Threat 4: Replay Attack**
- Attacker captures packet type 0 (input frame), replays it seconds later
- Host relays duplicate input → player moves twice

**Mitigation**:
  - Add sequence number to all packets
  - Reject packet if `sequence <= last_acked_sequence[from_player]`
  - **Cost**: 10 lines

---

## FOCUS AREA 5: Co-op vs DM Mode Divergence in Packet Handling

**File**: source/GAME.C:520, 531, 568, 1577-1697  
**Severity**: MEDIUM  
**Type**: Protocol coherence gap (not a bug, but inconsistent)

### Findings:

**Co-op vs DM Packet Format** (NO difference):
```c
// Packet type 5 send (line 6005):
tempbuf[8] = ud.m_coop;  // Same field sent for co-op AND DM

// Packet type 5 receive (line 520):
ud.m_coop = packbuf[8];  // Always unpacked

// Packet type 8 send (line 568):
ud.m_coop = ud.coop = packbuf[8];  // Same
```

**Issue**: The only difference between co-op and DM is the `ud.coop` flag value, but packet format is identical. **This is OK** — not a bug. But it means:
- A co-op server (ud.coop=1) and DM server (ud.coop=0) send same packet format
- No way to validate mode mismatch before join
- If client sends `ud.coop=1` when host expects `ud.coop=0`, no error

**Example Desync**:
1. Host set up as DM (ud.coop=0)
2. Client connects, receives packet type 5 with coop_flag=0
3. **But** client's local code has bug, sets ud.coop=1 anyway
4. Client sees friendly-fire disabled (co-op behavior) while host sees it enabled (DM)
5. Cheater can exploit this to shoot teammates without retaliation

**Blockers**: None; low priority. But **version check** (Round 1 Finding 6) would catch mode mismatches if version incremented per game version.

---

## FOCUS AREA 6: SRC Constants — Stale or Wrong Values

**File**: SRC/MMULTI.C:41-46, source/GAME.C:65  
**Severity**: MEDIUM  
**Type**: Protocol / Config Gap

### Constant Analysis:

| Constant | Value | Assessment | Notes |
|----------|-------|------------|-------|
| MAXPLAYERS | 16 | **Correct** | Matches Atomic Edition max |
| MAXPACKETSIZE | 2048 | **Conservative** | Safe for all MTUs; could be 4096 on modern LAN |
| NET_HEADER_SIZE | 4 | **Tight but OK** | No room for version/seq fields; redesign needed for security |
| PACKET_QUEUE_SIZE | 512 | **TOO SMALL** | 30 FPS * 16 players * 4 packets/frame = 1920 worst-case; 512 insufficient for lag spikes |
| CONNECT_TIMEOUT_SEC | 60 | **TOO LARGE** | Handshake timeout excessively long; 5-10s standard in modern games |
| DEFAULT_PORT | 23513 | **Arbitrary but reasonable** | No conflict with common ports |
| TIMERUPDATESIZ | 32 (source/GAME.C:65) | **Correct** | Handshake packet sent every 32 frames at 30 FPS = ~1 second sync |
| MOVEFIFOSIZ | ? | **Undefined** | Not found in MMULTI.C; defined in GAME.C or header, value unknown |

### New Finding: No Protocol Version Constant

**File**: SRC/MMULTI.C (implicit)  
**Severity**: HIGH

```c
// No #define for protocol version
// Packet type 6 checks BYTEVERSION (GAME.C line 537):
if (packbuf[1] != BYTEVERSION)
    gameexit("\nYou cannot play Duke with different versions.");

// But BYTEVERSION is NOT defined in MMULTI.C; defined elsewhere
// This means MMULTI.C doesn't enforce version on handshake — only GAME.C does
```

**Issue**: Host accepts any client at TCP level (MMULTI.C) without version check. Version check only happens at GAME.C layer. If client crashes before sending packet type 6, host slot consumed forever by wrong-version client.

**Mitigation**: Add protocol version to handshake (line 365-371):
```c
// Instead of [player_idx, numplayers, 0, 0], send:
// [player_idx, numplayers, protocol_version_lo, protocol_version_hi]
```

---

## PACKET STRUCTURE RE-ANALYSIS (Round 2)

### Current Header Format (4 bytes):
```
[1B sender] [1B dest] [2B len_little_endian]
```

### Missing Fields for Production:
- No protocol version → incompatible clients silently connect
- No sequence number → no replay protection, OOO detection impossible
- No CRC → packet corruption undetected
- No timestamp → no timeout tracking

### Recommended Redesign (8 bytes, backward-compatible via version field):
```
[1B protocol_version] [1B sender] [1B dest] [1B flags]
[2B payload_length] [2B crc16 or sequence]
```

---

## SEVERITY COUNTS (ROUND 2 NEW FINDINGS)

| Severity | Count | Examples |
|----------|-------|----------|
| **CRITICAL** | 1 | Packet queue wraparound (512 limit) |
| **HIGH** | 4 | Implicit sequence numbers, fragmentation undocumented, compat layer missing, protocol version missing |
| **MEDIUM** | 3 | Join/leave packets incomplete, save-state CRC missing, co-op/DM mode not validated, constants too small |
| **LOW** | 1 | Score sync implicit (design choice, not bug) |
| **INFO** | 0 | — |
| **TOTAL (NEW)** | **6** | — |

---

## COMBINED SEVERITY (ROUND 1 + ROUND 2)

| Severity | Round 1 | Round 2 | Combined |
|----------|---------|---------|----------|
| CRITICAL | 3 | 1 | **4** |
| HIGH | 4 | 4 | **8** |
| MEDIUM | 2 | 3 | **5** |
| LOW | 1 | 1 | **2** |
| INFO | 1 | 0 | **1** |
| **TOTAL** | **11** | **6** | **17** |

---

## RECOMMENDATIONS FOR ROUND 2

### Blocking Production (CRITICAL):
- [ ] **Increase PACKET_QUEUE_SIZE to 2048** (line 78) — burst protection
- [ ] **Implement sequence numbers** in packet header (requires protocol redesign)

### High Priority (HIGH):
- [ ] **Document MTU assumptions and TCP fragmentation strategy**
- [ ] **Create compat/net_socket.h abstraction layer**
- [ ] **Add protocol version field to handshake** (MMULTI.C line 365-371)
- [ ] **Add frame_number/sequence to packet header**

### Medium Priority (MEDIUM):
- [ ] **Add CRC to save-state packets** (GAME.C type 5/8)
- [ ] **Add explicit join/leave packet types**
- [ ] **Reduce CONNECT_TIMEOUT_SEC to 10** (line 46)
- [ ] **Document co-op/DM mode validation**
- [ ] **Define MOVEFIFOSIZ in public header**

---

## CONCLUSION (ROUND 2)

MMULTI.C remains architecturally sound (star topology, non-blocking I/O, TCP-based) but reveals 6 new protocol-level gaps in this audit:

1. **Implicit sequencing** — game layer assumes TCP ordering, no recovery from OOO
2. **Undersized queue** — 512 packets insufficient for burst playloads
3. **Fragmentation undocumented** — TCP fragmentation handling implicit, not documented
4. **Compat layer missing** — network abstraction layer needed for future ports
5. **Incomplete handshake** — no explicit join/leave packets, no three-way confirmation
6. **Stale timeouts** — 60s handshake timeout excessive for LAN

**Next steps**: Implement the 6 findings above before multiplayer beta testing.
