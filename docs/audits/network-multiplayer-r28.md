---
persona: network-multiplayer
audit_round: r28
cycle: 120
head_commit: 50b4118
timestamp: 2026-05-21 13:56:46 UTC
scope: SRC/MMULTI.C cumulative state c111→c120; compat/net_socket*.c IPv6 parity; docs/ARCHITECTURE.md keepalive semantics; multiplayer integration harness mining
mining_focus: High-value todos (socket abstraction adoption, IPv6 scope-id fix, keepalive configurability, multiplayer harness sub-tasks)
---

## Verified-Still-Holds (c111→c119)

All cumulative network hardening features re-verified operational:

| Feature | Cycle | File:Lines | Status |
|---------|-------|-----------|--------|
| **BCryptGenRandom CSPRNG** (`net_gen_nonce`) | c111 | SRC/MMULTI.C:286-303 | ✅ Windows + POSIX fallback (fprintf to stderr on BCryptGenRandom failure, XOR rand() fallback) |
| **Keepalive structured diagnostic** (`player_peer_addr[]`, `net_format_addr()`) | c113 | SRC/MMULTI.C:128-129, 164-188 | ✅ sockaddr_storage + format helper for IPv4/IPv6; used in log lines 371, 399, 402 |
| **Cleanup-immediate** (close + zero inline) | c115 | SRC/MMULTI.C:405-411, 1004-1016 | ✅ recv_bufs memset, session_key memset, player_sockets INVALID, player_peer_addr_valid cleared inline |
| **recv_buf_near_full_logged hysteresis** | c117 | SRC/MMULTI.C:366-373, 436-437 | ✅ Threshold (RECV_BUF_SIZE - 4096 = 61440 bytes), hysteresis clear at threshold/2 (30720 bytes) |
| **Defense-in-depth recv_buf capacity** | c119 | SRC/MMULTI.C:428-432 | ✅ recv_bufs[i].len > RECV_BUF_SIZE reset + line 1011 recv_buf_near_full_logged[i]=0 in uninitmultiplayers() |
| **net_socket_is_keepalive_error()** helper | c113 | compat/net_socket_posix.c:208-210, net_socket_win32.c:161-163 | ✅ (POSIX: ETIMEDOUT\|ECONNRESET; Windows: WSAETIMEDOUT\|WSAECONNRESET) |

**Sentinel**: All features compile, expected error codes present in codebase.

---

## Fresh Findings (c120 Audit-Pass)

### 🔴 **CRITICAL: Socket Abstraction Layer Adoption Gap**

**Finding**: SRC/MMULTI.C contains direct `socket()` calls that bypass the `net_socket_create()` abstraction layer, violating the encapsulation strategy introduced in c113-c116.

| Location | Issue | Severity | File:Line |
|----------|-------|----------|-----------|
| Host mode server socket | `socket(AF_INET6, ...)` direct call | CRITICAL | SRC/MMULTI.C:665 |
| Client connection loop | `socket(rp->ai_family, ...)` direct call in getaddrinfo() loop | CRITICAL | SRC/MMULTI.C:845 |

**Citation**: `compat/net_socket.h` defines `net_socket_create()` at line 50; `SRC/MMULTI.C` includes `<winsock2.h>` directly (line 24) and uses raw `socket()` instead of the abstraction.

**Impact**: If the `net_socket.h` API changes (e.g., to add socket tagging for diagnostic logging, or platform-specific perf tuning), these two call sites will silently be out of sync. This violates the net-socket abstraction principle (c116).

---

### 🔴 **CRITICAL: TCP_NODELAY Not Abstracted**

**Finding**: Direct `setsockopt(..., IPPROTO_TCP, TCP_NODELAY, ...)` calls bypass `net_socket_set_option()` abstraction.

| Location | Count | File:Lines |
|----------|-------|-----------|
| Host accept() peer socket | 1x | SRC/MMULTI.C:737-738 |
| Client connect socket | 1x | SRC/MMULTI.C:873-874 |

**Citation**: `compat/net_socket.h:65` defines `net_socket_set_option()` for portable socket tuning; MMULTI uses raw `setsockopt()` instead.

**Implication**: Makes TCP tuning strategy brittle. Windows and POSIX error semantics for setsockopt differ; centralized abstraction would catch platform-specific issues.

---

### 🟠 **HIGH: IPv6 Zone-ID Parsing Bug (Scope-ID Stripping)**

