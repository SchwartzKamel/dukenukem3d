/* net_socket_posix.c — POSIX (BSD sockets) implementation of net_socket abstraction layer
 * 
 * Compiled conditionally when !_WIN32 (Unix/Linux/macOS).
 * Provides thin wrappers around standard POSIX socket functions.
 */

#include "net_socket.h"
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <netdb.h>
#include <netinet/tcp.h>
#include <stdlib.h>

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

/* Enable TCP keepalive with optional tunable knobs (best-effort) */
int net_socket_enable_keepalive(net_socket_t sock)
{
	int on = 1;
	int ret;

	/* Enable SO_KEEPALIVE */
	ret = setsockopt(sock, SOL_SOCKET, SO_KEEPALIVE, &on, sizeof(on));
	if (ret < 0) {
		fprintf(stderr, "WARNING: net_socket_enable_keepalive: SO_KEEPALIVE failed (%s)\n", strerror(errno));
		return ret;
	}

	/* Helper macro to read and validate environment variable */
#define GET_KEEPALIVE_ENV(var_name, default_val, min_val, max_val) \
	do { \
		const char *env_str = getenv(var_name); \
		if (env_str != NULL) { \
			char *endptr; \
			long val = strtol(env_str, &endptr, 10); \
			if (endptr == env_str || *endptr != '\0') { \
				fprintf(stderr, "WARNING: net_socket_enable_keepalive: %s invalid format '%s', using default %d\n", \
					var_name, env_str, default_val); \
				val = default_val; \
			} else if (val < min_val || val > max_val) { \
				fprintf(stderr, "WARNING: net_socket_enable_keepalive: %s out of range %ld (valid: %d..%d), using default %d\n", \
					var_name, val, min_val, max_val, default_val); \
				val = default_val; \
			} \
			(default_val) = (int)val; \
		} \
	} while (0)

	/* Optional: Set keepalive timers on Linux if available */
#ifdef TCP_KEEPIDLE
	/* TCP_KEEPIDLE: time before first keepalive probe (2 hours default) */
	int keepidle = 120;  /* 2 minutes for faster dead connection detection */
	GET_KEEPALIVE_ENV("DUKE_NET_KEEPIDLE", keepidle, 1, 86400);
	ret = setsockopt(sock, IPPROTO_TCP, TCP_KEEPIDLE, &keepidle, sizeof(keepidle));
	if (ret < 0) {
		fprintf(stderr, "WARNING: net_socket_enable_keepalive: TCP_KEEPIDLE failed (%s)\n", strerror(errno));
	}
#endif

#ifdef TCP_KEEPINTVL
	/* TCP_KEEPINTVL: interval between keepalive probes (75 sec default) */
	int keepintvl = 30;  /* 30 seconds for faster detection */
	GET_KEEPALIVE_ENV("DUKE_NET_KEEPINTVL", keepintvl, 1, 86400);
	ret = setsockopt(sock, IPPROTO_TCP, TCP_KEEPINTVL, &keepintvl, sizeof(keepintvl));
	if (ret < 0) {
		fprintf(stderr, "WARNING: net_socket_enable_keepalive: TCP_KEEPINTVL failed (%s)\n", strerror(errno));
	}
#endif

#ifdef TCP_KEEPCNT
	/* TCP_KEEPCNT: number of keepalive probes before giving up (9 default) */
	int keepcnt = 5;  /* 5 probes × 30 sec = 150 sec total before timeout */
	GET_KEEPALIVE_ENV("DUKE_NET_KEEPCNT", keepcnt, 1, 100);
	ret = setsockopt(sock, IPPROTO_TCP, TCP_KEEPCNT, &keepcnt, sizeof(keepcnt));
	if (ret < 0) {
		fprintf(stderr, "WARNING: net_socket_enable_keepalive: TCP_KEEPCNT failed (%s)\n", strerror(errno));
	}
#endif

#undef GET_KEEPALIVE_ENV

	return 0;  /* SO_KEEPALIVE succeeded; optional tuning failures are logged but not fatal */
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

/* Check if error is keepalive-related (dead peer detected) */
int net_socket_is_keepalive_error(int err)
{
	return (err == ETIMEDOUT || err == ECONNRESET);
}
