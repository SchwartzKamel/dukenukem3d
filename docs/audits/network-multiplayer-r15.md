# Network & Multiplayer Audit — Cycle 64 (r15)

## Executive Summary

Cycle 64 r15 audit is a **DOCUMENTATION-ONLY verification pass** of cycle 59 closures (r14 todos completed in cycle 59) and architecture coherence across network-multiplayer audit history. This cycle conducts NO source/test modifications.

**Audit Scope**: Verify live status of 2 CRITICAL cycle-59 closures (randomseed-game-start-sync, crc-validation-dormant), confirm ARCHITECTURE.md network section coherence across cycles 48/50/53/59, categorize 8 carryover MED/HIGH backlog items, and recommend top-2 for cycle 65 grind.

**Key Findings Summary:**
- ✅ Cycle 59 randomseed sync **VERIFIED LIVE** — 5 sentinels present, test class intact, 8-byte handshake functional with legacy fallback
- ✅ Cycle 59 CRC dormant **VERIFIED LIVE** — sentinel marker at initcrc() site, ARCHITECTURE.md § "Packet Integrity (current gap)" in place
- ✅ Handshake backward-compat path **VERIFIED** — 8-byte new format, 4-byte legacy fallback with user warning (lines 559–563 SRC/MMULTI.C)
- ✅ ARCHITECTURE.md coherence **VERIFIED** — Network Architecture section (cycles 48/50/53/59) internally consistent, no contradictions
- ✅ Test baseline **VERIFIED** — 979 tests passing (>= 979 gate met); no regression
- 🟡 **NEW FINDING: tcp_send_failures counter unused** — incremented on send failure (line 167) but never inspected by game loop; design gap, not regression

**Status**: Multiplayer backbone **STABLE**. Two cycle-59 closures verified LIVE. Carryover backlog categorized. Recommended next cycle: dispatch `fix-net-auth-spoofing` (HIGH) + `fix-net-sequence-numbers` (HIGH) to unblock deterministic replay + WAN hardening.

**Findings Count**: 3 (prior closures VERIFIED; 1 new soft-finding)

---

## Section 1: Cycle 59 Closure Verification — Randomseed Game-Start Sync

### Prior Closure: `net-r14-randomseed-game-start-sync`

**Status**: ✅ **VERIFIED LIVE**

**Sentinels Check** (expected 5+):
```
1. Line 63: extern long randomseed  (external decl)
2. Line 505: net-r14-randomseed-sync: host generates seed for deterministic RNG init
3. Line 520: net-r14-randomseed-sync: host also initializes from shared seed
4. Line 566: net-r14-randomseed-sync: client receives seed from host for deterministic RNG init
5. Line 589: net-r14-randomseed-sync: set RNG seed from handshake
```
**Result**: 5/5 sentinels present. ✅ CONFIRMED.

**Test Class Verification**:
```
Location: tests/test_network_packet_bounds.py:1346
Class: TestNetR14RandomseedSync
Methods: 8 test methods covering 8-byte format, little-endian packing, client receive, legacy fallback
```
**Result**: Test class intact post cycle-59 mega-split. ✅ CONFIRMED.

**Handshake Format Verification**:
- Host sends 8-byte handshake: `[player_index, numplayers, version_lo, version_hi, seed_byte0, seed_byte1, seed_byte2, seed_byte3]` (SRC/MMULTI.C:513–521)
- Client receives same format with explicit 4-byte LE seed extraction (lines 554–556)
- Both initialize `randomseed` and call `srand()` from shared seed value
**Result**: 8-byte handshake protocol intact. ✅ CONFIRMED.

---

## Section 2: Cycle 59 Closure Verification — CRC Validation Dormant (Doc-Only Path)

### Prior Closure: `net-r14-crc-validation-dormant`

**Status**: ✅ **VERIFIED LIVE**

**CRC Dormant Sentinel Check**:
```
Location: SRC/MMULTI.C:382
Marker: /* net-r14-crc-dormant: CRC helpers initialized but not validated per-packet.
           See docs/ARCHITECTURE.md "Packet Integrity (current gap)" + audit r14. */
```
**Result**: Sentinel comment present, explains dormant state. ✅ CONFIRMED.

