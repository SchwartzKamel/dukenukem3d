/* "Build Engine & Tools" Copyright (c) 1993-1997 Ken Silverman
   Ken Silverman's official web site: "http://www.advsys.net/ken"
   See the included license file "BUILDLIC.TXT" for license info.

   TCP/IP multiplayer implementation (Spec 007).
   Replaces DOS IPX networking with BSD sockets (Linux) / Winsock (Windows).
   Star topology: host relays packets between clients.
   Usage: --host <port> [--players <n>]  or  --join <ip:port>
   No flags = single-player (numplayers=1), fully backward-compatible. */

#include "compat.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <time.h>
#include <stdint.h>
#include "pragmas_gcc.h"

/* Platform-specific networking */
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
typedef int socklen_t;
#define net_close closesocket
#define net_sleep(ms) Sleep(ms)
#else
#include <sys/socket.h>
#include <sys/select.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
typedef int SOCKET;
#define INVALID_SOCKET (-1)
#define SOCKET_ERROR (-1)
#define net_close close
#define net_sleep(ms) usleep((ms) * 1000)
#endif

#define MAXPLAYERS 16
#define MAXPACKETSIZE 2048
#define NET_HEADER_SIZE 4   /* [1B sender][1B dest][2B payload length] */
#define RECV_BUF_SIZE 65536
#define DEFAULT_PORT 23513
/* TCP connection timeout (seconds).
   Reduced from 60s to 30s to balance LAN responsiveness against
   misconfigured client scenarios. Handshake has separate 15s timeout. */
#define NET_CONNECT_TIMEOUT 30
#define HANDSHAKE_TIMEOUT_SEC 15
/* Host-side accept() timeout (seconds). Prevents crashed client from blocking forever.
   Asymmetric with client handshake timeout to allow graceful degradation. */
#define NET_HOST_ACCEPT_TIMEOUT_SEC 10
#define NET_PROTOCOL_VERSION 0x0001

#define updatecrc16(crc,dat) crc = (((crc<<8)&65535)^crctable[((((unsigned short)crc)>>8)&65535)^dat])

uint16_t crctable[256];

extern int32_t totalclock;
static int32_t timeoutcount = 60, resendagaincount = 4;
static int32_t lastsendtime[MAXPLAYERS];
static int tcp_send_failures = 0;

short myconnectindex, numplayers;
short connecthead, connectpoint2[MAXPLAYERS];
char syncstate = 0;

/* Watcom provided _argc/_argv as globals; define them for GCC */
int _argc = 1;
static char *_argv_default[] = {"game", NULL};
char **_argv = _argv_default;

/* ---- TCP/IP networking state ---- */
static SOCKET server_socket = INVALID_SOCKET;
static SOCKET player_sockets[MAXPLAYERS];
static int is_host = 0;
static int net_initialized = 0;

/* Per-socket receive buffers for TCP stream reassembly */
typedef struct {
	unsigned char buf[RECV_BUF_SIZE];
	int len;
} recv_buf_t;
static recv_buf_t recv_bufs[MAXPLAYERS];

/* Packet queue for getpacket() */
#define PACKET_QUEUE_SIZE 1024
typedef struct {
	char data[MAXPACKETSIZE];
	short length;
	short from_player;
} queued_packet_t;
static queued_packet_t packet_queue[PACKET_QUEUE_SIZE];
static int pq_head = 0, pq_tail = 0;
static int pq_count = 0;
static int pq_dropped_packets = 0;

/* ---- Endianness Convention & Wire Format ----
 *
 * WIRE FORMAT SPECIFICATION: ALL MULTI-BYTE INTEGERS ARE LITTLE-ENDIAN
 *
 * The network packet format assumes little-endian byte order throughout.
 * Today's targets (x86_64, ARM64-LE) are all little-endian, so this behavior
 * is preserved. However, the assumption was implicit in the 1996 code and
 * must be documented for future ports.
 *
 * Byte-packing sites (always use mm_pack_u16_le / mm_unpack_u16_le):
 *   - Payload length field in packet header: buf[2] (lo), buf[3] (hi)
 *   - Protocol version in handshake: msg[2] (lo), msg[3] (hi)
 *
 * This ensures explicit endianness handling and enables cross-platform
 * correctness if porting to big-endian or mixed-endian systems in future.
 */

