# Implement Basic HUD Rendering

## Priority: Medium

## Description
The game needs a heads-up display showing health, ammo, and weapon info. Currently the HUD drawing functions reference tiles that may not exist.

## Requirements
- Generate HUD tile assets (health bar, ammo counter, weapon icons)
- Implement number rendering using font tiles (2048+)
- Display health in bottom-left, ammo in bottom-right
- Display current weapon name/icon
- Draw a simple crosshair at screen center
- Generate tiles for HUD frame/border

## Files to modify
- `tools/generate_assets.py` — add HUD tile definitions
- `source/GAME.C` — HUD rendering in `displayrooms()` or equivalent
- `tools/map_format.py` — ensure HUD-related sprites exist

## Testing
- HUD elements visible during gameplay
- Numbers update correctly when health/ammo changes
