/* msvc_unistd.h — Minimal unistd.h stub for MSVC
   MSVC doesn't have unistd.h but provides equivalents in io.h and direct.h */
#ifndef MSVC_UNISTD_H
#define MSVC_UNISTD_H

#ifdef _MSC_VER

#include <io.h>        /* open, close, read, write, lseek, access */
#include <direct.h>    /* getcwd, chdir, mkdir */
#include <process.h>   /* getpid */

/* access() mode flags */
#ifndef R_OK
#define R_OK 4
#define W_OK 2
#define F_OK 0
#endif

/* Redirect POSIX names to MSVC underscore-prefixed versions */
#ifndef access
#define access _access
#endif
#ifndef open
#define open _open
#endif
#ifndef close
#define close _close
#endif
#ifndef read
#define read _read
#endif
#ifndef write
#define write _write
#endif
#ifndef lseek
#define lseek _lseek
#endif
#ifndef unlink
#define unlink _unlink
#endif
#ifndef getcwd
#define getcwd _getcwd
#endif
#ifndef chdir
#define chdir _chdir
#endif

#endif /* _MSC_VER */
#endif /* MSVC_UNISTD_H */
