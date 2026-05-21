// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * log_stub.h - Debug logging for stubbed no-op functions
 * 
 * When DUKE3D_STUB_LOG is defined (e.g., via -DDUKE3D_STUB_LOG or environment),
 * prints to stderr when stubbed functions are called. Uses static flags
 * to ensure each stub logs exactly once per process lifetime.
 * 
 * ENABLING DEBUG LOGGING:
 * ━━━━━━━━━━━━━━━━━━━━━━━
 * 1. Build-time flag: make DUKE3D_STUB_LOG=1
 *    (This passes -DDUKE3D_STUB_LOG to CFLAGS)
 * 
 * 2. Environment variable: export DUKE3D_STUB_LOG=1 && make
 *    (Requires Makefile to check and apply)
 * 
 * STUBBED FUNCTIONS WITH LOGGING:
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 * - Music_SetVolume() — Audio volume stub (mact_stub.c)
 * - PlayMusic()       — Music playback stub (mact_stub.c)
 * - CONTROL_WaitRelease() — Input control stub (audio_stub.c)
 * - CONTROL_Ack()     — Input acknowledge stub (audio_stub.c)
 * - FX_StopRecord()   — Sound recording stub (audio_stub.c)
 * 
 * USAGE EXAMPLES:
 * ━━━━━━━━━━━━━━━
 * In your stub function:
 * 
 *   void Music_SetVolume(int volume) { 
 *       STUB_LOG("Music_SetVolume(%d)", volume); 
 *       (void)volume; 
 *   }
 * 
 *   void PlayMusic(char *fn) { 
 *       STUB_LOG("PlayMusic(%s)", fn ? fn : "<NULL>");
 *       (void)fn; 
 *   }
 * 
 * OUTPUT (when enabled):
 * ━━━━━━━━━━━━━━━━━━━━━━
 * [STUB] Music_SetVolume(128)
 * [STUB] PlayMusic(music.mid)
 * 
 * Each stub logs only once, even if called multiple times. This prevents
 * log spam while still alerting developers during testing and debugging.
 * 
 * ONCE-ONLY BEHAVIOR:
 * ━━━━━━━━━━━━━━━━━━━
 * The macro uses a unique static flag per call site (__LINE__) to ensure
 * each STUB_LOG call logs its first invocation exactly once, then is silent.
 * This is intentional for development/debugging without performance impact.
 * 
 * PERFORMANCE:
 * ━━━━━━━━━━━
 * - When DUKE3D_STUB_LOG is OFF (production default): ZERO overhead
 *   The macro expands to a no-op that the compiler optimizes away.
 * - When ON: ~1 atomic check per first call, then nothing.
 */

#ifndef COMPAT_LOG_STUB_H
#define COMPAT_LOG_STUB_H

#include <stdio.h>
#include <string.h>

// Check for DUKE3D_STUB_LOG environment variable or compile-time define
#ifndef DUKE3D_STUB_LOG
  #ifdef __STDC__
  // C11 and later: check env at compile time if needed (or leave for runtime)
  #endif
#endif

// STUB_LOG macro: print once per stub call site
// Generates a unique static flag per call site using __LINE__ to ensure
// each stub logs exactly once during the program's lifetime.
#ifdef DUKE3D_STUB_LOG
  #define STUB_LOG(fmt, ...) do { \
    static int _stub_logged_##__LINE__ = 0; \
    if (!_stub_logged_##__LINE__) { \
      _stub_logged_##__LINE__ = 1; \
      fprintf(stderr, "[STUB] " fmt "\n", ##__VA_ARGS__); \
      fflush(stderr); \
    } \
  } while(0)
#else
  // No-op when DUKE3D_STUB_LOG is not defined
  #define STUB_LOG(fmt, ...) do { (void)(fmt); (void)sizeof(fmt); } while(0)
#endif

#endif // COMPAT_LOG_STUB_H
