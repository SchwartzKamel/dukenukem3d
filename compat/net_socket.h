/* net_socket.h — Portable socket API abstraction layer for Windows/POSIX
 * 
 * Provides a unified interface to socket operations across Windows (Winsock2)
 * and POSIX systems (BSD sockets). Hides platform-specific differences in:
 * - Socket type representation (SOCKET vs int)
 * - Error codes (WSAGetLastError vs errno)
 * - Setup/cleanup (WSAStartup/Cleanup vs none)
 * - Non-blocking socket control (ioctlsocket vs fcntl)
 */

#ifndef NET_SOCKET_H
#define NET_SOCKET_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/* Platform-specific socket type definitions */
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
typedef SOCKET net_socket_t;
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
typedef int net_socket_t;
#endif

/* IPv6 support: struct sockaddr_storage (dual-stack container) */
#ifndef _WIN32
#include <netinet/in.h>
#endif

/* Portable invalid socket constant */
#ifdef _WIN32
#define NET_SOCKET_INVALID INVALID_SOCKET
#else
#define NET_SOCKET_INVALID (-1)
#endif

/* Network initialization and shutdown */
void net_socket_init(void);
void net_socket_shutdown(void);

/* Socket creation */
net_socket_t net_socket_create(int domain, int type, int protocol);

/* Socket operations */
int net_socket_bind(net_socket_t sock, const struct sockaddr *addr, int addrlen);
int net_socket_listen(net_socket_t sock, int backlog);
net_socket_t net_socket_accept(net_socket_t sock, struct sockaddr *addr, int *addrlen);
int net_socket_connect(net_socket_t sock, const struct sockaddr *addr, int addrlen);
int net_socket_send(net_socket_t sock, const void *buf, int len);
int net_socket_recv(net_socket_t sock, void *buf, int len);

/* IPv6 support: address resolution via getaddrinfo */
int net_socket_resolve_address(const char *host, const char *port, struct sockaddr_storage *addr, int *addrlen);

/* Socket control */
int net_socket_set_nonblocking(net_socket_t sock);
int net_socket_set_option(net_socket_t sock, int level, int optname, const void *optval, int optlen);

/**
 * @brief Enable TCP keepalive on a socket with optional environment-variable tuning.
 * 
 * Enables SO_KEEPALIVE to detect dead connections. On POSIX systems (Linux/BSD/macOS),
 * also sets optional per-socket TCP keepalive timers if available:
 * 
 * **POSIX Tunables (defaults)**:
 * - TCP_KEEPIDLE: Time before first probe (120 seconds) — Override via DUKE_NET_KEEPIDLE
 * - TCP_KEEPINTVL: Interval between probes (30 seconds) — Override via DUKE_NET_KEEPINTVL
 * - TCP_KEEPCNT: Number of probes before timeout (5) — Override via DUKE_NET_KEEPCNT
 * 
 * Environment variables (POSIX only, parsed via getenv + strtol with range validation):
 * - DUKE_NET_KEEPIDLE: seconds (1..86400, default 120)
 * - DUKE_NET_KEEPINTVL: seconds (1..86400, default 30)
 * - DUKE_NET_KEEPCNT: count (1..100, default 5)
 * Invalid or out-of-range values fall back to defaults.
 * 
 * **Windows Behavior**:
 * Windows uses system-wide keepalive settings (HKEY_LOCAL_MACHINE TCP parameters).
 * Per-socket TCP_KEEPIDLE/INTVL/CNT are NOT supported; SO_KEEPALIVE only.
 * Environment variables are ignored on Windows.
 * 
 * **Semantics**:
 * Best-effort: logs warnings on setsockopt failure but returns 0 (SO_KEEPALIVE must succeed,
 * optional tuning failures are non-fatal). Does not abort or return error.
 * 
 * @param sock Socket to configure
 * @return 0 on success (SO_KEEPALIVE set), -1 if SO_KEEPALIVE itself fails
 * 
 * @note See tests/test_net_keepalive.py for verification and env-var override tests.
 */
int net_socket_enable_keepalive(net_socket_t sock);

/* Socket close */
void net_socket_close(net_socket_t sock);

/* Error handling */
int net_socket_last_error(void);
int net_socket_is_transient_error(int err);

/**
 * @brief Check if error is keepalive-related (ETIMEDOUT or ECONNRESET).
 * 
 * Used to distinguish keepalive-induced disconnects from other recv errors.
 * Returns non-zero if error indicates a dead peer detected by keepalive.
 * 
 * POSIX: ETIMEDOUT, ECONNRESET
 * Windows: WSAETIMEDOUT, WSAECONNRESET
 */
int net_socket_is_keepalive_error(int err);

#ifdef __cplusplus
}
#endif

#endif /* NET_SOCKET_H */
