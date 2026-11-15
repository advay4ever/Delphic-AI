"""Shared data models used by every future image provider."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RequiredObject:
    name: str
    count: int | None = None


@dataclass(frozen=True)
class ImageRequest:
    version: int
    mode: str
    subject: str
    main_subject: str
    required_objects: tuple[RequiredObject, ...]
    relationships: tuple[str, ...]
    required_text: tuple[str, ...]
    style: str
    view: str
    colors: tuple[str, ...]
    avoid: tuple[str, ...]
    aspect_ratio: str
    student_prompt: str


@dataclass(frozen=True)
class GeneratedImage:
    data: bytes
    mime_type: str
    width: int
    height: int
    provider: str
    model: str
    revised_prompt: str | None = None
    request_id: str | None = None
    cost_usd: float | None = None


@dataclass(frozen=True)
class ImageReview:
    passed: bool
    prompt_accuracy: int
    scientific_accuracy: int
    readability: int
    safety_problem: bool
    missing: tuple[str, ...] = ()
    incorrect: tuple[str, ...] = ()
    retry_instruction: str | None = None
    cost_usd: float | None = None


@dataclass(frozen=True)
class GenerationAttempt:
    attempt_number: int
    generation_provider: str
    generation_model: str
    generation_request_id: str | None
    review_provider: str
    review_model: str
    passed: bool
    safety_problem: bool
    generation_cost_usd: float | None = None
    review_cost_usd: float | None = None


@dataclass(frozen=True)
class GenerationResult:
    request: ImageRequest
    image: GeneratedImage
    review: ImageReview
    checklist: tuple[str, ...]
    provider_prompt: str
    attempt_count: int = 1
    attempts: tuple[GenerationAttempt, ...] = ()
