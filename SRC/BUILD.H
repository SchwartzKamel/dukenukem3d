// "Build Engine & Tools" Copyright (c) 1993-1997 Ken Silverman
// Ken Silverman's official web site: "http://www.advsys.net/ken"
// See the included license file "BUILDLIC.TXT" for license info.

#ifndef BUILD_H_
#define BUILD_H_
#pragma once

#include <stdint.h>

#define MAXSECTORS 1024
#define MAXWALLS 8192
#define MAXSPRITES 4096

#define MAXTILES 9216
#define MAXSTATUS 1024
#define MAXPLAYERS 16
#define MAXXDIM 1600
#define MAXYDIM 1200
#define MAXPALOOKUPS 256
#define MAXPSKYTILES 256
#define MAXSPRITESONSCREEN 1024

#define CLIPMASK0 (((1L)<<16)+1L)
#define CLIPMASK1 (((256L)<<16)+64L)

	//Make all variables in BUILD.H defined in the ENGINE,
	//and externed in GAME
#ifdef ENGINE
	#define EXTERN
#else
	#define EXTERN extern
#endif

#pragma pack(push,1)

//ceilingstat/floorstat:
//   bit 0: 1 = parallaxing, 0 = not                                 "P"
//   bit 1: 1 = groudraw, 0 = not
//   bit 2: 1 = swap x&y, 0 = not                                    "F"
//   bit 3: 1 = double smooshiness                                   "E"
//   bit 4: 1 = x-flip                                               "F"
//   bit 5: 1 = y-flip                                               "F"
//   bit 6: 1 = Align texture to first wall of sector                "R"
//   bits 7-8:                                                       "T"
//          00 = normal floors
//          01 = masked floors
//          10 = transluscent masked floors
//          11 = reverse transluscent masked floors
//   bits 9-15: reserved

	//40 bytes
typedef struct
{
	short wallptr, wallnum;
	int32_t ceilingz, floorz;
	short ceilingstat, floorstat;
	short ceilingpicnum, ceilingheinum;
	signed char ceilingshade;
	char ceilingpal, ceilingxpanning, ceilingypanning;
	short floorpicnum, floorheinum;
	signed char floorshade;
	char floorpal, floorxpanning, floorypanning;
	char visibility, filler;
	short lotag, hitag, extra;
} sectortype;

//cstat:
//   bit 0: 1 = Blocking wall (use with clipmove, getzrange)         "B"
//   bit 1: 1 = bottoms of invisible walls swapped, 0 = not          "2"
//   bit 2: 1 = align picture on bottom (for doors), 0 = top         "O"
//   bit 3: 1 = x-flipped, 0 = normal                                "F"
//   bit 4: 1 = masking wall, 0 = not                                "M"
//   bit 5: 1 = 1-way wall, 0 = not                                  "1"
//   bit 6: 1 = Blocking wall (use with hitscan / cliptype 1)        "H"
//   bit 7: 1 = Transluscence, 0 = not                               "T"
//   bit 8: 1 = y-flipped, 0 = normal                                "F"
//   bit 9: 1 = Transluscence reversing, 0 = normal                  "T"
//   bits 10-15: reserved

	//32 bytes
typedef struct
{
	int32_t x, y;
	short point2, nextwall, nextsector, cstat;
	short picnum, overpicnum;
	signed char shade;
	char pal, xrepeat, yrepeat, xpanning, ypanning;
	short lotag, hitag, extra;
} walltype;

//cstat:
//   bit 0: 1 = Blocking sprite (use with clipmove, getzrange)       "B"
//   bit 1: 1 = transluscence, 0 = normal                            "T"
//   bit 2: 1 = x-flipped, 0 = normal                                "F"
//   bit 3: 1 = y-flipped, 0 = normal                                "F"
//   bits 5-4: 00 = FACE sprite (default)                            "R"
//             01 = WALL sprite (like masked walls)
//             10 = FLOOR sprite (parallel to ceilings&floors)
//   bit 6: 1 = 1-sided sprite, 0 = normal                           "1"
//   bit 7: 1 = Real centered centering, 0 = foot center             "C"
//   bit 8: 1 = Blocking sprite (use with hitscan / cliptype 1)      "H"
//   bit 9: 1 = Transluscence reversing, 0 = normal                  "T"
//   bits 10-14: reserved
//   bit 15: 1 = Invisible sprite, 0 = not invisible

	//44 bytes
