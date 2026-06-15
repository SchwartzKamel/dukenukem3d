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
 *   5 — CODE_EXEC    (control-flow hijack: redirect a called-through hook)
 */
#ifndef CTF_H
#define CTF_H

#ifdef __cplusplus
extern "C" {
#endif

#define CTF_NUM_FLAGS 6

/* Emit flag N. Writes to atomic_shell_flags.log and sets ctf_flags_captured[n].
 * No-ops if already captured. flag_text is the full ghvctf{...} string. */
void ctf_emit_flag(int n, const char *flag_text);

/* 1 if flag N has been emitted this session, 0 otherwise. */
int ctf_flag_captured(int n);

/* Reset all flags (call on new game / level load). */
void ctf_reset(void);

/* --- D1 flag-funnel telemetry ----------------------------------------------
 * Append a structured funnel event to atomic_shell_events.jsonl (one JSON object
 * per line). `flag` is 0..4 (or -1 for session/level events), `stage` is one of
 * level_enter|enter|arm|unlock|progress|capture, `detail` is a short engine-
 * controlled literal (must contain no '"' or '\\'), `clk` is the caller's
 * totalclock. Each (flag,stage) pair is written at most once per session. No-op
 * if DUKE3D_EVENTS=0. The log is truncated on the first event of a session. */
void ctf_event(int flag, const char *stage, const char *detail, long clk);

/* Cache the engine clock so the `capture` event (emitted inside ctf_emit_flag)
 * can be timestamped without ctf.c including the game headers. */
void ctf_set_clock(long clk);

/* Pending HUD message from the last ctf_emit_flag call, or NULL.
 * Caller should copy or print then clear with ctf_clear_hud_message(). */
const char *ctf_pending_hud_message(void);
void ctf_clear_hud_message(void);

/* --- Flag 5 (CODE_EXEC): control-flow hijack ------------------------------
 * ctf_tick_hook is a function-pointer slot the engine calls once per CTF tick
 * (via ctf_run_tick_hook). It is NULL by default and nothing in normal play
 * sets it. The hack: write the published address of ctf_grant_codeexec() into
 * the slot, redirecting the engine's control flow to a function it never calls
 * — which emits flag 5. Teaches callback/vtable hijacking. */
extern void (*ctf_tick_hook)(void);
void ctf_grant_codeexec(void);   /* the "win" function; never called in normal flow */
void ctf_run_tick_hook(void);    /* call once per CTF tick; null-checks the slot */

#ifdef __cplusplus
}
#endif
#endif /* CTF_H */
