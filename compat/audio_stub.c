/*
 * audio_stub.c - Stub implementations of DOS audiolib, MACT, and keyboard APIs
 *
 * Replaces ~40K lines of DOS sound-card drivers and the precompiled MACT
 * control library with minimal stubs that compile on modern systems.
 *
 * FX_* / MUSIC_* functions are silent no-ops returning success.
 * TS_* (timer) provides a working SDL_GetTicks()-based task scheduler.
 * KB_* provides a keyboard queue wired into the SDL event layer.
 * CONTROL_* provides input mapping with SDL keyboard/mouse integration.
 * USRHOOKS_* delegates to malloc/free.
 */

#include "audio_stub.h"
#include "sdl_driver.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include "SDL.h"

/* ═══════════════════════════════════════════════════════════════════
   FX (Sound Effects) – silent stubs
   ═══════════════════════════════════════════════════════════════════ */

int FX_ErrorCode = FX_Ok;

static int  fx_volume      = 255;
static int  fx_reverb      = 0;
static int  fx_reverb_delay = 0;
static int  fx_reverse_stereo = 0;
static void (*fx_callback)(unsigned long) = NULL;

char *FX_ErrorString(int ErrorNumber)
{
    switch (ErrorNumber) {
    case FX_Ok:             return "FX ok.";
    case FX_Warning:        return "FX warning.";
    case FX_Error:          return "FX error.";
    case FX_ASSVersion:     return "FX ASS version error.";
    case FX_BlasterError:   return "FX Sound Blaster error.";
    case FX_SoundCardError: return "FX sound card error.";
    case FX_InvalidCard:    return "FX invalid card.";
    case FX_MultiVocError:  return "FX multivoc error.";
    case FX_DPMI_Error:     return "FX DPMI error.";
    default:                return "FX unknown error.";
    }
}

int FX_SetupCard(int SoundCard, fx_device *device)
{
    (void)SoundCard;
    if (device) {
        device->MaxVoices    = 8;
        device->MaxSampleBits = 16;
        device->MaxChannels  = 2;
    }
    return FX_Ok;
}

int FX_GetBlasterSettings(fx_blaster_config *blaster)
{
    if (blaster) memset(blaster, 0, sizeof(*blaster));
    return FX_Ok;
}

int FX_SetupSoundBlaster(fx_blaster_config blaster, int *MaxVoices,
                          int *MaxSampleBits, int *MaxChannels)
{
    (void)blaster;
    if (MaxVoices)    *MaxVoices    = 8;
    if (MaxSampleBits) *MaxSampleBits = 16;
    if (MaxChannels)  *MaxChannels  = 2;
    return FX_Ok;
}

int FX_Init(int SoundCard, int numvoices, int numchannels,
            int samplebits, unsigned mixrate)
{
    (void)SoundCard; (void)numvoices; (void)numchannels;
    (void)samplebits; (void)mixrate;
    fx_volume = 255;
    return FX_Ok;
}

int FX_Shutdown(void)
{
    fx_callback = NULL;
    return FX_Ok;
}

int FX_SetCallBack(void (*function)(unsigned long))
{
    fx_callback = function;
    return FX_Ok;
}

void FX_SetVolume(int volume)   { fx_volume = volume; }
int  FX_GetVolume(void)         { return fx_volume; }

void FX_SetReverseStereo(int setting) { fx_reverse_stereo = setting; }
int  FX_GetReverseStereo(void)        { return fx_reverse_stereo; }

void FX_SetReverb(int reverb)        { fx_reverb = reverb; }
void FX_SetFastReverb(int reverb)    { fx_reverb = reverb; }
int  FX_GetMaxReverbDelay(void)      { return 256; }
int  FX_GetReverbDelay(void)         { return fx_reverb_delay; }
void FX_SetReverbDelay(int delay)    { fx_reverb_delay = delay; }

int FX_VoiceAvailable(int priority)  { (void)priority; return 1; }

