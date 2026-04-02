/*
 * audio_stub.h - Stub audio/input system replacing DOS audiolib + MACT library
 *
 * The original audiolib (~40K lines) contains DOS-only sound card drivers
 * (Sound Blaster, GUS, Pro Audio Spectrum, etc.) that are unusable on modern
 * systems.  The MACT library (CONTROL system) was shipped as a precompiled
 * .LIB for Watcom/DOS.
 *
 * This header + audio_stub.c provide no-op / minimal-functional stubs for
 * every API the game code calls, allowing the project to compile and link
 * without the original DOS libraries.  Real audio can be layered in later
 * via SDL_mixer or similar.
 */

#ifndef AUDIO_STUB_H
#define AUDIO_STUB_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/* ═══════════════════════════════════════════════════════════════════
   Portable type aliases (match source/TYPES.H for the game code)
   ═══════════════════════════════════════════════════════════════════ */
#ifndef _types_public
typedef unsigned char  uint8;
typedef uint8          byte;
typedef signed char    int8;
typedef unsigned short uint16;
typedef uint16         word;
typedef short          int16;
typedef unsigned int   uint32;
typedef int            int32;
typedef uint32         dword;
typedef int32          fixed;
typedef int32          boolean;
#endif

typedef uint8 kb_scancode;

#ifndef true
#define true  (1 == 1)
#endif
#ifndef false
#define false (!true)
#endif

/* ═══════════════════════════════════════════════════════════════════
   SNDCARDS.H – sound card enumeration (from audiolib)
   ═══════════════════════════════════════════════════════════════════ */
#ifndef __SNDCARDS_H
#define __SNDCARDS_H

#define ASS_VERSION_STRING "1.1"

typedef enum {
    SoundBlaster,
    ProAudioSpectrum,
    SoundMan16,
    Adlib,
    GenMidi,
    SoundCanvas,
    Awe32,
    WaveBlaster,
    SoundScape,
    UltraSound,
    SoundSource,
    TandySoundSource,
    PC,
    NumSoundCards
} soundcardnames;

#endif /* __SNDCARDS_H */

/* ═══════════════════════════════════════════════════════════════════
   FX_MAN.H – sound effects API
   ═══════════════════════════════════════════════════════════════════ */

/* FX device description */
typedef struct {
    int MaxVoices;
    int MaxSampleBits;
    int MaxChannels;
} fx_device;

/* Sound Blaster configuration */
typedef struct {
    unsigned long Address;
    unsigned long Type;
    unsigned long Interrupt;
    unsigned long Dma8;
    unsigned long Dma16;
    unsigned long Midi;
    unsigned long Emu;
} fx_blaster_config;

/* Error codes */
enum FX_ERRORS {
    FX_Warning       = -2,
    FX_Error         = -1,
    FX_Ok            =  0,
    FX_ASSVersion,
    FX_BlasterError,
    FX_SoundCardError,
    FX_InvalidCard,
    FX_MultiVocError,
    FX_DPMI_Error
};

/* Stereo modes */
#define MonoFx   1
#define StereoFx 2

/* Global error variable */
extern int FX_ErrorCode;  /* read by game code after failed calls */

char *FX_ErrorString(int ErrorNumber);
int   FX_SetupCard(int SoundCard, fx_device *device);
int   FX_GetBlasterSettings(fx_blaster_config *blaster);
int   FX_SetupSoundBlaster(fx_blaster_config blaster, int *MaxVoices,
                           int *MaxSampleBits, int *MaxChannels);
int   FX_Init(int SoundCard, int numvoices, int numchannels,
              int samplebits, unsigned mixrate);
int   FX_Shutdown(void);
int   FX_SetCallBack(void (*function)(unsigned long));
void  FX_SetVolume(int volume);
int   FX_GetVolume(void);
void  FX_SetReverseStereo(int setting);
int   FX_GetReverseStereo(void);
void  FX_SetReverb(int reverb);
void  FX_SetFastReverb(int reverb);
int   FX_GetMaxReverbDelay(void);
int   FX_GetReverbDelay(void);
void  FX_SetReverbDelay(int delay);
int   FX_VoiceAvailable(int priority);
int   FX_EndLooping(int handle);
int   FX_SetPan(int handle, int vol, int left, int right);
int   FX_SetPitch(int handle, int pitchoffset);
int   FX_SetFrequency(int handle, int frequency);

