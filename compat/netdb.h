/* netdb shim: linuxbrew's i686-w64-mingw32 lacks <netdb.h>. On Windows builds
 * we forward to winsock2; on UNIX, we transparently include the system header. */
#ifndef _COMPAT_NETDB_SHIM_
#define _COMPAT_NETDB_SHIM_
#ifdef PLATFORM_WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#ifndef NI_MAXHOST
#define NI_MAXHOST 1025
#endif
#ifndef NI_MAXSERV
#define NI_MAXSERV 32
#endif
/* h_errno is a macro in MinGW (expands to WSAGetLastError()); do NOT declare. */
#else
/* Re-include the real system netdb.h. Use include_next so we don't loop. */
#include_next <netdb.h>
#endif
#endif