/* Little-endian u16 pack/unpack helpers (compile away to nothing on LE platforms) */
static inline void mm_pack_u16_le(unsigned char *buf, uint16_t val)
{
	buf[0] = (unsigned char)(val & 0xFF);
	buf[1] = (unsigned char)((val >> 8) & 0xFF);
}

static inline uint16_t mm_unpack_u16_le(const unsigned char *buf)
{
	return (uint16_t)(buf[0] | ((unsigned)buf[1] << 8));
}

/* ---- Internal helpers ---- */

static void net_set_nonblocking(SOCKET sock)
{
#ifdef _WIN32
	unsigned long mode = 1;
	ioctlsocket(sock, FIONBIO, &mode);
#else
	int flags = fcntl(sock, F_GETFL, 0);
	fcntl(sock, F_SETFL, flags | O_NONBLOCK);
#endif
}

static void net_send_raw(SOCKET sock, const unsigned char *data, int len)
{
	int sent = 0;
	while (sent < len) {
		int attempts = 0;
		int r = -1;
		/* Retry loop for send(): handle EINTR and EAGAIN up to 8 attempts */
		while (attempts < 8 && r < 0) {
			r = send(sock, (const char *)(data + sent), len - sent, 0);
			if (r < 0) {
				int err;
#ifdef _WIN32
				err = WSAGetLastError();
				if (err != WSAEWOULDBLOCK && err != WSAEINTR) break;
#else
				err = errno;
				if (err != EAGAIN && err != EWOULDBLOCK && err != EINTR) break;
#endif
				attempts++;
				if (attempts < 8) net_sleep(1);
			}
		}
		if (r <= 0) {
			tcp_send_failures++;
			break;
		}
		sent += r;
	}
}

/* Accept with timeout (prevents crashed client from blocking host indefinitely) */
static SOCKET net_accept_timeout(SOCKET server_sock, struct sockaddr_in *client_addr,
                                 socklen_t *client_len, int timeout_sec)
{
	SOCKET client;
	fd_set readfds;
	struct timeval tv;

	FD_ZERO(&readfds);
	FD_SET(server_sock, &readfds);
	tv.tv_sec = timeout_sec;
	tv.tv_usec = 0;

	if (select((int)server_sock + 1, &readfds, NULL, NULL, &tv) <= 0) {
		return INVALID_SOCKET;
	}

	client = accept(server_sock, (struct sockaddr *)client_addr, client_len);
	return client;
}

/* Blocking receive with timeout (used during handshake only) */
static int net_recv_all(SOCKET sock, unsigned char *buf, int len)
{
	int total = 0;
	time_t start = time(NULL);
	while (total < len) {
		int r = recv(sock, (char *)(buf + total), len - total, 0);
		if (r > 0) {
			total += r;
		} else if (r == 0) {
			return -1;
		} else {
#ifdef _WIN32
			if (WSAGetLastError() != WSAEWOULDBLOCK && WSAGetLastError() != WSAEINTR) return -1;
#else
			if (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) return -1;
#endif
		}
		if (time(NULL) - start > HANDSHAKE_TIMEOUT_SEC) return -1;
		if (total < len) net_sleep(10);
	}
	return total;
}