int   FX_PlayVOC(char *ptr, int pitchoffset, int vol, int left, int right,
                 int priority, unsigned long callbackval);
int   FX_PlayLoopedVOC(char *ptr, long loopstart, long loopend,
                       int pitchoffset, int vol, int left, int right,
                       int priority, unsigned long callbackval);
int   FX_PlayWAV(char *ptr, int pitchoffset, int vol, int left, int right,
                 int priority, unsigned long callbackval);
int   FX_PlayLoopedWAV(char *ptr, long loopstart, long loopend,
                       int pitchoffset, int vol, int left, int right,
                       int priority, unsigned long callbackval);
int   FX_PlayVOC3D(char *ptr, int pitchoffset, int angle, int distance,
                   int priority, unsigned long callbackval);
int   FX_PlayWAV3D(char *ptr, int pitchoffset, int angle, int distance,
                   int priority, unsigned long callbackval);
int   FX_PlayRaw(char *ptr, unsigned long length, unsigned rate,
                 int pitchoffset, int vol, int left, int right,
                 int priority, unsigned long callbackval);
int   FX_PlayLoopedRaw(char *ptr, unsigned long length, char *loopstart,
                       char *loopend, unsigned rate, int pitchoffset,
                       int vol, int left, int right, int priority,
                       unsigned long callbackval);
int   FX_Pan3D(int handle, int angle, int distance);
int   FX_SoundActive(int handle);
int   FX_SoundsPlaying(void);
int   FX_StopSound(int handle);
int   FX_StopAllSounds(void);
int   FX_StartDemandFeedPlayback(void (*function)(char **ptr, unsigned long *length),
                                 int rate, int pitchoffset, int vol, int left,
                                 int right, int priority, unsigned long callbackval);
int   FX_StartRecording(int MixRate, void (*function)(char *ptr, int length));
void  FX_StopRecord(void);

/* ═══════════════════════════════════════════════════════════════════
   MUSIC.H – MIDI music API
   ═══════════════════════════════════════════════════════════════════ */

enum MUSIC_ERRORS {
    MUSIC_Warning       = -2,
    MUSIC_Error         = -1,
    MUSIC_Ok            =  0,
    MUSIC_ASSVersion,
    MUSIC_SoundCardError,
    MUSIC_MPU401Error,
    MUSIC_InvalidCard,
    MUSIC_MidiError,
    MUSIC_TaskManError,
    MUSIC_FMNotDetected,
    MUSIC_DPMI_Error
};

#define MUSIC_LoopSong  (1 == 1)
#define MUSIC_PlayOnce  (!MUSIC_LoopSong)

typedef struct {
    unsigned long tickposition;
    unsigned long milliseconds;
    unsigned int  measure;
    unsigned int  beat;
    unsigned int  tick;
} songposition;

extern int MUSIC_ErrorCode;

char *MUSIC_ErrorString(int ErrorNumber);
int   MUSIC_Init(int SoundCard, int Address);
int   MUSIC_Shutdown(void);
void  MUSIC_SetMaxFMMidiChannel(int channel);
void  MUSIC_SetVolume(int volume);
void  MUSIC_SetMidiChannelVolume(int channel, int volume);
void  MUSIC_ResetMidiChannelVolumes(void);
int   MUSIC_GetVolume(void);
void  MUSIC_SetLoopFlag(int loopflag);
int   MUSIC_SongPlaying(void);
void  MUSIC_Continue(void);
void  MUSIC_Pause(void);
int   MUSIC_StopSong(void);
int   MUSIC_PlaySong(unsigned char *song, int loopflag);
void  MUSIC_SetContext(int context);
int   MUSIC_GetContext(void);
void  MUSIC_SetSongTick(unsigned long PositionInTicks);
void  MUSIC_SetSongTime(unsigned long milliseconds);
void  MUSIC_SetSongPosition(int measure, int beat, int tick);
void  MUSIC_GetSongPosition(songposition *pos);
void  MUSIC_GetSongLength(songposition *pos);
int   MUSIC_FadeVolume(int tovolume, int milliseconds);
int   MUSIC_FadeActive(void);
void  MUSIC_StopFade(void);
void  MUSIC_RerouteMidiChannel(int channel, int (*function)(int event, int c1, int c2));
void  MUSIC_RegisterTimbreBank(unsigned char *timbres);