typedef struct
{
	int32_t x, y, z;
	short cstat, picnum;
	signed char shade;
	char pal, clipdist, filler;
	unsigned char xrepeat, yrepeat;
	signed char xoffset, yoffset;
	short sectnum, statnum;
	short ang, owner, xvel, yvel, zvel;
	short lotag, hitag, extra;
} spritetype;

#pragma pack(pop)

/* Verify packed struct sizes match the BUILD engine binary format */
#if defined(__GNUC__) || defined(__clang__)
_Static_assert(sizeof(sectortype) == 40, "sectortype must be 40 bytes");
_Static_assert(sizeof(walltype) == 32, "walltype must be 32 bytes");
_Static_assert(sizeof(spritetype) == 44, "spritetype must be 44 bytes");
#elif defined(_MSC_VER)
static_assert(sizeof(sectortype) == 40, "sectortype must be 40 bytes");
static_assert(sizeof(walltype) == 32, "walltype must be 32 bytes");
static_assert(sizeof(spritetype) == 44, "spritetype must be 44 bytes");
#endif

EXTERN sectortype sector[MAXSECTORS];
EXTERN walltype wall[MAXWALLS];
EXTERN spritetype sprite[MAXSPRITES];

EXTERN long spritesortcnt;
EXTERN spritetype tsprite[MAXSPRITESONSCREEN];

EXTERN char vidoption;
EXTERN long xdim, ydim, ylookup[MAXYDIM+1], numpages;
EXTERN long yxaspect, viewingrange;

EXTERN long validmodecnt;
EXTERN short validmode[256];
EXTERN long validmodexdim[256], validmodeydim[256];

EXTERN short numsectors, numwalls;
EXTERN volatile long totalclock;
EXTERN long numframes, randomseed;
EXTERN short sintable[2048];
EXTERN char palette[768];
EXTERN short numpalookups;
EXTERN char *palookup[MAXPALOOKUPS];
EXTERN char parallaxtype, showinvisibility;
EXTERN long parallaxyoffs, parallaxyscale;
EXTERN long visibility, parallaxvisibility;

EXTERN long windowx1, windowy1, windowx2, windowy2;
EXTERN short startumost[MAXXDIM], startdmost[MAXXDIM];

EXTERN short pskyoff[MAXPSKYTILES], pskybits;

EXTERN short headspritesect[MAXSECTORS+1], headspritestat[MAXSTATUS+1];
EXTERN short prevspritesect[MAXSPRITES], prevspritestat[MAXSPRITES];
EXTERN short nextspritesect[MAXSPRITES], nextspritestat[MAXSPRITES];

EXTERN short tilesizx[MAXTILES], tilesizy[MAXTILES];
EXTERN char walock[MAXTILES];
EXTERN long numtiles, picanm[MAXTILES], waloff[MAXTILES];

	//These variables are for auto-mapping with the draw2dscreen function.
	//When you load a new board, these bits are all set to 0 - since
	//you haven't mapped out anything yet.  Note that these arrays are
	//bit-mapped.
	//If you want draw2dscreen() to show sprite #54 then you say:
	//   spritenum = 54;
	//   show2dsprite[spritenum>>3] |= (1<<(spritenum&7));
	//And if you want draw2dscreen() to not show sprite #54 then you say:
	//   spritenum = 54;
	//   show2dsprite[spritenum>>3] &= ~(1<<(spritenum&7));
	//Automapping defaults to 0 (do nothing).  If you set automapping to 1,
	//   then in 3D mode, the walls and sprites that you see will show up the
	//   next time you flip to 2D mode.

EXTERN char show2dsector[(MAXSECTORS+7)>>3];
EXTERN char show2dwall[(MAXWALLS+7)>>3];
EXTERN char show2dsprite[(MAXSPRITES+7)>>3];
EXTERN char automapping;

EXTERN char gotpic[(MAXTILES+7)>>3];
EXTERN char gotsector[(MAXSECTORS+7)>>3];