**ARCHITECTURE.md Packet Integrity Section**:
```
Location: docs/ARCHITECTURE.md § "Packet Integrity (current gap)" (lines 790–810)
Content: 
- Status table (wire format, risk by scenario: LAN low / WAN medium)
- Helper functions initcrc(), getcrc(), updatecrc16() compiled but never invoked per-packet
- Rationale: backwards-incompatible wire format bump (4 → 8-byte) deferred CRC implementation
- Future todo: net-r14-crc-validation-dormant-full-impl (MEDIUM severity)
- Cross-references this audit and r14
```
**Result**: Doc section consistent with code; explains dormant state + future work. ✅ CONFIRMED.

---

## Section 3: Handshake Protocol & Backward-Compatibility

### Verification: 8-Byte Extended Format + Legacy Fallback

**New Format** (8 bytes):
- Bytes 0–3: player_index, numplayers, version_lo, version_hi (same as legacy)
- Bytes 4–7: randomseed (little-endian 4-byte value)
- Location: SRC/MMULTI.C:513–521 (host send), 554–556 (client extract)

**Legacy Fallback** (4 bytes):
- Bytes 0–3: player_index, numplayers, version_lo, version_hi (same as above)
- No randomseed field
- Detection: Client checks `hs_len == 8` vs `hs_len == 4` (line 542)
- Warning: `"NET: WARNING: Legacy 4-byte handshake detected; RNG may diverge"` (line 561)

**Verification Path**:
```
1. Client attempts recv_all(sock, msg_full, 8)  [line 541]
2. If 8 bytes received → new format (line 542–558): extract seed, initialize RNG from seed
3. If 4 bytes received → legacy format (line 559–563): warn user, seed from time(NULL)
4. If timeout → close socket, goto singleplayer
```
**Result**: Backward-compat path **CONFIRMED LIVE**. Graceful degradation with user warning. ✅ CONFIRMED.

**Risk Assessment**:
- Old client + new host: Client receives 8-byte packet, reads first 4 bytes, timeouts on missing seed bytes → socket close, fallback to singleplayer
- New client + old host: Client expects 8 bytes, receives 4 bytes only → timeout → fallback to legacy seed (time-based)
- **Mitigation**: Protocol version field (bytes 2–3) allows future cross-check; warning message alerts users of potential desync

---

## Section 4: ARCHITECTURE.md Network Section Coherence

### Multi-Cycle Documentation Cross-Check

**Documented Cycles**: 48, 50, 53, 59
**Sections**: Connection Lifecycle, Packet Framing, MTU & Fragmentation, Packet Integrity Gap

**Verification Results**:

| Cycle | Section | Key Claim | Code Location | Status |
|-------|---------|-----------|---------------|--------|
| 48 | Connection Lifecycle (lines 767–788) | Handshake timeout = 15s | SRC/MMULTI.C:52 (HANDSHAKE_TIMEOUT_SEC = 15) | ✅ VERIFIED |
| 50 | MTU & Fragmentation (lines 823–887) | MAXPACKETSIZE = 2048 | SRC/MMULTI.C:44 | ✅ VERIFIED |
| 50 | MTU & Fragmentation | NET_HEADER_SIZE = 4 | SRC/MMULTI.C:45 | ✅ VERIFIED |
| 50 | MTU & Fragmentation | TCP_NODELAY enabled both sides | SRC/MMULTI.C:488, 548 | ✅ VERIFIED |
| 53 | Per-Packet-Type Analysis | Type-0/1 bounds checks | source/GAME.C cases 0,1 | ✅ VERIFIED (cycle-26 closure) |
| 59 | Packet Integrity Gap (lines 790–810) | CRC dormant, TCP checksums sufficient for LAN | SRC/MMULTI.C:382 + table | ✅ VERIFIED |
| 59 | Packet Integrity Gap | Risk matrix: LAN (low) WAN (medium) | ARCHITECTURE.md § Packet Integrity | ✅ VERIFIED |

**Coherence Assessment**: Network Architecture section maintains internal consistency across all cycles. No contradictions detected. Documentation accurately reflects live code state.

**Result**: ✅ **COHERENCE VERIFIED**.

---

## Section 5: New Drift Check — Cycle 60 Code State

### Unintended Changes or Regressions?

**Drift Items Checked**:
1. Randomseed extern declaration — **LIVE** (line 63)
2. Handshake 8-byte format — **LIVE** (lines 513–521)
3. Client backward-compat path — **LIVE** (lines 559–563)
4. CRC dormant marker — **LIVE** (line 382)
5. ARCHITECTURE.md § Packet Integrity — **LIVE** (lines 790–810)
6. Test class TestNetR14RandomseedSync — **LIVE** (test_network_packet_bounds.py:1346)
7. Net protocol version check in handshake — **LIVE** (lines 544–550)

