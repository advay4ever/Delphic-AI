"""Interfaces that keep Delphic independent from one image company."""

from __future__ import annotations

from typing import Protocol

from ..models import GeneratedImage, ImageRequest, ImageReview


class ImageProviderError(RuntimeError):
    """A provider failure with a message that is safe to show to a student."""

    def __init__(self, safe_message: str):
        super().__init__(safe_message)
        self.safe_message = safe_message


class ImageGenerationProvider(Protocol):
    provider_id: str
    model_id: str

    def generate(self, request: ImageRequest, provider_prompt: str) -> GeneratedImage:
        """Create one image from a validated request."""


class ImageReviewProvider(Protocol):
    provider_id: str
    model_id: str

    def review(
        self,
        image: GeneratedImage,
        request: ImageRequest,
        checklist: tuple[str, ...],
    ) -> ImageReview:
        """Review one generated image against its accuracy checklist."""
