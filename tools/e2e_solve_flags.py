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

Currently implemented and validated end-to-end: all five flags —
0 & 1 (boss god-mode), 3 (ghost teleport, via the CTF-1 level-load sync),
4 (vault code + file), and 2 (frozen clock). Windows-only (WriteProcessMemory).
"""
import argparse
import contextlib
import ctypes
import ctypes.wintypes as wt
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    from filelock import FileLock
except ImportError:  # filelock is a pinned requirement; degrade to no-op if absent
    FileLock = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMMAP_LOG = PROJECT_ROOT / "atomic_shell_memory_map.log"
FLAGS_LOG = PROJECT_ROOT / "atomic_shell_flags.log"

FLAG_TEXT = {
    0: "ghvctf{g0dm0d3_4ct1v4t3d}",
    1: "ghvctf{sh13ld_d0wn_r3v34l3d}",
    2: "ghvctf{t1m3_1s_4_fl4t_c1rcl3}",
    3: "ghvctf{gh0st_w4lk3r}",
    4: "ghvctf{m4st3r_h4x0r_0v3rm1nd}",
    5: "ghvctf{c0d3_3x3c_h1j4ck}",
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
                "ctf_timer_start", "ctf_vault_code", "ctf_ghost_target_x",
                "ctf_ghost_target_y", "ctf_ghost_target_z", "ctf_boss1_sprite",
                "ctf_boss2_sprite", "ctf_vault_unlocked",
                "ctf_codeexec_hook", "ctf_grant_codeexec"]:
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
    for f in (MEMMAP_LOG, FLAGS_LOG, PROJECT_ROOT / "vault_input.txt"):
        f.unlink(missing_ok=True)   # missing_ok: tolerate a concurrent cleanup
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


def solve_flag4(mem, mm):
    """Flag 4 — Vault: read ctf_vault_code, submit it via vault_input.txt, and be
    in the vault sector (lotag 0x5641, the connected room near (35840, 5120)).
    The game re-checks the file every ~30 ticks."""
    code = mem.read_i32(mm["ctf_vault_code"])
    if not code or code <= 0:
        return False
    (PROJECT_ROOT / "vault_input.txt").write_text(str(int(code)))
    vault_x, vault_y = 35840, 5120        # room 3 center (generate_ctf_map.py)
    deadline = time.time() + 18.0
    while time.time() < deadline:
        mem.write_i32(mm["player_posx"], vault_x)
        mem.write_i32(mm["player_posy"], vault_y)
        if FLAGS_LOG.is_file() and FLAG_TEXT[4] in FLAGS_LOG.read_text(errors="replace"):
            return True
        time.sleep(0.1)
    return False


def solve_flag2(mem, mm):
    """Flag 2 — Frozen clock: enter the timer room (lotag 0x544D) to arm
    ctf_timer=3600, then FREEZE it > 0 so the kill branch never fires. The engine
    emits the flag once 3600 game-tics have elapsed since the timer armed while
    ctf_timer is still positive — i.e. you outlasted a countdown that should have
    killed you. (See CTF-3 in the I1 spec: the threshold is measured in game-tics,
    so freezing is genuinely required.)

    Outlasting 3600 game-tics is ~2 min of real time, so for a fast, deterministic
    test we use the published `ctf_timer_start` hack surface: keep ctf_timer frozen
    high AND rewind ctf_timer_start so the deadline passes immediately. A player can
    instead just freeze ctf_timer and wait out the ~2 min.

    We teleport to a CORNER of the timer room (still sector 2), not its centre:
    the centre holds a hostile boss, and welding the player onto it via memory
    writes makes the boss spew projectiles until the sprite pool exhausts
    ("Too many sprites spawned.")."""
    timer_x, timer_y = 21500, 1600     # timer-room corner (sector 2), clear of boss
    have_start = "ctf_timer_start" in mm
    deadline = time.time() + 30.0
    while time.time() < deadline:
        mem.write_i32(mm["player_posx"], timer_x)   # hold in the timer room
        mem.write_i32(mm["player_posy"], timer_y)
        t = mem.read_i32(mm["ctf_timer"])
        if t is not None and t >= 0:
            mem.write_i32(mm["ctf_timer"], 3500)    # freeze high (required to survive)
            if have_start:
                start = mem.read_i32(mm["ctf_timer_start"])
                if start is not None:
                    mem.write_i32(mm["ctf_timer_start"], start - 16400)  # rewind past deadline
        if FLAGS_LOG.is_file() and FLAG_TEXT[2] in FLAGS_LOG.read_text(errors="replace"):
            return True
        time.sleep(0.05)
    return False


def solve_flag5(mem, mm):
    """Flag 5 — control-flow hijack: write the published ctf_grant_codeexec function
    address into the ctf_codeexec_hook slot the engine calls each CTF tick. The engine
    then executes the player-chosen target and emits the flag (a callback hijack)."""
    hook = mm.get("ctf_codeexec_hook")
    target = mm.get("ctf_grant_codeexec")
    if not hook or not target:
        return False
    payload = int(target).to_bytes(8, "little")
    deadline = time.time() + 12.0
    while time.time() < deadline:
        mem.write(hook, payload)
        if FLAGS_LOG.is_file() and FLAG_TEXT[5] in FLAGS_LOG.read_text(errors="replace"):
            return True
        time.sleep(0.05)
    return False


SOLVERS = {0: solve_flag0, 1: solve_flag1, 2: solve_flag2,
           3: solve_flag3, 4: solve_flag4, 5: solve_flag5}


# ── main ────────────────────────────────────────────────────────────────────
def _solve_lock():
    """Inter-process lock so concurrent solve() runs (e.g. test_solve_flags +
    test_ctf_events under pytest-xdist) don't race on the SHARED PROJECT_ROOT CTF
    logs (atomic_shell_memory_map.log / atomic_shell_flags.log / vault_input.txt) —
    the harness launches the engine in PROJECT_ROOT and those paths are fixed.
    Degrades to a no-op if filelock is unavailable."""
    if FileLock is None:
        return contextlib.nullcontext()
    name = "atomic_shell_solve_" + hashlib.sha1(
        str(PROJECT_ROOT).encode("utf-8")).hexdigest()[:16] + ".lock"
    return FileLock(os.path.join(tempfile.gettempdir(), name), timeout=300)


def solve(flags, verbose=True, extra_env=None):
    if sys.platform != "win32":
        print("e2e_solve_flags: Windows-only (WriteProcessMemory)")
        return {}
    with _solve_lock():
        return _solve_inner(flags, verbose, extra_env)


def _solve_inner(flags, verbose, extra_env):
    proc = launch(extra_env)
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


# ── boss-damage-ramp probe (boss-dmg-tune / D3) ─────────────────────────────
def _read_health_addr(text):
    m = re.search(r"^player_health\s*=\s*(0x[0-9A-Fa-f]+)", text, re.M)
    return int(m.group(1), 16) if m else None


def _probe_boss_damage_inner(verbose):
    """Teleport the player onto boss1 with high HP and sample player_health while
    holding position, measuring how the boss's proximity-damage CON drains HP.

    With the boss-dmg-tune ramp (addphealth -3/tic) the player SURVIVES proximity
    contact and HP declines gradually (300 -> 297 -> 294 ...). With the old instant
    kill (addphealth -1000) the very first in-range tic craters HP to <=0. (A boss
    *projectile* eventually lands for big damage once its AI engages — that's the
    boss's weapon, not the proximity aura — so we read the gradual ramp from the
    first samples, before any projectile/weld effects.)"""
    result = {"ok": False, "initial_hp": None, "samples": [],
              "near_full_alive": 0, "took_damage": False, "first_drop": None}
    proc = launch()
    try:
        mm = wait_memmap()
        if mm is None:
            if verbose:
                print("probe: memory map not written (level never entered?)")
            return result
        hp_addr = _read_health_addr(MEMMAP_LOG.read_text(errors="replace"))
        if hp_addr is None:
            if verbose:
                print("probe: player_health address not found in memmap")
            return result
        mem = Mem(proc.pid)
        try:
            base, sz = mm["sprite_base"], mm["sprite_size"]
            # wait for boss1's sprite slot to be assigned, with sane world coords
            idx = -1
            bx = by = bz = None
            deadline = time.time() + 15.0
            while time.time() < deadline:
                idx = mem.read_i16(mm["ctf_boss1_sprite"])
                if idx is not None and idx >= 0:
                    bx = mem.read_i32(base + idx * sz + 0)
                    by = mem.read_i32(base + idx * sz + 4)
                    bz = mem.read_i32(base + idx * sz + 8)
                    if bx is not None and abs(bx) < 100000 and abs(by) < 100000:
                        break
                time.sleep(0.1)
            if bx is None or abs(bx) >= 100000:
                if verbose:
                    print("probe: no valid boss1 position")
                return result
            result["initial_hp"] = mem.read_i16(hp_addr)
            # write high HP and teleport onto boss1 (its own sector is valid)
            mem.write_i32(mm["player_posx"], bx)
            mem.write_i32(mm["player_posy"], by)
            mem.write_i32(mm["player_posz"], bz)
            WRITTEN_HP = 300
            mem.write_i16(hp_addr, WRITTEN_HP)
            samples = []
            t0 = time.time()
            while time.time() - t0 < 0.6:
                bx = mem.read_i32(base + idx * sz + 0)
                by = mem.read_i32(base + idx * sz + 4)
                bz = mem.read_i32(base + idx * sz + 8)
                if bx is not None and abs(bx) < 100000:
                    mem.write_i32(mm["player_posx"], bx)
                    mem.write_i32(mm["player_posy"], by)
                    mem.write_i32(mm["player_posz"], bz)
                hp = mem.read_i16(hp_addr)
                samples.append(hp)
                time.sleep(0.02)
            result["samples"] = samples
            # samples where the player is alive and near the written HP (survived
            # proximity contact). With -1000 this collapses to ~1 (instant death).
            nf = [h for h in samples if h is not None and 100 < h <= WRITTEN_HP]
            result["near_full_alive"] = len(nf)
            result["took_damage"] = bool(nf) and min(nf) < WRITTEN_HP
            # first downward step from full == the per-tic proximity drop (~3, not ~300)
            for h in samples:
                if h is not None and h < WRITTEN_HP:
                    result["first_drop"] = WRITTEN_HP - h
                    break
            result["ok"] = True
            if verbose:
                print(f"probe: initial_hp={result['initial_hp']} samples={samples}")
                print(f"probe: near_full_alive={result['near_full_alive']} "
                      f"took_damage={result['took_damage']} "
                      f"first_drop={result['first_drop']}")
        finally:
            mem.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    return result


def probe_boss_damage_ramp(verbose=True):
    """Public entry: measure boss1 proximity-damage drain (boss-dmg-tune backpressure).
    Serialized against solve() via the shared PROJECT_ROOT lock (same logs/process)."""
    if sys.platform != "win32":
        print("probe_boss_damage_ramp: Windows-only (Read/WriteProcessMemory)")
        return {"ok": False}
    with _solve_lock():
        return _probe_boss_damage_inner(verbose)


def main():
    ap = argparse.ArgumentParser(description="Solve Atomic Shell CTF flags headless")
    ap.add_argument("--flags", default="0,1,2,3,4",
                    help="comma-separated flag indices to solve (default: all five "
                         "0,1,2,3,4 — every flag is validated end-to-end)")
    args = ap.parse_args()
    flags = [int(x) for x in args.flags.split(",") if x.strip() != ""]
    captured = solve(flags)
    ok = all(captured.get(n) for n in flags)
    print(f"\n{sum(1 for n in flags if captured.get(n))}/{len(flags)} flags captured")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
