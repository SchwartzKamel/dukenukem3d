#!/usr/bin/env python3
"""I1 — solve-each-flag E2E harness (Atomic Shell CTF).

Launches the game headless into the CTF arena, then captures the hidden
`ghvctf{...}` flags by memory-hacking the running process (the "hackable by
design" challenge), exactly as a player would with Cheat Engine / scouter.

All hack targets are published by the engine at level entry in
`atomic_shell_memory_map.log` (stable, no-ASLR addresses). Each captured flag is
written by the engine to `atomic_shell_flags.log`.

This is the project's demo-validation backbone and the holdout for the attended
`intptr_t` migration (E1). Built one flag at a time per
`docs/plans/2026-06-14_I1_SPEC.md`.

Currently implemented: Flags 0, 1 & 3 (boss god-mode + ghost teleport — validated
end-to-end). Flags 4 & 2 are not yet implemented. Windows-only (WriteProcessMemory).
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMMAP_LOG = PROJECT_ROOT / "atomic_shell_memory_map.log"
FLAGS_LOG = PROJECT_ROOT / "atomic_shell_flags.log"

FLAG_TEXT = {
    0: "ghvctf{g0dm0d3_4ct1v4t3d}",
    1: "ghvctf{sh13ld_d0wn_r3v34l3d}",
    2: "ghvctf{t1m3_1s_4_fl4t_c1rcl3}",
    3: "ghvctf{gh0st_w4lk3r}",
    4: "ghvctf{m4st3r_h4x0r_0v3rm1nd}",
}

# ── Win32 process memory ────────────────────────────────────────────────────
if sys.platform == "win32":
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _PROCESS_ACCESS = 0x0008 | 0x0010 | 0x0020 | 0x0400  # OPERATION|READ|WRITE|QUERY
    _k32.OpenProcess.restype = wt.HANDLE
    _k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    _k32.ReadProcessMemory.argtypes = [wt.HANDLE, wt.LPCVOID, wt.LPVOID,
                                       ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    _k32.WriteProcessMemory.argtypes = [wt.HANDLE, wt.LPVOID, wt.LPCVOID,
                                        ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    _k32.CloseHandle.argtypes = [wt.HANDLE]


class Mem:
    def __init__(self, pid):
        self.h = _k32.OpenProcess(_PROCESS_ACCESS, False, pid)
        if not self.h:
            raise OSError(f"OpenProcess({pid}) failed: {ctypes.get_last_error()}")

    def read(self, addr, size):
        buf = (ctypes.c_char * size)()
        n = ctypes.c_size_t(0)
        if not _k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, size,
                                      ctypes.byref(n)):
            return None
        return bytes(buf[:n.value])

    def write(self, addr, data):
        n = ctypes.c_size_t(0)
        ok = _k32.WriteProcessMemory(self.h, ctypes.c_void_p(addr), data, len(data),
                                     ctypes.byref(n))
        return bool(ok) and n.value == len(data)

    def read_i16(self, addr):
        b = self.read(addr, 2)
        return int.from_bytes(b, "little", signed=True) if b else None

    def read_i32(self, addr):
        b = self.read(addr, 4)
        return int.from_bytes(b, "little", signed=True) if b else None

    def write_i16(self, addr, v):
        return self.write(addr, int(v).to_bytes(2, "little", signed=True))

    def write_i32(self, addr, v):
        return self.write(addr, int(v).to_bytes(4, "little", signed=True))

    def close(self):
        if self.h:
            _k32.CloseHandle(self.h)
            self.h = None


# ── helpers ─────────────────────────────────────────────────────────────────
def _resolve_binary():
    exe = "duke3d.exe"
    for c in [PROJECT_ROOT / "build" / "Release" / exe,
              PROJECT_ROOT / "build" / exe, PROJECT_ROOT / exe]:
        if c.is_file():
            return c
    return None


def parse_memmap(text):
    mm = {}
    for key in ["player_posx", "player_posy", "player_posz", "ctf_timer",
                "ctf_vault_code", "ctf_ghost_target_x", "ctf_ghost_target_y",
                "ctf_ghost_target_z", "ctf_boss1_sprite", "ctf_boss2_sprite",
                "ctf_vault_unlocked"]:
        m = re.search(rf"^{key}\s*=\s*(0x[0-9A-Fa-f]+)", text, re.M)
        if m:
            mm[key] = int(m.group(1), 16)
    m = re.search(r"sprite\[\] array base\s*=\s*(0x[0-9A-Fa-f]+)", text)
    if m:
        mm["sprite_base"] = int(m.group(1), 16)
    m = re.search(r"each sprite\s*=\s*(\d+)\s*bytes", text)
    mm["sprite_size"] = int(m.group(1)) if m else 44
    m = re.search(r"boss_health offset within sprite\s*=\s*(\d+)", text)
    mm["extra_offset"] = int(m.group(1)) if m else 42
    return mm


def launch(extra_env=None):
    binary = _resolve_binary()
    if binary is None or not binary.is_file():
        raise FileNotFoundError("duke3d.exe not built")
    if not (PROJECT_ROOT / "DUKE3D.GRP").is_file():
        raise FileNotFoundError("DUKE3D.GRP not generated")
    for f in (MEMMAP_LOG, FLAGS_LOG):
        if f.exists():
            f.unlink()
    env = os.environ.copy()
    env.update({
        "SDL_VIDEODRIVER": "dummy", "DUKE3D_HEADLESS": "1", "DUKE3D_SKIP_LOGO": "1",
        "DUKE3D_SILENT_ERRORS": "1", "DUKE3D_AUTOPLAY": "1",
        "DUKE3D_MENU_KEYS": "28,28,28",   # Enter x3 -> NEW GAME -> CTF1.MAP
    })
    if extra_env:
        env.update(extra_env)
    return subprocess.Popen([str(binary)], cwd=str(PROJECT_ROOT), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_memmap(timeout=40.0):
    """Poll until the memory-map log is present with the keys we need."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if MEMMAP_LOG.is_file():
            text = MEMMAP_LOG.read_text(errors="replace")
            mm = parse_memmap(text)
            if "sprite_base" in mm and "ctf_boss1_sprite" in mm:
                return mm
        time.sleep(0.25)
    return None


