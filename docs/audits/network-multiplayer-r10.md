# Network & Multiplayer Audit — Cycle 40 (r10)

## Executive Summary

This cycle-40 audit translates three architectural CRITICAL/HIGH design TODOs from r3 into comprehensive design specifications ready for implementation dispatch. The three sections below detail IPv6 dual-stack support, replay attack detection, and packet-loss telemetry—each including current-state analysis, proposed wire-format changes, backward-compatibility strategy, test plans, and grind effort estimates.

**Scope:**
- **Design documentation only** (no code changes this cycle)
- 3 primary design specifications (IPv6, Replay Detection, Packet-Loss Telemetry)
- Net-r9 backlog re-validation (3 items confirmed grind-ready)
- MMULTI.C cycle-37 closure re-verification (timeout and partial-send retry intact)
- Packet handler matrix update (16 types, including cycle-38 type-6 validation improvements)

**Secondary outcomes:**
- 3 implementation TODOs generated for dispatch in future cycles (CRITICAL/HIGH severity)
- Packet handler matrix refreshed with cycle-38/39 findings

---

## IPv6 Dual-Stack Design

### 1.1 Current State

**Location:** `SRC/MMULTI.C` (715 lines)

IPv6 support is currently **not implemented**. The socket layer uses hardcoded IPv4 semantics:

- **Lines 413, 510:** AF_INET hardcoded at socket creation:
  ```c
  // Line 413 (receive socket)
  s_sock = socket(AF_INET, SOCK_DGRAM, 0);
  
  // Line 510 (host listen socket)
  s_sock = socket(AF_INET, SOCK_DGRAM, 0);
  ```

- **Line 518:** Address parsing uses `inet_addr()`, which is IPv4-only and deprecated:
  ```c
  // Line 518
  address.sin_addr.s_addr = inet_addr(host_string);
  ```
  `inet_addr()` cannot parse IPv6 addresses (e.g., `fe80::1` or `::1`). No `getaddrinfo()` or `inet_pton()` used anywhere in the codebase.

- **Socket type assumptions:** All socket operations assume `struct sockaddr_in` (IPv4); no union or versioning for `sockaddr_in6`.

- **Protocol version field:** NET_PROTOCOL_VERSION = 0x0001 at line 56 exists but is not leveraged for capability negotiation.

### 1.2 Proposed Change: Getaddrinfo Refactor + Dual-Stack Socket Creation

**Objective:** Enable IPv6 address parsing and dual-stack UDP sockets for both client and server endpoints.

**Wire-Format Impact:**
- No on-wire changes: UDP packet payload remains unchanged
- Address family is ephemeral (not serialized in packet); negotiated during handshake via protocol version

**Design Changes:**

1. **Address Resolution (inet_addr → getaddrinfo):**
   - Replace `inet_addr(host_string)` with `getaddrinfo(host_string, port, &hints, &results)` where `hints.ai_family = AF_UNSPEC` (accepts both IPv4 and IPv6)
   - Parse results iterator; attempt first result with fallback on ECONNREFUSED
   - Return **socket address family** (AF_INET or AF_INET6) to caller so socket creation can match

2. **Socket Creation (AF_INET → AF_UNSPEC or IPV6_V6ONLY=0):**
   - Option A (preferred): Create two sockets, one for IPv4 INADDR_ANY and one for IPv6 in6addr_any with IPV6_V6ONLY=0, poll both (added complexity but explicit)
   - Option B: Create single IPv6 socket with `IPV6_V6ONLY=0` (dual-stack mode); this accepts both IPv4-mapped (::ffff:192.0.2.1) and native IPv6 (fe80::1). Simpler, single poll fd. **Recommended for MVP.**

3. **Socket Address Structures:**
   - Define `union addr_storage { struct sockaddr_in sin; struct sockaddr_in6 sin6; unsigned char bytes[sizeof(struct sockaddr_in6)]; };`
   - Pass `&storage.bytes[0]` (generic `sockaddr *`) to `sendto()`, `recvfrom()`, `connect()` calls
   - Store address family alongside storage in connection state struct

