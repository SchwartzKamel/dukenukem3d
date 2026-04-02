# Optimize Software Rendering Performance

## Priority: Medium

## Description
The C replacements for the original x86 ASM rendering functions (vlineasm1, hlineasm4, etc.) in ENGINE.C are functional but unoptimized. Profile and optimize the hot rendering paths.

## Requirements
- Profile with `perf` or `gprof` to identify hottest functions
- Optimize `vlineasm1` / `vlineasm4` (vertical column drawing — the #1 bottleneck)
- Optimize `hlineasm4` (horizontal span drawing)
- Consider SIMD intrinsics (SSE2/AVX2) for batch pixel operations
- Optimize `drawslab` for status bar rendering
- Consider compiler hints: `__builtin_expect`, `restrict`, `__attribute__((hot))`
- Benchmark before/after with a fixed camera position

## Files to modify
- `SRC/ENGINE.C` — rendering functions (~lines 300-650)
- `Makefile` — add `-O2` or `-O3` optimization flag (currently missing!)

## Testing
- FPS counter or frame time measurement
- Visual output must be identical before/after
