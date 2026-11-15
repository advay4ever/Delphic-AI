"""Reviewed starter templates for local science diagrams."""

import re

from .diagram_spec import validate_diagram_spec


DIAGRAM_INTENT = re.compile(
    r"\b(diagram|draw|drawing|picture|visuali[sz]e|illustrat(?:e|ion)|show\s+me)\b",
    re.IGNORECASE,
)


def _force_diagram() -> dict:
    return {
        "version": 1,
        "type": "force_diagram",
        "title": "Forces on a box",
        "description": "An example free-body diagram showing equal and opposite vertical and horizontal force pairs on a box.",
        "objects": [
            {"id": "box", "kind": "box", "x": 38, "y": 37, "width": 24, "height": 20, "label": "Box"},
            {"id": "normal", "kind": "arrow", "x1": 50, "y1": 37, "x2": 50, "y2": 9, "label": "Normal force"},
            {"id": "weight", "kind": "arrow", "x1": 50, "y1": 57, "x2": 50, "y2": 85, "label": "Weight"},
            {"id": "applied", "kind": "arrow", "x1": 62, "y1": 47, "x2": 91, "y2": 47, "label": "Applied force"},
            {"id": "friction", "kind": "arrow", "x1": 38, "y1": 47, "x2": 9, "y2": 47, "label": "Friction"},
        ],
    }


def _circuit_diagram() -> dict:
    return {
        "version": 1,
        "type": "circuit_diagram",
        "title": "Simple closed circuit",
        "description": "A battery and resistor connected by one complete wire loop, allowing conventional current to flow.",
        "objects": [
            {"id": "wire-top-left", "kind": "line", "x1": 20, "y1": 18, "x2": 41, "y2": 18},
            {"id": "resistor", "kind": "resistor", "x": 41, "y": 13, "width": 22, "height": 10, "label": "Resistor"},
            {"id": "wire-top-right", "kind": "line", "x1": 63, "y1": 18, "x2": 84, "y2": 18},
            {"id": "wire-right", "kind": "line", "x1": 84, "y1": 18, "x2": 84, "y2": 74},
            {"id": "wire-bottom", "kind": "line", "x1": 84, "y1": 74, "x2": 20, "y2": 74},
            {"id": "wire-left-top", "kind": "line", "x1": 20, "y1": 18, "x2": 20, "y2": 42},
            {"id": "battery", "kind": "battery", "x": 14, "y": 38, "width": 12, "height": 18, "label": "Battery"},
            {"id": "wire-left-bottom", "kind": "line", "x1": 20, "y1": 51, "x2": 20, "y2": 74},
            {"id": "current", "kind": "arrow", "x1": 67, "y1": 74, "x2": 42, "y2": 74, "label": "Current"},
        ],
    }


def _water_cycle_diagram() -> dict:
    return {
        "version": 1,
        "type": "process_diagram",
        "title": "The water cycle",
        "description": "Water moves from Earth's surface into the air and returns through evaporation, condensation, precipitation, and collection.",
        "objects": [
            {"id": "ocean", "kind": "box", "x": 8, "y": 72, "width": 27, "height": 13, "label": "Ocean"},
            {"id": "vapor", "kind": "ellipse", "cx": 22, "cy": 25, "rx": 14, "ry": 9, "label": "Water vapor"},
            {"id": "cloud", "kind": "ellipse", "cx": 69, "cy": 24, "rx": 17, "ry": 10, "label": "Clouds"},
            {"id": "land", "kind": "box", "x": 65, "y": 72, "width": 27, "height": 13, "label": "Land"},
            {"id": "evaporation", "kind": "arrow", "x1": 20, "y1": 72, "x2": 20, "y2": 36, "label": "Evaporation"},
            {"id": "condensation", "kind": "arrow", "x1": 36, "y1": 24, "x2": 51, "y2": 24, "label": "Condensation"},
            {"id": "precipitation", "kind": "arrow", "x1": 72, "y1": 34, "x2": 76, "y2": 68, "label": "Precipitation"},
            {"id": "collection", "kind": "arrow", "x1": 65, "y1": 79, "x2": 39, "y2": 79, "label": "Collection"},
        ],
    }


def _plant_cell_diagram() -> dict:
    return {
        "version": 1,
        "type": "labeled_structure",
        "title": "Main parts of a plant cell",
        "description": "A simplified plant cell showing the cell wall, cell membrane, cytoplasm, nucleus, central vacuole, and chloroplasts.",
        "objects": [
            {"id": "cell-wall", "kind": "box", "x": 7, "y": 12, "width": 86, "height": 76, "label": "Cell wall"},
            {"id": "cell-membrane", "kind": "box", "x": 11, "y": 16, "width": 78, "height": 68, "label": "Cell membrane"},
            {"id": "vacuole", "kind": "ellipse", "cx": 56, "cy": 52, "rx": 20, "ry": 22, "label": "Central vacuole"},
            {"id": "nucleus", "kind": "circle", "cx": 28, "cy": 48, "r": 8, "label": "Nucleus"},
            {"id": "chloroplast-one", "kind": "ellipse", "cx": 44, "cy": 22, "rx": 9, "ry": 5, "label": "Chloroplast"},
            {"id": "chloroplast-two", "kind": "ellipse", "cx": 75, "cy": 67, "rx": 9, "ry": 5, "label": "Chloroplast"},
            {"id": "wall-callout", "kind": "line", "x1": 87, "y1": 12, "x2": 92, "y2": 8},
            {"id": "wall-label", "kind": "label", "x": 95, "y": 7, "text": "Cell wall", "anchor": "end"},
            {"id": "membrane-callout", "kind": "line", "x1": 85, "y1": 84, "x2": 92, "y2": 92},
            {"id": "membrane-label", "kind": "label", "x": 95, "y": 97, "text": "Cell membrane", "anchor": "end"},
            {"id": "vacuole-label", "kind": "label", "x": 56, "y": 53, "text": "Central vacuole", "anchor": "middle"},
            {"id": "nucleus-label", "kind": "label", "x": 28, "y": 49, "text": "Nucleus", "anchor": "middle"},
            {"id": "chloroplast-label", "kind": "label", "x": 44, "y": 23, "text": "Chloroplast", "anchor": "middle"},
            {"id": "cytoplasm-label", "kind": "label", "x": 27, "y": 72, "text": "Cytoplasm", "anchor": "middle"},
        ],
    }


TEMPLATES = {
    "force": _force_diagram,
    "circuit": _circuit_diagram,
    "water_cycle": _water_cycle_diagram,
    "plant_cell": _plant_cell_diagram,
}


def _topic_for_request(message: str) -> str | None:
    lowered = message.casefold()
    if re.search(r"\b(free[ -]?body|force|friction|normal force|weight)\b", lowered):
        return "force"
    if re.search(r"\b(circuit|battery|resistor|electric current)\b", lowered):
        return "circuit"
    if re.search(r"\b(water cycle|evaporation|condensation|precipitation)\b", lowered):
        return "water_cycle"
    if re.search(r"\b(plant cell|chloroplast|central vacuole)\b", lowered):
        return "plant_cell"
    return None


def build_science_diagram(message: object) -> dict | None:
    """Build a reviewed diagram only for an explicit, supported science request."""
    if not isinstance(message, str) or not DIAGRAM_INTENT.search(message):
        return None
    topic = _topic_for_request(message)
    if topic is None:
        return None
    return validate_diagram_spec(TEMPLATES[topic]())
