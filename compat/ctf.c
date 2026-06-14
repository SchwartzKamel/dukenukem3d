/* ctf.c — Atomic Shell CTF flag emission implementation */

#include "ctf.h"
#include <stdio.h>
#include <string.h>
#include <time.h>

static int   _captured[CTF_NUM_FLAGS]  = {0};
static char  _hud_msg[128]             = {0};
static int   _hud_pending              = 0;

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
}

const char *ctf_pending_hud_message(void)
{
    return _hud_pending ? _hud_msg : (const char *)0;
}

void ctf_clear_hud_message(void)
{
    _hud_pending = 0;
}
