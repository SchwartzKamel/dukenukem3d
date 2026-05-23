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
#include "sha256.h"  /* net-r17-hmac: HMAC-SHA256 + HKDF for player auth */
#include "../compat/net_socket.h"  /* net-r16-tcp-keepalive: TCP keepalive API */

/* Platform-specific networking */
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#include <netdb.h>
#include <bcrypt.h>
#include <iphlpapi.h>  /* net-r28-ipv6-zone-id: if_nametoindex for zone parsing */
#pragma comment(lib, "bcrypt.lib")
#pragma comment(lib, "iphlpapi.lib")
typedef int socklen_t;
#define net_close closesocket
#define net_sleep(ms) Sleep(ms)
#else
#include <sys/socket.h>
#include <sys/select.h>
#include <net/if.h>  /* net-r28-ipv6-zone-id: if_nametoindex for zone parsing */
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#include <netdb.h>
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
#define NET_HEADER_SIZE 5   /* net-r15-seqnum: [1B sender][1B dest][1B seq][2B payload length LE] */
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
#define NET_PROTOCOL_VERSION 0x0002  /* net-r17-hmac: bumped from 0x0001; HMAC-SHA256 handshake */

#define updatecrc16(crc,dat) crc = (((crc<<8)&65535)^crctable[((((unsigned short)crc)>>8)&65535)^dat])

uint16_t crctable[256];

extern volatile long totalclock; /* build-r16-lto-type: aligned to legacy K&R decl in BUILD.H */
extern long randomseed; /* net-r14-randomseed-sync: external RNG seed from GAME.C/CAVE.C */
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

/* net-r15-seqnum: Per-peer sequence number tracking */
/* Sender: monotonically incrementing sequence for each destination */
static unsigned char sender_sequence[MAXPLAYERS];
/* Receiver: last-seen sequence from each peer (for gap/reorder detection) */
static unsigned char last_seen_sequence[MAXPLAYERS];

/* net-r17-hmac: Per-session HMAC-SHA256 authentication state.
 * One symmetric 32-byte key per peer (host↔client_i).
 * Derived via HKDF-SHA256(salt=host_nonce||client_nonce,
 *                          ikm=zeros, info="AUTH_SPOOFING_V1").
 * session_key_valid[i] is set after handshake nonce exchange completes.
 * HMAC tag (32 bytes) is appended to every packet after session key is live.
 * Wire format: [ NET_HEADER(5B) ][ payload(NB) ][ HMAC-SHA256(32B) ]
 * Relay: host verifies with key[i], re-signs with key[dest] before forwarding.
 */
static unsigned char session_key[MAXPLAYERS][HMAC_SHA256_SIZE];
static int  session_key_valid[MAXPLAYERS];  /* 1 after HKDF derivation */
static unsigned char local_nonce[HMAC_SHA256_SIZE]; /* our ephemeral nonce */

/* net-r25-keepalive-error-semantics: Per-player peer address for diagnostic logging */
static struct sockaddr_storage player_peer_addr[MAXPLAYERS];
static int player_peer_addr_valid[MAXPLAYERS];

/* net-r26-recv-buf-near-full-diagnostic: Track per-player near-full warning state for hysteresis */
static int recv_buf_near_full_logged[MAXPLAYERS];

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
 *   - Sequence field in packet header: buf[2] (1 byte, no packing needed) [net-r15-seqnum]
 *   - Payload length field in packet header: buf[3] (lo), buf[4] (hi) [net-r15-seqnum]
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