/* Poll all connected sockets, extract framed packets into queue */
static void net_poll_sockets(void)
{
	int i, start, end;

	if (!net_initialized) return;

	start = is_host ? 1 : 0;
	end   = is_host ? numplayers : 1;

	for (i = start; i < end; i++) {
		SOCKET sock = player_sockets[i];
		if (sock == INVALID_SOCKET) continue;

		/* Read available data into receive buffer */
		while (recv_bufs[i].len < RECV_BUF_SIZE - 4096) {
			int r = recv(sock, (char *)(recv_bufs[i].buf + recv_bufs[i].len),
			             RECV_BUF_SIZE - recv_bufs[i].len, 0);
			if (r > 0) {
				recv_bufs[i].len += r;
			} else if (r == 0) {
				break;
			} else {
				int err;
#ifdef _WIN32
				err = WSAGetLastError();
				if (err == WSAEWOULDBLOCK || err == WSAEINTR) {
					/* net-r9-recv-eagain-distinguish: transient, retry */
					continue;
				}
#else
				err = errno;
				if (err == EAGAIN || err == EWOULDBLOCK || err == EINTR) {
					/* net-r9-recv-eagain-distinguish: transient, retry */
					continue;
				}
#endif
				break;
			}
		}

		/* Extract complete packets */
		while (recv_bufs[i].len >= NET_HEADER_SIZE) {
			int from_player = recv_bufs[i].buf[0];
			int dest        = recv_bufs[i].buf[1];
			int payload_len = mm_unpack_u16_le(recv_bufs[i].buf + 2);
			int total_len;

			/* Validate from_player bounds (CRITICAL: from_player is wire-supplied, attacker-controlled) */
			if (from_player < 0 || from_player >= MAXPLAYERS) {
				printf("NET: SECURITY: Invalid from_player=%d (out of bounds [0,%d)). Dropping packet.\n",
					from_player, MAXPLAYERS);
				recv_bufs[i].len -= NET_HEADER_SIZE;
				if (recv_bufs[i].len > 0)
					memmove(recv_bufs[i].buf, recv_bufs[i].buf + NET_HEADER_SIZE, recv_bufs[i].len);
				continue;
			}

			/* Validate bounds before relay-forwarding */
			if (payload_len <= 0 || payload_len > MAXPACKETSIZE - NET_HEADER_SIZE) {
				recv_bufs[i].len = 0;
				break;
			}

			total_len = NET_HEADER_SIZE + payload_len;
			if (recv_bufs[i].len < total_len) break;

			/* Host: relay to destination client (after bounds check) */
			if (is_host && dest != 0 && dest > 0 && dest < numplayers) {
				if (player_sockets[dest] != INVALID_SOCKET)
					net_send_raw(player_sockets[dest], recv_bufs[i].buf, total_len);
			}

			/* Queue locally if destined for us */
			if ((is_host && dest == 0) || (!is_host)) {
				int is_full = (pq_count >= PACKET_QUEUE_SIZE);
				
				if (is_full) {
					/* DROP-OLDEST policy: discard oldest unread packet to make room for new one */
					pq_head = (pq_head + 1) % PACKET_QUEUE_SIZE;
					pq_dropped_packets++;
				} else {
					pq_count++;
				}
				
				memcpy(packet_queue[pq_tail].data,
				       recv_bufs[i].buf + NET_HEADER_SIZE, payload_len);
				packet_queue[pq_tail].length      = (short)payload_len;
				packet_queue[pq_tail].from_player  = (short)from_player;
				pq_tail = (pq_tail + 1) % PACKET_QUEUE_SIZE;
			}

			/* Remove processed packet from buffer */
			recv_bufs[i].len -= total_len;
			if (recv_bufs[i].len > 0)
				memmove(recv_bufs[i].buf,
				        recv_bufs[i].buf + total_len, recv_bufs[i].len);
		}
	}
}

/* ---- CRC (kept for compatibility) ----
 * 
 * The initcrc(), getcrc(), and updatecrc16() functions are currently DORMANT.
 * The 4-byte wire format header [sender][dest][len_lo][len_hi] has no CRC field.
 * To enable CRC validation, the wire format must be bumped to 8 bytes to include
 * a 4-byte CRC checksum. This is a backwards-incompatible protocol change and would
 * require updating NET_PROTOCOL_VERSION and both sendpacket()/getpacket() to:
 *   (1) calculate CRC over the full payload
 *   (2) append CRC to transmitted packets
 *   (3) verify CRC on received packets
 * These functions are retained to facilitate that future protocol bump without
 * implementing CRC logic from scratch again.
 */

