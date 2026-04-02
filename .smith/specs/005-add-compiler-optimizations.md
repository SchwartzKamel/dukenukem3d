# Add Compiler Optimization Flags

## Priority: High

## Description
The Makefile currently compiles without any optimization flags (`-O0` by default). Add proper optimization levels for release builds and keep debug builds available.

## Requirements
- Default build: `-O2 -DNDEBUG` for release performance
- `make debug`: `-O0 -g -DDEBUG` for debugging
- Add `-march=native` option for local builds
- Add `-flto` (link-time optimization) for release builds
- Windows cross-compile should also use `-O2`
- Consider `-ffast-math` for rendering code (test for correctness)

## Files to modify
- `Makefile` — add BUILD_TYPE variable, optimization flags

## Testing
- `make` produces optimized binary
- `make debug` produces debuggable binary  
- Both pass all tests
- Measure FPS improvement from -O2