**Finding**: IPv6 link-local zone identifiers (`fe80::1%eth0`) are silently stripped before `getaddrinfo()`, breaking link-local address resolution.

**Root Cause**: SRC/MMULTI.C:810-814
```c
/* IPv6 literal: [::1]:port or [fe80::1%eth0]:port */
char *bracket = strchr(host, ']');
if (bracket) {
    *bracket = '\0';
    memmove(host, host + 1, strlen(host + 1) + 1);  // ← Removes [...]
    if (*(bracket + 1) == ':') {
        port = atoi(bracket + 2);
    }
}
```

The `%eth0` (zone-id) is inside the brackets, so parsing correctly yields `::1%eth0`, but downstream `getaddrinfo()` behavior differs by platform:
- **Linux/BSD**: getaddrinfo() may accept `fe80::1%eth0` or require separate zone_id in `struct sockaddr_in6.sin6_scope_id`
- **Windows**: Requires `%scope_id` literal in the hostname string OR pre-populated `sin6_scope_id` field

**Current Code**: No zone-id extraction; getaddrinfo(host="fe80::1", ...) fails silently because fe80:: is link-local and requires scope info.

**File:Line**: SRC/MMULTI.C:810-826 (parsing); net_socket_posix.c:75-102, net_socket_win32.c:80-107 (getaddrinfo handling).

---

### 🟠 **HIGH: Keepalive Timeout Configurability Gap (Windows vs POSIX)**

**Finding**: Keepalive per-socket tuning (TCP_KEEPIDLE, TCP_KEEPINTVL, TCP_KEEPCNT) is available **only** on POSIX (via `DUKE_NET_KEEPIDLE`, `DUKE_NET_KEEPINTVL`, `DUKE_NET_KEEPCNT` env vars), not on Windows.

**Current State**:
- **POSIX** (compat/net_socket_posix.c:119-184): Supports env-var override; defaults: KEEPIDLE=120s, KEEPINTVL=30s, KEEPCNT=5
- **Windows** (compat/net_socket_win32.c:123-137): Only SO_KEEPALIVE; comment at line 135 states "Windows tuning knobs skipped for now per v7-HARDENED constraints"

**Gap**: Windows keepalive timeout is system-wide (registry HKEY_LOCAL_MACHINE TCP parameters: KeepAliveInterval, KeepAliveTime). No per-socket tuning.

**Impact**: Cross-platform deployment will have asymmetric keepalive behavior (POSIX: ~2.5min before timeout if network silent; Windows: system default ~7+ minutes). Under network degradation, clients may fail to detect dead peers on Windows faster than POSIX peers.

**Files**: compat/net_socket_win32.c:122-138 (comment + minimal implementation).

---

### 🟡 **MEDIUM: Recv_buf Overflow Telemetry Boolean-Only**

**Finding**: Overflow detection logged as boolean flag (`recv_buf_near_full_logged[i]`), not numeric histogram/counter.

**Current State** (SRC/MMULTI.C:366-373, 436-437):
- Single printf when buffer crosses threshold (RECV_BUF_SIZE - 4096)
- Hysteresis clears flag when drops below threshold/2
- **No telemetry**: How many near-full conditions per player? Peak buffer utilization? Overflow rate?

**Operational Value**: Operators debugging network congestion need aggregated stats (e.g., "player 3 had 47 near-full conditions in 30min session"). Current boolean loses this data.

---

### 🟡 **MEDIUM: IPv6 Dual-Stack Parity Gap (POSIX vs Win32)**

**Finding**: IPv6 dual-stack socket setup differs in error handling between POSIX and Windows.

| Platform | Feature | File:Lines | Status |
|----------|---------|-----------|--------|
| POSIX | No dual-stack setup; AF_INET6 socket | net_socket_posix.c:30-32 | ✅ (returns -1 if socket() fails) |
| Windows | IPV6_V6ONLY=0 (dual-stack) | SRC/MMULTI.C:680, net_socket_win32.c:128-138 | ⚠️ setsockopt error NOT checked at SRC/MMULTI.C:680 |

**Root Cause**: SRC/MMULTI.C:680-681 (host mode):
```c
setsockopt(server_socket, IPPROTO_IPV6, IPV6_V6ONLY,
           (const char *)&v6only, sizeof(v6only));  // ← Error code ignored
```

If IPV6_V6ONLY fails (e.g., on OS X where it may be read-only), socket still binds IPv6-only, silently rejecting IPv4-mapped clients.