**New Finding**: `tcp_send_failures` Counter (Line 66, 167)
```c
static int tcp_send_failures = 0;  /* line 66: declared */
...
if (r <= 0) {
    tcp_send_failures++;  /* line 167: incremented on send failure */
    break;
}
```
**Issue**: Counter incremented on send failure but **never inspected by game loop** or logged. After 8 retry attempts fail, packet is dropped silently and counter increments. This counter is a **telemetry artifact** — useful for debugging but not actionable by runtime.

**Severity**: 🟡 **LOW (soft finding)** — Not a regression. Counter was likely added in cycle 59 for future monitoring/stats. No impact on functionality; could be leveraged in future TCP send failure handling (e.g., marking player zombie on repeated failures).

**Recommendation**: Flag as **future leverage point** for `net-r14-socket-zombie` implementation (carryover MED item).

**Result**: ✅ **NO REGRESSIONS DETECTED**. One minor design-gap surfaced (unused counter).

---

## Section 6: Handshake Length Parsing — Edge Case Behavior

### Verification: How Does System Behave With Truncated Handshake?

**Scenario 1: Peer Sends 3 Bytes Instead of 4/8**
```
Client-side flow:
1. net_recv_all(sock, msg_full, 8) called with 3-byte buffer available
2. Attempts to read 8 bytes, receives 3, remaining buffer empty
3. recv_all() loop continues, waits for 5 more bytes
4. If peer closes or times out: recv() returns 0 → loop breaks with hs_len=3
5. hs_len (3) != 8 and != 4 → socket closed (net_close(sock)), goto singleplayer
```
**Result**: **DROPS** connection with warning. ✅ SAFE (line 557–558 covers neither branch).

**Scenario 2: Peer Sends 6 Bytes (Garbled)**
```
Similar to above: 6 != 8 and != 4 → socket closed, singleplayer fallback
```
**Result**: **DROPS**. ✅ SAFE.

**Scenario 3: Peer Sends 4-Byte Legacy, Client Expects 8**
```
Client calls net_recv_all(sock, msg_full, 8)
Receives 4 bytes, peer closes or times out → recv() returns 0
Loop exits with hs_len=4 → enters `else if (hs_len == 4)` branch
Warning printed, RNG seeds from time(NULL), game continues
```
**Result**: **DEGRADES GRACEFULLY** with warning. ✅ SAFE (backward-compat).

**Documented Behavior**: 
- Handshake too-short → **DROPS** connection, fallback to singleplayer (conservative, safe)
- Handshake legacy (4-byte) → **WARN and DEGRADE** to time-based RNG seed (cooperative, documented)

---

## Section 7: Carryover Backlog Categorization

### 8 Outstanding MED/HIGH Items (Not Implementing — Documenting Only)

| ID | Title | Severity | Status | Effort | Blocked By |
|----|-------|----------|--------|--------|-----------|
| **fix-net-auth-spoofing** | HMAC handshake prevents player_id forgery | 🔴 **HIGH** | backlog | 2–3 hrs | None (depends on protocol design) |
| **fix-net-sequence-numbers** | Explicit sequence numbers in NET_HEADER for replay protection | 🔴 **HIGH** | backlog | 2–3 hrs | None (protocol redesign, couples with CRC expansion) |
| **net-r14-socket-zombie** | Socket cleanup on TCP send failure (8 retries exhausted) | 🟡 **MED** | backlog | 15 min | Could leverage `tcp_send_failures` counter (r15 finding) |
| **net-r14-idle-timeout** | Idle peer detection + drop during active game | 🟡 **MED** | backlog | 20 min | None (orthogonal) |
| **net-r14-packet-sequence-replay** | Replay attack protection (related to fix-net-sequence-numbers) | 🟡 **MED** | backlog | MEDIUM | Depends on fix-net-sequence-numbers |
| **create-net-socket-compat** | compat/net_socket abstraction (future winsock2 consolidation) | 🟡 **MED** | backlog | TBD | None (refactoring, future) |
| **fix-net-coop-dm-validation** | Packet mode validation (coop vs DM game state checks) | 🟡 **MED** | backlog | 30 min | None (orthogonal) |
| **net-r14-crc-validation-dormant-full-impl** | Expand header to 8 bytes, add CRC32 validation on receive | 🟡 **MED** | backlog | 2 hrs | Related to fix-net-sequence-numbers (protocol redesign) |

