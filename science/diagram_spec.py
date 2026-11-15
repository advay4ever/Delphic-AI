"""Validation for the small, data-only language used by science diagrams."""

from copy import deepcopy
import math
import re


class DiagramValidationError(ValueError):
    """Raised when diagram data is not safe or does not match the schema."""


DIAGRAM_TYPES = {
    "force_diagram",
    "circuit_diagram",
    "process_diagram",
    "labeled_structure",
}
OBJECT_FIELDS = {
    "box": {"id", "kind", "x", "y", "width", "height", "label"},
    "ellipse": {"id", "kind", "cx", "cy", "rx", "ry", "label"},
    "circle": {"id", "kind", "cx", "cy", "r", "label"},
    "line": {"id", "kind", "x1", "y1", "x2", "y2"},
    "arrow": {"id", "kind", "x1", "y1", "x2", "y2", "label"},
    "battery": {"id", "kind", "x", "y", "width", "height", "label"},
    "resistor": {"id", "kind", "x", "y", "width", "height", "label"},
    "label": {"id", "kind", "x", "y", "text", "anchor"},
}
ROOT_FIELDS = {"version", "type", "title", "description", "objects"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
UNSAFE_LABEL_PATTERN = re.compile(r"[<>]|(?:javascript|data)\s*:", re.IGNORECASE)
MAX_OBJECTS = 24


def _safe_text(value: object, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise DiagramValidationError(f"{field} must be text.")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum:
        raise DiagramValidationError(f"{field} must be between 1 and {maximum} characters.")
    if any(ord(character) < 32 for character in cleaned) or UNSAFE_LABEL_PATTERN.search(cleaned):
        raise DiagramValidationError(f"{field} contains unsafe text.")
    return cleaned


def _coordinate(value: object, field: str, minimum: float = 0, maximum: float = 100) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DiagramValidationError(f"{field} must be a number.")
    number = float(value)
    if not math.isfinite(number) or number < minimum or number > maximum:
        raise DiagramValidationError(f"{field} must be between {minimum} and {maximum}.")
    return number


def validate_diagram_spec(spec: object) -> dict:
    """Return a clean copy of a valid diagram or raise DiagramValidationError."""
    if not isinstance(spec, dict):
        raise DiagramValidationError("A diagram must be an object.")
    if set(spec) != ROOT_FIELDS:
        raise DiagramValidationError("The diagram has missing or unknown fields.")
    if spec.get("version") != 1:
        raise DiagramValidationError("The diagram version is not supported.")
    if spec.get("type") not in DIAGRAM_TYPES:
        raise DiagramValidationError("The diagram type is not supported.")

    title = _safe_text(spec.get("title"), "title", 80)
    description = _safe_text(spec.get("description"), "description", 300)
    objects = spec.get("objects")
    if not isinstance(objects, list) or not 1 <= len(objects) <= MAX_OBJECTS:
        raise DiagramValidationError(f"A diagram must contain 1 to {MAX_OBJECTS} objects.")

    clean_objects = []
    used_ids = set()
    for index, item in enumerate(objects):
        if not isinstance(item, dict):
            raise DiagramValidationError(f"Object {index + 1} must be an object.")
        kind = item.get("kind")
        expected_fields = OBJECT_FIELDS.get(kind)
        if expected_fields is None or set(item) != expected_fields:
            raise DiagramValidationError(f"Object {index + 1} has an unsupported shape or fields.")

        object_id = item.get("id")
        if not isinstance(object_id, str) or not ID_PATTERN.fullmatch(object_id):
            raise DiagramValidationError(f"Object {index + 1} has an invalid ID.")
        if object_id in used_ids:
            raise DiagramValidationError("Diagram object IDs must be unique.")
        used_ids.add(object_id)

        clean_item = deepcopy(item)
        for field in expected_fields - {"id", "kind", "label", "text", "anchor"}:
            minimum = 1 if field in {"width", "height", "rx", "ry", "r"} else 0
            clean_item[field] = _coordinate(item[field], field, minimum=minimum)
        if kind in {"box", "battery", "resistor"} and (
            clean_item["x"] + clean_item["width"] > 100
            or clean_item["y"] + clean_item["height"] > 100
        ):
            raise DiagramValidationError(f"Object {index + 1} extends beyond the drawing area.")
        if kind == "ellipse" and (
            clean_item["cx"] - clean_item["rx"] < 0
            or clean_item["cx"] + clean_item["rx"] > 100
            or clean_item["cy"] - clean_item["ry"] < 0
            or clean_item["cy"] + clean_item["ry"] > 100
        ):
            raise DiagramValidationError(f"Object {index + 1} extends beyond the drawing area.")
        if kind == "circle" and (
            clean_item["cx"] - clean_item["r"] < 0
            or clean_item["cx"] + clean_item["r"] > 100
            or clean_item["cy"] - clean_item["r"] < 0
            or clean_item["cy"] + clean_item["r"] > 100
        ):
            raise DiagramValidationError(f"Object {index + 1} extends beyond the drawing area.")
        if "label" in expected_fields:
            clean_item["label"] = _safe_text(item["label"], "label", 50)
        if "text" in expected_fields:
            clean_item["text"] = _safe_text(item["text"], "text", 60)
        if "anchor" in expected_fields and item["anchor"] not in {"start", "middle", "end"}:
            raise DiagramValidationError("Label anchor must be start, middle, or end.")
        clean_objects.append(clean_item)

    return {
        "version": 1,
        "type": spec["type"],
        "title": title,
        "description": description,
        "objects": clean_objects,
    }
