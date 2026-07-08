"""Tests for OVI card lifecycle FSM."""

import pytest

from ovi_cards.card_lifecycle import (
    CardLifecycleEvent,
    CardLifecycleManager,
    CardLifecycleState,
    create_card_lifecycle,
    transition_card_lifecycle,
)
from ovi_cards.models import CardType, MemorySuggestion, OVICard


def _sample_card(**overrides) -> OVICard:
    base = dict(
        schema_version="1.0.0",
        card_type=CardType.RESULT,
        task_id="task-001",
        source_agent="test-agent",
        timestamp="2026-06-08T00:00:00Z",
        objective="Analyze customer churn data",
        outcome="Identified three primary churn drivers from Q1 cohort analysis.",
        key_facts=["Driver A: pricing", "Driver B: support latency"],
        actions_taken=["Loaded dataset", "Ran regression"],
        next_actions=["Share report"],
        artifacts=[],
        confidence=0.82,
        memory_suggestion=MemorySuggestion(store=False, tags=[]),
    )
    base.update(overrides)
    return OVICard(**base)


class TestCardLifecycleTransitions:
    def test_happy_path_draft_to_archived(self):
        card = _sample_card()
        mgr = CardLifecycleManager(card)
        assert mgr.state == CardLifecycleState.DRAFT

        mgr.on_verification(True, "all checks passed")
        assert mgr.state == CardLifecycleState.VERIFIED

        mgr.on_route_to_decide(card)
        assert mgr.state == CardLifecycleState.ROUTED

        mgr.on_accepted()
        assert mgr.state == CardLifecycleState.ARCHIVED

    def test_verification_failure_rejects(self):
        card = _sample_card()
        mgr = CardLifecycleManager(card)
        mgr.on_verification(False, "outcome too generic")
        assert mgr.state == CardLifecycleState.REJECTED

    def test_schema_invalid_from_draft(self):
        record = create_card_lifecycle(_sample_card())
        transition_card_lifecycle(
            record, CardLifecycleEvent.SCHEMA_INVALID, "missing objective",
        )
        assert record.state == CardLifecycleState.REJECTED

    def test_invalid_transition_raises(self):
        record = create_card_lifecycle(_sample_card())
        transition_card_lifecycle(record, CardLifecycleEvent.VERIFICATION_FAILED)
        with pytest.raises(ValueError, match="Invalid card lifecycle"):
            transition_card_lifecycle(record, CardLifecycleEvent.ROUTED_TO_DECIDE)

    def test_immutability_violation_on_route(self):
        card = _sample_card()
        mgr = CardLifecycleManager(card)
        mgr.on_verification(True)
        mutated = _sample_card(objective="Changed objective after verify")
        mgr.on_route_to_decide(mutated)
        assert mgr.state == CardLifecycleState.REJECTED

    def test_in_place_mutation_violation_on_route(self):
        # The realistic agent-loop pattern: hold one card, mutate it in place,
        # and re-submit. The snapshot must be a copy or this slips through.
        card = _sample_card()
        mgr = CardLifecycleManager(card)
        mgr.on_verification(True)
        card.objective = "Changed objective in place after verify"
        mgr.on_route_to_decide(card)
        assert mgr.state == CardLifecycleState.REJECTED

    def test_transition_history_recorded(self):
        card = _sample_card()
        mgr = CardLifecycleManager(card)
        mgr.on_verification(True)
        mgr.on_route_to_decide(card)
        mgr.on_accepted()
        assert len(mgr.record.transitions) >= 4
