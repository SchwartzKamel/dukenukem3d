#!/usr/bin/env python3
"""Asset generation pipeline for Duke Nukem 3D.

Generates textures (via FLUX.2-pro AI or procedural fallback), converts them
to BUILD engine format and packs everything into a playable DUKE3D.GRP.

Usage:
    python3 tools/generate_assets.py [--no-ai]
"""

import argparse
import base64
import io
import math
import os
import random
import shutil
import struct
import sys
import time

from PIL import Image, ImageDraw

# Ensure the tools package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anm_format import create_placeholder_anm
from art_format import create_art_file, rgb_to_column_major
from demo_format import create_demo_stub, create_timbre_stub
from grp_format import create_grp
from map_format import create_level_map, create_test_map
from midi_format import create_simple_midi
from palette import build_palette, create_palette_dat, quantize_image
from tables import create_tables_dat
from voc_format import create_voc_stub

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TESTDATA_DIR = os.path.join(PROJECT_ROOT, "testdata")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "generated_assets")
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")

# Texture definitions: (tile_num, width, height, description, flux_prompt)
TEXTURE_DEFS = [
    # Walls
    (0, 64, 64, "Dark steel wall panel",
     "seamless tileable dark brushed steel wall panel texture with subtle rivets, cyberpunk industrial, moody dark lighting, game texture 64x64"),
    (1, 64, 64, "Corroded metal floor",
     "seamless tileable corroded industrial metal floor grating texture, rust stains, puddles, cyberpunk industrial, game texture 64x64"),
    (2, 64, 64, "Exposed pipe ceiling",
     "seamless tileable industrial ceiling with exposed pipes and conduits, dark metal, occasional dripping, cyberpunk, game texture 64x64"),
    (3, 64, 64, "Neon circuit wall",
     "seamless tileable dark wall panel with glowing cyan circuit traces and neon lines, cyberpunk tech wall, game texture 64x64"),
    (4, 64, 64, "Hazard stripe wall",
     "seamless tileable industrial wall with yellow-black hazard stripes and warning signs, grungy, game texture 64x64"),
    (5, 64, 64, "Hex tile floor",
     "seamless tileable dark hexagonal metal tile floor, cyberpunk industrial, subtle blue reflection, game texture 64x64"),
    (6, 128, 128, "Neon cityscape sky",
     "dark cyberpunk night sky with distant neon-lit skyscrapers, rain, smog, purple and cyan city lights, game skybox texture"),
    (7, 64, 64, "Blast door",
     "heavy industrial blast door texture with hydraulic pistons, warning lights, cyberpunk, game texture 64x64"),
    (8, 64, 64, "Toxic waste pool",
     "seamless tileable glowing toxic green radioactive liquid surface, bubbling, cyberpunk hazard, game texture 64x64"),
    (9, 64, 64, "Holographic terminal",
     "retro cyberpunk computer terminal with glowing cyan holographic display, scan lines, matrix-style text, game texture 64x64"),
    (10, 64, 64, "Concrete bunker wall",
     "seamless tileable cracked dark concrete bunker wall, cyberpunk grunge, spray paint tags, game texture 64x64"),
    (11, 64, 64, "Neon sign wall",
     "seamless tileable dark wall with flickering neon signs in pink and cyan, Japanese characters, cyberpunk alley, game texture 64x64"),
    (12, 64, 64, "Grated catwalk floor",
     "seamless tileable metal grated catwalk floor, see-through holes, industrial cyberpunk, game texture 64x64"),
    (13, 64, 64, "Bio-growth wall",
     "seamless tileable dark wall with bioluminescent green fungal growth, alien cyberpunk, organic decay, game texture 64x64"),
    (14, 64, 64, "Rust-eaten metal",
     "seamless tileable heavily rusted corroded metal wall, orange-brown decay, cyberpunk industrial ruin, game texture 64x64"),
    (15, 64, 64, "Magma vent",
     "seamless tileable glowing orange magma lava flow through cracked dark rock, game texture 64x64"),
    (16, 64, 64, "Cryo chamber wall",
     "seamless tileable frosted ice-blue cryo-chamber wall, frozen pipes, cyberpunk cold storage, game texture 64x64"),
    (17, 64, 64, "Sandblasted plate",
     "seamless tileable sandblasted gunmetal plate texture, industrial scratches, cyberpunk, game texture 64x64"),
    (18, 64, 64, "Marble command floor",
     "seamless tileable dark polished marble floor with gold inlay lines, cyberpunk executive suite, game texture 64x64"),
    (19, 64, 64, "Server rack wall",
     "seamless tileable wall of server racks with blinking LEDs red green blue, dark data center, cyberpunk, game texture 64x64"),
]

# Small item/sprite placeholder tiles
SPRITE_DEFS = [
    (20, 32, 32, "Stim-pack health"),
    (21, 32, 32, "Plasma cell ammo"),
    (22, 32, 32, "Nano-shield armor"),
    (23, 32, 32, "Access chip blue"),
    (24, 32, 32, "Access chip red"),
    (25, 32, 32, "Access chip gold"),
    (26, 32, 32, "Pulse pistol"),
    (27, 32, 32, "Scatter cannon"),
    (28, 32, 32, "Plasma launcher"),
    (29, 32, 32, "Explosion burst"),
]

# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------

def load_env(path):
    """Parse a simple KEY=VALUE .env file."""
    env = {}
    if not os.path.exists(path):
        return env
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip()
    return env

# ---------------------------------------------------------------------------
# FLUX AI texture generation
# ---------------------------------------------------------------------------

def generate_texture_ai(prompt, width, height, endpoint, api_key, model="FLUX.2-pro"):
    """Call FLUX.2-pro to generate a texture. Returns a PIL Image or None."""
    try:
        import requests
    except ImportError:
        print("    [!] requests not installed, skipping AI")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "width": 1024,
        "height": 1024,
        "steps": 25,
    }

    try:
        print(f"    Calling FLUX API...")
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=120)
        if resp.status_code != 200:
            print(f"    [!] API returned {resp.status_code}: {resp.text[:200]}")
            return None
        result = resp.json()

        image_b64 = None
        if "image" in result:
            image_b64 = result["image"]
        elif "data" in result:
            image_b64 = result["data"][0]["b64_json"]
        elif "output" in result:
            image_b64 = result["output"]

        if not image_b64:
            print(f"    [!] No image data in response: {list(result.keys())}")
            return None

        image_bytes = base64.b64decode(image_b64)
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = img.resize((width, height), Image.LANCZOS)
        return img

    except Exception as e:
        print(f"    [!] AI generation failed: {e}")
        return None

# ---------------------------------------------------------------------------
# Procedural texture generators
# ---------------------------------------------------------------------------

def proc_dark_steel(w, h):
    """Dark brushed steel with subtle rivets."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    rng = random.Random(42)
    for y in range(h):
        for x in range(w):
            base = 45 + int(8 * math.sin(y * 0.8)) + rng.randint(-3, 3)
            base += int(4 * math.sin(x * 0.5))
            px[x, y] = (base, base, base + 2)
    draw = ImageDraw.Draw(img)
    rivet_spacing = w // 4
    for ry in range(rivet_spacing // 2, h, rivet_spacing):
        for rx in range(rivet_spacing // 2, w, rivet_spacing):
            draw.ellipse([rx-1, ry-1, rx+1, ry+1], fill=(60, 60, 65))
            draw.point((rx, ry-1), fill=(70, 70, 75))
    for i in range(0, w, w // 2):
        draw.line([(i, 0), (i, h)], fill=(30, 30, 32), width=1)
    return img


def proc_corroded_floor(w, h):
    """Industrial corroded metal floor grating."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    rng = random.Random(43)
    for y in range(h):
        for x in range(w):
            base = 50 + rng.randint(-8, 8)
            gx = x % 8
            gy = y % 8
            if gx < 1 or gy < 1:
                px[x, y] = (30, 30, 32)
            else:
                rust = rng.random()
                if rust > 0.85:
                    px[x, y] = (min(255, base + 60), base + 15, base - 10)
                else:
                    px[x, y] = (base, base, base + 3)
    return img


