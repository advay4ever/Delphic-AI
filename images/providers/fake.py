"""Deterministic local providers for tests; these do not create real artwork."""

from __future__ import annotations

import struct
import uuid
import zlib

from ..models import GeneratedImage, ImageRequest, ImageReview


MODE_COLORS = {
    "educational_visual": (54, 196, 150),
    "realistic_image": (70, 125, 210),
    "creative_illustration": (230, 92, 160),
}


class FakeImageGenerationProvider:
    provider_id = "fake-local"
    model_id = "solid-color-test-v1"

    def __init__(self):
        self.prompts: list[str] = []

    def generate(self, request: ImageRequest, provider_prompt: str) -> GeneratedImage:
        self.prompts.append(provider_prompt)
        width, height = _dimensions_for_ratio(request.aspect_ratio)
        data = _solid_png(width, height, MODE_COLORS[request.mode])
        return GeneratedImage(
            data=data,
            mime_type="image/png",
            width=width,
            height=height,
            provider=self.provider_id,
            model=self.model_id,
            revised_prompt=provider_prompt,
            request_id=f"fake-{uuid.uuid4().hex}",
        )


class FakeImageReviewProvider:
    provider_id = "fake-local"
    model_id = "checklist-test-v1"

    def __init__(self, *, passed: bool = True, safety_problem: bool = False):
        self.passed = passed
        self.safety_problem = safety_problem

    def review(
        self,
        image: GeneratedImage,
        request: ImageRequest,
        checklist: tuple[str, ...],
    ) -> ImageReview:
        del image, request, checklist
        score = 100 if self.passed else 60
        return ImageReview(
            passed=self.passed and not self.safety_problem,
            prompt_accuracy=score,
            scientific_accuracy=score,
            readability=score,
            safety_problem=self.safety_problem,
            missing=() if self.passed else ("Fake review was configured to fail.",),
            retry_instruction=None if self.passed else "Correct the missing requirement.",
        )


def _dimensions_for_ratio(ratio: str) -> tuple[int, int]:
    return {
        "1:1": (96, 96),
        "4:3": (96, 72),
        "3:4": (72, 96),
        "16:9": (96, 54),
        "9:16": (54, 96),
    }[ratio]


def _solid_png(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    scanline = b"\x00" + bytes(color) * width
    raw_pixels = scanline * height

    def chunk(name: bytes, body: bytes) -> bytes:
        checksum = zlib.crc32(name + body) & 0xFFFFFFFF
        return struct.pack(">I", len(body)) + name + body + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw_pixels))
        + chunk(b"IEND", b"")
    )