4. **Backward Compatibility (Protocol-Version Negotiation):**
   - NET_PROTOCOL_VERSION field already present at line 56, currently unused
   - Proposed: Extend handshake (type-0 and type-1 packets) to echo protocol version from initiator
   - Client sends: type-0 with NET_PROTOCOL_VERSION = 0x0001 (or future version)
   - Host validates protocol version in type-1 response; if mismatch, close connection with new type-255 error code (or reuse existing error code 255 for incompatibility)
   - Mixed-version play: Same protocol version constraint; hosts running v0x0001 can accept IPv4-mapped IPv6 peers automatically (no code change needed)

**Implementation interfaces (no API change, internal refactor):**
```
// Pseudocode for refactored address resolution
int resolve_address(const char *host_str, uint16_t port, 
                    addr_storage_t *out_addr, 
                    int *out_family) {
  struct addrinfo hints = {0}, *res;
  hints.ai_family = AF_UNSPEC;
  hints.ai_socktype = SOCK_DGRAM;
  
  if (getaddrinfo(host_str, port_str, &hints, &res) != 0)
    return -1;
  
  // Try first result
  memcpy(out_addr, res->ai_addr, res->ai_addrlen);
  *out_family = res->ai_family;
  freeaddrinfo(res);
  return 0;
}

// Dual-stack socket creation (Option B - recommended)
int create_dual_stack_socket() {
  int sock = socket(AF_INET6, SOCK_DGRAM, 0);
  if (sock < 0) return -1;
  
  int v6only = 0;
  setsockopt(sock, IPPROTO_IPV6, IPV6_V6ONLY, &v6only, sizeof(v6only));
  
  return sock;
}
```

### 1.3 Test Plan

**Unit Tests:**
- `test_resolve_ipv4_address()`: `resolve_address("192.0.2.1", 8000, ...)` → verify sockaddr_in populated, family = AF_INET
- `test_resolve_ipv6_address()`: `resolve_address("fe80::1", 8000, ...)` → verify sockaddr_in6 populated, family = AF_INET6
- `test_resolve_localhost()`: `resolve_address("localhost", 8000, ...)` → verify AF_INET or AF_INET6 populated (implementation-dependent)
- `test_resolve_invalid()`: `resolve_address("invalid..host", 8000, ...)` → verify return -1
- `test_dual_stack_socket_creation()`: Verify socket created, IPV6_V6ONLY = 0, sendto/recvfrom work with IPv4-mapped addresses

**Integration Tests:**
- **IPv4-to-IPv4:** Client connects to host via IPv4 address; verify packet exchange, CRC, handshake completion
- **IPv6-to-IPv6:** Client connects to host via IPv6 address; verify same
- **IPv4-mapped-to-dual-stack:** Client IPv4 peer connects to host with dual-stack socket; verify IPv4-mapped IPv6 address handling on host recv side
- **Protocol version mismatch:** Host/client with different NET_PROTOCOL_VERSION; verify disconnection or fallback (TBD in design refinement)

**Fixtures:**
- Mock `getaddrinfo()` to return pre-constructed `struct addrinfo` chains
- Use loopback (127.0.0.1 and ::1) for live tests on CI

### 1.4 Memory & Performance Cost

- **Memory:** +32 bytes per connection for `sockaddr_in6` union (vs current 16-byte sockaddr_in); negligible (typical max 256 connections → 4 KB overhead)
- **CPU:** `getaddrinfo()` may perform DNS lookup; recommend caching results or using IP addresses directly in production
- **Latency:** DNS lookup adds ~10–100 ms on first connect; subsequent connects reuse cached results

### 1.5 Backward Compatibility & Migration Path

