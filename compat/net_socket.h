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
typedef int net_socket_t;
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

/* Socket control */
int net_socket_set_nonblocking(net_socket_t sock);
int net_socket_set_option(net_socket_t sock, int level, int optname, const void *optval, int optlen);

/* Socket close */
void net_socket_close(net_socket_t sock);

/* Error handling */
int net_socket_last_error(void);
int net_socket_is_transient_error(int err);

#ifdef __cplusplus
}
#endif

#endif /* NET_SOCKET_H */
