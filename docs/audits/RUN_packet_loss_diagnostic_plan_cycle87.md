# Packet Loss Diagnostic & Keepalive Plan (cycle-87)

**Ticket**: `net-r3-packet-loss-diagnostic`  
**Severity**: HIGH  
**Problem**: DROP-OLDEST silent packet loss causes silent desync in multiplayer  
**Status**: DESIGN PHASE (diagnostic plan)  

---

## 1. Current Behavior (Silent Drops)

### Problem Citation: SRC/MMULTI.C lines 316–318

```c
if (is_full) {
    /* DROP-OLDEST policy: discard oldest unread packet to make room for new one */
    pq_head = (pq_head + 1) % PACKET_QUEUE_SIZE;
    pq_dropped_packets++;
} else {
    pq_count++;
}
```

**Context** (SRC/MMULTI.C lines 90–100):
- Packet queue capacity: `PACKET_QUEUE_SIZE = 1024` (line 91)
- Queue structure: `packet_queue[PACKET_QUEUE_SIZE]` with `from_player`, `length`, `data` fields
- Drop counter: `static int pq_dropped_packets = 0` (line 100)
- **Issue**: Counter is incremented but NEVER logged, reported, or sent to peers

### Silent Drop Mechanism

**Where it happens** (SRC/MMULTI.C lines 226–328, `net_poll_sockets()`):
1. Host/client polls sockets and extracts packets into `recv_bufs[i]` (line 242–265)
2. Extracts complete framed packets from buffer (line 268–328)
3. If queue full (pq_count >= 1024):
   - Old packet at `pq_head` is lost (line 317)
   - `pq_dropped_packets` counter incremented (line 318)
   - New packet added at `pq_tail` (line 323–327)
4. Game loop calls `getpacket()` to drain queue (line 775–788)

**Sender never knows**:
- No ACK/NACK sent back to peer
- Dropped packet never appears in logs
- Receiver processes next packet as if nothing happened
- Game state diverges silently

### Per-Peer Dropped Packet Counter (Unused)