int FX_EndLooping(int handle)    { (void)handle; return FX_Ok; }
int FX_SetPan(int handle, int vol, int left, int right)
{
    (void)handle; (void)vol; (void)left; (void)right;
    return FX_Ok;
}
int FX_SetPitch(int handle, int pitchoffset)
{
    (void)handle; (void)pitchoffset;
    return FX_Ok;
}
int FX_SetFrequency(int handle, int frequency)
{
    (void)handle; (void)frequency;
    return FX_Ok;
}

/* All play functions return a dummy handle > FX_Ok so the game sees them
   as valid voices.  Handle 1 is used universally since we play nothing. */
#define STUB_VOICE_HANDLE 1

int FX_PlayVOC(char *ptr, int pitchoffset, int vol, int left, int right,
               int priority, unsigned long callbackval)
{
    (void)ptr; (void)pitchoffset; (void)vol; (void)left; (void)right;
    (void)priority; (void)callbackval;
    return STUB_VOICE_HANDLE;
}

int FX_PlayLoopedVOC(char *ptr, long loopstart, long loopend,
                     int pitchoffset, int vol, int left, int right,
                     int priority, unsigned long callbackval)
{
    (void)ptr; (void)loopstart; (void)loopend; (void)pitchoffset;
    (void)vol; (void)left; (void)right; (void)priority; (void)callbackval;
    return STUB_VOICE_HANDLE;
}

int FX_PlayWAV(char *ptr, int pitchoffset, int vol, int left, int right,
               int priority, unsigned long callbackval)
{
    (void)ptr; (void)pitchoffset; (void)vol; (void)left; (void)right;
    (void)priority; (void)callbackval;
    return STUB_VOICE_HANDLE;
}

int FX_PlayLoopedWAV(char *ptr, long loopstart, long loopend,
                     int pitchoffset, int vol, int left, int right,
                     int priority, unsigned long callbackval)
{
    (void)ptr; (void)loopstart; (void)loopend; (void)pitchoffset;
    (void)vol; (void)left; (void)right; (void)priority; (void)callbackval;
    return STUB_VOICE_HANDLE;
}

int FX_PlayVOC3D(char *ptr, int pitchoffset, int angle, int distance,
                 int priority, unsigned long callbackval)
{
    (void)ptr; (void)pitchoffset; (void)angle; (void)distance;
    (void)priority; (void)callbackval;
    return STUB_VOICE_HANDLE;
}

int FX_PlayWAV3D(char *ptr, int pitchoffset, int angle, int distance,
                 int priority, unsigned long callbackval)
{
    (void)ptr; (void)pitchoffset; (void)angle; (void)distance;
    (void)priority; (void)callbackval;
    return STUB_VOICE_HANDLE;
}

int FX_PlayRaw(char *ptr, unsigned long length, unsigned rate,
               int pitchoffset, int vol, int left, int right,
               int priority, unsigned long callbackval)
{
    (void)ptr; (void)length; (void)rate; (void)pitchoffset;
    (void)vol; (void)left; (void)right; (void)priority; (void)callbackval;
    return STUB_VOICE_HANDLE;
}

int FX_PlayLoopedRaw(char *ptr, unsigned long length, char *loopstart,
                     char *loopend, unsigned rate, int pitchoffset,
                     int vol, int left, int right, int priority,
                     unsigned long callbackval)
{
    (void)ptr; (void)length; (void)loopstart; (void)loopend; (void)rate;
    (void)pitchoffset; (void)vol; (void)left; (void)right;
    (void)priority; (void)callbackval;
    return STUB_VOICE_HANDLE;
}

int FX_Pan3D(int handle, int angle, int distance)
{
    (void)handle; (void)angle; (void)distance;
    return FX_Ok;
}

int FX_SoundActive(int handle)
{
    (void)handle;
    return 0; /* nothing playing */
}

int FX_SoundsPlaying(void) { return 0; }

int FX_StopSound(int handle)
{
    (void)handle;
    return FX_Ok;
}

int FX_StopAllSounds(void) { return FX_Ok; }

int FX_StartDemandFeedPlayback(void (*function)(char **ptr, unsigned long *length),
                               int rate, int pitchoffset, int vol, int left,
                               int right, int priority, unsigned long callbackval)
{
    (void)function; (void)rate; (void)pitchoffset; (void)vol;
    (void)left; (void)right; (void)priority; (void)callbackval;
    return STUB_VOICE_HANDLE;
}

