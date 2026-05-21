/* net_socket_win32.c — Windows (Winsock2) implementation of net_socket abstraction layer
 * 
 * Compiled conditionally when _WIN32 (Windows).
 * Provides thin wrappers around Winsock2 socket functions with proper error handling.
 */

#include "net_socket.h"
#include <string.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <netdb.h>

/* Global Winsock initialized flag */
static int winsock_initialized = 0;

/* Initialize Winsock (Windows-specific) */
void net_socket_init(void)
{
	WSADATA wsa;
	if (!winsock_initialized) {
		if (WSAStartup(MAKEWORD(2, 2), &wsa) == 0) {
			winsock_initialized = 1;
		}
	}
}

/* Shutdown Winsock (Windows-specific) */
void net_socket_shutdown(void)
{
	if (winsock_initialized) {
		WSACleanup();
		winsock_initialized = 0;
	}
}

/* Create a socket */
net_socket_t net_socket_create(int domain, int type, int protocol)
{
	return socket(domain, type, protocol);
}

/* Bind socket to address */
int net_socket_bind(net_socket_t sock, const struct sockaddr *addr, int addrlen)
{
	return bind(sock, addr, addrlen);
}

/* Listen for incoming connections */
int net_socket_listen(net_socket_t sock, int backlog)
{
	return listen(sock, backlog);
}

/* Accept an incoming connection */
net_socket_t net_socket_accept(net_socket_t sock, struct sockaddr *addr, int *addrlen)
{
	return accept(sock, addr, addrlen);
}

/* Connect to a remote address */
int net_socket_connect(net_socket_t sock, const struct sockaddr *addr, int addrlen)
{
	return connect(sock, addr, addrlen);
}

/* Send data on socket */
int net_socket_send(net_socket_t sock, const void *buf, int len)
{
	return send(sock, (const char *)buf, len, 0);
}

/* Receive data from socket */
int net_socket_recv(net_socket_t sock, void *buf, int len)
{
	return recv(sock, (char *)buf, len, 0);
}

/* Resolve hostname/port to sockaddr_storage (IPv4 and IPv6 support) */
int net_socket_resolve_address(const char *host, const char *port, struct sockaddr_storage *addr, int *addrlen)
{
	struct addrinfo hints, *res, *rp;
	int status;

	memset(&hints, 0, sizeof(hints));
	hints.ai_family = AF_UNSPEC;   /* Allow IPv4 or IPv6 */
	hints.ai_socktype = SOCK_STREAM;
	hints.ai_flags = AI_ADDRCONFIG;

	status = getaddrinfo(host, port, &hints, &res);
	if (status != 0) {
		return -1;
	}

	/* Use first result (prefer IPv6 if available per hints) */
	for (rp = res; rp != NULL; rp = rp->ai_next) {
		if (rp->ai_family == AF_INET6 || rp->ai_family == AF_INET) {
			memcpy(addr, rp->ai_addr, rp->ai_addrlen);
			*addrlen = (int)rp->ai_addrlen;
			freeaddrinfo(res);
			return 0;
		}
	}

	freeaddrinfo(res);
	return -1;
}

/* Set socket to non-blocking mode */
int net_socket_set_nonblocking(net_socket_t sock)
{
	unsigned long mode = 1;
	return ioctlsocket(sock, FIONBIO, &mode);
}

/* Set socket option */
int net_socket_set_option(net_socket_t sock, int level, int optname, const void *optval, int optlen)
{
	return setsockopt(sock, level, optname, (const char *)optval, optlen);
}

/* Close socket */
void net_socket_close(net_socket_t sock)
{
	if (sock != NET_SOCKET_INVALID) {
		closesocket(sock);
	}
}

/* Get last socket error (Windows-specific) */
int net_socket_last_error(void)
{
	return WSAGetLastError();
}

/* Check if error is transient (would retry) */
int net_socket_is_transient_error(int err)
{
	return (err == WSAEWOULDBLOCK || err == WSAEINTR);
}
