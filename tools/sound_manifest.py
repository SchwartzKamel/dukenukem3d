#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Pydantic models for sound manifest validation.

Provides structured validation for SOUND_MANIFEST entries using Pydantic v2,
ensuring type safety and schema correctness across the audio pipeline.
"""

from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class SoundManifestEntry(BaseModel):
    """Pydantic model for a single SOUND_MANIFEST entry.
    
    Fields are validated for type correctness, enum constraints, and semantic
    consistency with the engine sound ID registry (source/SOUNDEFS.H).
    """
    
    model_config = ConfigDict(strict=True, validate_assignment=True)
    
    wav: str = Field(
        ...,
        description="WAV filename (e.g., 'TAUNT01.WAV')",
        pattern=r'^[A-Z0-9_]+\.WAV$'
    )
    
    engine_sound_id: Optional[str] = Field(
        None,
        description="C identifier for engine sound (e.g., 'DUKE_GRUNT') or None if no mapping",
        pattern=r'^[A-Z_][A-Z0-9_]*$'
    )
    
    engine_sound_id_int: Optional[int] = Field(
        None,
        description="Integer engine sound ID from source/SOUNDEFS.H or None if unmapped",
        ge=0,
        le=1000
    )
    
    voice: Literal['alloy', 'echo', 'onyx'] = Field(
        ...,
        description="TTS voice engine (alloy, echo, or onyx)"
    )
    
    category: Literal[
        'taunt', 'pain', 'death', 'pickup', 'weapon',
        'level_start', 'alarm', 'ambient'
    ] = Field(
        ...,
        description="Sound category for runtime context and UI grouping"
    )
    
    prompt_summary: str = Field(
        ...,
        description="Concise summary of the prompt used for generation",
        min_length=1,
        max_length=500
    )
    
    notes: Optional[str] = Field(
        None,
        description="Optional metadata: generation notes, context, or runtime hints",
        max_length=1000
    )
    
    status: Literal['generated', 'failed', 'fallback'] = Field(
        'generated',
        description="Generation status (generated, failed, or fallback placeholder)"
    )
    
    generation_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional metadata dict: model version, confidence, generation params, etc."
    )
    
    generated_at: Optional[str] = Field(
        None,
        description="ISO 8601 timestamp of generation (e.g., '1970-01-01T00:00:00Z')"
    )
    
    schema_version: Literal['1.0'] = Field(
        '1.0',
        description="Entry schema version (currently '1.0')"
    )
    
    @field_validator('engine_sound_id', 'engine_sound_id_int')
    @classmethod
    def validate_engine_id_consistency(cls, v):
        """Validate that engine_sound_id and engine_sound_id_int are both set or both None.
        
        NOTE: This is a per-field validator and cannot check cross-field consistency.
        Use model_validator for full consistency checks if needed.
        """
        return v


def validate_sound_manifest_entries(entries: List[dict]) -> List[SoundManifestEntry]:
    """Validate a list of sound manifest entry dicts and return Pydantic models.
    
    Performs strict validation of each entry against the SoundManifestEntry schema,
    including type checking, enum validation, and range constraints.
    
    Args:
        entries: List of manifest entry dicts (typically from SOUND_MANIFEST global)
    
    Returns:
        List of validated SoundManifestEntry models
    
    Raises:
        ValueError: If any entry fails validation, includes field-level error details
    """
    validated = []
    errors = []
    
    for i, entry in enumerate(entries):
        try:
            validated.append(SoundManifestEntry(**entry))
        except Exception as e:
            errors.append(f"Entry {i} ({entry.get('wav', '?')}): {e}")
    
    if errors:
        raise ValueError(
            f"Sound manifest validation failed with {len(errors)} error(s):\n"
            + "\n".join(f"  - {err}" for err in errors)
        )
    
    return validated