int FX_StartRecording(int MixRate, void (*function)(char *ptr, int length))
{
    (void)MixRate; (void)function;
    return FX_Ok;
}

void FX_StopRecord(void) { }

/* ═══════════════════════════════════════════════════════════════════
   MUSIC (MIDI) – silent stubs
   ═══════════════════════════════════════════════════════════════════ */

int MUSIC_ErrorCode = MUSIC_Ok;

static int music_volume   = 255;
static int music_loop     = 0;
static int music_playing  = 0;
static int music_context  = 0;

char *MUSIC_ErrorString(int ErrorNumber)
{
    switch (ErrorNumber) {
    case MUSIC_Ok:             return "MUSIC ok.";
    case MUSIC_Warning:        return "MUSIC warning.";
    case MUSIC_Error:          return "MUSIC error.";
    case MUSIC_ASSVersion:     return "MUSIC ASS version error.";
    case MUSIC_SoundCardError: return "MUSIC sound card error.";
    case MUSIC_MPU401Error:    return "MUSIC MPU-401 error.";
    case MUSIC_InvalidCard:    return "MUSIC invalid card.";
    case MUSIC_MidiError:      return "MUSIC MIDI error.";
    case MUSIC_TaskManError:   return "MUSIC task manager error.";
    case MUSIC_FMNotDetected:  return "MUSIC FM not detected.";
    case MUSIC_DPMI_Error:     return "MUSIC DPMI error.";
    default:                   return "MUSIC unknown error.";
    }
}

int  MUSIC_Init(int SoundCard, int Address)
{
    (void)SoundCard; (void)Address;
    music_volume  = 255;
    music_playing = 0;
    return MUSIC_Ok;
}

int  MUSIC_Shutdown(void)       { music_playing = 0; return MUSIC_Ok; }
void MUSIC_SetMaxFMMidiChannel(int channel)          { (void)channel; }
void MUSIC_SetVolume(int volume)                     { music_volume = volume; }
void MUSIC_SetMidiChannelVolume(int channel, int vol) { (void)channel; (void)vol; }
void MUSIC_ResetMidiChannelVolumes(void)             { }
int  MUSIC_GetVolume(void)                           { return music_volume; }
void MUSIC_SetLoopFlag(int loopflag)                 { music_loop = loopflag; }
int  MUSIC_SongPlaying(void)                         { return music_playing; }
void MUSIC_Continue(void)                            { }
void MUSIC_Pause(void)                               { }

int MUSIC_StopSong(void)
{
    music_playing = 0;
    return MUSIC_Ok;
}

int MUSIC_PlaySong(unsigned char *song, int loopflag)
{
    (void)song;
    music_loop    = loopflag;
    music_playing = 1;
    return MUSIC_Ok;
}

void MUSIC_SetContext(int context)                    { music_context = context; }
int  MUSIC_GetContext(void)                           { return music_context; }
void MUSIC_SetSongTick(unsigned long t)              { (void)t; }
void MUSIC_SetSongTime(unsigned long ms)             { (void)ms; }
void MUSIC_SetSongPosition(int m, int b, int t)     { (void)m; (void)b; (void)t; }

void MUSIC_GetSongPosition(songposition *pos)
{
    if (pos) memset(pos, 0, sizeof(*pos));
}

void MUSIC_GetSongLength(songposition *pos)
{
    if (pos) memset(pos, 0, sizeof(*pos));
}

int  MUSIC_FadeVolume(int tovolume, int milliseconds)
{
    (void)milliseconds;
    music_volume = tovolume;
    return MUSIC_Ok;
}

int  MUSIC_FadeActive(void)     { return 0; }
void MUSIC_StopFade(void)       { }

void MUSIC_RerouteMidiChannel(int channel, int (*function)(int, int, int))
{
    (void)channel; (void)function;
}

void MUSIC_RegisterTimbreBank(unsigned char *timbres) { (void)timbres; }

/* ═══════════════════════════════════════════════════════════════════
   USRHOOKS – memory allocation hooks
   ═══════════════════════════════════════════════════════════════════ */

