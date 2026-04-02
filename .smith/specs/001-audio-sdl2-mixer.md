# Implement Audio via SDL2_mixer

## Priority: High

## Description
Replace the silent audio stubs in `compat/audio_stub.c` with a working SDL2_mixer implementation. Currently all FX_* and MUSIC_* functions are no-ops.

## Requirements
- Initialize SDL2_mixer in `FX_Init()` 
- Load and play WAV/VOC sound effects via `FX_PlaySound()` / `FX_Play3D()`
- Load and play MIDI music via `MUSIC_PlaySong()`
- Implement volume control (`FX_SetVolume`, `MUSIC_SetVolume`)
- 3D positional audio panning based on player position
- Graceful fallback if SDL2_mixer unavailable

## Files to modify
- `compat/audio_stub.c` — replace stubs with SDL2_mixer calls
- `compat/audio_stub.h` — add SDL2_mixer includes
- `Makefile` — add `-lSDL2_mixer` link flag

## Testing
- Build should still pass with and without SDL2_mixer installed
- Sound effects should play when triggered in-game
- Music should loop correctly