/*************************************************************************
POSITION VARIABLES:

		POSX is your x - position ranging from 0 to 65535
		POSY is your y - position ranging from 0 to 65535
			(the length of a side of the grid in EDITBORD would be 1024)
		POSZ is your z - position (height) ranging from 0 to 65535, 0 highest.
		ANG is your angle ranging from 0 to 2047.  Instead of 360 degrees, or
			 2 * PI radians, I use 2048 different angles, so 90 degrees would
			 be 512 in my system.

SPRITE VARIABLES:

	EXTERN short headspritesect[MAXSECTORS+1], headspritestat[MAXSTATUS+1];
	EXTERN short prevspritesect[MAXSPRITES], prevspritestat[MAXSPRITES];
	EXTERN short nextspritesect[MAXSPRITES], nextspritestat[MAXSPRITES];

	Example: if the linked lists look like the following:
		 ��������������������������������������������������������������Ŀ
		 �      Sector lists:               Status lists:               �
		 ��������������������������������������������������������������Ĵ
		 �  Sector0:  4, 5, 8             Status0:  2, 0, 8             �
		 �  Sector1:  16, 2, 0, 7         Status1:  4, 5, 16, 7, 3, 9   �
		 �  Sector2:  3, 9                                              �
		 ����������������������������������������������������������������
	Notice that each number listed above is shown exactly once on both the
		left and right side.  This is because any sprite that exists must
		be in some sector, and must have some kind of status that you define.


Coding example #1:
	To go through all the sprites in sector 1, the code can look like this:

		sectnum = 1;
		i = headspritesect[sectnum];
		while (i != -1)
		{
			nexti = nextspritesect[i];

			//your code goes here
			//ex: printf("Sprite %d is in sector %d\n",i,sectnum);

			i = nexti;
		}

Coding example #2:
	To go through all sprites with status = 1, the code can look like this:

		statnum = 1;        //status 1
		i = headspritestat[statnum];
		while (i != -1)
		{
			nexti = nextspritestat[i];

			//your code goes here
			//ex: printf("Sprite %d has a status of 1 (active)\n",i,statnum);

			i = nexti;
		}

			 insertsprite(short sectnum, short statnum);
			 deletesprite(short spritenum);
			 changespritesect(short spritenum, short newsectnum);
			 changespritestat(short spritenum, short newstatnum);

TILE VARIABLES:
		NUMTILES - the number of tiles found TILES.DAT.
		TILESIZX[MAXTILES] - simply the x-dimension of the tile number.
		TILESIZY[MAXTILES] - simply the y-dimension of the tile number.
		WALOFF[MAXTILES] - the actual 32-bit offset pointing to the top-left
								 corner of the tile.
		PICANM[MAXTILES] - flags for animating the tile.

TIMING VARIABLES:
		TOTALCLOCK - When the engine is initialized, TOTALCLOCK is set to zero.
			From then on, it is incremented 120 times a second by 1.  That
			means that the number of seconds elapsed is totalclock / 120.
		NUMFRAMES - The number of times the draw3dscreen function was called
			since the engine was initialized.  This helps to determine frame
			rate.  (Frame rate = numframes * 120 / totalclock.)

OTHER VARIABLES:

		STARTUMOST[320] is an array of the highest y-coordinates on each column
				that my engine is allowed to write to.  You need to set it only
				once.
		STARTDMOST[320] is an array of the lowest y-coordinates on each column
				that my engine is allowed to write to.  You need to set it only
				once.
		SINTABLE[2048] is a sin table with 2048 angles rather than the
			normal 360 angles for higher precision.  Also since SINTABLE is in
			all integers, the range is multiplied by 16383, so instead of the
			normal -1<sin(x)<1, the range of sintable is -16383<sintable[]<16383
			If you use this sintable, you can possibly speed up your code as
			well as save space in memory.  If you plan to use sintable, 2
			identities you may want to keep in mind are:
				sintable[ang&2047]       = sin(ang * (3.141592/1024)) * 16383
				sintable[(ang+512)&2047] = cos(ang * (3.141592/1024)) * 16383
		NUMSECTORS - the total number of existing sectors.  Modified every time
			you call the loadboard function.
***************************************************************************/

/* ======================================================================
 * BUILD Engine API function declarations
 * These are implemented in ENGINE.C and CACHE1D.C
 * ====================================================================== */
#ifndef ENGINE