int USRHOOKS_GetMem(void **ptr, unsigned long size)
{
    if (!ptr) return USRHOOKS_Error;
    *ptr = malloc(size);
    return (*ptr) ? USRHOOKS_Ok : USRHOOKS_Error;
}

int USRHOOKS_FreeMem(void *ptr)
{
    if (ptr) free(ptr);
    return USRHOOKS_Ok;
}

/* ═══════════════════════════════════════════════════════════════════
   TS (Task Manager) – working timer using SDL_GetTicks
   ═══════════════════════════════════════════════════════════════════ */

volatile int TS_InInterrupt = 0;

#define MAX_TASKS 8

static task  task_pool[MAX_TASKS];
static int   task_pool_used[MAX_TASKS];
static unsigned long timer_last_tick = 0;

void TS_Shutdown(void)
{
    int i;
    for (i = 0; i < MAX_TASKS; i++) {
        task_pool_used[i] = 0;
        task_pool[i].active = 0;
    }
}

task *TS_ScheduleTask(void (*Function)(task *), int rate,
                      int priority, void *data)
{
    int i;
    for (i = 0; i < MAX_TASKS; i++) {
        if (!task_pool_used[i]) {
            task *t = &task_pool[i];
            task_pool_used[i] = 1;
            memset(t, 0, sizeof(*t));
            t->TaskService = Function;
            t->rate        = rate;
            t->priority    = priority;
            t->data        = data;
            t->count       = 0;
            t->active      = 1;
            t->next        = NULL;
            t->prev        = NULL;
            return t;
        }
    }
    return NULL;
}

int TS_Terminate(task *ptr)
{
    int i;
    if (!ptr) return TASK_Error;
    for (i = 0; i < MAX_TASKS; i++) {
        if (&task_pool[i] == ptr) {
            task_pool_used[i] = 0;
            ptr->active = 0;
            return TASK_Ok;
        }
    }
    return TASK_Error;
}

void TS_Dispatch(void)
{
    if (!timer_last_tick)
        timer_last_tick = SDL_GetTicks();
    timer_update();
}

void TS_SetTaskRate(task *Task, int rate)
{
    if (Task) Task->rate = rate;
}

void TS_UnlockMemory(void) { }
int  TS_LockMemory(void)   { return TASK_Ok; }

/*
 * timer_update - call from main loop every frame.
 *
 * For each active task, accumulates elapsed milliseconds and fires the
 * callback at the task's configured rate (ticks-per-second).  This drives
 * the game's 120 Hz totalclock counter and any other timer-based logic.
 */
void timer_update(void)
{
    unsigned long now, elapsed, ms_per_tick;
    int i;

    now = SDL_GetTicks();
    if (!timer_last_tick) {
        timer_last_tick = now;
        return;
    }
    elapsed = now - timer_last_tick;
    if (elapsed == 0) return;

    TS_InInterrupt = 1;
    for (i = 0; i < MAX_TASKS; i++) {
        if (task_pool_used[i] && task_pool[i].active && task_pool[i].TaskService) {
            task *t = &task_pool[i];
            int rate = t->rate;
            if (rate <= 0) rate = 120;
            ms_per_tick = 1000 / (unsigned long)rate;
            if (ms_per_tick == 0) ms_per_tick = 1;

            t->count += elapsed;
            while (t->count >= (long)ms_per_tick) {
                t->TaskService(t);
                t->count -= (long)ms_per_tick;
            }
        }
    }
    TS_InInterrupt = 0;
    timer_last_tick = now;
}

/* ═══════════════════════════════════════════════════════════════════
   KB (Keyboard) – queue + state array driven by SDL events
   ═══════════════════════════════════════════════════════════════════ */

volatile byte        KB_KeyDown[MAXKEYBOARDSCAN];
volatile kb_scancode KB_LastScan = sc_None;

#define KB_QUEUE_SIZE 64
static char kb_queue[KB_QUEUE_SIZE];
static int  kb_queue_head = 0;
static int  kb_queue_tail = 0;
static int  kb_keypad_active = 0;

