import base64
import json
from io import BytesIO

import httpx
import pytest
from PIL import Image, PngImagePlugin

from images import build_image_request
from images.models import GeneratedImage
from images.providers.base import ImageProviderError
from images.providers.fake import FakeImageGenerationProvider
from images.providers.openrouter import (
    OPENROUTER_IMAGE_MODEL,
    OPENROUTER_IMAGE_MODELS,
    OPENROUTER_REVIEW_MODEL,
    OpenRouterImageGenerationProvider,
    OpenRouterImageReviewProvider,
)
from images.validation import ImageValidationError, sanitize_generated_image


def image_request():
    return build_image_request({
        "version": 1,
        "mode": "educational_visual",
        "subject": "science",
        "main_subject": "a plant cell",
        "required_objects": [{"name": "nucleus", "count": 1}],
        "relationships": ["the nucleus is inside the cell"],
        "required_text": [],
        "style": "clear textbook illustration",
        "view": "close-up",
        "colors": ["green cell wall"],
        "avoid": ["extra labels"],
        "aspect_ratio": "1:1",
        "student_prompt": "Create a clear plant cell illustration",
    })


def test_openrouter_generator_pins_model_provider_and_safe_options():
    png = FakeImageGenerationProvider().generate(image_request(), "test").data
    captured = {}

    def handler(request):
        captured["headers"] = request.headers
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={
            "id": "generation-123",
            "data": [{
                "b64_json": base64.b64encode(png).decode("ascii"),
                "media_type": "image/png",
            }],
            "usage": {"cost": 0.042},
        }, headers={"x-request-id": "request-123"})

    client = httpx.Client(
        base_url="https://openrouter.ai/api/v1",
        transport=httpx.MockTransport(handler),
    )
    provider = OpenRouterImageGenerationProvider("sk-or-test-key", client=client)

    result = provider.generate(image_request(), "Draw the cell")

    assert captured["payload"] == {
        "model": OPENROUTER_IMAGE_MODEL,
        "prompt": "Draw the cell",
        "n": 1,
        "aspect_ratio": "1:1",
        "quality": "medium",
        "moderation": "auto",
        "provider": {"only": ["openai"], "allow_fallbacks": False},
    }
    assert captured["headers"]["authorization"] == "Bearer sk-or-test-key"
    assert result.request_id == "request-123"
    assert result.cost_usd == pytest.approx(0.042)
    assert result.model == OPENROUTER_IMAGE_MODEL
    assert (result.width, result.height) == (96, 96)


def test_openrouter_generator_uses_the_selected_allowed_image_model():
    png = FakeImageGenerationProvider().generate(image_request(), "test").data
    captured = {}

    def handler(request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={
            "data": [{
                "b64_json": base64.b64encode(png).decode("ascii"),
                "media_type": "image/png",
            }],
        })

    client = httpx.Client(
        base_url="https://openrouter.ai/api/v1",
        transport=httpx.MockTransport(handler),
    )
    flare_model = OPENROUTER_IMAGE_MODELS[1]["id"]
    provider = OpenRouterImageGenerationProvider(
        "sk-or-test-key",
        model_id=flare_model,
        client=client,
    )

    result = provider.generate(image_request(), "Draw the cell")

    assert captured["payload"]["model"] == flare_model
    assert result.model == flare_model


def test_openrouter_generator_rejects_an_unlisted_image_model():
    with pytest.raises(ValueError, match="supported image model"):
        OpenRouterImageGenerationProvider(
            "sk-or-test-key",
            model_id="unknown/image-model",
        )


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, "rejected the API key"),
        (402, "needs more credits"),
        (403, "account or safety rule"),
        (429, "too many requests"),
        (503, "temporarily unavailable"),
    ],
)
def test_openrouter_errors_are_specific_without_leaking_response(status_code, expected):
    secret_body = "private-provider-error-details"
    client = httpx.Client(
        base_url="https://openrouter.ai/api/v1",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(status_code, text=secret_body)
        ),
    )
    provider = OpenRouterImageGenerationProvider("sk-or-test-key", client=client)

    with pytest.raises(ImageProviderError, match=expected) as error:
        provider.generate(image_request(), "Draw the cell")

    assert secret_body not in str(error.value)


def test_openrouter_generator_rejects_invalid_base64():
    client = httpx.Client(
        base_url="https://openrouter.ai/api/v1",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={
                "data": [{"b64_json": "not valid base64!", "media_type": "image/png"}],
            })
        ),
    )

    with pytest.raises(ImageProviderError, match="invalid image"):
        OpenRouterImageGenerationProvider("sk-or-test-key", client=client).generate(
            image_request(),
            "Draw the cell",
        )


def test_openrouter_reviewer_uses_structured_output_and_reads_cost():
    image = FakeImageGenerationProvider().generate(image_request(), "test")
    captured = {}
    review_json = {
        "passed": True,
        "prompt_accuracy": 95,
        "scientific_accuracy": 98,
        "readability": 93,
        "safety_problem": False,
        "missing": [],
        "incorrect": [],
        "retry_instruction": None,
    }

    def handler(request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(review_json)}}],
            "usage": {"cost": 0.003},
        })

    client = httpx.Client(
        base_url="https://openrouter.ai/api/v1",
        transport=httpx.MockTransport(handler),
    )
    reviewer = OpenRouterImageReviewProvider("sk-or-test-key", client=client)

    result = reviewer.review(image, image_request(), ("Show one nucleus.",))

    assert captured["payload"]["model"] == OPENROUTER_REVIEW_MODEL
    assert captured["payload"]["provider"] == {
        "only": ["openai"],
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert captured["payload"]["response_format"]["json_schema"]["strict"] is True
    image_url = captured["payload"]["messages"][1]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")
    assert result.passed is True
    assert result.cost_usd == pytest.approx(0.003)


def test_openrouter_reviewer_rejects_non_list_review_items():
    image = FakeImageGenerationProvider().generate(image_request(), "test")
    review_json = {
        "passed": False,
        "prompt_accuracy": 50,
        "scientific_accuracy": 50,
        "readability": 50,
        "safety_problem": False,
        "missing": "nucleus",
        "incorrect": [],
        "retry_instruction": "Add one nucleus.",
    }
    client = httpx.Client(
        base_url="https://openrouter.ai/api/v1",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(review_json)}}],
        })),
    )

    with pytest.raises(ImageProviderError, match="invalid result"):
        OpenRouterImageReviewProvider("sk-or-test-key", client=client).review(
            image,
            image_request(),
            ("Show one nucleus.",),
        )


def test_pillow_reencoding_removes_png_text_metadata():
    output = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private-note", "do not keep this")
    Image.new("RGB", (32, 32), (20, 40, 60)).save(output, format="PNG", pnginfo=metadata)
    image = GeneratedImage(
        data=output.getvalue(),
        mime_type="image/png",
        width=32,
        height=32,
        provider="test",
        model="test",
    )

    clean = sanitize_generated_image(image)

    with Image.open(BytesIO(clean.data)) as decoded:
        assert "private-note" not in decoded.info
        assert decoded.size == (32, 32)


def test_pillow_rejects_png_with_valid_header_but_broken_data():
    png = FakeImageGenerationProvider().generate(image_request(), "test").data
    broken = png[:33]
    image = GeneratedImage(
        data=broken,
        mime_type="image/png",
        width=96,
        height=96,
        provider="test",
        model="test",
    )

    with pytest.raises(ImageValidationError, match="safe PNG"):
        sanitize_generated_image(image)