/* ═══════════════════════════════════════════════════════════════════
   TASK_MAN.H – timer / task scheduler
   ═══════════════════════════════════════════════════════════════════ */

enum TASK_ERRORS {
    TASK_Warning = -2,
    TASK_Error   = -1,
    TASK_Ok      =  0
};

typedef struct task {
    struct task *next;
    struct task *prev;
    void (*TaskService)(struct task *);
    void       *data;
    long        rate;
    volatile long count;
    int         priority;
    int         active;
} task;

extern volatile int TS_InInterrupt;

void   TS_Shutdown(void);
task  *TS_ScheduleTask(void (*Function)(task *), int rate,
                       int priority, void *data);
int    TS_Terminate(task *ptr);
void   TS_Dispatch(void);
void   TS_SetTaskRate(task *Task, int rate);
void   TS_UnlockMemory(void);
int    TS_LockMemory(void);

/*
 * timer_update() – call from the main loop every frame.
 * Fires scheduled timer callbacks based on elapsed wall-clock time.
 */
void   timer_update(void);

/* ═══════════════════════════════════════════════════════════════════
   USRHOOKS.H – memory allocation hooks (called by audiolib internals)
   ═══════════════════════════════════════════════════════════════════ */

enum USRHOOKS_Errors {
    USRHOOKS_Warning = -2,
    USRHOOKS_Error   = -1,
    USRHOOKS_Ok      =  0
};

int  USRHOOKS_GetMem(void **ptr, unsigned long size);
int  USRHOOKS_FreeMem(void *ptr);

/* ═══════════════════════════════════════════════════════════════════
   KEYBOARD.H – keyboard input
   ═══════════════════════════════════════════════════════════════════ */

/* Scancodes (DOS XT set, extended codes use Duke's custom remapping) */
#define sc_None          0
#define sc_Bad           0xff
#define sc_Comma         0x33
#define sc_Period        0x34
#define sc_Return        0x1c
#define sc_Enter         sc_Return
#define sc_Escape        0x01
#define sc_Space         0x39
#define sc_BackSpace     0x0e
#define sc_Tab           0x0f
#define sc_LeftAlt       0x38
#define sc_LeftControl   0x1d
#define sc_CapsLock      0x3a
#define sc_LeftShift     0x2a
#define sc_RightShift    0x36
#define sc_F1            0x3b
#define sc_F2            0x3c
#define sc_F3            0x3d
#define sc_F4            0x3e
#define sc_F5            0x3f
#define sc_F6            0x40
#define sc_F7            0x41
#define sc_F8            0x42
#define sc_F9            0x43
#define sc_F10           0x44
#define sc_F11           0x57
#define sc_F12           0x58
#define sc_Kpad_Star     0x37
#define sc_Pause         0x59
#define sc_ScrollLock    0x46
#define sc_NumLock       0x45
#define sc_Slash         0x35
#define sc_SemiColon     0x27
#define sc_Quote         0x28
#define sc_Tilde         0x29
#define sc_BackSlash     0x2b
#define sc_OpenBracket   0x1a
#define sc_CloseBracket  0x1b

#define sc_1             0x02
#define sc_2             0x03
#define sc_3             0x04
#define sc_4             0x05
#define sc_5             0x06
#define sc_6             0x07
#define sc_7             0x08
#define sc_8             0x09
#define sc_9             0x0a
#define sc_0             0x0b
#define sc_Minus         0x0c
#define sc_Equals        0x0d
#define sc_Plus          0x0d