void KB_KeyEvent(int scancode, boolean keypressed)
{
    if (scancode < 0 || scancode >= MAXKEYBOARDSCAN) return;
    KB_KeyDown[scancode] = keypressed ? true : false;
    if (keypressed)
        KB_LastScan = (kb_scancode)scancode;
}

boolean KB_KeyWaiting(void)
{
    return (kb_queue_head != kb_queue_tail) ? true : false;
}

char KB_Getch(void)
{
    if (kb_queue_head == kb_queue_tail) return 0;
    {
        char ch = kb_queue[kb_queue_head];
        kb_queue_head = (kb_queue_head + 1) % KB_QUEUE_SIZE;
        return ch;
    }
}

void KB_Addch(char ch)
{
    int next = (kb_queue_tail + 1) % KB_QUEUE_SIZE;
    if (next != kb_queue_head) {
        kb_queue[kb_queue_tail] = ch;
        kb_queue_tail = next;
    }
}

void KB_FlushKeyboardQueue(void)
{
    kb_queue_head = kb_queue_tail = 0;
    KB_LastScan = sc_None;
}

void KB_ClearKeysDown(void)
{
    memset((void *)KB_KeyDown, 0, sizeof(KB_KeyDown));
    KB_LastScan = sc_None;
}

/* Scancode-to-name table for the most common keys */
static const struct { kb_scancode sc; const char *name; } sc_names[] = {
    { sc_Escape,       "Escape" },      { sc_Return,       "Enter" },
    { sc_Space,        "Space" },       { sc_BackSpace,    "BkSp" },
    { sc_Tab,          "Tab" },         { sc_LeftAlt,      "LAlt" },
    { sc_LeftControl,  "LCtrl" },       { sc_LeftShift,    "LShift" },
    { sc_RightShift,   "RShift" },      { sc_CapsLock,     "CapsLk" },
    { sc_F1,  "F1" },  { sc_F2,  "F2" },  { sc_F3,  "F3" },
    { sc_F4,  "F4" },  { sc_F5,  "F5" },  { sc_F6,  "F6" },
    { sc_F7,  "F7" },  { sc_F8,  "F8" },  { sc_F9,  "F9" },
    { sc_F10, "F10" }, { sc_F11, "F11" }, { sc_F12, "F12" },
    { sc_UpArrow,      "Up" },          { sc_DownArrow,    "Down" },
    { sc_LeftArrow,    "Left" },        { sc_RightArrow,   "Right" },
    { sc_Insert,       "Ins" },         { sc_Delete,       "Del" },
    { sc_Home,         "Home" },        { sc_End,          "End" },
    { sc_PgUp,         "PgUp" },        { sc_PgDn,         "PgDn" },
    { sc_A, "A" }, { sc_B, "B" }, { sc_C, "C" }, { sc_D, "D" },
    { sc_E, "E" }, { sc_F, "F" }, { sc_G, "G" }, { sc_H, "H" },
    { sc_I, "I" }, { sc_J, "J" }, { sc_K, "K" }, { sc_L, "L" },
    { sc_M, "M" }, { sc_N, "N" }, { sc_O, "O" }, { sc_P, "P" },
    { sc_Q, "Q" }, { sc_R, "R" }, { sc_S, "S" }, { sc_T, "T" },
    { sc_U, "U" }, { sc_V, "V" }, { sc_W, "W" }, { sc_X, "X" },
    { sc_Y, "Y" }, { sc_Z, "Z" },
    { sc_1, "1" }, { sc_2, "2" }, { sc_3, "3" }, { sc_4, "4" },
    { sc_5, "5" }, { sc_6, "6" }, { sc_7, "7" }, { sc_8, "8" },
    { sc_9, "9" }, { sc_0, "0" },
    { sc_Minus, "-" },   { sc_Equals, "=" },
    { sc_Comma, "," },   { sc_Period, "." },
    { sc_Slash, "/" },    { sc_SemiColon, ";" },
    { sc_Quote, "'" },   { sc_Tilde, "`" },
    { sc_BackSlash, "\\" },
    { sc_OpenBracket, "[" },  { sc_CloseBracket, "]" },
    { sc_RightAlt,     "RAlt" },   { sc_RightControl, "RCtrl" },
    { sc_kpad_Enter,   "KpdEnt" }, { sc_kpad_Slash, "Kpd/" },
    { sc_PrintScreen,  "PrtSc" },  { sc_Pause, "Pause" },
    { sc_None, NULL }
};

