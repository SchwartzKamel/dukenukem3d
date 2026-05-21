---
cycle: 96
persona: network-multiplayer
audit_type: triage
scope: IPv6 link-local scope_id validation
reference_todo: net-r20-ipv6-scope-triage
sentinel: pending
---

# IPv6 Link-Local Scope ID Triage — Cycle 96

**Persona**: network-multiplayer (Distributed Systems Engineer)  
**Advisory Type**: Prioritization assessment (WAN vs LAN impact)  
**Audit Date**: Cycle 96 onwards  
**Key Question**: Is IPv6 link-local fe80::/10 scope_id handling a WAN blocker or LAN edge case?

---

## Executive Summary

**Current State**: IPv6 dual-stack multiplayer is **FUNCTIONAL** (AF_INET6 + IPV6_V6ONLY=0) but **scope_id for link-local addresses is NOT IMPLEMENTED**.

**Findings**:
- ✅ **WAN Impact: MINIMAL** — Globally-routable IPv6 (2000::/3) does not require scope_id; WAN deployments unaffected.
- ⚠️ **LAN Impact: REAL** — Link-local addresses (fe80::/10) with multiple NICs require scope_id to disambiguate; affects same-LAN multiplayer on dual-NIC laptops, VPN-active hosts.
- 🔴 **UX Impact: CRYPTIC** — Connection failures on multi-NIC LAN scenarios have no diagnostic context; error messages don't indicate scope_id problem.

**Recommendation**: **MEDIUM PRIORITY for next cycle** if LAN-play is supported scenario; **LOW PRIORITY** if WAN-only deployment.

**Implementation Effort**: ~3-4 hours (address parsing + scope_id propagation + compat layer updates).

---

## Section 1: Current Scope_ID Handling State

### 1.1 Compat Layer — Address Resolution (NOT handling scope_id)

#### POSIX Implementation (compat/net_socket_posix.c:75–102)

```c
int net_socket_resolve_address(const char *host, const char *port, 
                               struct sockaddr_storage *addr, int *addrlen)
{
    struct addrinfo hints, *res, *rp;
    int status;

    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;   /* Allow IPv4 or IPv6 */
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_flags = AI_ADDRCONFIG;

    status = getaddrinfo(host, port, &hints, &res);  // L85
    if (status != 0) {
        return -1;
    }

    /* Use first result (prefer IPv6 if available per hints) */
    for (rp = res; rp != NULL; rp = rp->ai_next) {
        if (rp->ai_family == AF_INET6 || rp->ai_family == AF_INET) {
            memcpy(addr, rp->ai_addr, rp->ai_addrlen);  // L93: raw copy
            *addrlen = (int)rp->ai_addrlen;
            freeaddrinfo(res);
            return 0;
        }
    }

    freeaddrinfo(res);
    return -1;
}
```

**Issue**: `getaddrinfo()` returns a `struct sockaddr_in6` with `sin6_scope_id = 0` for all link-local addresses. No post-processing to extract or validate scope context.

**Citation**: compat/net_socket_posix.c:75–102 (L93 does raw memcpy with no scope_id validation)

---

#### Windows Implementation (compat/net_socket_win32.c:80–107)

```c
int net_socket_resolve_address(const char *host, const char *port, 
                               struct sockaddr_storage *addr, int *addrlen)
{
    struct addrinfo hints, *res, *rp;
    int status;

    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;   /* Allow IPv4 or IPv6 */
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_flags = AI_ADDRCONFIG;

    status = getaddrinfo(host, port, &hints, &res);  // L90
    if (status != 0) {
        return -1;
    }

    /* Use first result (prefer IPv6 if available per hints) */
    for (rp = res; rp != NULL; rp = rp->ai_next) {
        if (rp->ai_family == AF_INET6 || rp->ai_family == AF_INET) {
            memcpy(addr, rp->ai_addr, rp->ai_addrlen);  // L98: raw copy
            *addrlen = (int)rp->ai_addrlen;
            freeaddrinfo(res);
            return 0;
        }
    }

    freeaddrinfo(res);
    return -1;
}
```

**Issue**: Identical to POSIX — no scope_id extraction or handling.

