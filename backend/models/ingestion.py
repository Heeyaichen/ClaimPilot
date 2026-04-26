"""Pydantic models for Phase 1 ingestion outputs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# --- Document Intelligence ---


class DocumentField(BaseModel):
    """A single extracted field from Document Intelligence."""

    value: str | int | float | bool | None
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_regions: list[dict] = Field(default_factory=list)


class DocumentExtractionResult(BaseModel):
    """Structured output from Document Intelligence claim form extraction."""

    markdown_content: str = ""
    fields: dict[str, DocumentField] = Field(default_factory=dict)
    model_id: str = ""
    pages: int = 0
    extracted_at: datetime = Field(default_factory=datetime.utcnow)


# --- Content Understanding (image analysis) ---


class DamageIndicator(BaseModel):
    """A single damage observation from an accident image."""

    panel: str = Field(description="Vehicle panel: front, rear, driver_side, passenger_side, roof, undercarriage")
    severity: str = Field(description="minor, moderate, severe, total_loss_candidate")
    description: str = ""


class VehicleIdentification(BaseModel):
    """Vehicle characteristics identified from images."""

    make: str = ""
    model: str = ""
    year: int | None = None
    color: str = ""
    license_plate_visible: bool = False
    license_plate_value: str | None = None


class SceneConditions(BaseModel):
    """Environmental and contextual scene metadata."""

    time_of_day_estimated: str = ""
    weather_conditions: str = ""
    location_type: str = ""


class ImageAnalysisResult(BaseModel):
    """Structured output from Content Understanding image analysis."""

    damage_indicators: list[DamageIndicator] = Field(default_factory=list)
    vehicle_identification: VehicleIdentification = Field(default_factory=VehicleIdentification)
    scene_conditions: SceneConditions = Field(default_factory=SceneConditions)
    forensic_flags: list[str] = Field(default_factory=list)
    raw_response: dict = Field(default_factory=dict)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


# --- Speech STT ---


class VoiceTranscript(BaseModel):
    """Structured output from Speech STT transcription."""

    original_text: str
    translated_text: str | None = None
    detected_language: str = "en-US"
    duration_seconds: float = 0.0
    speaker_count: int = 1
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    transcribed_at: datetime = Field(default_factory=datetime.utcnow)


# --- Translator ---


class TranslationResult(BaseModel):
    """Structured output from Azure Translator."""

    original_text: str
    translated_text: str
    source_language: str
    target_language: str = "en"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    translated_at: datetime = Field(default_factory=datetime.utcnow)
