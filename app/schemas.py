"""Request and response models for the FastAPI application."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    participant_code: str | None = None
    mode: str = Field(default="pilot", pattern="^(pilot|dry_run|demo)$")


class InitialAnswer(BaseModel):
    answer: dict[str, Any]


class ConfidenceRating(BaseModel):
    confidence: int = Field(ge=0, le=100)


class TrialEvent(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    client_time_ms: float | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class FinalAnswer(BaseModel):
    answer: dict[str, Any]
    evidence_active_ms: int = Field(default=0, ge=0)
    focus_lost_ms: int = Field(default=0, ge=0)
    max_blur_ms: int = Field(default=0, ge=0)
    interaction_count: int = Field(default=0, ge=0)


class SessionComplete(BaseModel):
    questionnaire: dict[str, Any] = Field(default_factory=dict)
