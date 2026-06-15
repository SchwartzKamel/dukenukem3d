/* ctf.c — Atomic Shell CTF flag emission implementation */

#include "ctf.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int   _captured[CTF_NUM_FLAGS]  = {0};
static char  _hud_msg[128]             = {0};
static int   _hud_pending              = 0;

/* --- D1 telemetry state --------------------------------------------------- */
static long  _clk             = 0;     /* last totalclock from ctf_set_clock */
static int   _events_enabled  = -1;    /* lazy: 0 if DUKE3D_EVENTS=0, else 1 */
static int   _events_opened   = 0;     /* truncate the log on the first event */
#define CTF_MAX_EVENTS 32
static char  _ev_seen[CTF_MAX_EVENTS][24];
static int   _ev_seen_n       = 0;     /* (flag:stage) keys already emitted */

void ctf_set_clock(long clk)
{
    _clk = clk;
}

static int _events_on(void)
{
    if (_events_enabled < 0) {
        const char *e = getenv("DUKE3D_EVENTS");
        _events_enabled = (e && e[0] == '0') ? 0 : 1;   /* default on, local-first */
    }
    return _events_enabled;
}

/* Event-log path: DUKE3D_EVENT_LOG override (so parallel tests can isolate their
 * funnel), else the default next to the exe. Cached for the process lifetime. */
static const char *_ev_path(void)
{
    static const char *path = NULL;
    if (!path) {
        const char *e = getenv("DUKE3D_EVENT_LOG");
        path = (e && e[0]) ? e : "atomic_shell_events.jsonl";
    }
    return path;
}

/* Return 1 if `key` was already emitted this session; otherwise record it and
 * return 0. Caps at CTF_MAX_EVENTS (the funnel has ~12 distinct events). */
static int _ev_already(const char *key)
{
    int i;
    for (i = 0; i < _ev_seen_n; i++)
        if (strcmp(_ev_seen[i], key) == 0)
            return 1;
    if (_ev_seen_n < CTF_MAX_EVENTS) {
        strncpy(_ev_seen[_ev_seen_n], key, sizeof(_ev_seen[0]) - 1);
        _ev_seen[_ev_seen_n][sizeof(_ev_seen[0]) - 1] = '\0';
        _ev_seen_n++;
    }
    return 0;
}

void ctf_event(int flag, const char *stage, const char *detail, long clk)
{
    char key[24];
    FILE *fp;
    time_t now;
    char ts[32];

    if (!_events_on()) return;
    if (!stage) stage = "";

    snprintf(key, sizeof(key), "%d:%s", flag, stage);
    if (_ev_already(key)) return;   /* once per (flag,stage) per session */

    fp = fopen(_ev_path(), _events_opened ? "a" : "w");
    if (!fp) return;
    _events_opened = 1;

    now = time(NULL);
    strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%S", localtime(&now));
    /* detail is engine-controlled (no '"'/'\\'), so a plain %s is valid JSON. */
    fprintf(fp, "{\"ts\":\"%s\",\"clk\":%ld,\"flag\":%d,\"stage\":\"%s\",\"detail\":\"%s\"}\n",
            ts, clk, flag, stage, detail ? detail : "");
    fclose(fp);
}

void ctf_emit_flag(int n, const char *flag_text)
{
    FILE *fp;
    time_t now;
    char ts[32];

    if (n < 0 || n >= CTF_NUM_FLAGS) return;
    if (_captured[n]) return;   /* idempotent */

    _captured[n] = 1;

    /* --- write to flag log --- */
    fp = fopen("atomic_shell_flags.log", "a");
    if (fp)
    {
        now = time(NULL);
        strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%S", localtime(&now));
        fprintf(fp, "[%s] FLAG %d: %s\n", ts, n, flag_text ? flag_text : "");
        fclose(fp);
    }

    /* --- queue HUD message (caller polls ctf_pending_hud_message) --- */
    snprintf(_hud_msg, sizeof(_hud_msg),
             "FLAG CAPTURED: %s", flag_text ? flag_text : "???");
    _hud_pending = 1;

    /* --- also emit to stdout so it shows in the console window --- */
    printf("\n*** CTF FLAG %d CAPTURED: %s ***\n\n", n, flag_text ? flag_text : "");
    fflush(stdout);

    /* --- D1: funnel capture event (one place covers all 5 flags) --- */
    ctf_event(n, "capture", flag_text, _clk);
}

int ctf_flag_captured(int n)
{
    if (n < 0 || n >= CTF_NUM_FLAGS) return 0;
    return _captured[n];
}

void ctf_reset(void)
{
    memset(_captured, 0, sizeof(_captured));
    _hud_msg[0]  = '\0';
    _hud_pending = 0;
    /* D1: start a fresh funnel for the new level (next event truncates the log) */
    _ev_seen_n     = 0;
    _events_opened = 0;
}

const char *ctf_pending_hud_message(void)
{
    return _hud_pending ? _hud_msg : (const char *)0;
}

void ctf_clear_hud_message(void)
{
    _hud_pending = 0;
}