char *KB_ScanCodeToString(kb_scancode scancode)
{
    int i;
    for (i = 0; sc_names[i].name != NULL; i++) {
        if (sc_names[i].sc == scancode)
            return (char *)sc_names[i].name;
    }
    return "?";
}

kb_scancode KB_StringToScanCode(char *string)
{
    int i;
    if (!string) return sc_None;
    for (i = 0; sc_names[i].name != NULL; i++) {
        if (strcmp(sc_names[i].name, string) == 0)
            return sc_names[i].sc;
    }
    return sc_None;
}

void    KB_TurnKeypadOn(void)    { kb_keypad_active = 1; }
void    KB_TurnKeypadOff(void)   { kb_keypad_active = 0; }
boolean KB_KeypadActive(void)    { return kb_keypad_active; }

void KB_Startup(void)
{
    KB_ClearKeysDown();
    KB_FlushKeyboardQueue();
}

void KB_Shutdown(void)
{
    KB_ClearKeysDown();
    KB_FlushKeyboardQueue();
}

/* ═══════════════════════════════════════════════════════════════════
   CONTROL – input mapping system (replaces precompiled MACT library)
   ═══════════════════════════════════════════════════════════════════ */

/* Global state variables */
boolean CONTROL_RudderEnabled    = false;
boolean CONTROL_MousePresent     = false;
boolean CONTROL_JoysPresent[MaxJoys] = { false, false };
boolean CONTROL_MouseEnabled     = false;
boolean CONTROL_JoystickEnabled  = false;
byte    CONTROL_JoystickPort     = 0;
uint32  CONTROL_ButtonState1     = 0;
uint32  CONTROL_ButtonHeldState1 = 0;
uint32  CONTROL_ButtonState2     = 0;
uint32  CONTROL_ButtonHeldState2 = 0;

/* Key-to-function mapping: each game function has two scancodes */
#define MAX_CONTROL_FUNCTIONS MAXGAMEBUTTONS
static kb_scancode ctrl_key1[MAX_CONTROL_FUNCTIONS];
static kb_scancode ctrl_key2[MAX_CONTROL_FUNCTIONS];

/* Button-to-function mapping */
static int32 ctrl_button_map[MAXGAMEBUTTONS];
static int32 ctrl_button_dblclk_map[MAXGAMEBUTTONS];

/* Flag toggles */
static boolean ctrl_flag_toggle[MAX_CONTROL_FUNCTIONS];
static boolean ctrl_flag_state[MAX_CONTROL_FUNCTIONS];

/* Analog axis mapping */
#define MAX_AXES 8
static int32 ctrl_analog_map[MAX_AXES];
static int32 ctrl_digital_fwd[MAX_AXES];
static int32 ctrl_digital_rev[MAX_AXES];
static int32 ctrl_axis_scale[MAX_AXES];

/* Mouse sensitivity (arbitrary units, Duke's default is ~32) */
static int32 ctrl_mouse_sensitivity = 32;

/* Time function provided by game */
static int32 (*ctrl_time_func)(void) = NULL;
static int32 ctrl_tps = 120;

void CONTROL_MapKey(int32 which, kb_scancode key1, kb_scancode key2)
{
    if (which < 0 || which >= MAX_CONTROL_FUNCTIONS) return;
    ctrl_key1[which] = key1;
    ctrl_key2[which] = key2;
}

void CONTROL_MapButton(int32 whichfunction, int32 whichbutton,
                       boolean doubleclicked)
{
    if (whichbutton < 0 || whichbutton >= MAXGAMEBUTTONS) return;
    if (doubleclicked)
        ctrl_button_dblclk_map[whichbutton] = whichfunction;
    else
        ctrl_button_map[whichbutton] = whichfunction;
}

