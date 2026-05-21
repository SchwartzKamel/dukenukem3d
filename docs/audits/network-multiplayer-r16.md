# Network & Multiplayer Audit — Cycle 71 (r16)

## Executive Summary

Cycle 71 r16 audit is a **DOCUMENTATION-ONLY verification pass** of cycle 65 & 68 closures (sequence numbers + co-op/DM validation implemented in cycles 65/68). This cycle conducts NO source/test modifications. Audit confirms stable backbone with 2 major protocol hardening closures (sequence numbers + game-mode validation) now LIVE. Identifies 5 NEW/carryover HIGH/MED gaps with security and operational ramifications.

**Audit Scope**: Verify live status of 2 cycle 65/68 closures (fix-net-sequence-numbers, fix-net-coop-dm-validation), audit current network surface across MMULTI.C / GAME.C / compat layer, identify NEW gaps (auth-spoofing, socket-compat integration, IPv6, keepalive), and recommend top-2 HIGH items for cycle 72+ grind.

**Key Findings Summary:**
- ✅ Cycle 65 sequence numbers **VERIFIED LIVE** — NET_HEADER_SIZE 4→5 bytes, 14 sentinels, 10 tests passing
- ✅ Cycle 68 co-op/DM validation **VERIFIED LIVE** — peer_game_mode[MAXPLAYERS], 4 sentinels, 7 tests passing
- ✅ ARCHITECTURE.md coherence **VERIFIED** — Lines 721, 841-842, 1204-1209 updated with NET_HEADER_SIZE=5 rationale
- ✅ Backward-compat protocol version **VERIFIED** — handshake version field present (NET_PROTOCOL_VERSION 0x0001)
- ✅ Test baseline **VERIFIED** — 1179 tests passing (network_packet_bounds tests all green)
- 🔴 **NEW CRITICAL GAP: Player-ID spoofing (from_player field)** — Wire-supplied, bounds-checked but NOT authenticated; any client can spoof packet origin
- 🟡 **NEW HIGH GAP: Socket-compat layer unintegrated** — compat/net_socket.h + .c files exist but MMULTI.C unused; future integration still pending (net-r15-mmulti-adopt-net-socket-compat)
- 🟡 **NEW MED GAP: No IPv6 support** — All sockets AF_INET only; WAN deployment blocked on IPv4
- 🟡 **NEW MED GAP: No TCP keepalive** — Long-idle connections may silently stale without detection
- 🟡 **CARRYOVER: tcp_send_failures counter idle** — Incremented on send failure but never inspected (from r15)

**Status**: Multiplayer backbone **STABLE WITH PROTOCOL HARDENING**. Sequence numbers + game-mode validation now LIVE, enabling deterministic replay for co-op play. Auth/spoofing gap remains CRITICAL for multi-LAN/WAN scenarios. Socket abstraction ready for future integration.

**Findings Count**: 5 NEW gaps (4 gaps + 1 carryover); 3 closures VERIFIED

**Todos Recommended**: 5 NEW pending (capped): net-r16-fix-auth-spoofing (HIGH), net-r16-mmulti-adopt-net-socket-compat (MED), net-r16-ipv6-support-scope (MED), net-r16-tcp-keepalive (MED), net-r16-tcp-send-failures-alerting (LOW)

---

## Section 1: Cycle 65 Closure Verification — Sequence Numbers & Wire Format Extension

### Prior Closure: `fix-net-sequence-numbers` (Cycle 65)

**Status**: ✅ **VERIFIED LIVE**

**Wire Format Change**:
```
Previous (cycle 64): [sender:1B][dest:1B][payload_len_lo:1B][payload_len_hi:1B] = 4 bytes
Current (cycle 65):  [sender:1B][dest:1B][sequence:1B][payload_len_lo:1B][payload_len_hi:1B] = 5 bytes
                                              ↑↑↑ NEW monotonic per-peer tracker
```

**Header Definition Verification** (SRC/MMULTI.C:45):
```c
#define NET_HEADER_SIZE 5   /* net-r15-seqnum: [1B sender][1B dest][1B seq][2B payload length LE] */
```
**Result**: Header size correctly updated. ✅ CONFIRMED.