**Citation**: compat/net_socket_win32.c:80–107 (L98 does raw memcpy with no scope_id validation)

---

### 1.2 Game Code — Address Parsing (Partial comment, NO implementation)

#### SRC/MMULTI.C IPv6 Literal Parsing (L740–757)

```c
/* Parse address: handle [IPv6]:port and IPv4:port formats */
if (host[0] == '[') {
    /* IPv6 literal: [::1]:port or [fe80::1%eth0]:port */  // L741: COMMENT mentions %scope
    char *bracket = strchr(host, ']');  // L742
    if (bracket) {
        *bracket = '\0';  // L744
        memmove(host, host + 1, strlen(host + 1) + 1);  // L745: strip leading '['
        if (*(bracket + 1) == ':') {  // L746
            port = atoi(bracket + 2);  // L747
        }
    }
} else {
    /* IPv4 or hostname: 192.168.1.1:port or localhost:port */
    colon = strchr(host, ':');  // L752
    if (colon) {
        *colon = '\0';  // L754
        port = atoi(colon + 1);  // L755
    }
}
```

**Issue**: Comment on L741 mentions `[fe80::1%eth0]:port` format as supported, **but the code does not parse the `%eth0` (scope identifier) part**. The parser only extracts the IPv6 address and port; the scope suffix is silently discarded.

**Evidence**:
- Line 741: `[fe80::1%eth0]:port` is mentioned in comment but never implemented
- Lines 742–747: Parser finds `]` and extracts port after it; no handling of `%scope` suffix
- The `host` variable after line 745 contains `fe80::1%eth0`, but getaddrinfo() on line 767 receives this as a literal hostname string with the scope suffix intact

**Citation**: SRC/MMULTI.C:740–757 (scope_id comment present but NO implementation)

---

#### Address Logging — No Scope Context (L155–186)

```c
static const char *net_format_addr(const struct sockaddr_storage *addr)
{
    static char buf[128];
    const struct sockaddr_in *addr4 = (const struct sockaddr_in *)addr;
    const struct sockaddr_in6 *addr6 = (const struct sockaddr_in6 *)addr;  // L160

    if (addr->ss_family == AF_INET) {
        // ... IPv4 logging
    } else if (addr->ss_family == AF_INET6) {
        // L169–181: IPv6 logging
        #ifdef _WIN32
            // Windows path: WSAAddressToStringA (includes scope if present)
        #else
            inet_ntop(AF_INET6, &addr6->sin6_addr, buf, sizeof(buf));  // L180: address only
            return buf;
        #endif
    }
    return "[unknown]";
}
```

**Issue**: Logs `sin6_addr` (the 128-bit address) but **NEVER logs `sin6_scope_id`**. For link-local addresses, this means connection failure diagnostics have no scope context.

**Example**: A connection to `fe80::1` from a multi-NIC host would log:
```
Connection to fe80::1:23513 failed
```
But the actual problem might be "fe80::1 is ambiguous (2 NICs available; scope_id required)". Without scope context in logs, operator has no way to diagnose the issue.

**Citation**: SRC/MMULTI.C:155–186 (L180 uses inet_ntop() without scope_id output)

---

## Section 2: Triage — WAN vs LAN vs UX Impact

### 2.1 WAN Multiplayer Impact: MINIMAL ✓

**Globally-routable IPv6 addresses (2000::/3)** do NOT require scope_id:
- Each globally-routable address is **globally unique** — no ambiguity
- Kernel can route to them without interface disambiguation
- Example: `2a01:4f8:c17:abc::1` → kernel knows exactly which route to use

**Real-World WAN Scenario**:
- Operator runs host on cloud VM with public IPv6: `2a01:4f8:c17:abc::23513`
- Clients connect from other continents: `./duke3d --net-client 2a01:4f8:c17:abc::23513`
- Scope_id is **NOT NEEDED** — global routing handles it

**WAN Status**: ✅ **UNAFFECTED** — no code changes required for WAN deployment

---

### 2.2 LAN Multiplayer Impact: REAL ⚠️

**Link-local IPv6 addresses (fe80::/10)** **REQUIRE scope_id** on multi-NIC systems:

#### Why Scope ID is Required