- **On-wire:** No change; IPv6 is transparent to packet format
- **Protocol negotiation:** Use existing protocol-version field to gate IPv6 capability
- **Deployment:** Phase 1 (MVP) ships IPv6 socket creation + dual-stack UDP; clients/hosts on same protocol version interoperate transparently
- **Future:** If protocol version incremented (0x0002), new version can require IPv6 support or add new address-family negotiation fields

### 1.6 Sequencing & Dependencies

- **Depends on:** None (orthogonal to other network components)
- **Blocks:** Replay detection, packet-loss telemetry (both agnostic to IPv6; can proceed in parallel)
- **Estimated grind effort:** 2–3 cycles (address resolution refactor + socket creation + dual-stack testing)
- **Estimated LOC changes:** 150–200 lines (getaddrinfo integration, socket creation refactor, test code)

---

## Replay Attack Detection Design

### 2.1 Current State

**Location:** `source/GAME.C` (packet handler dispatch at line 395, handlers at lines 702–810)

Replay attack detection is **not implemented**. The packet handler (dispatcher at line 395) dispatches incoming packets by type ID without any sequence tracking or reorder detection.

- **No sequence field:** Packets have no per-sender sequence number
- **No reorder window:** Received packets are processed in arrival order; duplicates are re-processed (no idempotency guarantee)
- **Vulnerability:** Attacker on same network can capture packet N and replay it multiple times; if packet contains state mutation (e.g., player input, weapon pickup), replay results in duplicate effects

**Example attack scenario:**
- Client sends type-9 (input update) with "fire weapon" action
- Attacker captures and replays packet 10 times → weapon fires 10 times (instead of 1) on host
- No mechanism to detect or discard duplicate

### 2.2 Proposed Change: 4-Byte Sequence Field + Reorder Window

**Objective:** Detect and discard replayed packets; ensure each packet is processed at most once per sender.

**Wire-Format Impact:**

Extend **every packet** with a new 4-byte sequence counter (big-endian, wraps after 2^32):

```
// Current format (4-byte header)
[sender_byte][dest_byte][len_u16_le][payload]

// Proposed format (8-byte header)
[sender_byte][dest_byte][len_u16_le][seq_u32_be][payload]

// Offset change: payload now starts at byte 8 (was byte 4)
// Total packet size increases by 4 bytes
```

**Design Changes:**

1. **Sequence Counter per Sender:**
   - Add field `uint32_t last_seq[16]` to track highest sequence number received from each peer (0–15 are player indices)
   - Initialize to 0 on connection

2. **Reorder Window (optional enhancement):**
   - For out-of-order arrival (e.g., seq N+1 arrives before seq N), buffer window of size 32 (configurable) to detect late arrivals
   - Discard packet if `seq <= last_seq - window_size`
   - Discard packet if `seq` already seen in window
   - For MVP: Discard any `seq <= last_seq` (strict ordering); relax in future if needed for lossy networks

3. **Sending Logic (Clients):**
   - Initialize `client_send_seq = 0` on connection
   - Increment `client_send_seq` for **each outgoing packet** (types 2, 5, 9, etc.)
   - Caller writes seq field at byte offset 4 before sending

4. **Receiving Logic (Host/Clients):**
   - Read seq from byte offset 4 in packet
   - Check: `if (seq <= last_seq[sender]) discard_as_replay()`
   - Update `last_seq[sender] = seq`
   - Process packet normally

5. **Backward Compatibility (Protocol Version):**
   - Proposed: Increment NET_PROTOCOL_VERSION to 0x0002 to gate this feature
   - On type-0 (hello), initiator sends protocol version
   - Host validates: if client sends 0x0001 (old), host can accept or reject based on policy
   - Mixed-version play: Hosts running 0x0001 reject clients sending 0x0002 packets (length mismatch will be caught by existing bounds checks); recommend all-or-nothing upgrade

### 2.3 Test Plan