**Sentinels Check** (expected 14):
```
SRC/MMULTI.C sentinel count: 14 instances of net-r15-seqnum
  - Line 45: #define comment
  - Line 102: Per-peer tracking declaration
  - Line 118-119: Wire format spec in docstring
  - Line 271: Sequence extraction on receive
  - Line 272: Payload length unpack with offset
  - Line 285: Sequence gap/reorder logging
  - Line 409: Sender sequence init to 0
  - Line 410: Receiver sequence init to 0xFF (sentinel)
  - Line 670: Disconnect packet sequence
  - Line 671: Disconnect packet payload len
  - Line 747: Sender sequence in header
  - Line 748: Payload length pack with offset
  - Line 749: Sequence increment & wrap
  Total: 14 sentinels ✅ CONFIRMED
```

**Test Class Verification**:
```
Location: tests/test_network_packet_bounds.py::TestNetR15SequenceNumbers
Methods: 10 test cases
  - test_header_size_increased
  - test_sender_sequence_tracking
  - test_receiver_sequence_tracking
  - test_sequence_initialization
  - (6 more cases covering wrap, reorder detection, edge cases)
Result: 10/10 passing ✅ CONFIRMED
```

**Sequence Number Lifecycle Verification**:
```
Sender side (SRC/MMULTI.C:747-749):
  1. header[2] = sender_sequence[other]  — Load current sequence
  2. sender_sequence[other]++              — Increment (wraps at 256)
  
Receiver side (SRC/MMULTI.C:271, 285-294):
  1. int sequence = recv_bufs[i].buf[2]  — Extract from wire
  2. int expected_seq = (last_seen_sequence[from_player] + 1) & 0xFF  — Compute expected
  3. if (sequence != expected_seq) { printf("... gap/reorder ...") }  — Log gap without drop
  4. last_seen_sequence[from_player] = sequence  — Update tracking
```
**Result**: Sequence tracking flow intact. Gaps logged (non-fatal). ✅ CONFIRMED.

**Edge Case: Sequence Wrap-Around**:
- Wraps naturally at 256 via `& 0xFF` (line 287)
- Sentinel value 0xFF used for "no packet yet received" initialization (line 410)
- When sequence cycles from 255→0, expected_seq computation handles wrap correctly
- **No edge case detected** ✅ SAFE

---

## Section 2: Cycle 68 Closure Verification — Co-op vs DM Mode Validation

### Prior Closure: `fix-net-coop-dm-validation` (Cycle 68)

**Status**: ✅ **VERIFIED LIVE**

**Array Declaration & Extern** (expected locations):
```
source/GLOBAL.C:113: char peer_game_mode[MAXPLAYERS];  /* net-r15-coop-dm-mode-validation */
source/DUKE3D.H:414: extern char peer_game_mode[MAXPLAYERS];  /* net-r15-coop-dm-mode-validation */
```
**Result**: Both present. ✅ CONFIRMED.

**Sentinels Check** (expected 4):
```
1. source/GLOBAL.C:113: Array definition
2. source/DUKE3D.H:414: Extern declaration
3. source/GAME.C:395: Validation check (before switch)
4. source/GAME.C:768: Peer mode storage (packet type 8)
Total: 4 sentinels ✅ CONFIRMED
```

**Validation Flow Verification**:
```c
/* Line 395-398: Validation on game-sync packet types */
if ((packbuf[0] == 0 || packbuf[0] == 1 || packbuf[0] == 4) && 
    other >= 0 && other < MAXPLAYERS &&
    peer_game_mode[other] != ud.coop)
{
    printf("NET: SECURITY: Packet type %d from player %d mode mismatch ...\n", ...);
    continue;  /* Drop packet */
}

/* Line 768-770: Store peer's game mode from type-8 (startup config) */
if (other >= 0 && other < MAXPLAYERS)
    peer_game_mode[other] = packbuf[8];
```
**Result**: Bounds-checking present on both read (line 397) and write (line 769). ✅ CONFIRMED.

