"""Tests for JSON Schema + Pydantic validation."""

import pytest

from ovi_cards.validation import validate_card, validate_schema


VALID_CARD = {
    "schema_version": "0.1.0",
    "card_type": "RESULT",
    "task_id": "test-001",
    "source_agent": "tester:gpt-4",
    "timestamp": "2026-03-08T12:00:00Z",
    "objective": "Run the full test suite and report failures",
    "outcome": "All 142 tests passed in 3.2 seconds with no warnings",
    "key_facts": ["142 tests passed", "0 failures", "3.2s runtime"],
    "actions_taken": ["Executed pytest with verbose output"],
    "next_actions": ["Deploy to staging"],
    "artifacts": [],
    "confidence": 0.95,
    "memory_suggestion": {"store": False, "tags": []},
}


class TestValidateSchema:
    def test_valid_card_no_errors(self):
        errors = validate_schema(VALID_CARD)
        assert errors == []

    def test_missing_required_field(self):
        data = {k: v for k, v in VALID_CARD.items() if k != "outcome"}
        errors = validate_schema(data)
        assert len(errors) > 0
        assert any("outcome" in e for e in errors)

    def test_invalid_card_type(self):
        data = {**VALID_CARD, "card_type": "INVALID"}
        errors = validate_schema(data)
        assert len(errors) > 0

    def test_confidence_out_of_range(self):
        data = {**VALID_CARD, "confidence": 2.0}
        errors = validate_schema(data)
        assert len(errors) > 0

    def test_too_many_key_facts(self):
        data = {**VALID_CARD, "key_facts": ["a", "b", "c", "d"]}
        errors = validate_schema(data)
        assert len(errors) > 0

    def test_additional_properties_rejected(self):
        data = {**VALID_CARD, "extra_field": "nope"}
        errors = validate_schema(data)
        assert len(errors) > 0


class TestValidateCard:
    def test_valid_card(self):
        result = validate_card(VALID_CARD)
        assert result.valid
        assert result.card is not None
        assert result.card.task_id == "test-001"

    def test_schema_failure_stops_early(self):
        data = {**VALID_CARD, "card_type": "BOGUS"}
        result = validate_card(data)
        assert not result.valid
        assert len(result.errors) > 0
        assert result.card is None

    def test_pydantic_catches_business_rule(self):
        data = {**VALID_CARD, "card_type": "PATCH", "artifacts": []}
        result = validate_card(data)
        assert not result.valid
        assert any("non-empty" in e or "PATCH" in e or "artifact" in e for e in result.errors)