#define sc_kpad_1        0x4f
#define sc_kpad_2        0x50
#define sc_kpad_3        0x51
#define sc_kpad_4        0x4b
#define sc_kpad_5        0x4c
#define sc_kpad_6        0x4d
#define sc_kpad_7        0x47
#define sc_kpad_8        0x48
#define sc_kpad_9        0x49
#define sc_kpad_0        0x52
#define sc_kpad_Minus    0x4a
#define sc_kpad_Plus     0x4e
#define sc_kpad_Period   0x53

#define sc_A             0x1e
#define sc_B             0x30
#define sc_C             0x2e
#define sc_D             0x20
#define sc_E             0x12
#define sc_F             0x21
#define sc_G             0x22
#define sc_H             0x23
#define sc_I             0x17
#define sc_J             0x24
#define sc_K             0x25
#define sc_L             0x26
#define sc_M             0x32
#define sc_N             0x31
#define sc_O             0x18
#define sc_P             0x19
#define sc_Q             0x10
#define sc_R             0x13
#define sc_S             0x1f
#define sc_T             0x14
#define sc_U             0x16
#define sc_V             0x2f
#define sc_W             0x11
#define sc_X             0x2d
#define sc_Y             0x15
#define sc_Z             0x2c

/* Extended scan codes (Duke's remapping of E0-prefixed keys) */
#define sc_UpArrow       0x5a
#define sc_DownArrow     0x6a
#define sc_LeftArrow     0x6b
#define sc_RightArrow    0x6c
#define sc_Insert        0x5e
#define sc_Delete        0x5f
#define sc_Home          0x61
#define sc_End           0x62
#define sc_PgUp          0x63
#define sc_PgDn          0x64
#define sc_RightAlt      0x65
#define sc_RightControl  0x66
#define sc_kpad_Slash    0x67
#define sc_kpad_Enter    0x68
#define sc_PrintScreen   0x69
#define sc_LastScanCode  0x6e

/* ASCII codes for special keys */
#define asc_Enter        13
#define asc_Escape       27
#define asc_BackSpace    8
#define asc_Tab          9
#define asc_Space        32

#define MAXKEYBOARDSCAN  128

/* Keyboard state */
extern volatile byte        KB_KeyDown[MAXKEYBOARDSCAN];
extern volatile kb_scancode KB_LastScan;

/* Keyboard macros (match originals exactly) */
#define KB_GetLastScanCode()       (KB_LastScan)
#define KB_SetLastScanCode(sc)     { KB_LastScan = (sc); }
#define KB_ClearLastScanCode()     { KB_SetLastScanCode(sc_None); }
#define KB_KeyPressed(scan)        (KB_KeyDown[(scan)] != 0)
#define KB_ClearKeyDown(scan)      { KB_KeyDown[(scan)] = false; }

void      KB_KeyEvent(int scancode, boolean keypressed);
boolean   KB_KeyWaiting(void);
char      KB_Getch(void);
void      KB_Addch(char ch);
void      KB_FlushKeyboardQueue(void);
void      KB_ClearKeysDown(void);
char     *KB_ScanCodeToString(kb_scancode scancode);
kb_scancode KB_StringToScanCode(char *string);
void      KB_TurnKeypadOn(void);
void      KB_TurnKeypadOff(void);
boolean   KB_KeypadActive(void);
void      KB_Startup(void);
void      KB_Shutdown(void);

/* Alternate spelling used in some game code paths */
#define KB_FlushKeyBoardQueue KB_FlushKeyboardQueue
#define KB_GetCh              KB_Getch

/* ═══════════════════════════════════════════════════════════════════
   CONTROL.H – input control system (originally in MACT library)
   ═══════════════════════════════════════════════════════════════════ */

#define MaxJoys        2
#define MAXGAMEBUTTONS 64