initcrc()
{
	int32_t i, j, k, a;
	for(j=0;j<256;j++)
	{
		k = (j<<8); a = 0;
		for(i=7;i>=0;i--)
		{
			if (((k^a)&0x8000) > 0)
				a = ((a<<1)&65535) ^ 0x1021;
			else
				a = ((a<<1)&65535);
			k = ((k<<1)&65535);
		}
		crctable[j] = (uint16_t)(a&65535);
	}
}

uint16_t getcrc(char *buffer, short bufleng)
{
	int32_t i;
	uint16_t j;
	j = 0;
	for(i=bufleng-1;i>=0;i--) updatecrc16(j,buffer[i]);
	return(j&65535);
}

setpackettimeout(int32_t datimeoutcount, int32_t daresendagaincount)
{
	int32_t i;
	timeoutcount = datimeoutcount;
	resendagaincount = daresendagaincount;
	for(i=0;i<numplayers;i++) lastsendtime[i] = totalclock;
}

/* ---- Public networking API ---- */

initmultiplayers(char damultioption, char dacomrateoption, char dapriority)
{
	int32_t i;
	int host_port = 0;
	int expected_players = 2;
	char *join_addr = NULL;

	(void)damultioption;
	(void)dacomrateoption;
	(void)dapriority;

	initcrc();

	for (i = 0; i < MAXPLAYERS; i++) {
		player_sockets[i] = INVALID_SOCKET;
		recv_bufs[i].len = 0;
		lastsendtime[i] = 0;
	}
	pq_head = pq_tail = 0;
	pq_count = 0;
	pq_dropped_packets = 0;
	is_host = 0;
	net_initialized = 0;

	/* Parse command line for --host, --join, --players */
	for (i = 1; i < _argc; i++) {
		if (strcmp(_argv[i], "--host") == 0 && i + 1 < _argc) {
			host_port = atoi(_argv[++i]);
			is_host = 1;
		} else if (strcmp(_argv[i], "--join") == 0 && i + 1 < _argc) {
			join_addr = _argv[++i];
		} else if (strcmp(_argv[i], "--players") == 0 && i + 1 < _argc) {
			expected_players = atoi(_argv[++i]);
			if (expected_players < 2) expected_players = 2;
			if (expected_players > MAXPLAYERS) expected_players = MAXPLAYERS;
		}
	}

	if (!host_port && !join_addr) {
		/* Single-player mode - no networking */
		numplayers = 1;
		myconnectindex = 0;
		connecthead = 0;
		connectpoint2[0] = -1;
		return;
	}

#ifdef _WIN32
	{
		WSADATA wsa;
		if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
			printf("NET: WSAStartup failed\n");
			goto singleplayer;
		}
	}