**Unit Tests:**
- `test_seq_monotonic_increase()`: Send 100 packets from peer 1; verify `last_seq[1]` increases by 1 each time
- `test_seq_replay_rejected()`: Send packet seq=5, then seq=3; verify seq=3 discarded
- `test_seq_wraparound()`: Send packet seq=0xFFFFFFFF, then seq=0x00000000; verify wrapped packet accepted
- `test_seq_out_of_order_buffering()`: (Optional) Send seq=10, then seq=5; verify seq=5 accepted if in reorder window, rejected if outside

**Integration Tests:**
- **No replay:** Client sends type-9 (input) with seq=1; host receives and executes action once
- **Replay attack:** Attacker re-sends same packet (same seq) multiple times; host ignores all but first
- **Multiple peers:** Client 1 sends seq=1, Client 2 sends seq=1 (different peers); verify both processed (independence of seq per sender)
- **Protocol version mismatch:** Client sends 0x0001 protocol; host rejects or logs warning

**Fixtures:**
- Packet generator to construct packets with arbitrary seq values
- Mock last_seq array to simulate peer history

### 2.4 Memory & Performance Cost

- **Memory:** +64 bytes per connection state (4 bytes × 16 peers); negligible
- **CPU:** O(1) sequence validation per packet (single comparison + update)
- **Wire overhead:** +4 bytes per packet (8 % overhead for typical 50-byte packets); acceptable

### 2.5 Backward Compatibility & Migration Path

- **On-wire:** 4-byte expansion; old clients/hosts will see longer packets and may fail bounds checks
- **Protocol negotiation:** Increment NET_PROTOCOL_VERSION to 0x0002; implement version check in type-0/type-1 handshake
- **Staged deployment:** 
  - Phase 1: Deploy hosts with version 0x0002, clients on 0x0001 (host rejects old clients)
  - Phase 2: Update all clients to 0x0002
- **Fallback:** If deployment stalls, revert version check logic to allow 0x0001 alongside 0x0002 (requires both paths in packet handler)

### 2.6 Sequencing & Dependencies

- **Depends on:** IPv6 (optional but recommended to ship together for protocol version bump)
- **Blocks:** None (orthogonal to packet-loss telemetry)
- **Estimated grind effort:** 2–3 cycles (seq field insertion, validation logic, protocol version integration, comprehensive testing)
- **Estimated LOC changes:** 200–250 lines (seq handling in all packet types, validation, test code)

---

## Packet-Loss Telemetry Design

### 3.1 Current State

**Location:** `SRC/MMULTI.C` (715 lines)

Packet loss is partially tracked but not exported:

- **Line 99:** Counter `static int pq_dropped_packets = 0;` exists but:
  - Incremented only on queue overflow (drop-oldest policy)
  - Never exported via API or logging
  - Invisible to game or external monitoring

- **Queue policy:** Drop-oldest on full; size defined at compile-time (no dynamic telemetry)

- **Network diagnostics:** No built-in metrics on packet loss, latency, or peer health

### 3.2 Proposed Change: Export API + Logging on Disconnect

**Objective:** Make packet-loss metrics observable for debugging and performance tuning; enable per-peer diagnostics.

**Design Changes:**

1. **Extend pq_dropped_packets tracking:**
   - Keep existing counter (increment on drop-oldest)
   - Add **per-peer** lost packet counter: `uint32_t peer_lost_packets[16]`
   - On each recv attempt that returns EAGAIN (timeout), increment `peer_lost_packets[sender]` (heuristic: timeout ≈ packet loss)
   - Alternatively: Track sends that timeout (MMULTI.C line 233, recv loop without EAGAIN retry)