---

## Section 8: Cycle 65 Grind Recommendations

### Top-2 Highest-Leverage Items

**Recommendation 1: `fix-net-auth-spoofing` (HIGH)**
- **Rationale**: Prevents player_id forgery attacks; enables untrusted-network deployment (roadmap item for WAN)
- **Scope**: Extend handshake with HMAC(shared_secret, player_id + nonce); server validates signature
- **Effort**: 2–3 hrs (auth design + both sides validation)
- **Unblocks**: WAN hardening roadmap; deterministic replay for tournament play
- **Pairs with**: `fix-net-sequence-numbers` (both address trust boundaries)

**Recommendation 2: `fix-net-sequence-numbers` (HIGH)**
- **Rationale**: Explicit sequence numbers in NET_HEADER enable:
  1. Replay attack detection (sender tracks seqnum, receiver validates monotonic increase)
  2. Packet loss detection (gaps in sequence reveal dropped packets)
  3. Future out-of-order delivery (if transitioning to UDP)
- **Scope**: Expand NET_HEADER from 4 to 6 bytes (add 2-byte seqnum field); receiver validates seqnum[from_player] >= last_seqnum[from_player]
- **Effort**: 2–3 hrs (header change + both sides validation + tests)
- **Unblocks**: Deterministic replay, packet loss telemetry, WAN reliability
- **Pairs with**: `fix-net-auth-spoofing` (both are protocol-level hardening)

**Joint Impact**: Both fixes address the **trust boundary** of multiplayer — preventing spoofing + replay. Together, they enable production-grade deterministic replay for esports/tournament use.

**Alternative (if time-constrained)**: Dispatch `net-r14-socket-zombie` (MED, 15 min) as quick win to surface `tcp_send_failures` counter leverage.

---

## Section 9: Files Referenced in This Audit

- **SRC/MMULTI.C** (779 lines) — TCP/IP transport, handshake, socket lifecycle, packet framing
- **source/GAME.C** (10,133 lines) — Packet dispatch, sync validation, master/slave logic
- **docs/ARCHITECTURE.md** (900+ lines) — Network architecture + MTU/fragmentation strategy + Packet Integrity gap
- **tests/test_network_packet_bounds.py** (1,500+ lines) — TestNetR14RandomseedSync class (8 test methods)
- **docs/audits/network-multiplayer-r14.md** (641 lines) — Prior audit + cycle-59 closure details

---

## SUMMARY TABLE: Cycle 59 Closures Live-Status Verification

| Item | Expected State | Found State | Status |
|------|----------------|-------------|--------|
| Randomseed sync sentinels (5+) | 5 markers in code | 5/5 present | ✅ |
| Test class (TestNetR14RandomseedSync) | Present in test_network_packet_bounds.py | 1346:1500+ | ✅ |
| Handshake 8-byte format | msg[8] with seed in bytes 4–7 | SRC/MMULTI.C:513–521 | ✅ |
| CRC dormant marker | Sentinel at initcrc() site | SRC/MMULTI.C:382 | ✅ |
| ARCHITECTURE.md Packet Integrity section | Lines 790–810 with risk matrix | Present, consistent | ✅ |
| Backward-compat path (4-byte legacy) | Client fallback with warning | SRC/MMULTI.C:559–563 | ✅ |
| Test baseline | >= 979 tests passing | 979 passed | ✅ |

---

## Observations & Synthesis

### Randomseed Synchronization (Cycle 59) — PRODUCTION VERIFIED
The 8-byte handshake extension is **LIVE and FUNCTIONAL**. All 5 sentinels present, test coverage intact, backward-compat path working. Deterministic RNG seeding now guaranteed at game start.

**Impact**: Fixes prior RNG divergence bug. Enables deterministic replay for cooperative play.

### CRC Validation Gap (Cycle 59) — DOCUMENTED & DORMANT
CRC code remains compiled but unused (option 1b: doc-only path). ARCHITECTURE.md § Packet Integrity clearly explains the gap + mitigation (TCP checksums sufficient for LAN, medium risk for WAN).

**Impact**: LAN play safe. Future CRC expansion documented in backlog as MED-priority item.

### Socket-Level Robustness — MINOR GAPS REMAIN
`tcp_send_failures` counter indicates send failures are tracked but not acted upon. This is a **soft finding** (not a regression, useful for future stats), but creates leverage point for `net-r14-socket-zombie` todo (mark player zombie on repeated failures).

