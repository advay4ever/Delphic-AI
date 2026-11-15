"""Build a stable provider prompt and an accuracy checklist."""

from __future__ import annotations

from .models import ImageRequest


MODE_LABELS = {
    "educational_visual": "an educational visual",
    "realistic_image": "a realistic image",
    "creative_illustration": "a creative illustration",
}


def build_accuracy_checklist(request: ImageRequest) -> tuple[str, ...]:
    checklist = [f"Show the main subject: {request.main_subject}."]
    for item in request.required_objects:
        if item.count is None:
            checklist.append(f"Include {item.name}.")
        else:
            checklist.append(f"Include exactly {item.count} {item.name}.")
    checklist.extend(f"Show this relationship: {item}." for item in request.relationships)
    checklist.extend(f"Use this visible text exactly: {item}." for item in request.required_text)
    checklist.extend(f"Use this color instruction: {item}." for item in request.colors)
    checklist.extend(f"Do not include: {item}." for item in request.avoid)
    checklist.append(f"Use the style: {request.style}.")
    checklist.append(f"Use the view: {request.view}.")
    return tuple(checklist)


def build_provider_prompt(
    request: ImageRequest,
    checklist: tuple[str, ...],
) -> str:
    requirements = "\n".join(f"- {item}" for item in checklist)
    prompt = (
        f"Create one {MODE_LABELS[request.mode]} for a {request.subject} student.\n"
        "Keep the image appropriate for a school math or science lesson. "
        "Do not create targeted bullying, humiliation, hateful propaganda, "
        "sexual or nude imagery, graphic violence, self-harm imagery, "
        "impersonation of real people, fabricated evidence, "
        "or weapon-making instructions. Ordinary nonsexual scientific anatomy "
        "and medical illustrations are allowed.\n"
        "Follow every requirement below. Keep the main idea easy to see and do not add "
        "details that change its meaning.\n\n"
        f"Requirements:\n{requirements}\n\n"
        f"Canvas ratio: {request.aspect_ratio}.\n"
        f"Original student request: {request.student_prompt}"
    )
    return prompt


def build_retry_prompt(provider_prompt: str, correction: str) -> str:
    return (
        f"{provider_prompt}\n\n"
        "Correction for this one retry:\n"
        f"- {correction}\n"
        "Keep every original requirement while applying only this correction."
    )
