/* ctf.h — Atomic Shell CTF flag emission (hackable-by-design challenge system)
 *
 * Five flags are hidden in the game. Each requires a different memory-hacking
 * technique to capture. This header is the single public interface.
 *
 * Flag indices:
 *   0 — GODMODE      (boss regen defeated)
 *   1 — SHIELD_DOWN  (RPG-only boss killed)
 *   2 — FROZEN_CLOCK (countdown timer frozen)
 *   3 — GHOST_WALK   (teleport to sealed room)
 *   4 — VAULT        (vault code discovered)
 */
#ifndef CTF_H
#define CTF_H

#ifdef __cplusplus
extern "C" {
#endif

#define CTF_NUM_FLAGS 5

/* Emit flag N. Writes to atomic_shell_flags.log and sets ctf_flags_captured[n].
 * No-ops if already captured. flag_text is the full ghvctf{...} string. */
void ctf_emit_flag(int n, const char *flag_text);

/* 1 if flag N has been emitted this session, 0 otherwise. */
int ctf_flag_captured(int n);

/* Reset all flags (call on new game / level load). */
void ctf_reset(void);

/* Pending HUD message from the last ctf_emit_flag call, or NULL.
 * Caller should copy or print then clear with ctf_clear_hud_message(). */
const char *ctf_pending_hud_message(void);
void ctf_clear_hud_message(void);

#ifdef __cplusplus
}
#endif
#endif /* CTF_H */
