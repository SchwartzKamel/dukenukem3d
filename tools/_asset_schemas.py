"""Pydantic schemas for texture and sprite asset definitions.

This module defines strict validation schemas for texture and sprite tile
definitions, matching the pattern used for audio manifests. Schemas validate
at config-load time to catch typos and invalid dimensions early.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict


class TextureDef(BaseModel):
    """Validates texture definition tuples (tile_num, width, height, desc, prompt).
    
    Fields:
    - tile_num: Tile index in the asset table (0-4943 for 64k tiles)
    - width: Texture width in pixels (1-256)
    - height: Texture height in pixels (1-256)
    - description: Human-readable description of the texture
    - flux_prompt: FLUX.2 AI prompt for generation
    """
    
    tile_num: int = Field(..., ge=0, le=4943, description="Tile index (0-4943)")
    width: int = Field(..., ge=1, le=256, description="Texture width pixels (1-256)")
    height: int = Field(..., ge=1, le=256, description="Texture height pixels (1-256)")
    description: str = Field(..., min_length=1, max_length=256, description="Texture description")
    flux_prompt: str = Field(..., min_length=1, max_length=2048, description="FLUX.2 AI prompt")
    
    model_config = ConfigDict(extra='forbid')
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        """Ensure description is non-empty and reasonable length."""
        if not v or not v.strip():
            raise ValueError("description cannot be empty")
        return v.strip()
    
    @field_validator('flux_prompt')
    @classmethod
    def validate_flux_prompt(cls, v):
        """Ensure flux_prompt is non-empty and reasonable length."""
        if not v or not v.strip():
            raise ValueError("flux_prompt cannot be empty")
        return v.strip()


class SpriteDef(BaseModel):
    """Validates sprite definition tuples (tile_num, width, height, description).
    
    Sprites are small item/actor placeholder tiles used in the engine.
    
    Fields:
    - tile_num: Tile index in the asset table
    - width: Sprite width in pixels (1-256)
    - height: Sprite height in pixels (1-256)
    - description: Human-readable description of the sprite (item name, etc.)
    """
    
    tile_num: int = Field(..., ge=0, le=4943, description="Tile index (0-4943)")
    width: int = Field(..., ge=1, le=256, description="Sprite width pixels (1-256)")
    height: int = Field(..., ge=1, le=256, description="Sprite height pixels (1-256)")
    description: str = Field(..., min_length=1, max_length=256, description="Sprite description")
    
    model_config = ConfigDict(extra='forbid')
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        """Ensure description is non-empty and reasonable length."""
        if not v or not v.strip():
            raise ValueError("description cannot be empty")
        return v.strip()


def validate_texture_defs(texture_defs):
    """Validate a list of texture definitions against TextureDef schema.
    
    Args:
        texture_defs: List of tuples (tile_num, width, height, description, flux_prompt)
    
    Returns:
        List of validated TextureDef instances
    
    Raises:
        ValueError: If any texture definition is invalid
    """
    validated = []
    for i, tex_tuple in enumerate(texture_defs):
        try:
            if len(tex_tuple) != 5:
                raise ValueError(
                    f"Expected 5 elements (tile_num, width, height, description, flux_prompt), "
                    f"got {len(tex_tuple)}"
                )
            tile_num, width, height, description, flux_prompt = tex_tuple
            validated.append(TextureDef(
                tile_num=tile_num,
                width=width,
                height=height,
                description=description,
                flux_prompt=flux_prompt
            ))
        except ValueError as e:
            raise ValueError(f"TEXTURE_DEFS[{i}]: {str(e)}") from e
    return validated


def validate_sprite_defs(sprite_defs):
    """Validate a list of sprite definitions against SpriteDef schema.
    
    Args:
        sprite_defs: List of tuples (tile_num, width, height, description)
    
    Returns:
        List of validated SpriteDef instances
    
    Raises:
        ValueError: If any sprite definition is invalid
    """
    validated = []
    for i, sprite_tuple in enumerate(sprite_defs):
        try:
            if len(sprite_tuple) != 4:
                raise ValueError(
                    f"Expected 4 elements (tile_num, width, height, description), "
                    f"got {len(sprite_tuple)}"
                )
            tile_num, width, height, description = sprite_tuple
            validated.append(SpriteDef(
                tile_num=tile_num,
                width=width,
                height=height,
                description=description
            ))
        except ValueError as e:
            raise ValueError(f"SPRITE_DEFS[{i}]: {str(e)}") from e
    return validated