def proc_pipe_ceiling(w, h):
    """Ceiling with exposed pipes and conduits."""
    img = Image.new("RGB", (w, h), (35, 35, 40))
    draw = ImageDraw.Draw(img)
    rng = random.Random(44)
    pipe_positions = [h // 6, h // 3, h // 2, 2 * h // 3, 5 * h // 6]
    pipe_colors = [(55, 55, 60), (50, 52, 58), (45, 48, 55), (60, 55, 50), (48, 50, 55)]
    for i, py in enumerate(pipe_positions):
        pipe_w = rng.randint(3, 6)
        col = pipe_colors[i % len(pipe_colors)]
        draw.rectangle([0, py - pipe_w, w, py + pipe_w], fill=col)
        draw.line([(0, py - pipe_w), (w, py - pipe_w)], fill=(col[0]+15, col[1]+15, col[2]+15))
        draw.line([(0, py + pipe_w), (w, py + pipe_w)], fill=(col[0]-10, col[1]-10, col[2]-10))
    for _ in range(3):
        dx = rng.randint(0, w)
        dy = rng.randint(0, h)
        for dd in range(rng.randint(4, 10)):
            draw.point((dx, min(h-1, dy + dd)), fill=(30, 50, 45))
    return img


def proc_neon_circuit(w, h):
    """Dark wall with glowing cyan circuit traces."""
    img = Image.new("RGB", (w, h), (20, 22, 28))
    draw = ImageDraw.Draw(img)
    rng = random.Random(45)
    for x in range(0, w, 8):
        draw.line([(x, 0), (x, h)], fill=(25, 27, 33))
    for y in range(0, h, 8):
        draw.line([(0, y), (w, y)], fill=(25, 27, 33))
    cyan_bright = (0, 220, 255)
    cyan_dim = (0, 80, 120)
    for _ in range(4):
        y = rng.randint(4, h - 4)
        x_start = rng.randint(0, w // 4)
        x_end = rng.randint(w // 2, w)
        draw.line([(x_start, y), (x_end, y)], fill=cyan_dim, width=1)
        for nx in range(x_start, x_end, rng.randint(8, 16)):
            draw.rectangle([nx-1, y-1, nx+1, y+1], fill=cyan_bright)
    for _ in range(3):
        x = rng.randint(4, w - 4)
        y_start = rng.randint(0, h // 3)
        y_end = rng.randint(h // 2, h)
        draw.line([(x, y_start), (x, y_end)], fill=cyan_dim, width=1)
        draw.rectangle([x-1, y_start-1, x+1, y_start+1], fill=cyan_bright)
    return img


def proc_hazard_wall(w, h):
    """Yellow-black hazard stripes."""
    img = Image.new("RGB", (w, h), (40, 40, 42))
    draw = ImageDraw.Draw(img)
    stripe_w = max(w // 8, 4)
    for i in range(-h, w + h, stripe_w * 2):
        points = [(i, 0), (i + stripe_w, 0), (i + stripe_w - h, h), (i - h, h)]
        draw.polygon(points, fill=(200, 180, 0))
    px = img.load()
    rng = random.Random(46)
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            grime = rng.randint(-15, 5)
            px[x, y] = (max(0, r + grime), max(0, g + grime), max(0, b + grime))
    return img


def proc_hex_floor(w, h):
    """Dark hexagonal tile floor."""
    img = Image.new("RGB", (w, h), (30, 32, 38))
    draw = ImageDraw.Draw(img)
    rng = random.Random(47)
    hex_size = 8
    for row in range(0, h + hex_size, hex_size):
        for col in range(0, w + hex_size, hex_size):
            offset = hex_size // 2 if (row // hex_size) % 2 else 0
            cx = col + offset
            cy = row
            v = 35 + rng.randint(-5, 5)
            draw.rectangle([cx, cy, cx + hex_size - 1, cy + hex_size - 1],
                          outline=(22, 24, 30), fill=(v, v, v + 3))
    for _ in range(5):
        rx, ry = rng.randint(0, w-1), rng.randint(0, h-1)
        draw.point((rx, ry), fill=(40, 50, 70))
    return img


def proc_neon_sky(w, h):
    """Cyberpunk night sky with neon-lit city."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    rng = random.Random(48)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(15 + 20 * t)
        g = int(8 + 15 * t)
        b = int(35 + 30 * (1 - t))
        for x in range(w):
            px[x, y] = (max(0, r + rng.randint(-3, 3)),
                        max(0, g + rng.randint(-2, 2)),
                        min(255, b + rng.randint(-3, 3)))
    draw = ImageDraw.Draw(img)
    building_y = int(h * 0.55)
    for bx in range(0, w, rng.randint(6, 14)):
        bw = rng.randint(4, 12)
        bh = rng.randint(h // 6, h // 2)
        by = h - bh
        if by < building_y:
            by = building_y
        draw.rectangle([bx, by, bx + bw, h], fill=(10, 10, 15))
        for wy in range(by + 2, h - 2, 4):
            for wx in range(bx + 1, bx + bw - 1, 3):
                if rng.random() > 0.5:
                    color = rng.choice([(0, 180, 220), (220, 0, 160), (180, 160, 0), (40, 40, 50)])
                    draw.point((wx, wy), fill=color)
    for x in range(w):
        glow_r = int(60 * max(0, 1 - abs(x - w//3) / (w/4)))
        glow_b = int(80 * max(0, 1 - abs(x - 2*w//3) / (w/4)))
        for dy in range(-3, 4):
            y = building_y + dy
            if 0 <= y < h:
                r, g, b = px[x, y]
                px[x, y] = (min(255, r + glow_r), g, min(255, b + glow_b))
    return img


def proc_blast_door(w, h):
    """Heavy industrial blast door."""
    img = Image.new("RGB", (w, h), (50, 52, 58))
    draw = ImageDraw.Draw(img)
    draw.rectangle([3, 3, w-4, h-4], fill=(55, 58, 65), outline=(35, 37, 42), width=2)
    draw.line([(w//2, 3), (w//2, h-4)], fill=(30, 32, 38), width=2)
    for by in [h//4, h//2, 3*h//4]:
        for bx in [w//4, 3*w//4]:
            draw.ellipse([bx-2, by-2, bx+2, by+2], fill=(40, 42, 48))
            draw.point((bx, by-1), fill=(70, 72, 78))
    draw.rectangle([w//2 - 3, 5, w//2 + 3, 9], fill=(200, 30, 0))
    for i in range(0, w, 8):
        draw.rectangle([i, h-6, i+3, h-3], fill=(180, 160, 0))
    return img


def proc_toxic_waste(w, h):
    """Glowing toxic green waste pool."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    rng = random.Random(50)
    for y in range(h):
        for x in range(w):
            wave = math.sin(x * 0.3 + y * 0.2) * 20 + math.sin(x * 0.1 - y * 0.4) * 15
            g = int(140 + wave + rng.randint(-10, 10))
            r = int(20 + wave * 0.3 + rng.randint(-5, 5))
            b = int(5 + rng.randint(-3, 3))
            px[x, y] = (max(0, min(255, r)), max(0, min(255, g)), max(0, b))
    draw = ImageDraw.Draw(img)
    for _ in range(8):
        bx, by = rng.randint(0, w-1), rng.randint(0, h-1)
        draw.ellipse([bx-1, by-1, bx+2, by+2], fill=(100, 255, 50))
    return img


def proc_holo_terminal(w, h):
    """Holographic computer terminal with scan lines."""
    img = Image.new("RGB", (w, h), (5, 8, 12))
    draw = ImageDraw.Draw(img)
    draw.rectangle([2, 2, w-3, h-3], outline=(30, 35, 45), width=2)
    draw.rectangle([4, 4, w-5, h-5], fill=(5, 15, 20))
    rng = random.Random(51)
    for row in range(6, h-6, 3):
        draw.line([(4, row), (w-5, row)], fill=(0, 8, 12))
        if rng.random() > 0.3:
            length = rng.randint(4, w - 12)
            intensity = rng.randint(120, 255)
            draw.line([(6, row+1), (6 + length, row+1)], fill=(0, intensity, int(intensity * 0.7)))
    draw.rectangle([8, h - 10, 11, h - 7], fill=(0, 255, 200))
    return img


def proc_bunker_wall(w, h):
    """Cracked concrete bunker wall."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    rng = random.Random(52)
    for y in range(h):
        for x in range(w):
            v = 55 + rng.randint(-8, 8)
            px[x, y] = (v, v, v - 2)
    draw = ImageDraw.Draw(img)
    for _ in range(3):
        cx, cy = rng.randint(0, w), rng.randint(0, h)
        for _ in range(rng.randint(5, 12)):
            nx = cx + rng.randint(-3, 3)
            ny = cy + rng.randint(1, 4)
            draw.line([(cx, cy), (nx, ny)], fill=(35, 35, 33))
            cx, cy = nx, min(h-1, ny)
    gx = rng.randint(w//4, w//2)
    gy = rng.randint(h//4, h//2)
    draw.rectangle([gx, gy, gx+12, gy+6], fill=(180, 0, 120))
    return img


def proc_neon_sign_wall(w, h):
    """Dark alley wall with neon signs."""
    img = Image.new("RGB", (w, h), (22, 20, 25))
    draw = ImageDraw.Draw(img)
    px = img.load()
    rng = random.Random(53)
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            v = rng.randint(-5, 5)
            px[x, y] = (max(0, r+v), max(0, g+v), max(0, b+v))
    sx, sy = w // 6, h // 5
    draw.rectangle([sx, sy, sx + w//3, sy + h//5], outline=(0, 200, 240), width=1)
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            if dx == 0 and dy == 0:
                continue
            x1, y1 = max(0, sx+dx), max(0, sy+dy)
            x2, y2 = min(w-1, sx+w//3+dx), min(h-1, sy+h//5+dy)
            draw.rectangle([x1, y1, x2, y2], outline=(0, 40, 60))
    sx2, sy2 = w // 2, h // 2
    draw.rectangle([sx2, sy2, sx2 + w//4, sy2 + h//6], outline=(220, 0, 160), width=1)
    return img


def proc_grated_catwalk(w, h):
    """Metal grated catwalk floor."""
    img = Image.new("RGB", (w, h), (15, 15, 18))
    draw = ImageDraw.Draw(img)
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            offset = 2 if (y // 4) % 2 else 0
            gx = x + offset
            draw.rectangle([gx, y, gx+2, y+2], outline=(50, 52, 58))
    for bx in range(0, w, w // 4):
        draw.rectangle([bx, 0, bx + 1, h], fill=(60, 62, 68))
    return img


def proc_bio_growth(w, h):
    """Bioluminescent fungal growth on dark wall."""
    img = Image.new("RGB", (w, h), (18, 20, 18))
    px = img.load()
    rng = random.Random(55)
    for y in range(h):
        for x in range(w):
            v = 18 + rng.randint(-4, 4)
            px[x, y] = (v, v + 2, v)
    draw = ImageDraw.Draw(img)
    for _ in range(6):
        cx, cy = rng.randint(0, w), rng.randint(0, h)
        radius = rng.randint(3, 8)
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                dist = math.sqrt(dx*dx + dy*dy)
                if dist <= radius:
                    nx, ny = (cx + dx) % w, (cy + dy) % h
                    intensity = max(0, 1 - dist / radius)
                    r, g, b = px[nx, ny]
                    g_add = int(120 * intensity)
                    r_add = int(20 * intensity)
                    px[nx, ny] = (min(255, r + r_add), min(255, g + g_add), min(255, b + r_add // 2))
    return img


def proc_rust_metal(w, h):
    """Heavily rusted corroded metal wall."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    rng = random.Random(56)
    for y in range(h):
        for x in range(w):
            rust = rng.random()
            if rust > 0.6:
                r = 120 + rng.randint(-20, 30)
                g = 65 + rng.randint(-15, 15)
                b = 25 + rng.randint(-10, 10)
            else:
                v = 45 + rng.randint(-8, 8)
                r, g, b = v + 5, v, v - 3
            px[x, y] = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
    return img


def proc_magma(w, h):
    """Glowing magma through cracked rock."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    rng = random.Random(57)
    for y in range(h):
        for x in range(w):
            lava = (math.sin(x * 0.2 + y * 0.15) + math.sin(x * 0.1 - y * 0.3)) * 0.5 + 0.5
            if lava > 0.55:
                r = int(200 + 55 * lava)
                g = int(80 + 100 * lava)
                b = int(10 + 20 * lava)
            else:
                v = 25 + rng.randint(-5, 5)
                r, g, b = v, v - 3, v - 5
            px[x, y] = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
    return img


def proc_cryo(w, h):
    """Frosted cryo-chamber wall."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    rng = random.Random(58)
    for y in range(h):
        for x in range(w):
            base = 60 + int(15 * math.sin(x * 0.3 + y * 0.2))
            frost = rng.randint(-10, 10)
            r = max(0, min(255, base + frost - 20))
            g = max(0, min(255, base + frost))
            b = max(0, min(255, base + frost + 40))
            px[x, y] = (r, g, b)
    draw = ImageDraw.Draw(img)
    for _ in range(5):
        ix, iy = rng.randint(0, w-1), rng.randint(0, h-1)
        draw.line([(ix, iy), (ix + rng.randint(-5, 5), iy + rng.randint(-5, 5))], fill=(160, 200, 240))
    return img


def proc_sandblasted(w, h):
    """Sandblasted gunmetal plate."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    rng = random.Random(59)
    for y in range(h):
        for x in range(w):
            v = 60 + rng.randint(-6, 6) + int(3 * math.sin(x * 1.5 + y * 0.5))
            px[x, y] = (v, v, v + 2)
    draw = ImageDraw.Draw(img)
    for _ in range(8):
        sx = rng.randint(0, w)
        sy = rng.randint(0, h)
        draw.line([(sx, sy), (sx + rng.randint(-10, 10), sy + rng.randint(-2, 2))],
                  fill=(70, 70, 74))
    return img


def proc_marble_command(w, h):
    """Dark polished marble with gold inlay."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    rng = random.Random(60)
    for y in range(h):
        for x in range(w):
            v = 30 + int(10 * math.sin(x * 0.15 + y * 0.1)) + rng.randint(-4, 4)
            px[x, y] = (v + 2, v, v + 3)
    draw = ImageDraw.Draw(img)
    for gx in range(0, w, w // 2):
        draw.line([(gx, 0), (gx, h)], fill=(160, 130, 40), width=1)
    for gy in range(0, h, h // 2):
        draw.line([(0, gy), (w, gy)], fill=(160, 130, 40), width=1)
    return img


def proc_server_rack(w, h):
    """Server racks with blinking LEDs."""
    img = Image.new("RGB", (w, h), (15, 16, 20))
    draw = ImageDraw.Draw(img)
    rng = random.Random(61)
    unit_h = max(h // 8, 4)
    for uy in range(0, h, unit_h):
        draw.rectangle([1, uy, w-2, uy + unit_h - 1], outline=(25, 26, 32))
        for lx in range(3, w - 3, 4):
            color = rng.choice([
                (0, 200, 0), (200, 0, 0), (0, 100, 200), (0, 180, 0), (40, 40, 40)
            ])
            draw.point((lx, uy + unit_h // 2), fill=color)
    return img


def proc_sprite_placeholder(w, h, label, seed):
    """Cyberpunk-themed item sprite placeholder."""
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    colors = {
        "Stim": (0, 255, 100),
        "Plasma": (0, 180, 255),
        "Nano": (100, 200, 255),
        "blue": (50, 100, 255),
        "red": (255, 50, 50),
        "gold": (255, 200, 50),
        "Pulse": (200, 200, 220),
        "Scatter": (255, 150, 0),
        "launcher": (255, 80, 80),
        "Explosion": (255, 200, 50),
    }
    col = (0, 200, 200)
    for keyword, c in colors.items():
        if keyword.lower() in label.lower():
            col = c
            break
    cx, cy = w // 2, h // 2
    r = min(w, h) // 3
    points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    draw.polygon(points, fill=col)
    r2 = r // 2
    inner_col = (min(255, col[0] + 60), min(255, col[1] + 60), min(255, col[2] + 60))
    points2 = [(cx, cy - r2), (cx + r2, cy), (cx, cy + r2), (cx - r2, cy)]
    draw.polygon(points2, fill=inner_col)
    return img


PROCEDURAL_MAP = {
    0: proc_dark_steel,
    1: proc_corroded_floor,
    2: proc_pipe_ceiling,
    3: proc_neon_circuit,
    4: proc_hazard_wall,
    5: proc_hex_floor,
    6: proc_neon_sky,
    7: proc_blast_door,
    8: proc_toxic_waste,
    9: proc_holo_terminal,
    10: proc_bunker_wall,
    11: proc_neon_sign_wall,
    12: proc_grated_catwalk,
    13: proc_bio_growth,
    14: proc_rust_metal,
    15: proc_magma,
    16: proc_cryo,
    17: proc_sandblasted,
    18: proc_marble_command,
    19: proc_server_rack,
}

# Every tile has a dedicated generator
GENERIC_COLORS = {}

# ---------------------------------------------------------------------------
# NAMES.H parser and game-critical tile generation
# ---------------------------------------------------------------------------

def parse_names_h():
    """Parse source/NAMES.H to extract all #define NAME NUMBER entries."""
    names_h = os.path.join(PROJECT_ROOT, "source", "NAMES.H")
    result = {}
    with open(names_h) as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            if stripped.startswith("#define "):
                parts = stripped.split()
                if len(parts) >= 3:
                    name = parts[1]
                    try:
                        num = int(parts[2])
                        result[name] = num
                    except ValueError:
                        continue
    return result


def _classify_tile(name, tile_num):
    """Return (width, height, category) for a game tile."""
    # Full-screen tiles
    if name in ('MENUSCREEN', 'BETASCREEN', 'LOADSCREEN', 'BONUSSCREEN',
                'VICTORY1', 'ORDERING', 'TEXTSTORY', 'BORNTOBEWILDSCREEN',
                'F1HELP', 'TENSCREEN', 'BETAVERSION', 'DUKECAR', 'DREALMS',
                'VIEWBORDER'):
        return (320, 200, 'fullscreen')
    # HUD / status bars
    if name in ('BOTTOMSTATUSBAR', 'FRAGBAR', 'MENUBAR', 'HEADERBAR'):
        return (320, 16, 'hud_bar')
    # Logo text
    if name in ('DUKENUKEM', 'THREEDEE', 'INGAMEDUKETHREEDEE', 'PLUTOPAKSPRITE'):
        return (160, 40, 'logo')
    if name in ('LOGO', 'TITLE'):
        return (64, 32, 'logo')
    # Digital numbers (2472-2481)
    if 2472 <= tile_num <= 2481:
        return (10, 16, 'digit')
    # Slider / UI
    if name == 'SLIDEBAR':
        return (64, 8, 'hud_bar')
    if name in ('WINDOWBORDER1', 'WINDOWBORDER2', 'TEXTBOX'):
        return (128, 32, 'hud_bar')
    # Cursors & small UI
    if name in ('MOUSECURSOR', 'BIGFNTCURSOR', 'SMALLFNTCURSOR',
                'CAMCORNER', 'CAMLIGHT'):
        return (16, 16, 'icon')
    if name == 'CROSSHAIR':
        return (16, 16, 'weapon')
    # Font / alpha ranges
    if 2822 <= tile_num <= 2915:
        return (8, 8, 'font')
    if 2940 <= tile_num <= 3009:
        return (16, 16, 'font')
    if 3010 <= tile_num <= 3025:
        return (4, 5, 'font')
    if 3072 <= tile_num <= 3163:
        return (4, 5, 'font')
    if name in ('BIGPERIOD', 'BIGCOMMA', 'BIGX', 'BIGQ',
                'BIGSEMI', 'BIGCOLIN', 'BIGAPPOS'):
        return (16, 16, 'font')
    if name == 'BLANK':
        return (8, 8, 'font')
    # Weapon view sprites
    if name in ('DEVISTATOR', 'KNEE', 'FIRSTGUN', 'FIRSTGUNRELOAD', 'CHAINGUN',
                'RPGGUN', 'RPGMUZZLEFLASH', 'FREEZE', 'SHRINKER', 'TRIPBOMB',
                'RPG', 'SHOTGUN', 'HANDHOLDINGLASER', 'HANDHOLDINGACCESS',
                'HANDREMOTE', 'HANDTHROW', 'HAND', 'TIP', 'FALLINGCLIP',
                'CLIPINHAND', 'ROTATEGUN', 'GLAIR', 'CRACKKNUCKLES',
                'SCUBAMASK', 'SPACEMASK'):
        return (64, 64, 'weapon')
    # Boss sprites
    if name.startswith('BOSS') and 'SCREEN' not in name:
        return (80, 80, 'boss')
    # Enemy sprites
    if name in ('LIZTROOP', 'LIZTROOPRUNNING', 'LIZTROOPSTAYPUT', 'LIZTOP',
                'LIZTROOPSHOOT', 'LIZTROOPJETPACK', 'LIZTROOPDSPRITE',
                'LIZTROOPONTOILET', 'LIZTROOPJUSTSIT', 'LIZTROOPDUCKING',
                'OCTABRAIN', 'OCTABRAINSTAYPUT', 'OCTATOP', 'OCTADEADSPRITE',
                'INNERJAW', 'DRONE', 'COMMANDER', 'COMMANDERSTAYPUT',
                'RECON', 'TANK', 'PIGCOP', 'PIGCOPSTAYPUT', 'PIGCOPDIVE',
                'PIGCOPDEADSPRITE', 'PIGTOP', 'LIZMAN', 'LIZMANSTAYPUT',
                'LIZMANSPITTING', 'LIZMANFEEDING', 'LIZMANJUMP',
                'LIZMANDEADSPRITE', 'SHARK', 'NEWBEAST', 'NEWBEASTSTAYPUT',
                'NEWBEASTJUMP', 'NEWBEASTHANG', 'NEWBEASTHANGDEAD',
                'GREENSLIME', 'EGG'):
        return (64, 64, 'enemy')
    # Player / NPC sprites
    if name in ('APLAYER', 'APLAYERTOP', 'PLAYERONWATER', 'DUKELYINGDEAD',
                'DUKETORSO', 'DUKEGUN', 'DUKELEG', 'SPACEMARINE', 'HOLODUKE',
                'INDY', 'MONK', 'LUKE'):
        return (48, 48, 'character')
    if name.startswith('FEM') or name in ('NAKED1', 'TOUGHGAL', 'MAN', 'MAN2',
                                          'WOMAN', 'PODFEM1'):
        return (48, 48, 'character')
    # Icons
    if 'ICON' in name:
        return (24, 24, 'icon')
    # Medium effects
    if name in ('EXPLOSION2', 'EXPLOSION2BOT', 'COOLEXPLOSION1',
                'TRANSPORTERSTAR', 'TRANSPORTERBEAM', 'WATERSPLASH2',
                'RADIUSEXPLOSION', 'FORCERIPPLE', 'SHRINKEREXPLOSION',
                'MORTER', 'SHOTSPARK1', 'FORCESPHERE'):
        return (32, 32, 'effect')
    # Small particles / effects
    if name in ('SMALLSMOKE', 'FLOORFLAME', 'BURNING', 'FIRE', 'BURNING2',
                'FIRE2', 'SPIT', 'LOOGIE', 'TONGUE', 'FREEZEBLAST',
                'DEVISTATORBLAST', 'SHRINKSPARK', 'GROWSPARK', 'FIST',
                'SHELL', 'SHOTGUNSHELL', 'LASERLINE', 'LASERSITE',
                'BULLETHOLE', 'WATERDRIP', 'WATERBUBBLE', 'FOOTPRINTS',
                'FOOTPRINTS2', 'FOOTPRINTS3', 'FOOTPRINTS4', 'FOOTPRINT',
                'BLOOD', 'FIRELASER', 'CANNONBALL', 'SMALLSMOKEMAKER',
                'WATERBUBBLEMAKER', 'STEAM', 'CEILINGSTEAM'):
        return (16, 16, 'effect')
    if name.startswith('BLOODSPLAT') or name.startswith('WALLBLOOD'):
        return (16, 16, 'effect')
    if 'JIB' in name or name.startswith('SCRAP'):
        return (16, 16, 'effect')
    # Wall / floor textures
    if name in ('BIGFORCE', 'FLOORSLIME', 'WATERTILE', 'WATERTILE2',
                'PURPLELAVA', 'CLOUDYOCEAN', 'CLOUDYSKIES',
                'REFLECTWATERTILE', 'FLOORPLASMA', 'LAVABUBBLE'):
        return (64, 64, 'wall')
    if 'SKY' in name or 'ORBIT' in name:
        return (128, 128, 'wall')
    if name.startswith('SCREENBREAK'):
        return (16, 16, 'effect')
    if name.startswith('W_'):
        return (64, 64, 'wall')
    if name.startswith('DOORTILE'):
        return (64, 64, 'wall')
    if name.startswith('MASKWALL'):
        return (64, 64, 'wall')
    if 'SWITCH' in name or name == 'BUTTON1':
        return (16, 16, 'switch')
    if name.startswith('RESPAWNMARKER'):
        return (24, 24, 'icon')
    # Medium props
    if name in ('CRANE', 'BLIMP', 'HELECOPT', 'STATUE', 'STATUEFLASH',
                'REACTOR', 'REACTORSPARK', 'REACTORBURNT',
                'REACTOR2', 'REACTOR2BURNT', 'REACTOR2SPARK',
                'NUKEBARREL', 'NUKEBARRELDENTED', 'NUKEBARRELLEAKED',
                'EXPLODINGBARREL', 'EXPLODINGBARREL2', 'FIREBARREL',
                'VENDMACHINE', 'VENDMACHINEBROKE', 'COLAMACHINE',
                'COLAMACHINEBROKE', 'OOZFILTER', 'SEENINE', 'SEENINEDEAD',
                'SHOPPINGCART', 'DUKECUTOUT', 'DUKEBURGER'):
        return (48, 48, 'prop')
    # Default
    return (32, 32, 'prop')


# -- Category-specific tile generators ------------------------------------

def _draw_text_on_image(draw, cx, cy, text, color):
    """Draw text centered at (cx, cy) using built-in font glyphs."""
    _init_font()
    text = text.upper()
    char_w = 6
    total_w = len(text) * char_w
    sx = cx - total_w // 2
    sy = cy - 3
    for i, ch in enumerate(text):
        glyph = _FONT_GLYPHS.get(ord(ch))
        if glyph is None:
            continue
        bx = sx + i * char_w
        for row_idx, bits in enumerate(glyph):
            for col in range(5):
                if bits & (1 << (4 - col)):
                    px_x, px_y = bx + col, sy + row_idx
                    if px_x >= 0 and px_y >= 0:
                        try:
                            draw.point((px_x, px_y), fill=color)
                        except Exception:
                            pass


def _gen_fullscreen(w, h, name, seed):
    """Full-screen placeholder with scanlines and centered label."""
    img = Image.new("RGB", (w, h), (5, 5, 10))
    draw = ImageDraw.Draw(img)
    for y in range(0, h, 2):
        draw.line([(0, y), (w - 1, y)], fill=(8, 8, 15))
    draw.rectangle([2, 2, w - 3, h - 3], outline=(0, 80, 120))
    draw.rectangle([4, 4, w - 5, h - 5], outline=(0, 40, 60))
    _draw_text_on_image(draw, w // 2, h // 2 - 10, name[:20], (0, 200, 255))
    _draw_text_on_image(draw, w // 2, h // 2 + 10, "PLACEHOLDER", (0, 120, 160))
    for cx, cy in [(8, 8), (w - 12, 8), (8, h - 12), (w - 12, h - 12)]:
        draw.rectangle([cx, cy, cx + 4, cy + 4], fill=(0, 200, 255))
    return img


def _gen_hud_bar(w, h, name, seed):
    """HUD / status bar with metallic gradient and neon edges."""
    img = Image.new("RGB", (w, h), (20, 22, 30))
    draw = ImageDraw.Draw(img)
    px = img.load()
    draw.line([(0, 0), (w - 1, 0)], fill=(0, 200, 255))
    draw.line([(0, h - 1), (w - 1, h - 1)], fill=(0, 200, 255))
    for y in range(1, h - 1):
        v = int(25 + 10 * math.sin(y / max(h - 1, 1) * math.pi))
        for x in range(w):
            px[x, y] = (v, v + 2, v + 5)
    for x in range(10, w - 10, 40):
        draw.line([(x, 2), (x + 15, 2)], fill=(0, 180, 220))
    for dx in (w // 4, w // 2, 3 * w // 4):
        draw.line([(dx, 2), (dx, h - 3)], fill=(0, 100, 140))
    return img


def _gen_logo_text(w, h, name, seed):
    """Logo / title text with neon glow."""
    img = Image.new("RGB", (w, h), (2, 2, 8))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    for r in range(min(w, h) // 2, 0, -1):
        intensity = int(30 * (r / (min(w, h) // 2)))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     outline=(0, intensity // 2, intensity))
    _draw_text_on_image(draw, cx, cy, name[:16], (255, 0, 180))
    return img


def _gen_digit_tile(w, h, digit, seed):
    """Render a single HUD digit (0-9) with neon cyan."""
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    _init_font()
    glyph = _FONT_GLYPHS.get(ord('0') + digit)
    if glyph:
        sx = max(1, w // 6)
        sy = max(1, h // 8)
        ox = (w - 5 * sx) // 2
        oy = (h - 7 * sy) // 2
        for row_idx, bits in enumerate(glyph):
            for col in range(5):
                if bits & (1 << (4 - col)):
                    x0 = ox + col * sx
                    y0 = oy + row_idx * sy
                    x1 = min(w - 1, x0 + sx - 1)
                    y1 = min(h - 1, y0 + sy - 1)
                    draw.rectangle([x0, y0, x1, y1], fill=(0, 255, 220))
    return img


def _gen_weapon(w, h, name, seed):
    """Weapon view sprite with gun silhouette and neon highlight."""
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    draw.rectangle([cx - w // 4, cy - 2, cx + w // 4, cy + 2],
                   fill=(60, 65, 70))
    draw.rectangle([cx - w // 6, cy, cx - w // 6 + 6, cy + h // 3],
                   fill=(50, 55, 60))
    draw.rectangle([cx - w // 4 - 2, cy - 3, cx - w // 4 + 2, cy + 3],
                   fill=(40, 45, 50))
    draw.line([(cx - w // 4, cy - 2), (cx + w // 4, cy - 2)],
             fill=(0, 200, 255))
    draw.point((cx + w // 4, cy), fill=(255, 200, 50))
    draw.point((cx + w // 4 + 1, cy), fill=(255, 150, 0))
    return img


def _gen_boss(w, h, name, seed):
    """Boss sprite with menacing silhouette and red accents."""
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    bw, bh = w // 3, h // 2
    draw.rectangle([cx - bw // 2, cy - bh // 4, cx + bw // 2, cy + bh // 2],
                   fill=(60, 10, 10))
    hr = w // 6
    draw.ellipse([cx - hr, cy - bh // 4 - hr * 2, cx + hr, cy - bh // 4],
                 fill=(80, 15, 15))
    ey = cy - bh // 4 - hr
    draw.point((cx - 3, ey), fill=(255, 0, 0))
    draw.point((cx + 3, ey), fill=(255, 0, 0))
    draw.rectangle([cx - bw // 2 - 1, cy - bh // 4 - hr * 2 - 1,
                    cx + bw // 2 + 1, cy + bh // 2 + 1],
                   outline=(255, 0, 80))
    return img


def _gen_enemy(w, h, name, seed):
    """Enemy sprite with color-coded humanoid silhouette."""
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    if 'LIZ' in name:
        body_col, accent = (20, 80, 20), (0, 255, 100)
    elif 'OCTA' in name:
        body_col, accent = (40, 20, 60), (180, 0, 255)
    elif 'PIG' in name:
        body_col, accent = (60, 30, 30), (255, 100, 100)
    elif 'SHARK' in name:
        body_col, accent = (30, 40, 60), (0, 150, 255)
    elif 'DRONE' in name:
        body_col, accent = (40, 40, 50), (255, 200, 0)
    elif 'NEWBEAST' in name:
        body_col, accent = (50, 20, 10), (255, 80, 0)
    else:
        body_col, accent = (40, 40, 40), (0, 200, 200)
    draw.ellipse([cx - 5, cy - h // 3, cx + 5, cy - h // 3 + 10],
                 fill=body_col)
    draw.rectangle([cx - 8, cy - h // 3 + 10, cx + 8, cy + h // 6],
                   fill=body_col)
    draw.rectangle([cx - 12, cy - h // 3 + 12, cx - 8, cy + h // 6 - 2],
                   fill=body_col)
    draw.rectangle([cx + 8, cy - h // 3 + 12, cx + 12, cy + h // 6 - 2],
                   fill=body_col)
    draw.rectangle([cx - 6, cy + h // 6, cx - 2, cy + h // 3],
                   fill=body_col)
    draw.rectangle([cx + 2, cy + h // 6, cx + 6, cy + h // 3],
                   fill=body_col)
    draw.rectangle([cx - 13, cy - h // 3 - 1, cx + 13, cy + h // 3 + 1],
                   outline=accent)
    return img


def _gen_character(w, h, name, seed):
    """Character / NPC sprite placeholder."""
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    draw.ellipse([cx - 4, cy - h // 4, cx + 4, cy - h // 4 + 8],
                 fill=(30, 40, 60))
    draw.rectangle([cx - 6, cy - h // 4 + 8, cx + 6, cy + h // 6],
                   fill=(25, 35, 55))
    draw.rectangle([cx - 4, cy + h // 6, cx - 1, cy + h // 4],
                   fill=(25, 35, 55))
    draw.rectangle([cx + 1, cy + h // 6, cx + 4, cy + h // 4],
                   fill=(25, 35, 55))
    draw.rectangle([cx - 7, cy - h // 4 - 1, cx + 7, cy + h // 4 + 1],
                   outline=(0, 150, 200))
    return img


def _gen_icon(w, h, name, seed):
    """Small icon tile with color-coded diamond shape."""
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    if 'HEALTH' in name or 'FIRSTAID' in name:
        col = (255, 50, 50)
    elif 'AMMO' in name or 'KILL' in name:
        col = (255, 200, 0)
    elif 'BOOT' in name or 'JET' in name:
        col = (0, 200, 255)
    elif 'HEAT' in name or 'NUKE' in name:
        col = (255, 100, 0)
    elif 'STEROIDS' in name:
        col = (100, 255, 100)
    elif 'ACCESS' in name:
        col = (255, 255, 0)
    elif 'DUKE' in name or 'BADGUY' in name:
        col = (255, 0, 180)
    else:
        col = (0, 200, 200)
    cx, cy = w // 2, h // 2
    r = min(w, h) // 3
    draw.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)],
                 fill=col)
    inner = (min(255, col[0] + 60), min(255, col[1] + 60), min(255, col[2] + 60))
    r2 = r // 2
    draw.polygon([(cx, cy - r2), (cx + r2, cy), (cx, cy + r2), (cx - r2, cy)],
                 fill=inner)
    return img


def _gen_effect(w, h, name, seed):
    """Effect / particle placeholder with radial gradient."""
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    if 'EXPLO' in name or 'BLAST' in name or 'SPARK' in name:
        col = (255, 200, 50)
    elif 'BLOOD' in name:
        col = (180, 0, 0)
    elif 'WATER' in name or 'SPLASH' in name:
        col = (0, 100, 200)
    elif 'FIRE' in name or 'BURN' in name or 'FLAME' in name:
        col = (255, 100, 0)
    elif 'FREEZE' in name:
        col = (100, 200, 255)
    elif 'SMOKE' in name or 'STEAM' in name:
        col = (80, 80, 80)
    elif 'FOOT' in name:
        col = (60, 50, 40)
    else:
        col = (200, 200, 200)
    r = min(w, h) // 3
    for i in range(r, 0, -1):
        t = i / max(r, 1)
        c = (int(col[0] * t), int(col[1] * t), int(col[2] * t))
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=c)
    return img


def _gen_wall_texture(w, h, name, seed):
    """Wall / floor texture placeholder with subtle grid."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    rng = random.Random(seed)
    for y in range(h):
        for x in range(w):
            v = rng.randint(-6, 6)
            px[x, y] = (max(0, 35 + v), max(0, 38 + v), max(0, 45 + v))
    draw = ImageDraw.Draw(img)
    step_x = max(w // 4, 1)
    step_y = max(h // 4, 1)
    for gx in range(0, w, step_x):
        draw.line([(gx, 0), (gx, h - 1)], fill=(28, 30, 36))
    for gy in range(0, h, step_y):
        draw.line([(0, gy), (w - 1, gy)], fill=(28, 30, 36))
    return img


def _gen_switch(w, h, name, seed):
    """Switch / button tile."""
    img = Image.new("RGB", (w, h), (25, 28, 35))
    draw = ImageDraw.Draw(img)
    draw.rectangle([2, 2, w - 3, h - 3], outline=(50, 55, 65))
    cx, cy = w // 2, h // 2
    draw.rectangle([cx - 2, cy - 2, cx + 2, cy + 2], fill=(0, 200, 100))
    return img


def _gen_font_char(w, h, tile_num, seed):
    """Font character tile for STARTALPHANUM / BIGALPHANUM / MINIFONT ranges."""
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    _init_font()
    if 2822 <= tile_num <= 2915:
        char_code = 33 + (tile_num - 2822)
    elif 2940 <= tile_num <= 3009:
        char_code = 33 + (tile_num - 2940)
    elif 3072 <= tile_num <= 3163:
        char_code = 33 + (tile_num - 3072)
    elif 3010 <= tile_num <= 3025:
        char_code = 48 + (tile_num - 3010)
    else:
        char_code = 32
    glyph = _FONT_GLYPHS.get(char_code)
    if glyph:
        sx = max(1, w // 6)
        sy = max(1, h // 8)
        ox = max(0, (w - 5 * sx) // 2)
        oy = max(0, (h - 7 * sy) // 2)
        for row_idx, bits in enumerate(glyph):
            for col in range(5):
                if bits & (1 << (4 - col)):
                    x0 = ox + col * sx
                    y0 = oy + row_idx * sy
                    x1 = min(w - 1, x0 + sx - 1)
                    y1 = min(h - 1, y0 + sy - 1)
                    if x0 < w and y0 < h:
                        draw.rectangle([x0, y0, x1, y1], fill=(255, 255, 255))
    return img


def _gen_default_prop(w, h, name, seed):
    """Default prop / item placeholder."""
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    hue = sum(ord(c) for c in name) % 6
    colors = [
        (0, 200, 200), (200, 0, 200), (0, 200, 100),
        (200, 200, 0), (100, 100, 255), (255, 100, 50),
    ]
    col = colors[hue]
    cx, cy = w // 2, h // 2
    r = min(w, h) // 3
    outer = (min(255, col[0] + 50), min(255, col[1] + 50), min(255, col[2] + 50))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col, outline=outer)
    return img


_CATEGORY_GENERATORS = {
    'fullscreen': lambda w, h, name, tn, seed: _gen_fullscreen(w, h, name, seed),
    'hud_bar':    lambda w, h, name, tn, seed: _gen_hud_bar(w, h, name, seed),
    'logo':       lambda w, h, name, tn, seed: _gen_logo_text(w, h, name, seed),
    'digit':      lambda w, h, name, tn, seed: _gen_digit_tile(w, h, tn - 2472, seed),
    'font':       lambda w, h, name, tn, seed: _gen_font_char(w, h, tn, seed),
    'weapon':     lambda w, h, name, tn, seed: _gen_weapon(w, h, name, seed),
    'boss':       lambda w, h, name, tn, seed: _gen_boss(w, h, name, seed),
    'enemy':      lambda w, h, name, tn, seed: _gen_enemy(w, h, name, seed),
    'character':  lambda w, h, name, tn, seed: _gen_character(w, h, name, seed),
    'icon':       lambda w, h, name, tn, seed: _gen_icon(w, h, name, seed),
    'effect':     lambda w, h, name, tn, seed: _gen_effect(w, h, name, seed),
    'wall':       lambda w, h, name, tn, seed: _gen_wall_texture(w, h, name, seed),
    'switch':     lambda w, h, name, tn, seed: _gen_switch(w, h, name, seed),
    'prop':       lambda w, h, name, tn, seed: _gen_default_prop(w, h, name, seed),
}


def generate_game_tiles(palette):
    """Generate procedural tiles for every tile number defined in NAMES.H.

    Returns dict of tile_num -> (width, height, picanm, column_major_pixels).
    """
    names = parse_names_h()
    tiles = {}

    # Build number -> canonical name mapping
    num_to_name = {}
    for name, num in names.items():
        if num not in num_to_name:
            num_to_name[num] = name

    # Fill implicit ranges: DIGITALNUM+0..+9, font ranges
    dn_base = names.get('DIGITALNUM', 2472)
    for d in range(10):
        t = dn_base + d
        if t not in num_to_name:
            num_to_name[t] = f'DIGITALNUM_{d}'

    sa = names.get('STARTALPHANUM', 2822)
    ea = names.get('ENDALPHANUM', 2915)
    for t in range(sa, ea + 1):
        if t not in num_to_name:
            num_to_name[t] = f'ALPHANUM_{t - sa}'

    ba = names.get('BIGALPHANUM', 2940)
    for t in range(ba, ba + 70):
        if t not in num_to_name:
            num_to_name[t] = f'BIGALPHA_{t - ba}'

    tbf = names.get('THREEBYFIVE', 3010)
    for t in range(tbf, tbf + 16):
        if t not in num_to_name:
            num_to_name[t] = f'THREEBYFIVE_{t - tbf}'

    mf = names.get('MINIFONT', 3072)
    for t in range(mf, mf + 92):
        if t not in num_to_name:
            num_to_name[t] = f'MINIFONT_{t - mf}'

    for tile_num, name in sorted(num_to_name.items()):
        w, h, category = _classify_tile(name, tile_num)
        seed = tile_num * 7 + 31337
        gen = _CATEGORY_GENERATORS.get(category, _CATEGORY_GENERATORS['prop'])
        img = gen(w, h, name, tile_num, seed)
        indexed = quantize_image(img, palette)
        col_major = rgb_to_column_major(indexed, w, h)
        tiles[tile_num] = (w, h, 0, col_major)

    return tiles


# ---------------------------------------------------------------------------
# Font tile generation (tiles 2048-2175, 8x8 each)
# ---------------------------------------------------------------------------

# Minimal 5x7 bitmap font for printable ASCII 32-127.
# Each glyph is stored as 7 bytes; each byte is a row bitmask (LSB = leftmost).
_FONT_GLYPHS = {}

def _init_font():
    """Initialise a minimal procedural font covering ASCII 32-95."""
    if _FONT_GLYPHS:
        return
    # Space
    _FONT_GLYPHS[32] = [0, 0, 0, 0, 0, 0, 0]
    # ! 
    _FONT_GLYPHS[33] = [0b00100, 0b00100, 0b00100, 0b00100, 0b00000, 0b00100, 0b00000]
    # A-Z (simplified block letters)
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    simple = [
        [0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0],  # A
        [0b11110, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110, 0],  # B
        [0b01110, 0b10001, 0b10000, 0b10000, 0b10001, 0b01110, 0],  # C
        [0b11100, 0b10010, 0b10001, 0b10001, 0b10010, 0b11100, 0],  # D
        [0b11111, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111, 0],  # E
        [0b11111, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000, 0],  # F
        [0b01110, 0b10000, 0b10111, 0b10001, 0b10001, 0b01110, 0],  # G
        [0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001, 0],  # H
        [0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110, 0],  # I
        [0b00111, 0b00010, 0b00010, 0b00010, 0b10010, 0b01100, 0],  # J
        [0b10001, 0b10010, 0b11100, 0b10010, 0b10001, 0b10001, 0],  # K
        [0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111, 0],  # L
        [0b10001, 0b11011, 0b10101, 0b10001, 0b10001, 0b10001, 0],  # M
        [0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0],  # N
        [0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110, 0],  # O
        [0b11110, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000, 0],  # P
        [0b01110, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101, 0],  # Q
        [0b11110, 0b10001, 0b11110, 0b10010, 0b10001, 0b10001, 0],  # R
        [0b01110, 0b10000, 0b01110, 0b00001, 0b10001, 0b01110, 0],  # S
        [0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0],  # T
        [0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110, 0],  # U
        [0b10001, 0b10001, 0b10001, 0b01010, 0b01010, 0b00100, 0],  # V
        [0b10001, 0b10001, 0b10101, 0b10101, 0b11011, 0b10001, 0],  # W
        [0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001, 0],  # X
        [0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100, 0],  # Y
        [0b11111, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111, 0],  # Z
    ]
    for i, ch in enumerate(letters):
        _FONT_GLYPHS[ord(ch)] = simple[i]

    # Digits 0-9
    digits = [
        [0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b01110, 0],
        [0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b01110, 0],
        [0b01110, 0b10001, 0b00010, 0b00100, 0b01000, 0b11111, 0],
        [0b01110, 0b10001, 0b00110, 0b00001, 0b10001, 0b01110, 0],
        [0b00010, 0b00110, 0b01010, 0b11111, 0b00010, 0b00010, 0],
        [0b11111, 0b10000, 0b11110, 0b00001, 0b10001, 0b01110, 0],
        [0b01110, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110, 0],
        [0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0],
        [0b01110, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110, 0],
        [0b01110, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100, 0],
    ]
    for i in range(10):
        _FONT_GLYPHS[ord("0") + i] = digits[i]

    # Additional punctuation
    _FONT_GLYPHS[34]  = [0b01010, 0b01010, 0, 0, 0, 0, 0]                # "
    _FONT_GLYPHS[35]  = [0b01010, 0b11111, 0b01010, 0b11111, 0b01010, 0, 0]  # #
    _FONT_GLYPHS[36]  = [0b00100, 0b01111, 0b10100, 0b01110, 0b00101, 0b11110, 0b00100]  # $
    _FONT_GLYPHS[37]  = [0b11001, 0b11010, 0b00100, 0b01000, 0b01011, 0b10011, 0]  # %
    _FONT_GLYPHS[38]  = [0b01100, 0b10010, 0b01100, 0b10101, 0b10010, 0b01101, 0]  # &
    _FONT_GLYPHS[39]  = [0b00100, 0b00100, 0, 0, 0, 0, 0]                # '
    _FONT_GLYPHS[40]  = [0b00010, 0b00100, 0b01000, 0b01000, 0b00100, 0b00010, 0]  # (
    _FONT_GLYPHS[41]  = [0b01000, 0b00100, 0b00010, 0b00010, 0b00100, 0b01000, 0]  # )
    _FONT_GLYPHS[42]  = [0, 0b00100, 0b10101, 0b01110, 0b10101, 0b00100, 0]  # *
    _FONT_GLYPHS[43]  = [0, 0b00100, 0b00100, 0b11111, 0b00100, 0b00100, 0]  # +
    _FONT_GLYPHS[44]  = [0, 0, 0, 0, 0b00100, 0b00100, 0b01000]          # ,
    _FONT_GLYPHS[45]  = [0, 0, 0, 0b11111, 0, 0, 0]                      # -
    _FONT_GLYPHS[46]  = [0, 0, 0, 0, 0, 0b00100, 0]                      # .
    _FONT_GLYPHS[47]  = [0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0, 0]  # /
    _FONT_GLYPHS[58]  = [0, 0b00100, 0, 0, 0b00100, 0, 0]                # :
    _FONT_GLYPHS[59]  = [0, 0b00100, 0, 0, 0b00100, 0b00100, 0b01000]    # ;
    _FONT_GLYPHS[60]  = [0b00010, 0b00100, 0b01000, 0b00100, 0b00010, 0, 0]  # <
    _FONT_GLYPHS[61]  = [0, 0, 0b11111, 0, 0b11111, 0, 0]                # =
    _FONT_GLYPHS[62]  = [0b01000, 0b00100, 0b00010, 0b00100, 0b01000, 0, 0]  # >
    _FONT_GLYPHS[63]  = [0b01110, 0b10001, 0b00010, 0b00100, 0, 0b00100, 0]  # ?
    _FONT_GLYPHS[64]  = [0b01110, 0b10001, 0b10111, 0b10101, 0b10110, 0b10000, 0b01110]  # @
    _FONT_GLYPHS[91]  = [0b01110, 0b01000, 0b01000, 0b01000, 0b01000, 0b01110, 0]  # [
    _FONT_GLYPHS[92]  = [0b10000, 0b01000, 0b00100, 0b00010, 0b00001, 0, 0]  # backslash
    _FONT_GLYPHS[93]  = [0b01110, 0b00010, 0b00010, 0b00010, 0b00010, 0b01110, 0]  # ]
    _FONT_GLYPHS[94]  = [0b00100, 0b01010, 0b10001, 0, 0, 0, 0]          # ^
    _FONT_GLYPHS[95]  = [0, 0, 0, 0, 0, 0b11111, 0]                      # _
    _FONT_GLYPHS[96]  = [0b01000, 0b00100, 0, 0, 0, 0, 0]                # `
    # Lowercase a-z reuse uppercase bitmaps (classic retro style)
    for i in range(26):
        _FONT_GLYPHS[97 + i] = _FONT_GLYPHS[65 + i]
    _FONT_GLYPHS[123] = [0b00010, 0b00100, 0b01100, 0b00100, 0b00100, 0b00010, 0]  # {
    _FONT_GLYPHS[124] = [0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0]  # |
    _FONT_GLYPHS[125] = [0b01000, 0b00100, 0b00110, 0b00100, 0b00100, 0b01000, 0]  # }
    _FONT_GLYPHS[126] = [0, 0, 0b01101, 0b10010, 0, 0, 0]                # ~


def _render_font_tile(char_code, tile_w=8, tile_h=8):
    """Render a single font character as an 8x8 PIL Image."""
    _init_font()
    img = Image.new("RGB", (tile_w, tile_h), (0, 0, 0))
    px = img.load()
    glyph = _FONT_GLYPHS.get(char_code)
    if glyph is None:
        return img
    for row_idx, bits in enumerate(glyph):
        if row_idx >= tile_h:
            break
        for col in range(5):
            if bits & (1 << (4 - col)):
                if col < tile_w and row_idx < tile_h:
                    px[col + 1, row_idx] = (255, 255, 255)
    return img


# ---------------------------------------------------------------------------
# Audio asset helpers
# ---------------------------------------------------------------------------

def parse_music_filenames(user_con_path):
    """Parse music directives from USER.CON and return unique MIDI filenames."""
    midi_files = set()
    if not os.path.exists(user_con_path):
        return midi_files
    with open(user_con_path, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("music "):
                tokens = line.split()
                # tokens[0] = "music", tokens[1] = episode, rest = filenames
                for tok in tokens[2:]:
                    tok = tok.strip()
                    if tok.lower().endswith(".mid"):
                        midi_files.add(tok)
    return midi_files


def parse_voc_filenames(user_con_path):
    """Parse definesound entries from USER.CON and return unique VOC filenames."""
    voc_files = set()
    if not os.path.exists(user_con_path):
        return voc_files
    with open(user_con_path, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("definesound "):
                tokens = line.split()
                if len(tokens) >= 3:
                    fname = tokens[2].strip()
                    if fname.lower().endswith(".voc"):
                        voc_files.add(fname)
    return voc_files


def generate_audio_assets(user_con_path):
    """Generate all MIDI music and VOC sound effect files.

    Returns:
        dict: filename (UPPERCASE) -> bytes data
    """
    audio = {}

    # Parse filenames from USER.CON
    midi_names = parse_music_filenames(user_con_path)
    voc_names = parse_voc_filenames(user_con_path)

    print(f"  Found {len(midi_names)} unique MIDI files in USER.CON")
    print(f"  Found {len(voc_names)} unique VOC files in USER.CON")

    # Generate MIDI files
    for name in sorted(midi_names):
        data = create_simple_midi(name, duration_seconds=5)
        audio[name.upper()] = data

    # Generate VOC stubs
    for name in sorted(voc_names):
        data = create_voc_stub(name, duration_ms=100)
        audio[name.upper()] = data

    return audio


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Duke3D asset generator")
    parser.add_argument("--no-ai", action="store_true",
                        help="Skip FLUX API calls; use only procedural textures")
    args = parser.parse_args()

    env = load_env(ENV_FILE)
    flux_endpoint = env.get("FLUX_ENDPOINT", "")
    flux_api_key = env.get("FLUX_API_KEY", "")
    flux_model = env.get("FLUX_MODEL", "FLUX.2-pro")
    use_ai = not args.no_ai and flux_endpoint and flux_api_key

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    palette = build_palette()

    # -- 1. Generate textures -------------------------------------------------
    print("=== Generating textures ===")
    # tiles dict: tile_num -> (width, height, picanm, column_major_pixels)
    tiles = {}

    for tile_num, tw, th, desc, prompt in TEXTURE_DEFS:
        print(f"  Tile {tile_num:3d} ({tw}x{th}) {desc}")
        img = None

        if use_ai:
            img = generate_texture_ai(prompt, tw, th, flux_endpoint, flux_api_key, flux_model)
            if img:
                print(f"    [AI] OK")

        if img is None:
            if tile_num in PROCEDURAL_MAP:
                img = PROCEDURAL_MAP[tile_num](tw, th)
            elif tile_num in GENERIC_COLORS:
                img = proc_generic(tw, th, GENERIC_COLORS[tile_num], 100 + tile_num)
            else:
                img = proc_generic(tw, th, (128, 128, 128), 100 + tile_num)
            print(f"    [Procedural] OK")

        indexed = quantize_image(img, palette)
        col_major = rgb_to_column_major(indexed, tw, th)
        tiles[tile_num] = (tw, th, 0, col_major)

    # Sprite placeholders
    for tile_num, tw, th, desc in SPRITE_DEFS:
        print(f"  Tile {tile_num:3d} ({tw}x{th}) {desc}")
        img = proc_sprite_placeholder(tw, th, desc, 200 + tile_num)
        indexed = quantize_image(img, palette)
        col_major = rgb_to_column_major(indexed, tw, th)
        tiles[tile_num] = (tw, th, 0, col_major)

    # Font characters (tiles 2048-2175 → 128 tiles covering ASCII 0-127)
    print("  Generating font tiles 2048-2175")
    for i in range(128):
        char_code = i  # ASCII 0-127
        img = _render_font_tile(char_code, 8, 8)
        indexed = quantize_image(img, palette)
        col_major = rgb_to_column_major(indexed, 8, 8)
        tiles[2048 + i] = (8, 8, 0, col_major)

    # -- Game-critical tiles from NAMES.H ------------------------------------
    print("\n=== Generating game-critical tiles from NAMES.H ===")
    game_tiles = generate_game_tiles(palette)
    new_count = 0
    for tile_num, tile_data in game_tiles.items():
        if tile_num not in tiles:
            tiles[tile_num] = tile_data
            new_count += 1
    print(f"  Parsed {len(game_tiles)} tile definitions, added {new_count} new tiles")

    # -- 2. Build ART file(s) ------------------------------------------------
    print("\n=== Building ART files ===")

    # We need to cover tile range 0 through max used tile.
    # BUILD engine expects TILES000.ART to start at tile 0.
    # We'll make one big ART from 0 .. max_tile.
    max_tile = max(tiles.keys())
    art_tiles = []
    for t in range(max_tile + 1):
        if t in tiles:
            art_tiles.append(tiles[t])
        else:
            # Empty placeholder (0x0)
            art_tiles.append((0, 0, 0, b""))

    tiles000 = create_art_file(art_tiles, localtilestart=0)
    print(f"  TILES000.ART: {len(tiles000)} bytes ({max_tile + 1} tiles)")

    # -- 3. PALETTE.DAT -------------------------------------------------------
    print("\n=== Creating PALETTE.DAT ===")
    palette_dat = create_palette_dat(palette)
    print(f"  PALETTE.DAT: {len(palette_dat)} bytes")

    # -- 4. TABLES.DAT --------------------------------------------------------
    print("\n=== Creating TABLES.DAT ===")
    tables_dat = create_tables_dat()
    print(f"  TABLES.DAT: {len(tables_dat)} bytes")

    # -- 5. Level MAPs --------------------------------------------------------
    print("\n=== Creating level MAPs (4 episodes × 11 levels) ===")
    map_data = {}
    for ep in range(1, 5):
        for lv in range(1, 12):
            name = f"E{ep}L{lv}.MAP"
            map_bytes = create_level_map(ep, lv)
            map_data[name] = map_bytes
            print(f"  {name}: {len(map_bytes)} bytes")
    print(f"  Total: {len(map_data)} maps generated")

    # -- 6. Copy data files from testdata/ ------------------------------------
    print("\n=== Copying data files from testdata/ ===")
    data_files = {}
    for fname in ["GAME.CON", "DEFS.CON", "USER.CON", "LOOKUP.DAT"]:
        src = os.path.join(TESTDATA_DIR, fname)
        if os.path.exists(src):
            with open(src, "rb") as f:
                data_files[fname] = f.read()
            print(f"  {fname}: {len(data_files[fname])} bytes")
        else:
            print(f"  [!] {fname} not found in testdata/")

    # -- 7. Generate ANM animation files --------------------------------------
    print("\n=== Generating ANM animations ===")
    anm_files = {
        "LOGO.ANM": ("DUKE NUKEM 3D", 10),
        "CINEOV2.ANM": ("EPISODE 2 END", 10),
        "CINEOV3.ANM": ("EPISODE 3 END", 10),
        "DUKETEAM.ANM": ("DUKE NUKEM TEAM", 10),
        "RADLOGO.ANM": ("3D REALMS", 10),
        "VOL41A.ANM": ("EPISODE 4", 10),
        "VOL42A.ANM": ("EPISODE 4-2", 10),
        "VOL43A.ANM": ("EPISODE 4-3", 10),
        "VOL4E1.ANM": ("EPISODE 4 END", 10),
        "VOL4E2.ANM": ("EPISODE 4 END 2", 10),
        "VOL4E3.ANM": ("EPISODE 4 END 3", 10),
    }
    anm_data = {}
    for fname, (text, fps) in anm_files.items():
        data = create_placeholder_anm(text=text, fps=fps)
        anm_data[fname] = data
        print(f"  {fname}: {len(data)} bytes")

    # -- 8. Generate MIDI music and VOC sound effects --------------------------
    print("\n=== Generating audio assets (MIDI + VOC) ===")
    user_con_path = os.path.join(TESTDATA_DIR, "USER.CON")
    audio_assets = generate_audio_assets(user_con_path)
    midi_count = sum(1 for k in audio_assets if k.endswith(".MID"))
    voc_count = sum(1 for k in audio_assets if k.endswith(".VOC"))
    print(f"  Generated {midi_count} MIDI files, {voc_count} VOC files")

    # -- 9. Generate demo stubs and timbre file --------------------------------
    print("\n=== Generating demo stubs and timbre file ===")
    demo0 = create_demo_stub(volume=0, level=0, skill=2)
    demo1 = create_demo_stub(volume=0, level=1, skill=2)
    timbre = create_timbre_stub()
    print(f"  DEMO0.DMO: {len(demo0)} bytes (0-frame stub, E1L1)")
    print(f"  DEMO1.DMO: {len(demo1)} bytes (0-frame stub, E1L2)")
    print(f"  D3DTIMBR.TMB: {len(timbre)} bytes")

    # -- 10. Pack GRP ---------------------------------------------------------
    print("\n=== Packing DUKE3D.GRP ===")
    grp_contents = {}
    grp_contents["TILES000.ART"] = tiles000
    grp_contents["PALETTE.DAT"] = palette_dat
    grp_contents["TABLES.DAT"] = tables_dat
    grp_contents.update(map_data)
    grp_contents.update(data_files)
    grp_contents.update(anm_data)
    grp_contents.update(audio_assets)
    grp_contents["DEMO0.DMO"] = demo0
    grp_contents["DEMO1.DMO"] = demo1
    grp_contents["D3DTIMBR.TMB"] = timbre

    # -- Include pre-generated audio files if they exist
    sounds_dir = os.path.join(OUTPUT_DIR, "sounds")
    if os.path.isdir(sounds_dir):
        for snd_file in sorted(os.listdir(sounds_dir)):
            if snd_file.upper().endswith(".WAV"):
                snd_path = os.path.join(sounds_dir, snd_file)
                with open(snd_path, "rb") as f:
                    grp_contents[snd_file.upper()] = f.read()
                print(f"  {snd_file.upper()}: {os.path.getsize(snd_path)} bytes")

    grp_data = create_grp(grp_contents)
    print(f"  DUKE3D.GRP: {len(grp_data)} bytes ({len(grp_contents)} files)")

    # -- 11. Write output files -----------------------------------------------
    print("\n=== Writing output ===")

    # Write individual files to generated_assets/
    for fname, data in grp_contents.items():
        out_path = os.path.join(OUTPUT_DIR, fname)
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"  {out_path}")

    # Write GRP to generated_assets/ and project root
    grp_out = os.path.join(OUTPUT_DIR, "DUKE3D.GRP")
    with open(grp_out, "wb") as f:
        f.write(grp_data)
    print(f"  {grp_out}")

    grp_root = os.path.join(PROJECT_ROOT, "DUKE3D.GRP")
    with open(grp_root, "wb") as f:
        f.write(grp_data)
    print(f"  {grp_root}")

    # -- Summary --------------------------------------------------------------
    print("\n=== Done! ===")
    print(f"  Total tiles: {len(tiles)}")
    print(f"  GRP size:    {len(grp_data):,} bytes")
    print(f"  Output:      {OUTPUT_DIR}/")
    print(f"  GRP copy:    {grp_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