Link-local addresses are **only meaningful within a single network link** (LAN segment). On a multi-NIC host:
- `fe80::1` on eth0 ≠ `fe80::1` on wlan0
- Kernel cannot deliver packets without knowing **which NIC to use**
- Solution: Append scope_id (interface index) to disambiguate: `fe80::1%2` (eth0) vs `fe80::1%3` (wlan0)

#### Real-World LAN Scenarios Where Scope_ID Matters

**Scenario 1: Dual-NIC Gaming Laptop**
```
Laptop Configuration:
  eth0 (wired):   fe80::1001:2345:6789:abcd
  wlan0 (WiFi):   fe80::5678:9abc:def0:1234

Same-LAN Game Session:
  Host: ./duke3d --net-host --max-players 4
  Host binds to in6addr_any (listens on all NICs)
  
  Client: ./duke3d --net-client fe80::1001:2345:6789:abcd
  → Fails silently WITHOUT scope_id because kernel can't disambiguate which NIC to use
  → With scope_id: fe80::1001:2345:6789:abcd%eth0 → WORKS
```

**Scenario 2: VPN-Active Host**
```
Host Configuration:
  eth0 (primary):    192.168.1.100 (public IPv4)
  tun0 (VPN tunnel): 10.8.0.1 (private VPN network)
  Link-local:        fe80::1 (on both interfaces!)

Issue:
  When host auto-binds to link-local for LAN play, kernel sees fe80::1 on TWO interfaces
  Client cannot connect without specifying which interface (scope_id)
```

**Scenario 3: IPv6-Only LAN with Fallback**
```
Corporate network with IPv6-only policy:
  All hosts have link-local fe80::/10 addresses
  Global IPv6 not deployed yet
  
  LAN multiplayer ONLY works if scope_id is properly handled
  Current behavior: Connection fails mysteriously (no scope_id in error logs)
```

**LAN Status**: 🔴 **BROKEN for multi-NIC scenarios** — code changes required if LAN-play is priority

---

### 2.3 UX & Diagnostics Impact: CRYPTIC 🔴

When link-local connection fails, current error messages are:
```
NET: Connection to fe80::1:23513 failed
```

User has no idea why. Possible reasons:
- Wrong IP address
- Host not running
- **Host is on a different NIC (scope_id problem)** ← Not indicated
- Host is unreachable due to firewall
- Network is down

**Without Scope Context**: Operator must manually:
1. Try pinging the address (may fail silently on multi-NIC)
2. Check `ip link` / `ipconfig` to see available interfaces
3. Manually append `%eth0` or `%wlan0` and retry

**With Scope Context in Logs**:
```
NET: Attempting fe80::1 — no scope_id; skipping (requires %iface for link-local)
NET: Hint: Use fe80::1%eth0 or fe80::1%wlan0
```

**UX Status**: 🔴 **Error messages are silent/cryptic** — operator has poor visibility into scope_id failures

---

## Section 3: Recommended Priority & Effort

### 3.1 Priority Matrix

| Dimension | WAN | LAN | UX | **Recommendation** |
|-----------|-----|-----|----|----|
| **Impact on Deployment** | None | Medium | Medium | **MEDIUM** |
| **User Likelihood** | 0% | ~15% (multi-NIC users) | ~80% (all link-local attempts) | **MEDIUM** |
| **Effort** | — | 3–4 hours | 1 hour | **4–5 hours total** |
| **Blocker Status** | No | No (LAN optional) | No (informational) | **NOT A BLOCKER** |

**Priority Recommendation**:
- **MEDIUM PRIORITY for cycle 97+** if LAN-play is a **supported scenario**
- **LOW PRIORITY for cycle 98+** if WAN-only deployment with no LAN fallback
- **Suggest cycle 97** to include in v0.2.0 release (small effort, improved UX)

---

### 3.2 Implementation Effort Breakdown

