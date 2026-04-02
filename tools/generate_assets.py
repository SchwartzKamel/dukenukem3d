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

from art_format import create_art_file, rgb_to_column_major
from grp_format import create_grp
from map_format import create_test_map
from palette import build_palette, create_palette_dat, quantize_image
from tables import create_tables_dat

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
# Font tile generation (tiles 2048-2079, 8x8 each)
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

    # Font characters (tiles 2048-2079 → 32 tiles covering space..?)
    print("  Generating font tiles 2048-2079")
    for i in range(32):
        char_code = 32 + i  # space=32 .. '?'=63
        img = _render_font_tile(char_code, 8, 8)
        indexed = quantize_image(img, palette)
        col_major = rgb_to_column_major(indexed, 8, 8)
        tiles[2048 + i] = (8, 8, 0, col_major)

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

    # -- 5. Test MAP ----------------------------------------------------------
    print("\n=== Creating test MAP ===")
    test_map = create_test_map()
    print(f"  E1L1.MAP: {len(test_map)} bytes")

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

    # -- 7. Pack GRP ----------------------------------------------------------
    print("\n=== Packing DUKE3D.GRP ===")
    grp_contents = {}
    grp_contents["TILES000.ART"] = tiles000
    grp_contents["PALETTE.DAT"] = palette_dat
    grp_contents["TABLES.DAT"] = tables_dat
    grp_contents["E1L1.MAP"] = test_map
    grp_contents.update(data_files)

    grp_data = create_grp(grp_contents)
    print(f"  DUKE3D.GRP: {len(grp_data)} bytes ({len(grp_contents)} files)")

    # -- 8. Write output files ------------------------------------------------
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