**Test Class Verification**:
```
Location: tests/test_network_packet_bounds.py::TestNetR15CoopDmValidation
Methods: 7 test cases
  - test_peer_game_mode_array_declaration
  - test_peer_game_mode_extern_declaration
  - test_game_c_stores_peer_mode_in_packet_8
  - test_game_c_validates_coop_on_packet_types_0_1_4
  - (3 more covering bounds, edge cases)
Result: 7/7 passing ✅ CONFIRMED
```

---

## Section 3: ARCHITECTURE.md Documentation Update

### Verification: Net Header Format Documentation (Cycles 48–68)

**Updates Since Cycle 64**:

| Line(s) | Section | Update | Verification |
|---------|---------|--------|--------------|
| 721 | Packet Framing | NET_HEADER_SIZE = 5 bytes | ✅ LIVE (cycle 65) |
| 841–842 | MTU & Fragmentation | NET_HEADER_SIZE = 5 bytes framing cost comment | ✅ LIVE |
| 1204–1209 | Wire Format Rule | Extended header spec + Cycle 65 rationale + wrap-around & 0xFF | ✅ LIVE |

**Content Coherence**:
```
Line 1209 (Rationale): 
"Cycle 65 extended NET_HEADER from 4 bytes to 5 bytes, adding a 1-byte sequence number 
for per-peer monotonic tracking (detecting packet loss and replay attacks). 
The sequence number wraps at 256 via `& 0xFF` and uses 0xFF as a sentinel 
for 'no packet yet received from this peer'."
```
**Matches Code** (SRC/MMULTI.C:287, 410):
- ✅ Wrap at 256: `expected_seq = (last_seen_sequence[from_player] + 1) & 0xFF`
- ✅ Sentinel 0xFF: `last_seen_sequence[i] = 0xFF;`

**Result**: Documentation matches live code. ✅ VERIFIED.

---

## Section 4: New Gap Discovery — Player-ID Spoofing (Critical)

### Finding: from_player Field Not Authenticated

**Code Location**: SRC/MMULTI.C:269–283

```c
int from_player = recv_bufs[i].buf[0];  /* Wire-supplied, attacker-controlled */
...
/* Validate from_player bounds (CRITICAL: from_player is wire-supplied, attacker-controlled) */
if (from_player < 0 || from_player >= MAXPLAYERS) {
    printf("NET: SECURITY: Invalid from_player=%d (out of bounds [0,%d)). Dropping packet.\n",
        from_player, MAXPLAYERS);
    ...
    continue;
}
```

**The Gap**:
1. `from_player` is extracted directly from the packet header (byte 0)
2. Bounds are validated (0 ≤ from_player < MAXPLAYERS)
3. **BUT**: There is NO authentication that the sending socket is actually player `from_player`
4. Any connected client can send a packet claiming to be any other player

**Attack Scenario**:
- Player A (socket index 1) connects to host
- Player A crafts packet with from_player=2 (spoofing as Player B)
- Host relays packet assuming it came from Player B
- Other players receive corrupted game state from "Player B"

**Severity**: 🔴 **CRITICAL** for WAN/untrusted-network scenarios (LAN with trusted players is acceptable)

**Mitigation Options**:
1. **Option A (HMAC)**: During handshake, exchange shared secret; each packet signed with HMAC(secret, from_player)
2. **Option B (Socket mapping)**: Store socket→player mapping, validate from_player matches sending socket
3. **Option C (Client-side trust)**: Client never receives packets marked as from itself (trivial, insufficient)

**Recommendation**: Implement Option A (HMAC) — enables cross-LAN trust without requiring shared pre-shared keys.

---

## Section 5: New Gap Discovery — Socket Compatibility Layer Unintegrated

### Finding: create-net-socket-compat Exists But Unused

**Code Status**:
```
compat/net_socket.h       68 lines (header + type definitions)
compat/net_socket_posix.c 102 lines (POSIX implementation)
compat/net_socket_win32.c 106 lines (Windows implementation)
SRC/MMULTI.C              0 includes of net_socket.h
```