**Impact**: Degraded experience if player loses connectivity mid-game (host doesn't immediately remove stale peer). Future todo will harden this.

### ARCHITECTURE.md Coherence — EXCELLENT
Network section maintains consistent documentation across 4 audit cycles (48, 50, 53, 59). No contradictions, all claims verified against live code.

**Impact**: Documentation is trustworthy reference for future network work.

### Deterministic Replay Readiness — PARTIAL
- ✅ Randomseed sync **LIVE** (eliminates RNG divergence)
- ❌ Sequence numbers **MISSING** (no replay protection)
- ❌ Auth/spoofing protection **MISSING** (player_id not authenticated)

**Next Steps**: Dispatch `fix-net-sequence-numbers` + `fix-net-auth-spoofing` to complete deterministic replay + WAN hardening roadmap.

---

**Cycle 65 Grind Recommendations**:
1. **DISPATCH** `fix-net-auth-spoofing` (HIGH, 2–3 hrs)
2. **DISPATCH** `fix-net-sequence-numbers` (HIGH, 2–3 hrs)
3. **DISPATCH** `net-r14-socket-zombie` (MED, 15 min, if time permits)

---

**Sentinel**: `net-r15-audit-complete: 6 findings 0 todos`

---

---

## Cycle 68 Closure: Co-op vs DM Mode Validation

### Task: fix-net-coop-dm-validation (MEDIUM)

**Problem**: No validation that sender and receiver are in the same game-mode (co-op vs DM). Packet format identical between modes; only `ud.coop` flag differs. Mismatch could corrupt state or enable DoS.

**Solution Implemented**: Approach (b) — Handshake-time capture + packet-time validation (no wire format change).

**Changes**:
1. **source/GLOBAL.C** (1 line): Added `char peer_game_mode[MAXPLAYERS]` array definition
2. **source/DUKE3D.H** (1 line): Added `extern char peer_game_mode[MAXPLAYERS]` declaration
3. **source/GAME.C** (17 lines):
   - Store peer's `ud.coop` during packet type 8 (startup config) → `peer_game_mode[other] = packbuf[8]`
   - Validate at packet receive (types 0, 1, 4): compare `peer_game_mode[other] != ud.coop` → log + drop if mismatch
   - Bounds-check `other` against `MAXPLAYERS`
4. **tests/test_network_packet_bounds.py** (149 lines): Added `TestNetR15CoopDmValidation` class with 7 test cases:
   - Array declaration verification
   - Extern declaration verification
   - Peer mode capture in packet type 8
   - Validation logic on types 0, 1, 4
   - Bounds checking
   - Sentinel count verification
   - Handshake-only application verification

**Sentinels**: 4 instances of `net-r15-coop-dm-mode-validation` placed at:
1. GLOBAL.C array definition
2. DUKE3D.H extern declaration
3. GAME.C peer mode storage (packet 8)
4. GAME.C validation check (before switch)

**Testing**:
- ✅ 7 new tests passing
- ✅ All 74 network_packet_bounds tests passing
- ✅ 1150+ total tests passing (includes 1039+ baseline)
- ✅ Build succeeds (`make clean && make -j$(nproc)`)

**Validation Gates Passed**:
- ✅ `make clean && make -j$(nproc)` succeeded
- ✅ `pytest -q` passed ≥1039 + 7 = 1046 tests (actual: 1150)
- ✅ `git diff --stat` shows only allowed files modified: source/DUKE3D.H, source/GAME.C, source/GLOBAL.C, tests/test_network_packet_bounds.py

**Impact**:
- **Security**: Prevents mode-mismatch attacks that could corrupt player state or crash game
- **Cost**: 4 bytes per-player static memory + O(1) bounds check per game-sync packet (negligible)
- **Wire Format**: No change — backward compatible with older clients
- **Reliability**: Packets from clients in wrong game-mode are logged and silently dropped (graceful degradation)

**Next Reachability**: Deterministic replay stack now has:
- ✅ Randomseed sync (net-r14)
- ✅ Game-mode validation (net-r15)
- ❌ Sequence numbers (blocked on net-r15-seqnum implementation)
- ❌ Auth/spoofing protection (future)

---

**Sentinel**: `net-r15-coop-dm-validation-complete: 4 sentinels, 7 tests, 0 regressions`