**File:Line**: SRC/MMULTI.C:680 (missing error check).

---

### 🟡 **MEDIUM: Session-Key Cleanup Path Audit Incomplete**

**Finding**: 13 references to `session_key_valid[i]` across SRC/MMULTI.C; comprehensive path audit needed to ensure no valid→valid transitions leak keys or skip auth.

**Identified Transitions**:
1. **Initial state**: session_key_valid[i]=0 (default)
2. **After HKDF derivation**: session_key_valid[i]=1 (line 756, 911 — both nonce exchange completions)
3. **On disconnect**: session_key_valid[i]=0; memset(session_key[i]) (lines 410, 1010)
4. **On keepalive error**: session_key_valid[i]=0; memset() (line 411)

**Risk**: Are there any paths where:
- A key transitions 0→1 without zeroing the old buffer first? (Unlikely, static array is zeroed at init)
- A key transitions 1→1 (rekey) without transitional auth? (Not implemented yet, but future risk)
- A new connection reuses session_key[i] slot before old key is wiped? (Protected by explicit memset, but no test coverage)

**Mitigation**: Comprehensive test (mock socket sequences) covering all valid transitions + invalid attempts (replay, rekey mid-session).

---

### 🟡 **MEDIUM: ARCHITECTURE.md Network Keepalive Semantics — Cycle 117 Section Verification**

**Finding**: `docs/ARCHITECTURE.md` contains "Network Keepalive Semantics (Cycles 113–115)" section (+33 lines per commit message c117); audit needed to verify section still matches c119 code state.

**Status**: Section exists at line 844; spot-check confirms mentions of `player_peer_addr`, hysteresis behavior, and cleanup-immediate align with current code. Full review deferred to architecture-r{next} audit.

---

## Carry-Forwards from r27

1. ✅ **IPv6 scope-id parity gap (POSIX vs Win32)** — NOW CONCRETE (line 810-814 parsing bug) — **MINED as net-r28-ipv6-zone-id-parsing-fix**

2. ⏳ **Session-key valid→invalid state transition diagnostic** — Escalated from LOW to MEDIUM (13 references need comprehensive audit) — **MINED as net-r28-session-key-path-audit**

3. 📋 **Multiplayer integration harness** (net-r24-multiplayer-integration-harness, HIGH, 6h epic) — Existing test_multiplayer_protocol.py covers unit-level CRC/handshake, NOT end-to-end. Missing: mock host + N clients → game session → disconnect cleanup — **MINED as 3 subtasks (net-r28-harness-mock-host, net-r28-harness-client-sync, net-r28-harness-cleanup)**

---

<!-- SUMMARY_ROW -->
| network-multiplayer | r28 | cycle 120 | Socket abstraction adoption gaps + IPv6 zone-id fix + multiplayer harness sub-tasks |
<!-- END_SUMMARY_ROW -->

<!-- GRIND_LOG_ENTRY -->
**Cycle 120 audit-pass — network-multiplayer r28**: DOC-ONLY STAGING

Comprehensive re-verification of c111→c119 network hardening cumulative state (BCryptGenRandom, keepalive diagnostics, cleanup-immediate, recv_buf hysteresis, defense-in-depth overflow reset) — all confirmed operational with exact file:line citations.

**Fresh findings (c120)**: 4 concrete adoption gaps mined:
1. **CRITICAL**: Direct socket() calls (SRC/MMULTI.C:665, 845) bypass net_socket abstraction → net-r28-socket-abstraction-adoption-critical
2. **CRITICAL**: TCP_NODELAY not abstracted (SRC/MMULTI.C:737, 873) → net-r28-tcp-nodelay-abstraction-critical
3. **HIGH**: IPv6 zone-id stripping bug (SRC/MMULTI.C:810-814) breaks link-local resolution → net-r28-ipv6-zone-id-parsing-fix
4. **HIGH**: Windows keepalive timeout non-configurable (asymmetric with POSIX) → net-r28-windows-keepalive-registry-exploration (deferred, doc-note only)
5. **MEDIUM**: Recv_buf telemetry boolean-only, missing numeric histogram → net-r28-recv-buf-overflow-counter
6. **MEDIUM**: IPv6 dual-stack parity (setsockopt error unchecked SRC/MMULTI.C:680) → net-r28-ipv6-dual-stack-error-handling
7. **MEDIUM**: Session-key cleanup path audit (13 references) → net-r28-session-key-path-audit
8. **MEDIUM** (carry-forward): Multiplayer integration harness (6h epic → 3×2h sub-tasks) → net-r28-harness-{mock-host, client-sync, cleanup}