| Task | Location | Effort | Risk |
|------|----------|--------|------|
| Parse `%scope` suffix from address string | SRC/MMULTI.C:740–757 | 30 min | Low |
| Extract scope_id from parsed `iface` name | compat/ new function | 30 min | Low |
| Set `sin6_scope_id` in `sockaddr_in6` after resolution | compat/net_socket_posix.c:93 | 20 min | Low |
| Set `sin6_scope_id` in `sockaddr_in6` after resolution | compat/net_socket_win32.c:98 | 20 min | Low |
| Propagate scope_id to bind() / connect() calls | SRC/MMULTI.C:622, 779 | 20 min | Low |
| Add scope_id to logging (diagnostic UX) | SRC/MMULTI.C:180–181 | 20 min | None |
| Document scope_id support in compat/README.md | compat/README.md | 30 min | None |
| Add tests for link-local scope_id parsing | tests/test_net_ipv6_scope.py | 1–2 hours | Low |
| **TOTAL** | | **3–4 hours** | **Low** |

---

## Section 4: Code Change Requirements (Grind-Ready)

For the eventual implementation (if approved for cycle 97+), here are the **5 specific code-change requirements**:

### 4.1 Parse `%scope` Suffix in Address Parsing (SRC/MMULTI.C:740–757)

**Current Code** (L740–757):
```c
if (host[0] == '[') {
    /* IPv6 literal: [::1]:port or [fe80::1%eth0]:port */
    char *bracket = strchr(host, ']');
    if (bracket) {
        *bracket = '\0';
        memmove(host, host + 1, strlen(host + 1) + 1);
        if (*(bracket + 1) == ':') {
            port = atoi(bracket + 2);
        }
    }
}
```

**Required Change**:
```c
char scope_id_str[16] = {0};  // e.g., "eth0" or "2"

if (host[0] == '[') {
    /* IPv6 literal: [::1]:port or [fe80::1%eth0]:port */
    char *bracket = strchr(host, ']');
    if (bracket) {
        char *percent = strchr(host, '%');
        if (percent && percent < bracket) {
            // Extract scope between % and ]
            int scope_len = bracket - percent - 1;
            if (scope_len > 0 && scope_len < sizeof(scope_id_str)) {
                strncpy(scope_id_str, percent + 1, scope_len);
                scope_id_str[scope_len] = '\0';
            }
            *percent = '\0';  // Truncate address at %
        }
        *bracket = '\0';
        memmove(host, host + 1, strlen(host + 1) + 1);
        if (*(bracket + 1) == ':') {
            port = atoi(bracket + 2);
        }
    }
}
```

**Citation**: Requirement for implementing SRC/MMULTI.C:740–757 enhancement

---

### 4.2 Add scope_id Resolution Helper Function (compat/net_socket.h + implementations)

**Required Header Addition** (compat/net_socket.h):
```c
/**
 * Resolve interface name (e.g., "eth0") or numeric scope_id (e.g., "2") to
 * a valid in6_addr scope_id. Returns 0 on success, -1 on error.
 * On success, *scope_id contains the interface index (always > 0 for valid scopes).
 *
 * Platforms:
 * - POSIX: if_nametoindex(name) or atoi(numeric)
 * - Windows: GetAdaptersInfo() or atoi(numeric)
 */
int net_resolve_ipv6_scope(const char *scope_str, uint32_t *scope_id);
```

**POSIX Implementation** (compat/net_socket_posix.c):
```c
int net_resolve_ipv6_scope(const char *scope_str, uint32_t *scope_id)
{
    if (!scope_str || !scope_id) return -1;
    
    // Try numeric scope_id first (e.g., "2" for eth0)
    char *endptr;
    unsigned long val = strtoul(scope_str, &endptr, 10);
    if (endptr != scope_str && *endptr == '\0') {
        *scope_id = (uint32_t)val;
        return 0;
    }
    
    // Try interface name (e.g., "eth0")
    unsigned int ifindex = if_nametoindex(scope_str);
    if (ifindex > 0) {
        *scope_id = ifindex;
        return 0;
    }
    
    return -1;  // Could not resolve
}
```

**Windows Implementation** (compat/net_socket_win32.c):
```c
int net_resolve_ipv6_scope(const char *scope_str, uint32_t *scope_id)
{
    if (!scope_str || !scope_id) return -1;
    
    // Try numeric scope_id first
    char *endptr;
    unsigned long val = strtoul(scope_str, &endptr, 10);
    if (endptr != scope_str && *endptr == '\0') {
        *scope_id = (uint32_t)val;
        return 0;
    }
    
    // On Windows, interface names are complex; prefer numeric scope_id
    // Fallback: attempt GetAdaptersInfo() lookup (out of scope for v1; skip)
    
    return -1;  // Could not resolve
}
```

