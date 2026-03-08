"""Tests for OVI Card Pydantic models."""

import pytest
from pydantic import ValidationError

from ovi_cards.models import (
    CardType,
    MemorySuggestion,
    MemoryTarget,
    OVICard,
)


VALID_CARD_DATA = {
    "schema_version": "0.1.0",
    "card_type": "RESULT",
    "task_id": "code-review-42",
    "source_agent": "reviewer:gpt-4",
    "timestamp": "2026-03-08T12:00:00Z",
    "objective": "Review the authentication module for security issues",
    "outcome": "Found 2 SQL injection vulnerabilities in login handler, both patched",
    "key_facts": [
        "login_handler.py had unsanitized user input on lines 45, 67",
        "Both queries now use parameterized statements",
        "No other injection vectors found in auth module",
    ],
    "actions_taken": [
        "Static analysis with bandit on auth/ directory",
        "Manual review of all SQL query construction",
        "Applied parameterized query fix to both locations",
    ],
    "next_actions": [
        "Run integration tests to verify login still works",
        "Schedule broader codebase scan for similar patterns",
    ],
    "artifacts": ["auth/login_handler.py"],
    "confidence": 0.92,
    "memory_suggestion": {
        "store": True,
        "target": "BEST_PRACTICE",
        "tags": ["security", "sql-injection"],
    },
}


class TestCardType:
    def test_all_types_exist(self):
        assert set(CardType) == {
            CardType.RESULT, CardType.ERROR, CardType.PLAN,
            CardType.PATCH, CardType.NOTE,
        }

    def test_string_coercion(self):
        assert CardType("RESULT") == CardType.RESULT


class TestMemorySuggestion:
    def test_store_false_no_target(self):
        ms = MemorySuggestion(store=False, tags=[])
        assert ms.target is None

    def test_store_true_requires_target(self):
        with pytest.raises(ValidationError, match="target is required"):
            MemorySuggestion(store=True, tags=["test"])

    def test_store_true_with_target(self):
        ms = MemorySuggestion(store=True, target=MemoryTarget.SOP, tags=["ops"])
        assert ms.target == MemoryTarget.SOP


class TestOVICard:
    def test_valid_result_card(self):
        card = OVICard.model_validate(VALID_CARD_DATA)
        assert card.card_type == CardType.RESULT
        assert card.confidence == 0.92
        assert len(card.key_facts) == 3

    def test_empty_objective_rejected(self):
        data = {**VALID_CARD_DATA, "objective": ""}
        with pytest.raises(ValidationError):
            OVICard.model_validate(data)

    def test_objective_max_length(self):
        data = {**VALID_CARD_DATA, "objective": "x" * 257}
        with pytest.raises(ValidationError):
            OVICard.model_validate(data)

    def test_confidence_bounds(self):
        data = {**VALID_CARD_DATA, "confidence": 1.5}
        with pytest.raises(ValidationError):
            OVICard.model_validate(data)

        data = {**VALID_CARD_DATA, "confidence": -0.1}
        with pytest.raises(ValidationError):
            OVICard.model_validate(data)

    def test_patch_requires_artifacts(self):
        data = {
            **VALID_CARD_DATA,
            "card_type": "PATCH",
            "artifacts": [],
        }
        with pytest.raises(ValidationError, match="PATCH cards must have at least one artifact"):
            OVICard.model_validate(data)

    def test_patch_with_artifacts_passes(self):
        data = {
            **VALID_CARD_DATA,
            "card_type": "PATCH",
            "artifacts": ["src/main.py"],
        }
        card = OVICard.model_validate(data)
        assert card.card_type == CardType.PATCH

    def test_bad_schema_version_format(self):
        data = {**VALID_CARD_DATA, "schema_version": "v1"}
        with pytest.raises(ValidationError):
            OVICard.model_validate(data)

    def test_serialization_roundtrip(self):
        card = OVICard.model_validate(VALID_CARD_DATA)
        data = card.model_dump()
        card2 = OVICard.model_validate(data)
        assert card == card2