#endif

	if (is_host) {
		struct sockaddr_in addr;
		int opt = 1;
		time_t start;

		server_socket = socket(AF_INET, SOCK_STREAM, 0);
		if (server_socket == INVALID_SOCKET) {
			printf("NET: Failed to create server socket\n");
			goto singleplayer;
		}

		setsockopt(server_socket, SOL_SOCKET, SO_REUSEADDR,
		           (const char *)&opt, sizeof(opt));

		memset(&addr, 0, sizeof(addr));
		addr.sin_family = AF_INET;
		addr.sin_addr.s_addr = INADDR_ANY;
		addr.sin_port = htons((unsigned short)host_port);

		if (bind(server_socket, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
			printf("NET: Failed to bind port %d\n", host_port);
			net_close(server_socket);
			server_socket = INVALID_SOCKET;
			goto singleplayer;
		}

		listen(server_socket, MAXPLAYERS - 1);
		printf("NET: Hosting on port %d, waiting for %d player(s)...\n",
		       host_port, expected_players);

		net_set_nonblocking(server_socket);

		myconnectindex = 0;
		numplayers = 1;

		/* Accept connections until expected count or timeout */
		start = time(NULL);
		while (numplayers < expected_players) {
			struct sockaddr_in client_addr;
			socklen_t client_len = sizeof(client_addr);
			SOCKET client;

			if (time(NULL) - start > NET_CONNECT_TIMEOUT) {
				printf("NET: Timeout waiting for players (%d connected)\n",
				       numplayers);
				if (numplayers < 2) {
					net_close(server_socket);
					server_socket = INVALID_SOCKET;
					goto singleplayer;
				}
				break;
			}

			client = net_accept_timeout(server_socket,
			                            (struct sockaddr *)&client_addr, &client_len,
			                            NET_HOST_ACCEPT_TIMEOUT_SEC);
			if (client != INVALID_SOCKET) {
				int idx = numplayers;
				int flag = 1;

				player_sockets[idx] = client;
				setsockopt(client, IPPROTO_TCP, TCP_NODELAY,
				           (const char *)&flag, sizeof(flag));

				numplayers++;
				printf("NET: Player %d connected from %s\n",
				       idx, inet_ntoa(client_addr.sin_addr));
			}

			net_sleep(50);
		}

		printf("NET: Starting game with %d players\n", numplayers);

		/* Send handshake to each client: [player_index, numplayers, version_lo, version_hi] */
		for (i = 1; i < numplayers; i++) {
			unsigned char msg[4];
			msg[0] = (unsigned char)i;
			msg[1] = (unsigned char)numplayers;
		mm_pack_u16_le(msg + 2, NET_PROTOCOL_VERSION);
			net_send_raw(player_sockets[i], msg, 4);
			net_set_nonblocking(player_sockets[i]);
		}

	} else if (join_addr) {
		/* Client mode */
		char ip[64];
		int port = DEFAULT_PORT;
		char *colon;
		SOCKET sock;
		struct sockaddr_in addr;
		int flag;
		unsigned char msg[4];

		strncpy(ip, join_addr, sizeof(ip) - 1);
		ip[sizeof(ip) - 1] = '\0';
		colon = strchr(ip, ':');
		if (colon) {
			*colon = '\0';
			port = atoi(colon + 1);
		}

		sock = socket(AF_INET, SOCK_STREAM, 0);
		if (sock == INVALID_SOCKET) {
			printf("NET: Failed to create socket\n");
			goto singleplayer;
		}

		memset(&addr, 0, sizeof(addr));
		addr.sin_family = AF_INET;
		addr.sin_addr.s_addr = inet_addr(ip);
		addr.sin_port = htons((unsigned short)port);

		printf("NET: Connecting to %s:%d...\n", ip, port);
		if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
			printf("NET: Connection failed\n");
			net_close(sock);
			goto singleplayer;
		}

		flag = 1;
		setsockopt(sock, IPPROTO_TCP, TCP_NODELAY,
		           (const char *)&flag, sizeof(flag));

		/* Receive handshake: [player_index, numplayers, version_lo, version_hi] */
		if (net_recv_all(sock, msg, 4) != 4) {
			printf("NET: Handshake failed (timeout or connection closed)\n");
			net_close(sock);
			goto singleplayer;
		}

		/* Verify protocol version */
		uint16_t peer_version = mm_unpack_u16_le(msg + 2);
		if (peer_version != NET_PROTOCOL_VERSION) {
			printf("NET: Protocol version mismatch (expected 0x%04x, got 0x%04x)\n",
			       NET_PROTOCOL_VERSION, peer_version);
			net_close(sock);
			goto singleplayer;
		}

		myconnectindex = (short)msg[0];
		numplayers     = (short)msg[1];
		player_sockets[0] = sock;

		net_set_nonblocking(sock);

		printf("NET: Connected as player %d of %d\n",
		       myconnectindex, numplayers);
	}

	/* Build connected player linked list */
	connecthead = 0;
	for (i = 0; i < numplayers - 1; i++)
		connectpoint2[i] = (short)(i + 1);
	connectpoint2[numplayers - 1] = -1;

	for (i = 0; i < numplayers; i++)
		lastsendtime[i] = totalclock;

	net_initialized = 1;
	return;

singleplayer:
	numplayers = 1;
	myconnectindex = 0;
	connecthead = 0;
	connectpoint2[0] = -1;
}

