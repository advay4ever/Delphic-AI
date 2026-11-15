"""Safe, local science diagram support for Delphic AI."""

from .diagram_spec import DiagramValidationError, validate_diagram_spec
from .diagram_templates import build_science_diagram

__all__ = [
    "DiagramValidationError",
    "build_science_diagram",
    "validate_diagram_spec",
]