#define BUTTON(x) \
    (((x) > 31) ? ((CONTROL_ButtonState2 >> ((x) - 32)) & 1) \
                : ((CONTROL_ButtonState1 >> (x)) & 1))
#define BUTTONHELD(x) \
    (((x) > 31) ? ((CONTROL_ButtonHeldState2 >> ((x) - 32)) & 1) \
                : ((CONTROL_ButtonHeldState1 >> (x)) & 1))
#define BUTTONJUSTPRESSED(x)  (BUTTON(x) && !BUTTONHELD(x))
#define BUTTONRELEASED(x)     (!BUTTON(x) && BUTTONHELD(x))
#define BUTTONSTATECHANGED(x) (BUTTON(x) != BUTTONHELD(x))

typedef enum {
    axis_up, axis_down, axis_left, axis_right
} axisdirection;

typedef enum {
    analog_turning = 0,
    analog_strafing = 1,
    analog_lookingupanddown = 2,
    analog_elevation = 3,
    analog_rolling = 4,
    analog_moving = 5,
    analog_maxtype
} analogcontrol;

typedef enum {
    dir_North, dir_NorthEast, dir_East, dir_SouthEast,
    dir_South, dir_SouthWest, dir_West, dir_NorthWest, dir_None
} direction;

typedef struct {
    boolean   button0;
    boolean   button1;
    direction dir;
} UserInput;

typedef struct {
    fixed dx;
    fixed dy;
    fixed dz;
    fixed dyaw;
    fixed dpitch;
    fixed droll;
} ControlInfo;

typedef enum {
    controltype_keyboard,
    controltype_keyboardandmouse,
    controltype_keyboardandjoystick,
    controltype_keyboardandexternal,
    controltype_keyboardandgamepad,
    controltype_keyboardandflightstick,
    controltype_keyboardandthrustmaster
} controltype;

/* Global state */
extern boolean CONTROL_RudderEnabled;
extern boolean CONTROL_MousePresent;
extern boolean CONTROL_JoysPresent[MaxJoys];
extern boolean CONTROL_MouseEnabled;
extern boolean CONTROL_JoystickEnabled;
extern byte    CONTROL_JoystickPort;
extern uint32  CONTROL_ButtonState1;
extern uint32  CONTROL_ButtonHeldState1;
extern uint32  CONTROL_ButtonState2;
extern uint32  CONTROL_ButtonHeldState2;

void    CONTROL_MapKey(int32 which, kb_scancode key1, kb_scancode key2);
void    CONTROL_MapButton(int32 whichfunction, int32 whichbutton,
                          boolean doubleclicked);
void    CONTROL_DefineFlag(int32 which, boolean toggle);
boolean CONTROL_FlagActive(int32 which);
void    CONTROL_ClearAssignments(void);
void    CONTROL_GetUserInput(UserInput *info);
void    CONTROL_GetInput(ControlInfo *info);
void    CONTROL_ClearButton(int32 whichbutton);
void    CONTROL_ClearUserInput(UserInput *info);
void    CONTROL_WaitRelease(void);
void    CONTROL_Ack(void);
void    CONTROL_CenterJoystick(void (*CenterCenter)(void),
                               void (*UpperLeft)(void),
                               void (*LowerRight)(void),
                               void (*CenterThrottle)(void),
                               void (*CenterRudder)(void));
int32   CONTROL_GetMouseSensitivity(void);
void    CONTROL_SetMouseSensitivity(int32 newsensitivity);
void    CONTROL_Startup(controltype which, int32 (*TimeFunction)(void),
                        int32 ticspersecond);
void    CONTROL_Shutdown(void);
void    CONTROL_MapAnalogAxis(int32 whichaxis, int32 whichanalog);
void    CONTROL_MapDigitalAxis(int32 whichaxis, int32 whichfunction,
                               int32 direction);
void    CONTROL_SetAnalogAxisScale(int32 whichaxis, int32 axisscale);
void    CONTROL_PrintAxes(void);

#ifdef __cplusplus
}
#endif
#endif /* AUDIO_STUB_H */