void CONTROL_DefineFlag(int32 which, boolean toggle)
{
    if (which < 0 || which >= MAX_CONTROL_FUNCTIONS) return;
    ctrl_flag_toggle[which] = toggle;
    ctrl_flag_state[which]  = false;
}

boolean CONTROL_FlagActive(int32 which)
{
    if (which < 0 || which >= MAX_CONTROL_FUNCTIONS) return false;
    return ctrl_flag_state[which];
}

void CONTROL_ClearAssignments(void)
{
    memset(ctrl_key1, sc_None, sizeof(ctrl_key1));
    memset(ctrl_key2, sc_None, sizeof(ctrl_key2));
    memset(ctrl_button_map, -1, sizeof(ctrl_button_map));
    memset(ctrl_button_dblclk_map, -1, sizeof(ctrl_button_dblclk_map));
    memset(ctrl_flag_toggle, 0, sizeof(ctrl_flag_toggle));
    memset(ctrl_flag_state, 0, sizeof(ctrl_flag_state));
    memset(ctrl_analog_map, -1, sizeof(ctrl_analog_map));
    memset(ctrl_digital_fwd, -1, sizeof(ctrl_digital_fwd));
    memset(ctrl_digital_rev, -1, sizeof(ctrl_digital_rev));
    memset(ctrl_axis_scale, 0, sizeof(ctrl_axis_scale));
}

void CONTROL_GetUserInput(UserInput *info)
{
    if (!info) return;
    info->button0 = false;
    info->button1 = false;
    info->dir     = dir_None;

    /* Map common keys to simple directional input */
    if (KB_KeyDown[sc_UpArrow] || KB_KeyDown[sc_W])
        info->dir = dir_North;
    else if (KB_KeyDown[sc_DownArrow] || KB_KeyDown[sc_S])
        info->dir = dir_South;
    else if (KB_KeyDown[sc_LeftArrow] || KB_KeyDown[sc_A])
        info->dir = dir_West;
    else if (KB_KeyDown[sc_RightArrow] || KB_KeyDown[sc_D])
        info->dir = dir_East;

    if (KB_KeyDown[sc_Return] || KB_KeyDown[sc_Space])
        info->button0 = true;
    if (KB_KeyDown[sc_Escape])
        info->button1 = true;
}

void CONTROL_GetInput(ControlInfo *info)
{
    int i, mdx, mdy, mbuttons;

    if (!info) return;
    memset(info, 0, sizeof(*info));

    /* Save previous button state for HELD detection */
    CONTROL_ButtonHeldState1 = CONTROL_ButtonState1;
    CONTROL_ButtonHeldState2 = CONTROL_ButtonState2;
    CONTROL_ButtonState1 = 0;
    CONTROL_ButtonState2 = 0;

    /* Evaluate keyboard-to-function mapping → set button bits */
    for (i = 0; i < MAX_CONTROL_FUNCTIONS; i++) {
        int pressed = 0;
        if (ctrl_key1[i] != sc_None && KB_KeyDown[ctrl_key1[i]])
            pressed = 1;
        if (ctrl_key2[i] != sc_None && KB_KeyDown[ctrl_key2[i]])
            pressed = 1;

        if (pressed) {
            if (i < 32)
                CONTROL_ButtonState1 |= (1u << i);
            else
                CONTROL_ButtonState2 |= (1u << (i - 32));

            /* For toggle flags, flip state on press edge */
            if (ctrl_flag_toggle[i]) {
                int was_held = (i < 32)
                    ? ((CONTROL_ButtonHeldState1 >> i) & 1)
                    : ((CONTROL_ButtonHeldState2 >> (i - 32)) & 1);
                if (!was_held)
                    ctrl_flag_state[i] = !ctrl_flag_state[i];
            } else {
                ctrl_flag_state[i] = true;
            }
        } else {
            if (!ctrl_flag_toggle[i])
                ctrl_flag_state[i] = false;
        }
    }

    /* Read mouse delta from SDL driver */
    sdl_getmouse(&mdx, &mdy, &mbuttons);

    /* Apply mouse to yaw (turning) and pitch (looking) */
    info->dyaw  = (fixed)(mdx * ctrl_mouse_sensitivity / 4);
    info->dpitch = (fixed)(-mdy * ctrl_mouse_sensitivity / 4);

    /* Mouse buttons → game functions via button map */
    if (mbuttons & 1) { /* left click */
        int func = ctrl_button_map[0];
        if (func >= 0 && func < 32)
            CONTROL_ButtonState1 |= (1u << func);
        else if (func >= 32 && func < MAXGAMEBUTTONS)
            CONTROL_ButtonState2 |= (1u << (func - 32));
    }
    if (mbuttons & 4) { /* right click */
        int func = ctrl_button_map[1];
        if (func >= 0 && func < 32)
            CONTROL_ButtonState1 |= (1u << func);
        else if (func >= 32 && func < MAXGAMEBUTTONS)
            CONTROL_ButtonState2 |= (1u << (func - 32));
    }
    if (mbuttons & 2) { /* middle click */
        int func = ctrl_button_map[2];
        if (func >= 0 && func < 32)
            CONTROL_ButtonState1 |= (1u << func);
        else if (func >= 32 && func < MAXGAMEBUTTONS)
            CONTROL_ButtonState2 |= (1u << (func - 32));
    }
}

