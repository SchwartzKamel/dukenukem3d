#ifndef SDL_DRIVER_H
#define SDL_DRIVER_H

#include <stdint.h>

/* Video */
int sdl_init(int xdim, int ydim);
void sdl_shutdown(void);
void sdl_nextpage(void);
void sdl_setpalette(unsigned char *pal, int start, int num);
char *sdl_getscreen(void);
long sdl_getbytesperline(void);

/* Input */
void sdl_pollevents(void);
int sdl_keystatus(int scancode);
void sdl_setkeystatus(int scancode, int state);
void sdl_getmouse(int *dx, int *dy, int *buttons);
int sdl_checkquit(void);

/* Timer */
void sdl_inittimer(void);
long sdl_getticks(void);
void sdl_delay(int ms);

/* Globals exposed to engine */
extern int sdl_quit_requested;

#endif