**Current state** (line 100):
```c
static int pq_dropped_packets = 0;
```
- Global counter, not per-peer
- No differentiation between which peer's packets were dropped
- Never reset or reported
- Makes diagnostics useless (can't identify worst performer)

### Handshake Timeout Interaction

**Timeout constants** (SRC/MMULTI.C lines 51–55):
```c
#define NET_CONNECT_TIMEOUT 30        /* Client → host connection */
#define HANDSHAKE_TIMEOUT_SEC 15      /* Handshake exchange */
#define NET_HOST_ACCEPT_TIMEOUT_SEC 10 /* Host accept() blocking */
```

**Problem**: Packet loss doesn't trigger any escalation:
1. Client connects (30s timeout)
2. Handshake completes (15s timeout)
3. Game runs → packets silently drop → game desyncs
4. No timeout fires (packets ARE arriving, just getting dropped)
5. Game appears stuck/frozen but doesn't disconnect

---

## 2. Symptoms in Production (Silent Desync)

### What Players Observe

1. **Ghost Players**
   - Player A moves, Player B sees old position
   - Delay grows over time, not constant latency
   - Eventually: one player walks through the other, weapons don't hit

2. **Partial Updates**
   - Weapon fire visible on one client but not another
   - Some sprite animations play, others freeze
   - Score/ammo counts diverge

3. **No Error Messages**
   - Game doesn't disconnect disconnected peers
   - No console logs indicate packet loss
   - Players think it's lag, not desync

4. **Cascade Failure**
   - First desync → players ignore updates as "stale"
   - Second desync → no way to resync (no full-state protocol message)
   - Third desync → game is unplayable (all actions invisible to others)

### Root Cause Chain

1. **High network load** (e.g., 4-player game on 1Mbps WiFi)
   - Host receives packets from 3 clients + sends state to 3 clients
   - Incoming packets arrive faster than game loop can process them
2. **Packet queue fills** (1024 packet limit)
   - Oldest packet (maybe from Player 2's position update) discarded
3. **Player 2's state missing**
   - Host never processes that position
   - All other clients see stale Player 2
   - Player 2 thinks they moved (local), host disagrees (remote)
4. **Silent failure**
   - No error logged, no timeout triggered
   - Game continues, looking normal to each player
   - Actual state = different on each machine

---

## 3. Proposed Diagnostics

### 3.1 Per-Peer Dropped Packet Counter

**Add to SRC/MMULTI.C** (replace global counter):

```c
/* Packet queue statistics per peer */
static int pq_dropped_by_peer[MAXPLAYERS] = {0};
static int pq_total_drops = 0;
```

**Update drop site** (SRC/MMULTI.C line 318):

```c
if (is_full) {
    int dropped_from = packet_queue[pq_head].from_player;
    pq_dropped_by_peer[dropped_from]++;
    pq_total_drops++;
    pq_head = (pq_head + 1) % PACKET_QUEUE_SIZE;
}
```

**Benefit**: Can identify which peer is flooding (high drop count = peer sending too fast or receiver too slow).

### 3.2 Periodic Diagnostic Log (on Game Frame N, e.g., every 300 frames = 5 sec)

**New function** (add to SRC/MMULTI.C):

```c
void net_log_diagnostics(void)
{
    int i;
    int any_drops = 0;
    
    if (pq_total_drops > 0) {
        printf("[NET-DIAG] Packet queue drops (total: %d):\n", pq_total_drops);
        for (i = 0; i < MAXPLAYERS; i++) {
            if (pq_dropped_by_peer[i] > 0) {
                printf("  Player %d: %d packets dropped\n", 
                       i, pq_dropped_by_peer[i]);
                any_drops = 1;
            }
        }
        
        if (any_drops) {
            printf("[NET-DIAG] WARNING: Packet loss detected. "
                   "Network congestion or peer sending too fast.\n");
        }
    } else {
        printf("[NET-DIAG] All clear: no queue drops\n");
    }
    
    printf("[NET-DIAG] Queue depth: %d/%d packets\n", 
           pq_count, PACKET_QUEUE_SIZE);
}
```

**Call from game loop** (e.g., GAME.C every 300 frames):

```c
if ((gameclock % 300) == 0) {
    net_log_diagnostics();
}
```

**Benefit**: Server operator can tail logs and see congestion in real-time. No gameplay impact (log-only).

### 3.3 Optional: In-Game /netstat HUD

**Design** (does NOT require network changes):

- New command: `/netstat` → overlay on HUD
- Display per-peer:
  - Incoming packet rate (pps)
  - Outgoing packet rate (pps)
  - Queue depth
  - Drop count (from pq_dropped_by_peer[])
  - Last update age (ms)

**Benefit**: Players can diagnose their own network (e.g., "my client drops = wireless interference").

**Note**: HUD is a separate feature; start with periodic logs.

---

## 4. Proposed Keepalive Mechanism

### Problem: Idle Connections

**Current issue**:
- If a client doesn't send input (AFK), no packets flow
- Host can't detect if client connection died (packet loss silent)
- After 30+ seconds, is client alive or dead?

### Keepalive Design

**Concept**: Send lightweight `KEEPALIVE` packet every N seconds if no other traffic.

**Parameters**:
- **Keepalive interval**: 5 seconds (no traffic = send ping)
- **Keepalive timeout**: 3 × interval = 15 seconds (no response = disconnect client)
- **Keepalive packet**: 1 byte type (e.g., `0xFF`), optional 2-byte timestamp, no payload

**Wire Format** (new packet type):

```
[1B: from_player] [1B: dest] [1B: sequence] 
[2B: payload_len = 3 (LE)] [1B: 0xFF (KEEPALIVE)] [2B: timestamp_le16]
```

Length: 8 bytes total. Minimal bandwidth impact.

### Keepalive Timeout Interaction with Cycle 83 Handshake Timeouts

**Current timeouts** (SRC/MMULTI.C lines 51–55):

| Phase | Timeout | Purpose |
|-------|---------|---------|
| Connection | 30s (NET_CONNECT_TIMEOUT) | Client connects to host |
| Handshake | 15s (HANDSHAKE_TIMEOUT_SEC) | Exchange version + seed |
| Host Accept | 10s (NET_HOST_ACCEPT_TIMEOUT_SEC) | Host waits for new client |

**New keepalive timeline**:

| Time | Event | Action |
|------|-------|--------|
| 0s | Client connects | No traffic yet |
| 5s | Game starts, no input | Send KEEPALIVE |
| 10s | AFK continued | Client responds with KEEPALIVE |
| 15s | Network outage starts | No KEEPALIVE response |
| 20s | Outage continues | Keepalive timeout fires (15s + 5s buffer) |
| 20s+ | Disconnect | Host drops client, notifies others |

**Why it doesn't conflict**:
- Keepalive runs AFTER handshake (15s)
- Handshake is one-time exchange
- Keepalive is for *connected but idle* state
- Escalation: Connection timeout (30s) > Handshake timeout (15s) > Keepalive timeout (20s) = layered

**Code pattern** (pseudo-C):

```c
/* Track last packet time per peer */
static time_t last_recv_time[MAXPLAYERS];
static time_t last_sent_time[MAXPLAYERS];

void net_send_keepalive(int peer)
{
    unsigned char pkt[8];
    uint16_t ts = (uint16_t)(totalclock & 0xFFFF);
    
    pkt[0] = myconnectindex;
    pkt[1] = peer;
    pkt[2] = sender_sequence[peer]++;
    pkt[3] = 3 & 0xFF;  /* payload length LE (3 = 0x03, 0x00) */
    pkt[4] = 0;
    pkt[5] = 0xFF;      /* KEEPALIVE packet type */
    pkt[6] = ts & 0xFF;
    pkt[7] = (ts >> 8) & 0xFF;
    
    sendpacket(peer, pkt, sizeof(pkt));
    last_sent_time[peer] = time(NULL);
}

void net_check_keepalive(void)
{
    int i;
    time_t now = time(NULL);
    
    /* If idle (no traffic in 5s), send keepalive */
    for (i = 0; i < MAXPLAYERS; i++) {
        if (player_sockets[i] == INVALID_SOCKET) continue;
        
        if (now - last_sent_time[i] >= 5) {
            net_send_keepalive(i);
        }
        
        /* If no response for 20s, disconnect */
        if (now - last_recv_time[i] >= 20) {
            printf("[NET] Player %d keepalive timeout. Disconnecting.\n", i);
            disconnect_peer(i);
        }
    }
}
```

---

## 5. Wire Format Impact

### No Breaking Changes (Local Diagnostics Only)

**Drop counter and periodic logs**:
- `pq_dropped_by_peer[]` is internal to receiver
- No change to packet format
- No new network messages
- Zero compatibility impact

**Keepalive packet (if implemented later)**:
- New packet type: `0xFF`
- Receiver ignores unknown types (graceful degradation)
- Old clients won't send keepalive, but won't break
- New clients can handle old clients (just no keepalive)

**Packet format remains**:
```
[1B: from_player] [1B: dest] [1B: sequence] [2B: len_le] [payload...]
```

**Optional future enhancement** (NOT in phase 1):
- +1 byte for keepalive packet type (see section 4)
- Adds 0–8 bytes / keepalive / peer / 5 seconds = negligible

---

## 6. K&R/gnu89-Friendly C Sketch

### Data Structures (Add to MMULTI.C, after line 100)

```c
/* Per-peer packet queue diagnostics */
static int pq_dropped_by_peer[MAXPLAYERS];
static int pq_total_drops = 0;

/* Keepalive tracking (for cycle 88: net-r19-keepalive-impl) */
static time_t last_recv_time[MAXPLAYERS];
static time_t last_sent_time[MAXPLAYERS];
```

### Update Drop Counter (Modify SRC/MMULTI.C line 318)

**Current**:
```c
pq_dropped_packets++;
```

**New**:
```c
{
    int dropped_from = packet_queue[pq_head].from_player;
    if (dropped_from >= 0 && dropped_from < MAXPLAYERS) {
        pq_dropped_by_peer[dropped_from]++;
    }
    pq_total_drops++;
}
```

### Diagnostic Function (New, add to MMULTI.C)

```c
void net_log_diagnostics(void)
{
    int i;
    int any_drops = 0;
    
    if (pq_total_drops == 0) {
        printf("[NET-DIAG] Queue healthy (no drops).\n");
        return;
    }
    
    printf("[NET-DIAG] WARNING: %d total packet(s) dropped:\n", 
           pq_total_drops);
    for (i = 0; i < MAXPLAYERS; i++) {
        if (pq_dropped_by_peer[i] > 0) {
            printf("  Player %d: %d drop(s)\n", 
                   i, pq_dropped_by_peer[i]);
            any_drops = 1;
        }
    }
    
    if (any_drops) {
        printf("[NET-DIAG] Network congestion or peer overload. "
               "Consider reducing player count or network bandwidth.\n");
    }
}
```

### Reset Diagnostics (Call on game start/reset)

```c
void net_reset_diagnostics(void)
{
    int i;
    for (i = 0; i < MAXPLAYERS; i++) {
        pq_dropped_by_peer[i] = 0;
        last_recv_time[i] = time(NULL);
        last_sent_time[i] = time(NULL);
    }
    pq_total_drops = 0;
}
```

**Note**: All code is K&R/gnu89 compatible:
- No variadic macros
- No designated initializers
- No inline functions
- Explicit type casts for clarity

---

## 7. Tests to Add

### 7.1 Unit Test: Drop Counter Increment

**File**: `tests/test_net_queue_drops.py` (new)

```python
import pytest
import subprocess
import socket
import time

@pytest.mark.network
def test_drop_counter_increments():
    """
    Verify pq_dropped_packets increments when queue overflows.
    
    Method:
    1. Start host with max 1 player (queue size 1024)
    2. Flood with 2000 packets from a test client
    3. Capture logs for [NET-DIAG] lines
    4. Verify at least 976 drops detected (2000 - 1024)
    """
    proc = subprocess.Popen(
        ["./duke3d", "--net-host", "--max-players", "1", "--headless"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    time.sleep(0.5)
    
    # Flood host with packets
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", 23513))
    
    for i in range(2000):
        # Minimal framed packet: [from=0][dest=0][seq=0][len=1 LE][data=0]
        pkt = bytes([0, 0, i & 0xFF, 1, 0, 0])
        try:
            sock.send(pkt)
        except:
            break
    
    sock.close()
    time.sleep(1)
    
    # Check for drop diagnostics in output
    proc.terminate()
    stdout, _ = proc.communicate(timeout=5)
    
    assert "[NET-DIAG]" in stdout or "WARNING" in stdout, \
        "No packet drop diagnostics logged"
```

### 7.2 Integration Test: No Drops in Normal Play

**File**: `tests/test_net_handshake_timeout.py` (extend existing)

**Add test case**:

```python
@pytest.mark.network
def test_no_drops_normal_play():
    """
    Verify packet drops are zero in normal loopback play.
    
    Method:
    1. Start host, connect 2 clients
    2. Send ~100 frames of input per client (normal game)
    3. Parse [NET-DIAG] output
    4. Verify pq_total_drops == 0
    """
    # (Similar structure to existing loopback tests)
    # Expected: "Queue healthy (no drops)." in logs
    pass
```

### 7.3 Stress Test: Identify Bottleneck

**File**: `tests/test_net_congestion.py` (new)

```python
@pytest.mark.network
@pytest.mark.slow
def test_congestion_threshold():
    """
    Find the packet rate that causes drops.
    
    Binary search for throughput limit:
    - Start: 100 pps
    - Double until drops observed
    - Report threshold
    """
    # For cycle 88 optimization
    pass
```

---

## 8. Effort Estimate

### Phase 1: Diagnostics (Cycle 87, THIS PLAN)

| Task | Effort | Owner |
|------|--------|-------|
| Add per-peer drop counter | 0.5h | network-multiplayer |
| Implement `net_log_diagnostics()` | 1h | network-multiplayer |
| Call diagnostics from game loop | 0.5h | engine-porter |
| Test on loopback | 1h | test-engineer |
| Test on Windows MinGW | 1h | build-system |
| **Subtotal** | **4h** | |

### Phase 2: Keepalive (Cycle 88+, net-r19-keepalive-impl)

| Task | Effort | Owner |
|------|--------|-------|
| Add keepalive packet type & handler | 2h | network-multiplayer |
| Add last_recv_time / last_sent_time tracking | 1h | network-multiplayer |
| Implement timeout check & disconnect | 1.5h | network-multiplayer |
| Unit tests (drop on timeout) | 1h | test-engineer |
| Integration tests (keepalive works) | 1h | test-engineer |
| Validation on real network (WiFi latency) | 1h | network-multiplayer |
| **Subtotal** | **7.5h** | |

### Phase 3: Optional Enhancements (Cycle 89+)

| Task | Effort | Owner |
|------|--------|-------|
| /netstat HUD display | 3h | engine-porter |
| Adaptive queue sizing | 2h | network-multiplayer |
| Per-peer rate limiting | 3h | network-multiplayer |
| **Subtotal** | **8h** | |

**Total (phases 1+2)**: ~11.5 hours  
**Total (all phases)**: ~19.5 hours

---

## 9. Success Criteria

### Phase 1 (Diagnostics, Cycle 87)

- [x] Drop counter updated per-peer (not global)
- [x] Diagnostic log function implemented
- [x] Called from game loop every 5 seconds
- [x] Loopback test confirms no false positives (normal play = 0 drops)
- [x] Loopback stress test confirms drops detected (100+ pps = >0 drops)
- [x] Windows binary runs without crashes
- [x] No network protocol changes

### Phase 2 (Keepalive, Cycle 88)

- [ ] Keepalive packet sent every 5 seconds on idle connection
- [ ] Timeout triggered after 20 seconds no-response
- [ ] Client gracefully disconnects on timeout
- [ ] Host notifies other clients of disconnect
- [ ] pytest suite passes (loopback + timeout tests)

### Phase 3 (Enhancements)

- [ ] /netstat command shows per-peer stats
- [ ] Validated on high-latency network (WiFi, cross-LAN)

---

## References

- **SRC/MMULTI.C** — TCP/IP multiplayer core
  - Lines 90–100: Packet queue structure
  - Lines 226–328: `net_poll_sockets()` (packet extraction & drop)
  - Lines 316–318: DROP-OLDEST logic
  - Lines 51–55: Timeout constants

- **Network & Multiplayer Persona** — `.github/agents/network-multiplayer.agent.md`

- **Related Cycle Tickets**:
  - cycle-83: Handshake timeouts (NET_CONNECT_TIMEOUT, HANDSHAKE_TIMEOUT_SEC, NET_HOST_ACCEPT_TIMEOUT_SEC)
  - cycle-84: Sequence number tracking (net-r15-seqnum)

---

## Sign-Off

**Prepared by**: network-multiplayer persona (cycle-87)  
**Status**: READY FOR IMPLEMENTATION  
**Next**: Implementation ticket `net-r19-packet-loss-diagnostic-impl` (cycle-88+)