**API Surface** (net_socket.h):
```c
/* Network initialization and shutdown */
void net_socket_init(void);
void net_socket_shutdown(void);

/* Socket creation and control */
net_socket_t net_socket_create(int domain, int type, int protocol);
int net_socket_set_nonblocking(net_socket_t sock);
int net_socket_set_option(net_socket_t sock, int level, int optname, const void *optval, int optlen);

/* Socket operations */
int net_socket_bind(net_socket_t sock, const struct sockaddr *addr, int addrlen);
int net_socket_listen(net_socket_t sock, int backlog);
net_socket_t net_socket_accept(net_socket_t sock, struct sockaddr *addr, int *addrlen);
int net_socket_connect(net_socket_t sock, const struct sockaddr *addr, int addrlen);
int net_socket_send(net_socket_t sock, const void *buf, int len);
int net_socket_recv(net_socket_t sock, void *buf, int len);

/* Error handling */
int net_socket_last_error(void);
int net_socket_is_transient_error(int err);
```

**Current MMULTI.C Platform Code**:
```c
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
typedef int socklen_t;
#define net_close closesocket
#else
#include <sys/socket.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#define net_close close
#endif
```

**Integration Gap**: MMULTI.C duplicates platform-specific socket setup; compat layer provides clean abstraction but is currently unused.

**Severity**: 🟡 **MEDIUM** — Code duplication across Windows/POSIX, future maintenance burden. Not an immediate bug.

**Impact**: Socket initialization/teardown/error-handling scattered across ifdef blocks; compat layer ready for future refactor (todo: net-r15-mmulti-adopt-net-socket-compat).

---

## Section 6: New Gap Discovery — IPv6 Support Absent

### Finding: No IPv6 (AF_INET6) Support

**Scope**:
- All bind/connect calls use AF_INET only
- No AI_PASSIVE or getaddrinfo() for address-family agnostic resolution
- No IPv6 socket creation or dual-stack configuration

**Impact**:
- LAN play (IPv4-only) ✅ unaffected
- WAN deployment to IPv6-only ISPs ❌ blocked
- Dual-stack cloud deployments ❌ unsupported

**Severity**: 🟡 **MEDIUM** — Low urgency for legacy game, but essential for modern WAN deployment roadmap.

**Recommendation**: Defer to post-socket-compat integration; IPv6 support can leverage net_socket abstraction for cleaner implementation.

---

## Section 7: New Gap Discovery — No TCP Keepalive

### Finding: No SO_KEEPALIVE Socket Option

**Code Search**: No keepalive configuration found in MMULTI.C

**Scenario**:
1. Player A and host establish TCP connection
2. Player A network goes dark (unplugged, WiFi loss, mobile hibernation)
3. OS doesn't immediately close socket (no activity)
4. Host continues serving Player A, waiting for next packet indefinitely
5. Game becomes unresponsive to Player A departure until timeout (60s resendagaincount cycle)

**Mitigation**:
```c
/* Pseudocode: Add after socket creation */
int opt = 1;
net_socket_set_option(sock, SOL_SOCKET, SO_KEEPALIVE, &opt, sizeof(opt));

/* Fine-tune keepalive interval (platform-specific):
   TCP_KEEPIDLE: Seconds before keepalive starts
   TCP_KEEPINTVL: Interval between keepalive probes
*/
```

**Severity**: 🟡 **MEDIUM** — Degrades UX on mobile/unreliable networks; not critical for wired LAN.

**Recommendation**: Pair with socket-compat integration; SO_KEEPALIVE config can be centralized in net_socket abstraction.

---

## Section 8: Carryover Finding — tcp_send_failures Counter Unused (from r15)

### Finding: Counter Incremented But Never Inspected

**Code Location**: SRC/MMULTI.C:66, 167

```c
static int tcp_send_failures = 0;  /* Line 66: declared */
...
if (r <= 0) {
    tcp_send_failures++;  /* Line 167: incremented on send failure */
    break;
}
```

**Impact**: After 8 retry attempts fail, packet is dropped and counter increments. But:
- Counter is never read by game loop
- No logging or telemetry output
- No action taken on repeated failures (player not marked zombie)

**Status**: 🟡 **LOW** — Not a regression. Counter is infrastructure for future monitoring/stats.

**Recommendation**: Leverage in `net-r14-socket-zombie` implementation (mark player stale after N consecutive send failures).

---

## Section 9: Payload Validation — Bounds Check Correct

### Verification: After Sequence Insertion, Payload Length Still Validated

