/* net_socket_posix.c — POSIX (BSD sockets) implementation of net_socket abstraction layer
 * 
 * Compiled conditionally when !_WIN32 (Unix/Linux/macOS).
 * Provides thin wrappers around standard POSIX socket functions.
 */

#include "net_socket.h"
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <netdb.h>

/* POSIX: socket initialization is a no-op */
void net_socket_init(void)
{
	/* Intentionally empty on POSIX systems */
}

/* POSIX: socket shutdown is a no-op */
void net_socket_shutdown(void)
{
	/* Intentionally empty on POSIX systems */
}

/* Create a socket */
net_socket_t net_socket_create(int domain, int type, int protocol)
{
	return socket(domain, type, protocol);
}

/* Bind socket to address */
int net_socket_bind(net_socket_t sock, const struct sockaddr *addr, int addrlen)
{
	return bind(sock, addr, (socklen_t)addrlen);
}

/* Listen for incoming connections */
int net_socket_listen(net_socket_t sock, int backlog)
{
	return listen(sock, backlog);
}

/* Accept an incoming connection */
net_socket_t net_socket_accept(net_socket_t sock, struct sockaddr *addr, int *addrlen)
{
	socklen_t len = (socklen_t)(*addrlen);
	net_socket_t client = accept(sock, addr, &len);
	*addrlen = (int)len;
	return client;
}

/* Connect to a remote address */
int net_socket_connect(net_socket_t sock, const struct sockaddr *addr, int addrlen)
{
	return connect(sock, addr, (socklen_t)addrlen);
}

/* Send data on socket */
int net_socket_send(net_socket_t sock, const void *buf, int len)
{
	return (int)send(sock, buf, len, 0);
}

/* Receive data from socket */
int net_socket_recv(net_socket_t sock, void *buf, int len)
{
	return (int)recv(sock, buf, len, 0);
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
	int flags = fcntl(sock, F_GETFL, 0);
	if (flags < 0) return -1;
	return fcntl(sock, F_SETFL, flags | O_NONBLOCK);
}

/* Set socket option */
int net_socket_set_option(net_socket_t sock, int level, int optname, const void *optval, int optlen)
{
	return setsockopt(sock, level, optname, optval, (socklen_t)optlen);
}

/* Close socket */
void net_socket_close(net_socket_t sock)
{
	if (sock != NET_SOCKET_INVALID) {
		close(sock);
	}
}

/* Get last socket error */
int net_socket_last_error(void)
{
	return errno;
}

/* Check if error is transient (would retry) */
int net_socket_is_transient_error(int err)
{
	return (err == EAGAIN || err == EWOULDBLOCK || err == EINTR);
}