/* Engine core */
int initengine(void);
void uninitengine(void);
int setgamemode(char vidopt, long daxdim, long daydim);
void nextpage(void);
int loadboard(char *filename, int32_t *daposx, int32_t *daposy, int32_t *daposz, short *daang, short *dacursectnum);
int saveboard(char *filename, int32_t *daposx, int32_t *daposy, int32_t *daposz, short *daang, short *dacursectnum);
int loadpics(char *filename, long asession);
void setview(long x1, long y1, long x2, long y2);
void setbrightness(char brightness, char *dapal);

/* 3D Rendering */
void drawrooms(long daposx, long daposy, long daposz, short daang, long dahoriz, short dacursectnum);
void drawmasks(void);
int setsprite(short spritenum, long newx, long newy, long newz);
void dorotatesprite(long sx, long sy, long z, short a, short picnum, signed char dashade, char dapalnum, char dastat, long cx1, long cy1, long cx2, long cy2);
void rotatesprite(long sx, long sy, long z, short a, short picnum, signed char dashade, char dapalnum, char dastat, long cx1, long cy1, long cx2, long cy2);
void clearview(long dacol);
void clearallviews(long dacol);
void drawline256(long x1, long y1, long x2, long y2, char col);
void printext256(long xpos, long ypos, short col, short backcol, char *name, char fontsize);
void printext16(long xpos, long ypos, short col, short backcol, char *name, char fontsize);

/* Sprite management */
short insertsprite(short sectnum, short statnum);
short deletesprite(short spritenum);
short changespritesect(short spritenum, short newsectnum);
short changespritestat(short spritenum, short newstatnum);

/* Map queries */
void updatesector(long x, long y, short *sectnum);
void updatesectorz(long x, long y, long z, short *sectnum);
int cansee(long x1, long y1, long z1, short sect1, long x2, long y2, long z2, short sect2);
void hitscan(long xs, long ys, long zs, short sectnum, long vx, long vy, long vz, short *hitsect, short *hitwall, short *hitsprite, long *hitx, long *hity, long *hitz, unsigned long cliptype);
void neartag(long xs, long ys, long zs, short sectnum, short ange, short *neartagsector, short *neartagwall, short *neartagsprite, long *neartaghitdist, long neartagrange, char tagsearch);
int clipmove(int32_t *x, int32_t *y, int32_t *z, short *sectnum, long xvect, long yvect, long walldist, long ceildist, long flordist, unsigned long cliptype);
void pushmove(int32_t *x, int32_t *y, int32_t *z, short *sectnum, long walldist, long ceildist, long flordist, unsigned long cliptype);
void getzrange(long x, long y, long z, short sectnum, long *ceilz, long *ceilhit, long *florz, long *florhit, long walldist, unsigned long cliptype);
long getangle(long xvect, long yvect);
long ksqrt(long num);
void rotatepoint(long xpivot, long ypivot, long x, long y, short daang, int32_t *x2, int32_t *y2);
long inside(long x, long y, short sectnum);
long FindDistance2D(long x, long y);
long FindDistance3D(long x, long y, long z);

/* Cache/file system */
void initcache(long dacachestart, long dacachesize);
void allocache(long *newhandle, long newbytes, char *newlockptr);
int kopen4load(char *filename, char searchfirst);
long kread(long handle, void *buffer, long leng);
long klseek(long handle, long offset, long whession);
long kfilelength(long handle);
void kclose(long handle);
void kdfread(void *buf, long size, long count, long fil);
void kdfwrite(void *buf, long size, long count, long fil);

/* Palette / lookup */
void makepalookup(long palnum, char *remapbuf, signed char r, signed char g, signed char b, char daession);

/* Mirrors */
void preparemirror(long dax, long day, long daz, short daang, long dahoriz, short dawall, short dasector, long *tposx, long *tposy, short *tang);
void completemirror(void);

/* Animation */
long animateoffs(short tilenum, short fession);

/* Timing */
void faketimerhandler(void);

/* RNG */
long krand(void);

/* Misc */
long getkensmessagecrc(long param);
void copytilepiece(long a1, long a2, long a3, long a4, long a5, long a6, long a7, long a8);
void drawoverheadmap(long cposx, long cposy, long czoom, short cang);
long setviewcnt;
void setviewtotile(short tilenume, long xsiz, long ysiz);
void setviewback(void);
void squarerotatetile(short tilenume);
void flushperms(void);
long initgroupfile(char *filename);
void uninitgroupfile(void);

#endif /* !ENGINE */

#endif /* BUILD_H_ */