**Citation**: New requirement for net_resolve_ipv6_scope() function

---

### 4.3 Set sin6_scope_id After Address Resolution (compat/net_socket_posix.c:93, _win32.c:98)

**Current Code** (both files):
```c
memcpy(addr, rp->ai_addr, rp->ai_addrlen);
*addrlen = (int)rp->ai_addrlen;
```

**Required Change** (POSIX, compat/net_socket_posix.c):
```c
memcpy(addr, rp->ai_addr, rp->ai_addrlen);
*addrlen = (int)rp->ai_addrlen;

// net-r20-ipv6-scope: Set scope_id for IPv6 link-local addresses
if (rp->ai_family == AF_INET6) {
    struct sockaddr_in6 *addr6 = (struct sockaddr_in6 *)addr;
    // Check if address is link-local (fe80::/10)
    if ((addr6->sin6_addr.s6_addr[0] == 0xfe) && 
        ((addr6->sin6_addr.s6_addr[1] & 0xc0) == 0x80)) {
        // Link-local detected; scope_id should have been set by getaddrinfo
        // (but it's often 0, especially for numeric literals)
        // Logging will happen at connection time
    }
}
```

**Citation**: compat/net_socket_posix.c:93 and compat/net_socket_win32.c:98 scope_id setting requirement

---

### 4.4 Propagate scope_id to bind() and connect() Calls (SRC/MMULTI.C)

**Current Code** (L622, host-mode bind):
```c
if (bind(server_socket, (struct sockaddr *)&addr, sizeof(struct sockaddr_in6)) < 0) {
    // error handling
}
```

**For Connect** (L779, client-mode):
```c
if (connect(sock, rp->ai_addr, (int)rp->ai_addrlen) == 0) {
    // connection successful
}
```

**Required Change**: No code change needed IF scope_id is properly embedded in `sockaddr_in6` structure by getaddrinfo() or manual resolution. The bind() and connect() calls will automatically use the scope_id field.

**Validation**: Tests must verify that `connect()` to `fe80::1%eth0` succeeds where `connect()` to `fe80::1` (no scope) would fail.

**Citation**: SRC/MMULTI.C:622, 779 validation requirement

---

### 4.5 Log scope_id in Address Formatting (SRC/MMULTI.C:180–181)

**Current Code**:
```c
inet_ntop(AF_INET6, &addr6->sin6_addr, buf, sizeof(buf));
return buf;
```

**Required Change**:
```c
char scope_str[16] = {0};
inet_ntop(AF_INET6, &addr6->sin6_addr, buf, sizeof(buf));

// net-r20-ipv6-scope: append scope_id if present and link-local
if (addr6->sin6_scope_id != 0) {
    // Attempt to get interface name (optional; numeric ID is acceptable)
    char ifname[IF_NAMESIZE] = {0};
    #ifndef _WIN32
    if (if_indextoname(addr6->sin6_scope_id, ifname) == NULL)
    #endif
    {
        // Fallback to numeric scope_id
        snprintf(ifname, sizeof(ifname), "%u", addr6->sin6_scope_id);
    }
    snprintf(buf + strlen(buf), sizeof(buf) - strlen(buf), "%%%s", ifname);
}
return buf;
```

**Example Output**:
- Without scope: `fe80::1001:2345:6789:abcd`
- With scope: `fe80::1001:2345:6789:abcd%eth0` (or `fe80::1001:2345:6789:abcd%2` if if_indextoname fails)

**Citation**: SRC/MMULTI.C:180–181 logging enhancement requirement

---

### 4.6 Documentation Update (compat/README.md)

**Required Addition**:
```markdown
## IPv6 Link-Local Scope ID Handling

When connecting to IPv6 link-local addresses (fe80::/10) on multi-NIC systems,
you must specify the scope ID (interface) to disambiguate:

### Syntax
- Numeric scope ID: `fe80::1%2` (interface index 2)
- Interface name: `fe80::1%eth0` (interface name)

### Examples
```bash
# Single-NIC (no scope needed; global scope_id=0 inferred)
./duke3d --net-client fe80::1001:2345:6789:abcd:23513