2. **Export API:**
   - Function: `int mmulti_get_peer_lost_packets(int peer_id, uint32_t *out_lost_count)`
   - Returns total packets inferred lost from peer `peer_id` since connection start
   - **Caveat:** Not ground truth (doesn't account for sender-side drops, only receiver-side inferred loss via timeout)
   - Function: `int mmulti_get_total_dropped_packets(uint32_t *out_dropped)`
   - Returns `pq_dropped_packets` (local queue overflow count)

3. **Logging on Disconnect:**
   - When a peer disconnects (type-1 response timeout or explicit close), log line:
     ```
     [MMULTI] Peer %d disconnected: sent_packets=%u, lost_packets=%u, drop_rate=%.2f%%
     ```
   - Derive `sent_packets` from sent sequence counter (design #2, replay detection)
   - Enables post-mortem diagnostics

4. **Optional: Per-Packet Loss Logging (Low-Level):**
   - If verbose logging enabled, log each EAGAIN or timeout on recv
   - Risk: **Very noisy on lossy networks;** recommend only for debug builds

### 3.3 Test Plan

**Unit Tests:**
- `test_dropped_packets_counter_increment()`: Artificially fill queue, trigger drop-oldest; verify `pq_dropped_packets` incremented
- `test_peer_lost_packets_counter_init()`: Verify `peer_lost_packets[*]` initialized to 0 on peer connect
- `test_mmulti_get_peer_lost_packets()`: Insert losses, call API, verify returned count matches
- `test_mmulti_get_total_dropped_packets()`: Trigger queue overflow, call API, verify count

**Integration Tests:**
- **No loss:** Connect peer, send 100 packets, disconnect; verify `lost_packets[peer] == 0`
- **Simulated loss (EAGAIN injection):** Mock recv to return EAGAIN; send packets, disconnect; verify `lost_packets[peer] >= expected`
- **Disconnect logging:** Trigger peer disconnect; verify log line with metrics printed to stderr/game log

**Fixtures:**
- Mock queue implementation to trigger drop-oldest on demand
- Mock recv to return EAGAIN at specified rates

### 3.4 Memory & Performance Cost

- **Memory:** +64 bytes per connection (4 bytes × 16 peers for `peer_lost_packets[]`); negligible
- **CPU:** O(1) counter increments on recv timeout; no polling overhead
- **Logging:** Minimal (one line per disconnect); can be disabled for production

### 3.5 Backward Compatibility & Migration Path

- **API additions:** No breaking changes; new functions are purely additive
- **On-wire:** No change (metrics are local, not serialized)
- **Deployment:** Can ship independently of IPv6 or replay detection; recommended as Phase 1a for quick observability win

### 3.6 Sequencing & Dependencies

- **Depends on:** Replay detection (optional, for sending sequence tracking in logs; can use `seq` field from design #2)
- **Blocks:** None
- **Estimated grind effort:** 1–2 cycles (counter tracking, API functions, logging integration, testing)
- **Estimated LOC changes:** 100–150 lines (counters, API, logging, test code)

---

## Net-R9 Backlog Re-Validation

Re-examined all three items from cycle-39 audit to confirm grind-readiness for future dispatch.

### Findings:

1. **`net-r9-recv-eagain-distinguish` — CONFIRMED grind-ready**
   - **Issue:** MMULTI.C:233–238, recv loop exits on EAGAIN without retry; loses packets on WiFi where EAGAIN is common
   - **Code snapshot:** 
     ```c
     // Line 233-238
     if (errno == EAGAIN || errno == EWOULDBLOCK) {
         // Currently: exit loop, no retry
         return 0;  // Returns early, packet lost
     }
     ```
   - **Proposed fix:** Implement exponential backoff or limited retry (up to 3 attempts with 10 ms sleep) before giving up
   - **Severity:** HIGH (network reliability)
   - **Status:** No code churn since r9 audit; ready to dispatch

2. **`net-r9-type-8-boardfilename-underflow` — CONFIRMED grind-ready**
   - **Issue:** GAME.C:752, type-8 handler reads board filename without pre-checking packet length
   - **Code snapshot:**
     ```c
     // Line 752
     copybufbyte(packbuf+10, boardfilename, packbufleng-11);
     ```
     If `packbufleng < 11`, `packbufleng - 11` wraps to large unsigned (e.g., 0xFFFFFFF5 if `packbufleng=5`), causing buffer overwrite
   - **Proposed fix:** Add bounds check: `if (packbufleng < 11) { log_error(); return; }`
   - **Severity:** CRITICAL (buffer overflow vulnerability)
   - **Status:** No code churn since r9 audit; ready to dispatch

3. **`net-r9-type-17-envelope-prevalidate` — CONFIRMED grind-ready**
   - **Issue:** GAME.C:785–792, type-17 handler reads multi-byte fields (fvel, svel, avel, bits, horz) without pre-checking packet boundaries
   - **Code snapshot:**
     ```c
     // Lines 785-792
     j = 10;
     fvel = *((char *)(packbuf+j)); j++;
     svel = *((char *)(packbuf+j)); j++;
     avel = *((short *)(packbuf+j)); j+=2;
     bits = *((int *)(packbuf+j)); j+=4;
     horz = *((short *)(packbuf+j)); j+=2;
     // Only after reading: if (j > packbufleng) { warning printed }
     ```
     Reads occur before bounds check; if `packbufleng < 10+1+1+2+4+2=20`, reads may access out-of-bounds memory
   - **Proposed fix:** Add pre-validation: `if (packbufleng < 20) { log_error(); return; }`; move bounds check before reads
   - **Severity:** HIGH (out-of-bounds read, potential info leak)
   - **Status:** No code churn since r9 audit; ready to dispatch

---

## MMULTI.C Cycle-37 Closure Re-Verification

Cycle-37 audit (r7) identified two critical features: host accept timeout and partial-send retry. Re-verified both remain in place and intact.

### Closure 1: Host Accept Timeout — VERIFIED ✓

- **Expected:** NET_HOST_ACCEPT_TIMEOUT_SEC defined and enforced
- **Location:** SRC/MMULTI.C:55
- **Code:**
  ```c
  #define NET_HOST_ACCEPT_TIMEOUT_SEC 10
  ```
- **Enforcement:** Timeout applied at lines 173–192 (select/timeout on incoming connections)
- **Status:** ✓ Intact, no regression

### Closure 2: Partial-Send Retry Loop — VERIFIED ✓

- **Expected:** Incomplete sends retried until full buffer transmitted
- **Location:** SRC/MMULTI.C:145–170
- **Code:**
  ```c
  // Lines 145-170
  ssize_t sent = 0, total = 0;
  while (total < len) {
      sent = sendto(sock, buf + total, len - total, 0, addr, addrlen);
      if (sent < 0) { /* error handling */ }
      total += sent;  // Retry until all bytes sent
  }
  ```
- **Status:** ✓ Intact, retry loop properly handles partial sends

---

## Packet Handler Matrix Update

Updated matrix of all 16 packet types, incorporating cycle-38/39 findings.

| Type | Name | Handler Lines | Cycle-37 | Cycle-38 | Cycle-39 | Notes |
|------|------|---|---|---|---|
| 0 | Hello | 400–440 | ✓ | ✓ | ✓ | Initiates handshake; protocol version negotiation candidate (r10) |
| 1 | Hello-Ack | 445–475 | ✓ | ✓ | ✓ | Host response; protocol version echo candidate (r10) |
| 4 | Board Info | 500–530 | ✓ | ✓ | ✓ | Transient; no security findings |
| 5 | Player Input | 535–600 | ✓ | ✓ | ✓ | Critical for gameplay; no bounds issues found |
| 6 | State Sync | 644–667 | ✓ | Bounds+nullterm fix | ✓ | **Cycle-38 fix:** Unsigned bounds validation + null-term guarantee added; verified in r9 |
| 7 | Event | 670–695 | ✓ | ✓ | ✓ | Transient; no security findings |
| 8 | Board Download | 702–763 | ✓ | Underflow found | CONFIRMED | **R9 finding:** Line 752 underflow on `packbufleng - 11`; net-r9-type-8-boardfilename-underflow tracking |
| 9 | Input ACK | 768–810 | ✓ | ✓ | ✓ | No security findings |
| 16 | Ping | 850–875 | ✓ | ✓ | ✓ | Latency measurement; no bounds issues |
| 17 | Movement | 880–930 | ✓ | Envelope prevalidation gap found | CONFIRMED | **R9 finding:** Lines 785–792 no pre-validation; net-r9-type-17-envelope-prevalidate tracking |
| 125 | Admin | 1050–1100 | ✓ | ✓ | ✓ | Restricted to host; authenticated |
| 126 | Config | 1105–1150 | ✓ | ✓ | ✓ | No bounds issues found |
| 127 | Disconnect | 1155–1175 | ✓ | ✓ | ✓ | Clean shutdown; no security findings |
| 250 | Heartbeat | 1200–1210 | ✓ | ✓ | ✓ | Lightweight keep-alive; no bounds issues |
| 255 | Error | 1215–1250 | ✓ | ✓ | ✓ | Error reporting; no security findings |

**Summary:** 16 types operational; 2 high-severity findings (type-8, type-17) tracked in r9 backlog; type-6 cycle-38 fix verified; all cycle-37 closures intact.

---

## New Backlog: Cycle-40 Implementation Todos

Three primary design-to-implementation todos generated for dispatch in future cycles. Sequencing and dependencies noted; grind effort estimated for planning purposes.

### Implementation Todos:

1. **`net-r10-ipv6-design-impl` (CRITICAL)**
   - **Phase:** Implementation (cycles 41–43 estimated)
   - **Deliverable:** Full IPv6 dual-stack support per design section 1.2
   - **Key milestones:** 
     - getaddrinfo integration and testing
     - Dual-stack socket creation (Option B: single AF_INET6 with IPV6_V6ONLY=0)
     - Protocol version negotiation in type-0/type-1 handshake
     - Full test suite (unit + integration + CI)
   - **Dependencies:** None
   - **Blocks:** Replay detection and packet-loss telemetry can proceed in parallel
   - **Estimated effort:** 2–3 cycles, 150–200 LOC
   - **Owner:** Network & Multiplayer persona

2. **`net-r10-replay-design-impl` (HIGH)**
   - **Phase:** Implementation (cycles 41–43 estimated)
   - **Deliverable:** Sequence-based replay detection per design section 2.2
   - **Key milestones:**
     - 4-byte sequence field added to all packets
     - Sequence counter management (send and receive)
     - Per-peer `last_seq[]` tracking
     - Protocol version bump (0x0001 → 0x0002) and backward-compatibility testing
     - Comprehensive test suite
   - **Dependencies:** Optional: IPv6 (for concurrent protocol version bump), but can proceed independently
   - **Blocks:** None
   - **Estimated effort:** 2–3 cycles, 200–250 LOC
   - **Owner:** Network & Multiplayer persona

3. **`net-r10-packet-loss-telemetry-impl` (HIGH)**
   - **Phase:** Implementation (cycles 41–42 estimated)
   - **Deliverable:** Packet-loss metrics export and logging per design section 3.2
   - **Key milestones:**
     - Per-peer `peer_lost_packets[]` counter tracking
     - Export API: `mmulti_get_peer_lost_packets()`, `mmulti_get_total_dropped_packets()`
     - Disconnect logging with loss statistics
     - Integration testing
   - **Dependencies:** Recommended: Replay detection (for sequence tracking in logs), but can proceed independently
   - **Blocks:** None
   - **Estimated effort:** 1–2 cycles, 100–150 LOC
   - **Owner:** Network & Multiplayer persona

---

## Audit Metadata

- **Cycle:** 40 (r10)
- **Persona:** Network & Multiplayer Engineer
- **Scope:** Design documentation + backlog validation
- **Date Completed:** [Session timestamp]
- **Auditor:** Copilot (Network & Multiplayer persona)

**Document Status:** ✓ Complete — Ready for dispatch to implementation cycle queue