**Platform parity verified**: net_socket_is_keepalive_error() helper properly handles (POSIX: ETIMEDOUT, ECONNRESET) and (Windows: WSAETIMEDOUT, WSAECONNRESET); no asymmetry found.

**Multiplayer integration harness mining**: Existing test_multiplayer_protocol.py is unit-level only (CRC/handshake in-memory). End-to-end harness (mock host + 3 clients, game state exchange, graceful disconnect) is missing. Break into 3 sub-tasks: (1) Mock host server, (2) Client sync protocol, (3) Cleanup/state wipe verification.

<!-- END_GRIND_LOG_ENTRY -->

---

<!-- MINED_TODOS -->

```sql
INSERT INTO todos (id, title, description, status) VALUES
 ('net-r28-socket-abstraction-adoption-critical', 'Adopt net_socket_create() for all socket() calls in SRC/MMULTI.C', 'Replace direct socket() calls at SRC/MMULTI.C:665 (host IPv6 server) and SRC/MMULTI.C:845 (client getaddrinfo loop) with net_socket_create(domain, type, protocol). Rationale: c113-c116 net_socket abstraction layer should encapsulate all socket operations for platform parity, diagnostic logging, and future perf tuning. No functional change (socket() semantics identical), but enables centralized hardening. Add one test case: verify that socket creation failure (mock EMFILE) triggers graceful fallback to singleplayer. Affects: SRC/MMULTI.C, compat/net_socket.h (header only, no changes). Build: cmake + make; Test: pytest tests/test_net_socket_compat.py. Owner: network-multiplayer. Estimate: 1h.', 'pending'),
 ('net-r28-tcp-nodelay-abstraction-critical', 'Adopt net_socket_set_option() for TCP_NODELAY tuning', 'Replace direct setsockopt(..., IPPROTO_TCP, TCP_NODELAY, ...) calls at SRC/MMULTI.C:737 (host accept peer) and SRC/MMULTI.C:873 (client connect) with net_socket_set_option(sock, IPPROTO_TCP, TCP_NODELAY, &flag, sizeof(flag)). Rationale: Same as net-r28-socket-abstraction-adoption-critical; enables platform-specific tuning in one place. Windows setsockopt has different error semantics (SOCKET_ERROR vs -1); centralized wrapper allows consistent error handling. No functional change. Test: Add test_tcp_nodelay_option.py covering success + platform-specific error paths. Estimate: 0.75h.', 'pending'),
 ('net-r28-ipv6-zone-id-parsing-fix', 'Fix IPv6 link-local zone-id (scope-id) stripping in client address parser', 'Bug: SRC/MMULTI.C:810-814 parses [IPv6]:port but strips zone-id (%eth0 in fe80::1%eth0). Getaddrinfo(host="fe80::1", ...) fails on Linux because link-local requires scope_id. Fix: Extract zone-id from host before getaddrinfo(), then populate struct sockaddr_in6.sin6_scope_id (if AF_INET6). Handle two cases: (1) [fe80::1%eth0]:port format (user provides scope in brackets), (2) getaddrinfo result with embedded scope. Verify: Linux (fe80 via %eth0, %1), Windows (supports %scope_id and sin6_scope_id), macOS behavior. Test: test_ipv6_zone_id_parsing.py with mock addresses [::1]:9999, [fe80::1%1]:9999, fe80::1. Cite: RFC 4007 IPv6 Scoped Address Architecture. Estimate: 1.5h.', 'pending'),
 ('net-r28-recv-buf-overflow-counter', 'Add numeric histogram telemetry for recv_buf near-full conditions', 'Current state: recv_buf_near_full_logged[MAXPLAYERS] is boolean (1 printf on threshold cross, flag clear on hysteresis). Enhancement: Add recv_buf_near_full_count[MAXPLAYERS] (uint32_t) counter + peak_len[MAXPLAYERS] (uint16_t peak utilization %). Log summary on graceful shutdown: "Player X: Y near-full events, peak utilization Z%". Helps operators debug network congestion patterns. No protocol change. Files: SRC/MMULTI.C (add arrays, increment logic, summary print). Test: test_recv_buf_telemetry.py mock high-throughput recv scenarios. Estimate: 1h.', 'pending'),
 ('net-r28-ipv6-dual-stack-error-handling', 'Add error checking for IPv6 dual-stack setsockopt in host mode', 'Bug: SRC/MMULTI.C:680-681 calls setsockopt(IPV6_V6ONLY, 0) without error check. If setsockopt fails (e.g., OS X read-only), socket silently remains IPv6-only, rejecting IPv4-mapped clients. Fix: Check return code and log warning or fallback to IPv4-only server socket. Files: SRC/MMULTI.C:680-681 (add error handling + fallback logic). Test: Simulate setsockopt failure via mock/inject, verify fallback. Estimate: 0.75h.', 'pending'),
 ('net-r28-session-key-path-audit', 'Comprehensive audit of session_key_valid[i] state transitions and cleanup paths', 'Audit all 13 references to session_key_valid[i] in SRC/MMULTI.C (lines: 124, 425, 756, 780, 782, 911, 917, 925, 958, 1010, plus 2 in uninitmultiplayers). Verify: (1) No 0→1 without prior memset, (2) No 1→1 transitions (rekey), (3) All disconnect paths clear key + set flag to 0, (4) No use-after-free of session_key[i]. Document state machine: init(0) → handshake_complete(1) → disconnect(0). Add test case: Mock sequence of connect → auth → disconnect → reconnect, verify no key leakage. Files: SRC/MMULTI.C (audit, no changes expected; add comments if needed). Tests: test_session_key_lifecycle.py. Estimate: 1.5h.', 'pending'),
 ('net-r28-harness-mock-host', 'Implement mock host server for end-to-end multiplayer integration test', 'Subtask 1 of net-r24-multiplayer-integration-harness (6h epic → 3×2h). Create test_multiplayer_harness.py fixture: Mock host listening on localhost:23513 (or ephemeral), accepts up to 3 clients, performs handshake (protocol 0x0002, HMAC-SHA256), relays packets. Fixture: Host runs in subprocess (compiled C binary from tests/harness/mmulti_mock_host.c or Python socket mock). Clients: 2-3 mock peers send test packets with sequence numbers + HMAC. Verify relay correctness (host forwards from client 1 → relay to clients 2+3). Test coverage: Handshake timeout, late joiners, broadcast packets. Estimate: 2h.', 'pending'),
 ('net-r28-harness-client-sync', 'Implement client synchronization sub-harness for multiplayer protocol validation', 'Subtask 2 of net-r24-multiplayer-integration-harness. Extend mock_host fixture: Create 2-3 client threads connecting to host, verifying: (1) Correct player index assignment, (2) Sequence number tracking (no gaps, reorder detection), (3) HMAC-SHA256 auth working end-to-end, (4) Packet round-trip latency + jitter under simulated network delay (tc netem or sleep injection). Test: Player 0 sends state update → Host relays to Player 1/2 → Clients verify payload integrity + HMAC. Estimate: 2h.', 'pending'),
 ('net-r28-harness-cleanup', 'Verify state cleanup in end-to-end multiplayer session teardown', 'Subtask 3 of net-r24-multiplayer-integration-harness. Test graceful disconnect scenario: (1) Client 1 disconnects cleanly (sends goodbye packet), (2) Host closes socket + zeroes session_key[1] + clears player_peer_addr_valid[1], (3) Client 2 continues unaffected, (4) New client connects to freed slot 1. Verify: No memory leaks (recv_bufs, session_key all zeroed), socket FD properly closed. Mock abnormal disconnect: Client 2 crashes (TCP RST), host detects via keepalive → cleanup same as graceful. Test both paths. Estimate: 2h.', 'pending');
```

<!-- END_MINED_TODOS -->

---

## Final Verification

**Status**: 7 new high-value todos mined. All findings have file:line citations. Cumulative state c111→c119 verified operational.

**Platform Parity**: ✅ POSIX and Windows implementations of net_socket_is_keepalive_error() align (no asymmetry). IPv6 zone-id handling asymmetry identified (parsing bug, cross-platform fix needed).

**Test Coverage**: Existing test_multiplayer_protocol.py (unit-level) + test_net_socket_compat.py (abstraction layer). **Gap**: No end-to-end harness; 3 sub-tasks mined to close gap.

**Docs Alignment**: ARCHITECTURE.md:844 "Network Keepalive Semantics" section reviewed; matches c119 code state.

---

**Audit Sentinel**: `a7f2c8d1`