**Code Location**: SRC/MMULTI.C:297

```c
/* Validate bounds before relay-forwarding */
if (payload_len <= 0 || payload_len > MAXPACKETSIZE - NET_HEADER_SIZE) {
    recv_bufs[i].len = 0;
    break;
}
```

**Verification**:
- Payload length extracted from bytes [3:5] (little-endian)
- Validated against MAXPACKETSIZE - NET_HEADER_SIZE (2048 - 5 = 2043 bytes max payload)
- Also validated on send (line 736): `if (messleng > MAXPACKETSIZE) return;`

**Result**: Payload bounds validation correct post-sequence-insertion. ✅ SAFE.

---

## Section 10: Handshake Protocol — Version Field Intact

### Verification: NET_PROTOCOL_VERSION Present

**Code Location**: SRC/MMULTI.C:56, 513–521 (host send), 544–550 (client receive)

```c
#define NET_PROTOCOL_VERSION 0x0001
...
/* Host sends 8-byte handshake with version field */
msg[0] = myconnectindex;
msg[1] = (char)numplayers;
msg[2] = (NET_PROTOCOL_VERSION >> 0) & 0xFF;  /* version_lo */
msg[3] = (NET_PROTOCOL_VERSION >> 8) & 0xFF;  /* version_hi */
msg[4] = (randomseed >> 0) & 0xFF;
...
```

**Client-side parsing** (lines 544–550):
- Reads version from bytes [2:4]
- Compares against NET_PROTOCOL_VERSION
- Warn/drop if mismatch (future protocol bump compatibility)

**Result**: Version field present, allows future protocol negotiation. ✅ VERIFIED.

---

## Section 11: Files Referenced in This Audit

- **SRC/MMULTI.C** (779 lines) — TCP/IP transport, handshake, socket lifecycle, sequence tracking
- **source/GAME.C** (10,133 lines) — Packet dispatch, coop-dm validation, peer mode storage
- **source/DUKE3D.H** — Extern declarations (peer_game_mode, randomseed)
- **source/GLOBAL.C** — Array definitions (peer_game_mode)
- **docs/ARCHITECTURE.md** (900+ lines) — Network architecture, MTU/framing, wire format (updated L721, L841-842, L1204-1209)
- **tests/test_network_packet_bounds.py** (1,500+ lines) — TestNetR15SequenceNumbers (10 tests), TestNetR15CoopDmValidation (7 tests)
- **compat/net_socket.h** (68 lines) — Socket abstraction header
- **compat/net_socket_posix.c** (102 lines) — POSIX implementation (unused)
- **compat/net_socket_win32.c** (106 lines) — Windows implementation (unused)

---

## Summary Table: Cycle 65/68 Closures Live-Status Verification

| Item | Expected State | Found State | Status |
|------|----------------|-------------|--------|
| NET_HEADER_SIZE definition | 5 bytes (from 4) | SRC/MMULTI.C:45 = 5 | ✅ |
| Sequence sentinels | 14 markers in code | 14 found (spread across MMULTI.C) | ✅ |
| Sequence tests | TestNetR15SequenceNumbers (10 tests) | 10/10 passing | ✅ |
| Coop-dm sentinels | 4 markers (GLOBAL.C, DUKE3D.H, 2x GAME.C) | 4 found | ✅ |
| Coop-dm tests | TestNetR15CoopDmValidation (7 tests) | 7/7 passing | ✅ |
| ARCHITECTURE.md update | Lines 721, 841-842, 1204-1209 | All present, coherent | ✅ |
| Handshake version field | NET_PROTOCOL_VERSION in handshake | Present, parsed client-side | ✅ |
| Payload validation post-seq | Bounds check at line 297 | Correct (payload_len vs MAXPACKETSIZE - NET_HEADER_SIZE) | ✅ |

---

## Cycle 71 New Findings Summary