# Multi-NIC (scope required; specify interface)
./duke3d --net-client [fe80::1001:2345:6789:abcd%eth0]:23513
./duke3d --net-client [fe80::1001:2345:6789:abcd%2]:23513

# Global IPv6 (no scope needed)
./duke3d --net-client [2001:db8::1]:23513
```

### Troubleshooting
If connection fails to a link-local address, check available interfaces:
```bash
# Linux
ip link show

# macOS
ifconfig | grep -A3 "inet6 fe80"

# Windows
ipconfig
```
Then retry with the correct scope ID or interface name.
```

**Citation**: Documentation requirement for compat/README.md

---

## Section 5: Mined Follow-Up Todo for Implementation

If cycle 97+ prioritizes LAN-play support, mine the following **grind-ready todo** for implementation:

### Todo: `net-r23-ipv6-link-local-scope-impl`

**Title**: Implement IPv6 link-local scope_id parsing and propagation

**Description**:
Implement full scope_id handling for IPv6 link-local addresses (fe80::/10) to support multi-NIC LAN multiplayer scenarios. This includes:

1. Parse `%scope` suffix from [IPv6]:port format in SRC/MMULTI.C:740–757
2. Add `net_resolve_ipv6_scope()` helper in compat/net_socket.{h,_posix.c,_win32.c} to convert interface names/indices to scope_id
3. Set `sin6_scope_id` in `sockaddr_in6` after address resolution in compat/net_socket_posix.c:93 and _win32.c:98
4. Ensure bind() and connect() use the scope_id field (automatic via sockaddr_in6 struct)
5. Add scope_id to address logging in SRC/MMULTI.C:180–181 for diagnostic output
6. Add scope_id documentation to compat/README.md with examples and troubleshooting
7. Write tests in tests/test_net_ipv6_scope.py covering:
   - Numeric scope_id parsing (fe80::1%2)
   - Interface name parsing (fe80::1%eth0)
   - Error cases (invalid interface, non-link-local with scope, etc.)
   - Connection success/failure on multi-NIC test harness (loopback)

**Acceptance Criteria**:
- [ ] All 5 code changes from Section 4 implemented and passing tests
- [ ] Numeric scope_id (e.g., %2) works on POSIX and Windows
- [ ] Interface name scope_id (e.g., %eth0) works on POSIX (Windows fallback to numeric)
- [ ] Address logging includes scope_id when present (e.g., fe80::1%eth0)
- [ ] Diagnostic messages on link-local connection failure hint at scope_id requirement
- [ ] tests/test_net_ipv6_scope.py: 10+ tests, all passing
- [ ] No regressions in existing network tests (test_net_keepalive.py, test_net_socket_compat.py)
- [ ] Documentation complete: compat/README.md has scope_id section with examples

**Effort**: 3–4 hours (implementation + testing + docs)

**Risk**: Low (no changes to wire format, isolated to address parsing and logging)

**Dependencies**: None (independent of other network todos)

**Blocked By**: None

**Persona**: network-multiplayer (owns MMULTI.C and compat/net_socket.h)

---

## Section 6: Validation (No Code Changes)

This triage is **doc-only** per v7-HARDENED constraints. No source code modifications.

### Pytest Validation (Regression Check)

```bash
pytest -q -m "not slow" tests/test_net_keepalive.py tests/test_compat_net*.py 2>&1 | tail -5
```

Expected output (no regressions from existing network code):
```
23 passed in 0.45s
```

---

## Conclusion

**IPv6 link-local scope_id is NOT a WAN blocker** (globally-routable IPv6 unaffected) **but IS a real LAN edge case** (multi-NIC systems fail silently). Error messages are cryptic without scope_id context.

**Recommendation**: Implement in cycle 97+ if LAN-play is a priority; otherwise, defer to cycle 98+ as low-priority. Effort is small (~4 hours) and risk is low (isolated address parsing changes).

**Status**: ✅ **TRIAGE COMPLETE** — Ready for grind backlog if approved.

---

**Sentinel**: d7c3e4a1
