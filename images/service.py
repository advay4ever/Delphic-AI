"""Provider-neutral image generation workflow."""

from __future__ import annotations

from collections.abc import Mapping

from .models import GeneratedImage, GenerationAttempt, GenerationResult, ImageRequest, ImageReview
from .prompt_builder import build_accuracy_checklist, build_provider_prompt, build_retry_prompt
from .providers.base import ImageGenerationProvider, ImageProviderError, ImageReviewProvider
from .safety import ImageSafetyError, validate_image_safety, validate_image_safety_text
from .validation import (
    build_image_request,
    sanitize_generated_image,
    validate_image_review,
)


MAX_AUTOMATIC_RETRIES = 1


class ImageGenerationError(RuntimeError):
    """A student-safe failure that does not expose provider secrets."""


def generate_checked_image(
    payload: Mapping,
    generator: ImageGenerationProvider,
    reviewer: ImageReviewProvider,
) -> GenerationResult:
    """Validate, generate, review, and retry at most once when useful."""
    request = build_image_request(payload)
    validate_image_safety(request)
    checklist = build_accuracy_checklist(request)
    provider_prompt = build_provider_prompt(request, checklist)
    attempts = []

    image, review = _run_attempt(
        request,
        checklist,
        provider_prompt,
        generator,
        reviewer,
    )
    attempts.append(_attempt_record(1, image, review, reviewer))

    for _retry_index in range(MAX_AUTOMATIC_RETRIES):
        if review.passed or review.safety_problem or not review.retry_instruction:
            break
        validate_image_safety_text(review.retry_instruction)
        retry_prompt = build_retry_prompt(provider_prompt, review.retry_instruction)
        image, review = _run_attempt(
            request,
            checklist,
            retry_prompt,
            generator,
            reviewer,
        )
        attempts.append(_attempt_record(len(attempts) + 1, image, review, reviewer))

    return GenerationResult(
        request=request,
        image=image,
        review=review,
        checklist=checklist,
        provider_prompt=provider_prompt,
        attempt_count=len(attempts),
        attempts=tuple(attempts),
    )


def _run_attempt(
    request: ImageRequest,
    checklist: tuple[str, ...],
    provider_prompt: str,
    generator: ImageGenerationProvider,
    reviewer: ImageReviewProvider,
) -> tuple[GeneratedImage, ImageReview]:
    try:
        image = generator.generate(request, provider_prompt)
    except ImageProviderError as error:
        raise ImageGenerationError(error.safe_message) from error
    except Exception as error:
        raise ImageGenerationError("The image provider could not create an image.") from error
    image = sanitize_generated_image(image)

    try:
        review = reviewer.review(image, request, checklist)
    except ImageProviderError as error:
        raise ImageGenerationError(error.safe_message) from error
    except Exception as error:
        raise ImageGenerationError("The image reviewer could not check the result.") from error
    validate_image_review(review)
    if review.safety_problem:
        raise ImageSafetyError(
            "This image did not pass the student safety check. "
            "Try an educational math or science image."
        )
    return image, review


def _attempt_record(
    attempt_number: int,
    image: GeneratedImage,
    review: ImageReview,
    reviewer: ImageReviewProvider,
) -> GenerationAttempt:
    review_provider = getattr(reviewer, "provider_id", None)
    review_model = getattr(reviewer, "model_id", None)
    if (
        not isinstance(review_provider, str)
        or not review_provider.strip()
        or not isinstance(review_model, str)
        or not review_model.strip()
    ):
        raise ImageGenerationError("The image reviewer metadata is incomplete.")
    return GenerationAttempt(
        attempt_number=attempt_number,
        generation_provider=image.provider,
        generation_model=image.model,
        generation_request_id=image.request_id,
        review_provider=review_provider,
        review_model=review_model,
        passed=review.passed,
        safety_problem=review.safety_problem,
        generation_cost_usd=image.cost_usd,
        review_cost_usd=review.cost_usd,
    )