uninitmultiplayers()
{
	int32_t i;
	unsigned char disconnect_pkt[NET_HEADER_SIZE + 1];

	if (!net_initialized) return;

	/* Send DISCONNECT (marker=0xFF) to all known peers before closing sockets */
	disconnect_pkt[0] = (unsigned char)myconnectindex;
	disconnect_pkt[1] = 255;  /* broadcast */
	mm_pack_u16_le(disconnect_pkt + 2, 1);  /* payload length = 1 */
	disconnect_pkt[4] = 0xFF; /* disconnect marker */
	
	for (i = 0; i < MAXPLAYERS; i++) {
		if (player_sockets[i] != INVALID_SOCKET) {
			net_send_raw(player_sockets[i], disconnect_pkt, NET_HEADER_SIZE + 1);
		}
	}

	/* Wait ~250ms for packets to drain from the wire */
	net_sleep(250);

	for (i = 0; i < MAXPLAYERS; i++) {
		if (player_sockets[i] != INVALID_SOCKET) {
			/* net-r11-player-disconnect-memset: zero sensitive per-player state on disconnect */
			memset(&recv_bufs[i], 0, sizeof(recv_bufs[i]));
			net_close(player_sockets[i]);
			player_sockets[i] = INVALID_SOCKET;
		}
	}
	if (server_socket != INVALID_SOCKET) {
		net_close(server_socket);
		server_socket = INVALID_SOCKET;
	}

#ifdef _WIN32
	WSACleanup();
#endif

	net_initialized = 0;
}

sendlogon()
{
}

sendlogoff()
{
	int32_t i;
	char tempbuf[2];

	tempbuf[0] = (char)255;
	tempbuf[1] = (char)myconnectindex;
	for(i=connecthead;i>=0;i=connectpoint2[i])
		if (i != myconnectindex)
			sendpacket(i,tempbuf,2L);
}

getoutputcirclesize()
{
	return(0);
}

setsocket(short newsocket)
{
	(void)newsocket;
}

sendpacket(int32_t other, char *bufptr, int32_t messleng)
{
	SOCKET sock;
	unsigned char header[NET_HEADER_SIZE];

	if (numplayers < 2 || !net_initialized) return;
	if (other == myconnectindex) return;
	if (messleng <= 0 || messleng > MAXPACKETSIZE) return;

	/* Validate other is in bounds (CRITICAL: other used as array index for player_sockets) */
	if (other < 0 || other >= MAXPLAYERS) {
		printf("NET: SECURITY: Invalid other=%d (out of bounds [0,%d)). Dropping packet.\n",
			other, MAXPLAYERS);
		return;
	}

	header[0] = (unsigned char)(myconnectindex & 0xFF);
	header[1] = (unsigned char)(other & 0xFF);
	mm_pack_u16_le(header + 2, (uint16_t)messleng);

	if (is_host) {
		sock = player_sockets[other];
	} else {
		sock = player_sockets[0]; /* everything routes through host */
	}

	if (sock == INVALID_SOCKET) return;

	net_send_raw(sock, header, NET_HEADER_SIZE);
	net_send_raw(sock, (const unsigned char *)bufptr, (int)messleng);

	lastsendtime[other] = totalclock;
}

short getpacket(short *other, char *bufptr)
{
	short len;

	if (numplayers < 2 || !net_initialized) return 0;

	net_poll_sockets();

	if (pq_head == pq_tail) return 0;

	*other = packet_queue[pq_head].from_player;
	len    = packet_queue[pq_head].length;
	memcpy(bufptr, packet_queue[pq_head].data, len);
	pq_head = (pq_head + 1) % PACKET_QUEUE_SIZE;

	return len;
}

flushpackets()
{
	int32_t i;

	if (numplayers < 2 || !net_initialized) return;

	/* Drain packet queue */
	pq_head = pq_tail = 0;

	/* Clear receive buffers */
	for (i = 0; i < MAXPLAYERS; i++)
		recv_bufs[i].len = 0;
}

genericmultifunction(long other, char *bufptr, long messleng, long command)
{
	(void)other;
	(void)bufptr;
	(void)messleng;
	(void)command;
}