def flag_in_log(n, timeout=15.0):
    """Poll the flags log for flag n's text."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if FLAGS_LOG.is_file():
            if FLAG_TEXT[n] in FLAGS_LOG.read_text(errors="replace"):
                return True
        time.sleep(0.2)
    return False


# ── solvers (one per flag) ──────────────────────────────────────────────────
def _solve_boss(mem, mm, sprite_key):
    """Boss god-mode: write sprite[<boss>].extra <= 0 (health hack)."""
    deadline = time.time() + 15.0
    while time.time() < deadline:
        idx = mem.read_i16(mm[sprite_key])
        if idx is not None and idx >= 0:
            addr = mm["sprite_base"] + idx * mm["sprite_size"] + mm["extra_offset"]
            if mem.write_i16(addr, 0):
                return True
        time.sleep(0.25)
    return False


def solve_flag0(mem, mm):
    """Flag 0 — Meatbag boss god-mode."""
    return _solve_boss(mem, mm, "ctf_boss1_sprite")


def solve_flag1(mem, mm):
    """Flag 1 — Warden boss god-mode."""
    return _solve_boss(mem, mm, "ctf_boss2_sprite")


def solve_flag3(mem, mm):
    """Flag 3 — Ghost walk: teleport into the sealed room by copying the exposed
    ctf_ghost_target_{x,y,z} into player_pos{x,y,z}, held for a few ticks. The
    ghost sector is large, so re-writing position keeps cursectnum there while
    the engine accumulates the >=5 ghost ticks. (Works since CTF-1 synced the
    target to the real ghost sector at level load.)"""
    gx = mem.read_i32(mm["ctf_ghost_target_x"])
    gy = mem.read_i32(mm["ctf_ghost_target_y"])
    gz = mem.read_i32(mm["ctf_ghost_target_z"])
    if gx is None or (gx == 0 and gy == 0):
        return False
    deadline = time.time() + 12.0
    while time.time() < deadline:
        mem.write_i32(mm["player_posx"], gx)
        mem.write_i32(mm["player_posy"], gy)
        mem.write_i32(mm["player_posz"], gz)
        if FLAGS_LOG.is_file() and FLAG_TEXT[3] in FLAGS_LOG.read_text(errors="replace"):
            return True
        time.sleep(0.05)
    return False


SOLVERS = {0: solve_flag0, 1: solve_flag1, 3: solve_flag3}


# ── main ────────────────────────────────────────────────────────────────────
def solve(flags, verbose=True):
    if sys.platform != "win32":
        print("e2e_solve_flags: Windows-only (WriteProcessMemory)")
        return {}
    proc = launch()
    captured = {}
    try:
        mm = wait_memmap()
        if mm is None:
            print("FAIL: memory map not written (level never entered?)")
            return captured
        mem = Mem(proc.pid)
        try:
            for n in flags:
                solver = SOLVERS.get(n)
                if solver is None:
                    print(f"flag {n}: no solver yet (see I1 spec)")
                    continue
                ok_write = solver(mem, mm)
                ok_flag = flag_in_log(n) if ok_write else False
                captured[n] = ok_flag
                if verbose:
                    print(f"flag {n} ({FLAG_TEXT[n]}): "
                          f"{'CAPTURED' if ok_flag else 'FAILED'}")
        finally:
            mem.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    return captured


def main():
    ap = argparse.ArgumentParser(description="Solve Atomic Shell CTF flags headless")
    ap.add_argument("--flags", default="0,1,3",
                    help="comma-separated flag indices to solve (default: 0,1,3 — "
                         "the validated boss + ghost flags; 4/2 are WIP)")
    args = ap.parse_args()
    flags = [int(x) for x in args.flags.split(",") if x.strip() != ""]
    captured = solve(flags)
    ok = all(captured.get(n) for n in flags)
    print(f"\n{sum(1 for n in flags if captured.get(n))}/{len(flags)} flags captured")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
