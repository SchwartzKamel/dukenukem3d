/*
 * hud.h - Simple framebuffer HUD for Duke Nukem 3D compat layer
 *
 * Draws health, ammo, armor, and crosshair directly into the 8-bit
 * framebuffer using basic pixel operations, independent of the
 * original tile-based HUD system.
 */

#ifndef HUD_H
#define HUD_H

#ifdef __cplusplus
extern "C" {
#endif

/* Call once after engine init to set up HUD state */
void hud_init(void);

/* Draw the HUD overlay onto the current framebuffer.
 * Call after drawrooms()/animatesprites()/drawmasks() but before nextpage().
 * framebuf = pointer to 8-bit framebuffer
 * pitch    = bytes per scanline
 * width, height = screen dimensions
 */
void hud_draw(unsigned char *framebuf, int pitch, int width, int height,
              int health, int ammo, int armor, int current_weapon);

#ifdef __cplusplus
}
#endif

#endif /* HUD_H */