void CONTROL_ClearButton(int32 whichbutton)
{
    if (whichbutton < 0 || whichbutton >= MAXGAMEBUTTONS) return;
    if (whichbutton < 32) {
        CONTROL_ButtonState1     &= ~(1u << whichbutton);
        CONTROL_ButtonHeldState1 &= ~(1u << whichbutton);
    } else {
        CONTROL_ButtonState2     &= ~(1u << (whichbutton - 32));
        CONTROL_ButtonHeldState2 &= ~(1u << (whichbutton - 32));
    }
}

void CONTROL_ClearUserInput(UserInput *info)
{
    if (info) {
        info->button0 = false;
        info->button1 = false;
        info->dir     = dir_None;
    }
}

void CONTROL_WaitRelease(void)
{
    /* Spin until all keys released (in real use, pump SDL events) */
}

void CONTROL_Ack(void)
{
    /* Wait for a key press then release */
}

void CONTROL_CenterJoystick(void (*CenterCenter)(void),
                            void (*UpperLeft)(void),
                            void (*LowerRight)(void),
                            void (*CenterThrottle)(void),
                            void (*CenterRudder)(void))
{
    (void)CenterCenter; (void)UpperLeft; (void)LowerRight;
    (void)CenterThrottle; (void)CenterRudder;
}

int32 CONTROL_GetMouseSensitivity(void)
{
    return ctrl_mouse_sensitivity;
}

void CONTROL_SetMouseSensitivity(int32 newsensitivity)
{
    ctrl_mouse_sensitivity = newsensitivity;
}

void CONTROL_Startup(controltype which, int32 (*TimeFunction)(void),
                     int32 ticspersecond)
{
    (void)which;
    ctrl_time_func = TimeFunction;
    ctrl_tps = ticspersecond;

    CONTROL_ClearAssignments();

    /* Enable mouse by default on modern systems */
    CONTROL_MousePresent = true;
    CONTROL_MouseEnabled = true;
}

void CONTROL_Shutdown(void)
{
    CONTROL_ClearAssignments();
    CONTROL_MousePresent = false;
    CONTROL_MouseEnabled = false;
}

void CONTROL_MapAnalogAxis(int32 whichaxis, int32 whichanalog)
{
    if (whichaxis >= 0 && whichaxis < MAX_AXES)
        ctrl_analog_map[whichaxis] = whichanalog;
}

void CONTROL_MapDigitalAxis(int32 whichaxis, int32 whichfunction,
                            int32 direction)
{
    if (whichaxis < 0 || whichaxis >= MAX_AXES) return;
    if (direction == 0)
        ctrl_digital_fwd[whichaxis] = whichfunction;
    else
        ctrl_digital_rev[whichaxis] = whichfunction;
}

void CONTROL_SetAnalogAxisScale(int32 whichaxis, int32 axisscale)
{
    if (whichaxis >= 0 && whichaxis < MAX_AXES)
        ctrl_axis_scale[whichaxis] = axisscale;
}

void CONTROL_PrintAxes(void) { }
