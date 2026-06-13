// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef SDL_DRIVER_H
#define SDL_DRIVER_H

#include <stdint.h>
#include "compat.h"

/* Validate int32_t size (compat layer convention) */
_Static_assert(sizeof(int32_t) == 4, "int32_t must be exactly 4 bytes");

/* Video */
int sdl_init(int xdim, int ydim);
void sdl_shutdown(void);
void sdl_nextpage(void);
void sdl_setpalette(unsigned char *pal, int start, int num);
char *sdl_getscreen(void);
int32_t sdl_getbytesperline(void);

/* Input */
void sdl_pollevents(void);
int sdl_keystatus(int scancode);
void sdl_setkeystatus(int scancode, int state);
void sdl_getmouse(int *dx, int *dy, int *buttons);
int sdl_checkquit(void);
int sdl_quit_requested_get(void);

/* Timer */
void sdl_inittimer(void);
int32_t sdl_getticks(void);
void sdl_delay(int ms);

/* Frame capture (AI playtesting) */
int sdl_capture_frame(const char *filename);
int sdl_get_frame_count(void);

#endif
