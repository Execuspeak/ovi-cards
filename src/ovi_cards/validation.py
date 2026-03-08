"""Schema and structural validation for OVI Cards.

Provides two layers of validation:
1. JSON Schema validation (structural conformance)
2. Pydantic model validation (type safety + business rules)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any

import jsonschema

from .models import OVICard

_SCHEMA_CACHE: dict | None = None


def _load_schema() -> dict:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        schema_path = files("ovi_cards").joinpath("schema.json")
        _SCHEMA_CACHE = json.loads(schema_path.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE


@dataclass
class ValidationResult:
    """Result of validating an OVI card."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    card: OVICard | None = None


def validate_schema(data: dict[str, Any]) -> list[str]:
    """Validate raw data against the OVI Card JSON Schema.

    Returns a list of error messages (empty if valid).
    """
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    return [e.message for e in validator.iter_errors(data)]


def validate_card(data: dict[str, Any]) -> ValidationResult:
    """Full validation: JSON Schema + Pydantic model construction.

    Returns a ValidationResult with the constructed OVICard if valid.
    """
    errors: list[str] = []

    schema_errors = validate_schema(data)
    if schema_errors:
        return ValidationResult(valid=False, errors=schema_errors)

    try:
        card = OVICard.model_validate(data)
    except Exception as exc:
        return ValidationResult(valid=False, errors=[str(exc)])

    return ValidationResult(valid=True, card=card)