/* Format IPv4/IPv6 address for logging (handles both AF_INET and AF_INET6) */
static const char *net_format_addr(const struct sockaddr_storage *addr)
{
	static char buf[128];
	const struct sockaddr_in *addr4 = (const struct sockaddr_in *)addr;
	const struct sockaddr_in6 *addr6 = (const struct sockaddr_in6 *)addr;

	if (addr->ss_family == AF_INET) {
#ifdef _WIN32
		snprintf(buf, sizeof(buf), "%s", inet_ntoa(addr4->sin_addr));
#else
		inet_ntop(AF_INET, &addr4->sin_addr, buf, sizeof(buf));
#endif
		return buf;
	} else if (addr->ss_family == AF_INET6) {
#ifdef _WIN32
		char tmp[128];
		DWORD len = sizeof(tmp);
		if (WSAAddressToStringA((struct sockaddr *)addr6, sizeof(struct sockaddr_in6),
		                        NULL, tmp, &len) == 0) {
			snprintf(buf, sizeof(buf), "%s", tmp);
			return buf;
		}
		return "[IPv6]";
#else
		inet_ntop(AF_INET6, &addr6->sin6_addr, buf, sizeof(buf));
		return buf;
#endif
	}
	return "[unknown]";
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
static SOCKET net_accept_timeout(SOCKET server_sock, struct sockaddr_storage *client_addr,
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

/* net-r17-hmac: Generate a cryptographically random 32-byte nonce.
 * POSIX: reads /dev/urandom.
 * Windows: uses BCryptGenRandom (CSPRNG) for cryptographic entropy.
 * Fallback (both platforms): if entropy source fails, use getentropy-style fallback. */
static void net_gen_nonce(unsigned char *nonce, int len)
{
	int i;
#ifdef _WIN32
	/* Windows: Use BCryptGenRandom for cryptographically secure random bytes */
	NTSTATUS status = BCryptGenRandom(NULL, nonce, len, BCRYPT_USE_SYSTEM_PREFERRED_RNG);
	if (BCRYPT_SUCCESS(status)) {
		return;
	}
	/* Fallback: if BCryptGenRandom fails, XOR rand() with time-based entropy */
	fprintf(stderr, "WARNING: BCryptGenRandom failed, using fallback entropy\n");
	for (i = 0; i < len; i++)
		nonce[i] = (unsigned char)(rand() & 0xFF);
#else
	/* POSIX: Try /dev/urandom first */
	FILE *f = fopen("/dev/urandom", "rb");
	if (f != NULL) {
		size_t read_count = fread(nonce, 1, (size_t)len, f);
		fclose(f);
		if (read_count == (size_t)len) {
			return;
		}
		/* Partial read: XOR in rand() bytes for remaining positions */
		for (i = 0; i < len; i++)
			nonce[i] ^= (unsigned char)(rand() & 0xFF);
		return;
	}
	/* Fallback: no /dev/urandom, use rand() */
	for (i = 0; i < len; i++)
		nonce[i] = (unsigned char)(rand() & 0xFF);
#endif
}

/* net-r17-hmac: Derive a 32-byte per-session HMAC key from two ephemeral nonces.
 * Design: HKDF-SHA256 with salt = host_nonce || client_nonce (64 bytes),
 *         IKM = 32 zero bytes (no pre-shared secret),
 *         info = "AUTH_SPOOFING_V1" (16 bytes, no null terminator).
 * Both peers run this with the same inputs → identical key. */
static void net_derive_session_key(const unsigned char *host_nonce,
                                   const unsigned char *client_nonce,
                                   unsigned char *key_out)
{
	/* salt = host_nonce || client_nonce */
	unsigned char salt[64];
	unsigned char ikm[32];
	/* Literal ASCII context string, per r17 design — NON-NEGOTIABLE. */
	static const unsigned char AUTH_INFO[] = {
		'A','U','T','H','_','S','P','O','O','F','I','N','G','_','V','1'
	};

	memcpy(salt,      host_nonce,   32);
	memcpy(salt + 32, client_nonce, 32);
	memset(ikm, 0, 32); /* no pre-shared secret */

	hkdf_sha256(salt, 64, ikm, 32, AUTH_INFO, 16, key_out, 32);
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
				/* net-r26-recv-buf-near-full-diagnostic: Warn once when buffer crosses threshold */
				if (recv_bufs[i].len > (RECV_BUF_SIZE - 4096) && !recv_buf_near_full_logged[i]) {
					const char *peer_str = "unknown";
					if (player_peer_addr_valid[i]) {
						peer_str = net_format_addr(&player_peer_addr[i]);
					}
					printf("NET: Player %d [%s] recv buffer near capacity: %d / %d bytes\n",
						i, peer_str, recv_bufs[i].len, RECV_BUF_SIZE);
					recv_buf_near_full_logged[i] = 1;
				}
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
			/* net-r25-keepalive-error-semantics: Log diagnostic when keepalive detects dead peer */
			if (net_socket_is_keepalive_error(err)) {
				const char *peer_str = "unknown";
				if (player_peer_addr_valid[i]) {
					peer_str = net_format_addr(&player_peer_addr[i]);
				}
#ifdef _WIN32
				printf("NET: Player %d [%s] disconnected: TCP keepalive detected dead peer (WSAERROR=%d)\n",
					i, peer_str, err);
#else
				printf("NET: Player %d [%s] disconnected: TCP keepalive detected dead peer (%s)\n",
					i, peer_str, err == ETIMEDOUT ? "ETIMEDOUT" : "ECONNRESET");
#endif
				/* net-r26-keepalive-socket-cleanup-immediate: Close socket immediately on keepalive error */
				net_close(player_sockets[i]);
				player_sockets[i] = INVALID_SOCKET;
				player_peer_addr_valid[i] = 0;
				memset(&recv_bufs[i], 0, sizeof(recv_bufs[i]));
				memset(session_key[i], 0, HMAC_SHA256_SIZE);
				session_key_valid[i] = 0;
			}
			break;
		}
		}

		/* Extract complete packets */
		while (recv_bufs[i].len >= NET_HEADER_SIZE) {
			int from_player = recv_bufs[i].buf[0];
			int dest        = recv_bufs[i].buf[1];
			int sequence    = recv_bufs[i].buf[2];  /* net-r15-seqnum: extract sequence */
			int payload_len = mm_unpack_u16_le(recv_bufs[i].buf + 3);  /* net-r15-seqnum: offset +3 for seq field */
			int total_len;
			/* net-r17-hmac: socket index i identifies the actual sender */
			int has_hmac = session_key_valid[i];

			/* engine-r29-mmulti-recv-buf-capacity-codify: Defense-in-depth check on recv buffer size */
			if (recv_bufs[i].len > RECV_BUF_SIZE) {
				printf("NET: Player %d recv buffer overflow detected: %d / %d bytes. Resetting.\n",
					i, recv_bufs[i].len, RECV_BUF_SIZE);
				recv_bufs[i].len = 0;
				break;
			}

			/* net-r26-recv-buf-near-full-diagnostic: Hysteresis clear when buffer drops below threshold/2 */
			if (recv_buf_near_full_logged[i] && recv_bufs[i].len < (RECV_BUF_SIZE - 4096) / 2) {
				recv_buf_near_full_logged[i] = 0;
			}

			/* Validate from_player bounds (CRITICAL: from_player is wire-supplied, attacker-controlled) */
			if (from_player < 0 || from_player >= MAXPLAYERS) {
				printf("NET: SECURITY: Invalid from_player=%d (out of bounds [0,%d)). Dropping packet.\n",
					from_player, MAXPLAYERS);
				recv_bufs[i].len -= NET_HEADER_SIZE;
				if (recv_bufs[i].len > 0)
					memmove(recv_bufs[i].buf, recv_bufs[i].buf + NET_HEADER_SIZE, recv_bufs[i].len);
				continue;
			}

			/* net-r15-seqnum: Log sequence gaps/reorders without dropping */
			{
				int expected_seq = (last_seen_sequence[from_player] + 1) & 0xFF;
				int is_first = (last_seen_sequence[from_player] == 0xFF);
				if (!is_first && sequence != expected_seq) {
					printf("NET: Sequence gap/reorder from player %d: expected %d, got %d\n",
						from_player, expected_seq, sequence);
				}
				last_seen_sequence[from_player] = sequence;
			}

			/* Validate bounds before relay-forwarding */
			if (payload_len <= 0 || payload_len > MAXPACKETSIZE - NET_HEADER_SIZE) {
				recv_bufs[i].len = 0;
				break;
			}

			/* net-r17-hmac: total_len accounts for appended HMAC tag when key is live */
			total_len = NET_HEADER_SIZE + payload_len + (has_hmac ? HMAC_SHA256_SIZE : 0);
			if (recv_bufs[i].len < total_len) break;

			/* net-r17-hmac: Verify HMAC tag using the actual sender's key (socket index i).
			 * Using socket index (not attacker-supplied from_player) prevents spoofing.
			 * Silent drop on mismatch per cycle-65 policy (SRC/MMULTI.C L316-318). */
			if (has_hmac) {
				unsigned char expected_tag[HMAC_SHA256_SIZE];
				const unsigned char *received_tag =
					recv_bufs[i].buf + NET_HEADER_SIZE + payload_len;
				hmac_sha256(session_key[i], HMAC_SHA256_SIZE,
				            recv_bufs[i].buf, (size_t)(NET_HEADER_SIZE + payload_len),
				            expected_tag);
				if (hmac_sha256_verify_ct(expected_tag, received_tag, HMAC_SHA256_SIZE) != 0) {
					/* Silent drop: HMAC mismatch — potential forgery or from_player spoof */
					printf("NET: SECURITY: HMAC mismatch from socket %d (from_player=%d). Dropping.\n",
					       i, from_player);
					pq_dropped_packets++;
					recv_bufs[i].len -= total_len;
					if (recv_bufs[i].len > 0)
						memmove(recv_bufs[i].buf,
						        recv_bufs[i].buf + total_len, recv_bufs[i].len);
					continue;
				}
			}

			/* Host: relay to destination client.
			 * net-r17-hmac: re-sign with destination's key so recipient can verify. */
			if (is_host && dest != 0 && dest > 0 && dest < numplayers) {
				if (player_sockets[dest] != INVALID_SOCKET) {
					if (has_hmac && session_key_valid[dest]) {
						/* Re-sign: compute new tag with dest's key */
						unsigned char relay_tag[HMAC_SHA256_SIZE];
						hmac_sha256(session_key[dest], HMAC_SHA256_SIZE,
						            recv_bufs[i].buf, (size_t)(NET_HEADER_SIZE + payload_len),
						            relay_tag);
						net_send_raw(player_sockets[dest],
						             recv_bufs[i].buf, NET_HEADER_SIZE + payload_len);
						net_send_raw(player_sockets[dest], relay_tag, HMAC_SHA256_SIZE);
					} else if (!has_hmac) {
						/* Legacy (pre-HMAC) relay — forward as-is */
						net_send_raw(player_sockets[dest], recv_bufs[i].buf, total_len);
					}
					/* else has_hmac && !session_key_valid[dest]: dest not ready, drop */
				}
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

	/* net-r14-crc-dormant: CRC helpers initialized but not validated per-packet.
	   See docs/ARCHITECTURE.md "Packet Integrity (current gap)" + audit r14. */
	initcrc();

	for (i = 0; i < MAXPLAYERS; i++) {
		player_sockets[i] = INVALID_SOCKET;
		recv_bufs[i].len = 0;
		lastsendtime[i] = 0;
		sender_sequence[i] = 0;  /* net-r15-seqnum: init to 0 */
		last_seen_sequence[i] = 0xFF;  /* net-r15-seqnum: init to 0xFF as sentinel (no packet yet) */
		/* net-r17-hmac: clear session keys */
		session_key_valid[i] = 0;
		memset(session_key[i], 0, HMAC_SHA256_SIZE);
	}
	memset(local_nonce, 0, HMAC_SHA256_SIZE); /* net-r17-hmac */
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
		struct sockaddr_storage addr;
		int opt = 1;
		int v6only = 0;  /* Enable dual-stack: IPv6 socket accepts IPv4-mapped IPv6 addresses */
		time_t start;

		server_socket = net_socket_create(AF_INET6, SOCK_STREAM, 0);
		if (server_socket == INVALID_SOCKET) {
			printf("NET: Failed to create server socket\n");
			goto singleplayer;
		}

		/* net-r16-tcp-keepalive: enable TCP keepalive on server socket */
		net_socket_enable_keepalive(server_socket);

		setsockopt(server_socket, SOL_SOCKET, SO_REUSEADDR,
		           (const char *)&opt, sizeof(opt));

		/* net-r3-ipv6: Disable IPV6_V6ONLY to enable dual-stack
		   (IPv6 socket accepts both IPv6 and IPv4-mapped IPv6 connections) */
#ifdef IPV6_V6ONLY
		setsockopt(server_socket, IPPROTO_IPV6, IPV6_V6ONLY,
		           (const char *)&v6only, sizeof(v6only));
#endif

		memset(&addr, 0, sizeof(addr));
		struct sockaddr_in6 *addr6 = (struct sockaddr_in6 *)&addr;
		addr6->sin6_family = AF_INET6;
		addr6->sin6_addr = in6addr_any;
		addr6->sin6_port = htons((unsigned short)host_port);

		if (bind(server_socket, (struct sockaddr *)&addr, sizeof(struct sockaddr_in6)) < 0) {
			printf("NET: Failed to bind port %d\n", host_port);
			net_close(server_socket);
			server_socket = INVALID_SOCKET;
			goto singleplayer;
		}

		listen(server_socket, MAXPLAYERS - 1);
		printf("NET: Hosting on port %d (IPv6 dual-stack), waiting for %d player(s)...\n",
		       host_port, expected_players);

		net_set_nonblocking(server_socket);

		myconnectindex = 0;
		numplayers = 1;

		/* Accept connections until expected count or timeout */
		start = time(NULL);
		while (numplayers < expected_players) {
			struct sockaddr_storage client_addr;
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
			                            &client_addr, &client_len,
			                            NET_HOST_ACCEPT_TIMEOUT_SEC);
			if (client != INVALID_SOCKET) {
				int idx = numplayers;
				int flag = 1;

				player_sockets[idx] = client;
				/* net-r25-keepalive-error-semantics: Store peer address for diagnostic logging */
				memcpy(&player_peer_addr[idx], &client_addr, sizeof(client_addr));
				player_peer_addr_valid[idx] = 1;
				/* net-r16-tcp-keepalive: enable TCP keepalive on accepted client socket */
				net_socket_enable_keepalive(client);
				net_socket_set_option(client, IPPROTO_TCP, TCP_NODELAY,
				                      (const char *)&flag, sizeof(flag));

				numplayers++;
				printf("NET: Player %d connected from %s\n",
				       idx, net_format_addr(&client_addr));
			}

			net_sleep(50);
		}

		printf("NET: Starting game with %d players\n", numplayers);

		/* Send handshake to each client: [player_index, numplayers, version_lo, version_hi, seed_le32]
		 * net-r14-randomseed-sync: host generates seed for deterministic RNG init.
		 * net-r17-hmac: extended to 40 bytes: 8 original + 32-byte host nonce.
		 * After sending, receive 32-byte client nonce and derive session key. */
		{
			unsigned long seed = (unsigned long)totalclock ^ 0x12345678UL;
			/* Generate one host nonce shared across all clients */
			net_gen_nonce(local_nonce, HMAC_SHA256_SIZE);  /* net-r17-hmac */
			for (i = 1; i < numplayers; i++) {
				/* net-r14-randomseed-sync: old format was unsigned char msg[8];
				 * that was: net_send_raw(player_sockets[i], msg, 8)
				 * net-r17-hmac: extended to 40 bytes (8 header + 32-byte nonce). */
				unsigned char msg[40]; /* net-r17-hmac: 8 bytes header + 32-byte nonce */
				unsigned char client_nonce_buf[HMAC_SHA256_SIZE];
				int nr;
				msg[0] = (unsigned char)i;
				msg[1] = (unsigned char)numplayers;
				mm_pack_u16_le(msg + 2, NET_PROTOCOL_VERSION);
				msg[4] = (unsigned char)(seed & 0xFF);
				msg[5] = (unsigned char)((seed >> 8) & 0xFF);
				msg[6] = (unsigned char)((seed >> 16) & 0xFF);
				msg[7] = (unsigned char)((seed >> 24) & 0xFF);
				memcpy(msg + 8, local_nonce, HMAC_SHA256_SIZE); /* net-r17-hmac: append host nonce */
				net_send_raw(player_sockets[i], msg, 40);

				/* net-r17-hmac: receive client nonce (blocking, within HANDSHAKE_TIMEOUT_SEC) */
				nr = net_recv_all(player_sockets[i], client_nonce_buf, HMAC_SHA256_SIZE);
				if (nr == HMAC_SHA256_SIZE) {
					net_derive_session_key(local_nonce, client_nonce_buf, session_key[i]);
					session_key_valid[i] = 1;
					printf("NET: HMAC session key derived for player %d\n", i);
				} else {
					printf("NET: WARNING: Nonce exchange failed for player %d (got %d bytes), HMAC disabled\n",
					       i, nr);
				}
				net_set_nonblocking(player_sockets[i]);
			}
			/* net-r14-randomseed-sync: host also initializes from shared seed */
			randomseed = (long)seed;
			srand((unsigned)randomseed);
		}

	} else if (join_addr) {
		/* Client mode: net-r3-ipv6 - dual-stack IPv4/IPv6 support via getaddrinfo */
		char host[64], port_str[16];
		char zone_id[16];  /* net-r28-ipv6-zone-id: RFC 4007 link-local zone identifier */
		int port = DEFAULT_PORT;
		char *colon;
		SOCKET sock;
		struct sockaddr_storage addr;
		int addrlen;
		int flag;
		unsigned char msg[4];
		struct addrinfo hints, *res, *rp;
		int gai_status;

		zone_id[0] = '\0';  /* Initialize zone_id as empty */
		strncpy(host, join_addr, sizeof(host) - 1);
		host[sizeof(host) - 1] = '\0';

		/* Parse address: handle [IPv6]:port and IPv4:port formats */
		if (host[0] == '[') {
			/* IPv6 literal: [::1]:port or [fe80::1%eth0]:port */
			char *bracket = strchr(host, ']');
			if (bracket) {
				*bracket = '\0';
				/* Extract zone-id before stripping brackets (RFC 4007) */
				char *percent = strchr(host + 1, '%');
				if (percent) {
					strncpy(zone_id, percent + 1, sizeof(zone_id) - 1);
					zone_id[sizeof(zone_id) - 1] = '\0';
					*percent = '\0';  /* Strip zone-id from host */
				}
				memmove(host, host + 1, strlen(host + 1) + 1);
				if (*(bracket + 1) == ':') {
					port = atoi(bracket + 2);
				}
			}
		} else {
			/* IPv4 or hostname: 192.168.1.1:port or localhost:port */
			colon = strchr(host, ':');
			if (colon) {
				*colon = '\0';
				port = atoi(colon + 1);
			}
			/* Check for zone-id in non-bracketed format (fe80::1%eth0) */
			char *percent = strchr(host, '%');
			if (percent) {
				strncpy(zone_id, percent + 1, sizeof(zone_id) - 1);
				zone_id[sizeof(zone_id) - 1] = '\0';
				*percent = '\0';  /* Strip zone-id from host */
			}
		}

		snprintf(port_str, sizeof(port_str), "%d", port);

		/* Resolve hostname/IP using getaddrinfo (supports both IPv4 and IPv6) */
		memset(&hints, 0, sizeof(hints));
		hints.ai_family = AF_UNSPEC;     /* Allow both IPv4 and IPv6 */
		hints.ai_socktype = SOCK_STREAM;
		hints.ai_flags = 0;

		gai_status = getaddrinfo(host, port_str, &hints, &res);
		if (gai_status != 0) {
			printf("NET: Failed to resolve %s:%d (%s)\n", host, port, gai_strerror(gai_status));
			goto singleplayer;
		}

		/* Try each address until successful connection */
		sock = INVALID_SOCKET;
		for (rp = res; rp != NULL; rp = rp->ai_next) {
			sock = net_socket_create(rp->ai_family, rp->ai_socktype, rp->ai_protocol);
			if (sock == INVALID_SOCKET) continue;

			if (connect(sock, rp->ai_addr, (int)rp->ai_addrlen) == 0) {
				/* Connection successful */
				memcpy(&addr, rp->ai_addr, rp->ai_addrlen);
				addrlen = (int)rp->ai_addrlen;
				
				/* net-r28-ipv6-zone-id-parsing-fix: Populate sin6_scope_id for link-local (RFC 4007) */
				if (zone_id[0] != '\0' && rp->ai_family == AF_INET6) {
					struct sockaddr_in6 *sa6 = (struct sockaddr_in6 *)&addr;
					uint32_t if_index = 0;
#ifdef _WIN32
					/* Windows: try if_nametoindex from iphlpapi.h */
					if_index = (uint32_t)if_nametoindex(zone_id);
#else
					/* POSIX: if_nametoindex from net/if.h */
					if_index = (uint32_t)if_nametoindex(zone_id);
#endif
					if (if_index == 0) {
						/* Try parsing as numeric index */
						char *end;
						long numeric_index = strtol(zone_id, &end, 10);
						if (end != zone_id && numeric_index > 0 && numeric_index <= 0xFFFFFFFFUL) {
							if_index = (uint32_t)numeric_index;
						}
					}
					if (if_index > 0) {
						sa6->sin6_scope_id = if_index;
						printf("NET: IPv6 link-local zone %%%s -> index %u\n", zone_id, if_index);
					} else {
						printf("NET: WARNING - IPv6 zone %%%s not found, using scope 0\n", zone_id);
					}
				}
				break;
			}
			net_close(sock);
			sock = INVALID_SOCKET;
		}

		freeaddrinfo(res);

		if (sock == INVALID_SOCKET) {
			printf("NET: Connection to %s:%d failed\n", host, port);
			goto singleplayer;
		}

		/* net-r16-tcp-keepalive: enable TCP keepalive on client socket */
		net_socket_enable_keepalive(sock);

		/* net-r25-keepalive-error-semantics: Store peer address (host) for diagnostic logging */
		memcpy(&player_peer_addr[0], &addr, addrlen);
		player_peer_addr_valid[0] = 1;

		flag = 1;
		net_socket_set_option(sock, IPPROTO_TCP, TCP_NODELAY,
		                       (const char *)&flag, sizeof(flag));

		/* Receive handshake from host.
		 * net-r17-hmac: extended protocol (0x0002) sends 40 bytes:
		 *   8 bytes: [idx, numplayers, ver_lo, ver_hi, seed_le32]
		 *  32 bytes: host nonce
		 * Then client sends back its own 32-byte nonce and both derive session key.
		 * net-r14-randomseed-sync: client receives seed from host. */
		{
			int hs_len;
			unsigned long seed;
			unsigned char msg_full[8];
			uint16_t peer_version;

			hs_len = net_recv_all(sock, msg_full, 8);
			if (hs_len == 8) {
				peer_version = mm_unpack_u16_le(msg_full + 2);
				if (peer_version != NET_PROTOCOL_VERSION) {
					printf("NET: Protocol version mismatch (expected 0x%04x, got 0x%04x)\n",
					       NET_PROTOCOL_VERSION, peer_version);
					net_close(sock);
					goto singleplayer;
				}
				myconnectindex = (short)msg_full[0];
				numplayers = (short)msg_full[1];
				/* Extract randomseed from bytes 4-7 (little-endian) */
				seed = (unsigned long)(msg_full[4] | (msg_full[5] << 8) |
						       (msg_full[6] << 16) | (msg_full[7] << 24));
				randomseed = seed;
				/* net-r14-randomseed-sync: set RNG seed from handshake */
				srand((unsigned)randomseed);

				/* net-r17-hmac: receive host nonce, send our nonce, derive session key */
				{
					unsigned char host_nonce_buf[HMAC_SHA256_SIZE];
					int nr = net_recv_all(sock, host_nonce_buf, HMAC_SHA256_SIZE);
					if (nr == HMAC_SHA256_SIZE) {
						net_gen_nonce(local_nonce, HMAC_SHA256_SIZE);
						net_send_raw(sock, local_nonce, HMAC_SHA256_SIZE);
						net_derive_session_key(host_nonce_buf, local_nonce, session_key[0]);
						session_key_valid[0] = 1;
						printf("NET: HMAC session key derived\n");
					} else {
						printf("NET: WARNING: Failed to receive host nonce (%d bytes), HMAC disabled\n", nr);
					}
				}
			} else if (hs_len == 4) {
				/* Legacy 4-byte handshake (backward-compat: no randomseed, no HMAC).
				 * net-r14-randomseed-sync: legacy path does not sync RNG seed. */
				printf("NET: WARNING: Legacy 4-byte handshake detected; RNG may diverge; HMAC disabled\n");
				peer_version = mm_unpack_u16_le(msg_full + 2);
				if (peer_version != NET_PROTOCOL_VERSION) {
					printf("NET: Protocol version mismatch (expected 0x%04x, got 0x%04x)\n",
					       NET_PROTOCOL_VERSION, peer_version);
					net_close(sock);
					goto singleplayer;
				}
				myconnectindex = (short)msg_full[0];
				numplayers = (short)msg_full[1];
				/* Seed from time as fallback (original behavior) */
				randomseed = (long)time(NULL);
				srand((unsigned)randomseed);
				/* session_key_valid[0] remains 0: HMAC disabled for this connection */
			} else {
				printf("NET: Handshake failed (expected 4 or 8 bytes, got %d)\n", hs_len);
				net_close(sock);
				goto singleplayer;
			}
		}
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
	disconnect_pkt[2] = sender_sequence[0];  /* net-r15-seqnum: include sequence number */
	mm_pack_u16_le(disconnect_pkt + 3, 1);  /* net-r15-seqnum: payload length = 1 at offset +3 */
	disconnect_pkt[5] = 0xFF; /* disconnect marker */
	
	for (i = 0; i < MAXPLAYERS; i++) {
		if (player_sockets[i] != INVALID_SOCKET) {
			/* net-r17-hmac: tag disconnect packet if session key is live */
			int key_idx = is_host ? i : 0;
			if (session_key_valid[key_idx]) {
				unsigned char disc_tag[HMAC_SHA256_SIZE];
				hmac_sha256(session_key[key_idx], HMAC_SHA256_SIZE,
				            disconnect_pkt, NET_HEADER_SIZE + 1,
				            disc_tag);
				net_send_raw(player_sockets[i], disconnect_pkt, NET_HEADER_SIZE + 1);
				net_send_raw(player_sockets[i], disc_tag, HMAC_SHA256_SIZE);
			} else {
				net_send_raw(player_sockets[i], disconnect_pkt, NET_HEADER_SIZE + 1);
			}
		}
	}

	/* Wait ~250ms for packets to drain from the wire */
	net_sleep(250);

	for (i = 0; i < MAXPLAYERS; i++) {
		if (player_sockets[i] != INVALID_SOCKET) {
			/* net-r11-player-disconnect-memset: zero sensitive per-player state on disconnect */
			memset(&recv_bufs[i], 0, sizeof(recv_bufs[i]));
			/* net-r17-hmac: wipe session key on disconnect */
			memset(session_key[i], 0, HMAC_SHA256_SIZE);
			session_key_valid[i] = 0;
			recv_buf_near_full_logged[i] = 0;
			net_close(player_sockets[i]);
			player_sockets[i] = INVALID_SOCKET;
		}
	}
	memset(local_nonce, 0, HMAC_SHA256_SIZE); /* net-r17-hmac: wipe local nonce */
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
	header[2] = sender_sequence[other];  /* net-r15-seqnum: include sequence number */
	mm_pack_u16_le(header + 3, (uint16_t)messleng);  /* net-r15-seqnum: offset +3 for seq field */
	sender_sequence[other]++;  /* net-r15-seqnum: increment and wrap at 256 */

	if (is_host) {
		sock = player_sockets[other];
	} else {
		sock = player_sockets[0]; /* everything routes through host */
	}

	if (sock == INVALID_SOCKET) return;

	/* net-r17-hmac: append HMAC-SHA256 tag when session key is live.
	 * Tag covers header || payload to prevent both header and payload tampering.
	 * Key index: is_host → key[other];  client → key[0] (the host connection key). */
	{
		int key_idx = is_host ? other : 0;
		if (session_key_valid[key_idx]) {
			/* Build HMAC input: header (5B) || payload (messleng B) */
			unsigned char hmac_input[NET_HEADER_SIZE + MAXPACKETSIZE];
			unsigned char hmac_tag[HMAC_SHA256_SIZE];
			memcpy(hmac_input, header, NET_HEADER_SIZE);
			memcpy(hmac_input + NET_HEADER_SIZE, bufptr, (size_t)messleng);
			hmac_sha256(session_key[key_idx], HMAC_SHA256_SIZE,
			            hmac_input, (size_t)(NET_HEADER_SIZE + messleng),
			            hmac_tag);
			net_send_raw(sock, header, NET_HEADER_SIZE);
			net_send_raw(sock, (const unsigned char *)bufptr, (int)messleng);
			net_send_raw(sock, hmac_tag, HMAC_SHA256_SIZE);
		} else {
			net_send_raw(sock, header, NET_HEADER_SIZE);
			net_send_raw(sock, (const unsigned char *)bufptr, (int)messleng);
		}
	}

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