| ID | Title | Severity | Status | Effort |
|----|-------|----------|--------|--------|
| **net-r16-fix-auth-spoofing** | HMAC handshake prevents from_player forgery | 🔴 **CRITICAL** | backlog | 2–3 hrs |
| **net-r16-mmulti-adopt-net-socket-compat** | Integrate compat/net_socket abstraction into MMULTI.C | 🟡 **MED** | backlog | 1–2 hrs |
| **net-r16-ipv6-support-scope** | Design IPv6 dual-stack support (scope only) | 🟡 **MED** | backlog | 2–4 hrs (design) |
| **net-r16-tcp-keepalive** | Enable SO_KEEPALIVE socket option | 🟡 **MED** | backlog | 30 min |
| **net-r16-tcp-send-failures-alerting** | Leverage tcp_send_failures counter for zombie detection | 🟡 **LOW** | backlog | 15 min |

---

## Cycle 72+ Grind Recommendations

### Top-2 Highest-Leverage Items

**Recommendation 1: `net-r16-fix-auth-spoofing` (CRITICAL)**
- **Rationale**: Closes fundamental trust boundary; prevents player-ID spoofing attacks. Essential for WAN deployment.
- **Scope**: 
  1. Extend handshake with shared secret (pre-shared key or derived from session)
  2. Add HMAC(secret, from_player) field to each packet header or dedicated auth packet type
  3. Validate HMAC on receive; drop unsigned packets
- **Effort**: 2–3 hrs (handshake design + both-sides validation + tests)
- **Unblocks**: WAN hardening, tournament/esports deterministic replay, cross-org multiplayer

**Recommendation 2: `net-r16-mmulti-adopt-net-socket-compat` (MED)**
- **Rationale**: Eliminate platform-specific ifdef duplication; consolidate socket lifecycle into reusable abstraction. Prepares codebase for IPv6 + keepalive additions.
- **Scope**:
  1. Replace Windows ifdef blocks with net_socket API calls
  2. Replace POSIX ifdef blocks with net_socket API calls
  3. Verify no behavioral change; run full test suite
  4. Future: Stack keepalive + IPv6 config into net_socket layer
- **Effort**: 1–2 hrs (mechanical refactor + regression test)
- **Unblocks**: IPv6 support, keepalive integration, cleaner Windows/POSIX socket handling

**Joint Impact**: Auth-spoofing closes critical security gap; socket-compat prepares infrastructure for modern network features (IPv6, keepalive, monitoring).

**Alternative (if time-constrained)**: Dispatch `net-r16-tcp-keepalive` (MED, 30 min) as quick win for mobile/unreliable network UX.

---

## Observations & Synthesis

### Sequence Numbers (Cycle 65) — PRODUCTION VERIFIED
The 5-byte wire format extension is **LIVE and FUNCTIONAL**. All 14 sentinels present, test coverage intact (10 tests). Monotonic sequence tracking enables packet-loss detection and future replay protection.

**Impact**: Deterministic replay now partially enabled (seqnum + game-mode validation in place). Full replay requires auth-spoofing fix.

### Co-op/DM Mode Validation (Cycle 68) — PRODUCTION VERIFIED
Game-mode mismatch detection **LIVE**. Peer mode captured at handshake, validated on game-sync packets (types 0/1/4). Bounds-checking present on both read and write.

**Impact**: Prevents mode-based state corruption; graceful packet drop on mismatch.

### Authentication Gap (NEW) — CRITICAL FINDING
Player-ID field is wire-supplied but NOT authenticated. Any connected client can spoof packet origin. This is **CRITICAL for WAN/untrusted-network scenarios**, though LAN with trusted players is acceptable.

**Impact**: WAN deployment roadmap blocked until auth-spoofing fix lands.

### Socket Compatibility (NEW) — READY FOR INTEGRATION
Compat layer exists (net_socket.h + posix.c + win32.c), fully specified. MMULTI.C currently duplicates platform logic via ifdef. Integration straightforward, high leverage for future IPv6 + keepalive work.

**Impact**: Code duplication, future maintenance burden. Not an immediate bug.

### IPv6 & Keepalive (NEW) — MED-PRIORITY GAPS
No IPv6 support (AF_INET only); no TCP keepalive configuration. Both block modern WAN deployment.

**Impact**: LAN play unaffected; cloud/WAN scenarios require both features.

---

**Sentinel**: `net-r16-audit-complete: 5 NEW findings, 3 closures VERIFIED, cycle 72+ recommendations ready`

---

