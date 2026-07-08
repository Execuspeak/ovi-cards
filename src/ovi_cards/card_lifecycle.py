"""OVI Card lifecycle FSM — DRAFT → VERIFIED → ROUTED → ARCHIVED (+ REJECTED).

Mirrors Friday Runtime src/core/CardLifecycle.ts for cross-language parity.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .models import OVICard


class CardLifecycleState(str, Enum):
    DRAFT = "DRAFT"
    VERIFIED = "VERIFIED"
    ROUTED = "ROUTED"
    ARCHIVED = "ARCHIVED"
    REJECTED = "REJECTED"


class CardLifecycleEvent(str, Enum):
    CREATED = "created"
    SCHEMA_INVALID = "schema_invalid"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"
    ROUTED_TO_DECIDE = "routed_to_decide"
    ACCEPTED = "accepted"
    EXPLICIT_REJECT = "explicit_reject"


CARD_LIFECYCLE_TRANSITIONS: dict[
    CardLifecycleState, dict[CardLifecycleEvent, CardLifecycleState]
] = {
    CardLifecycleState.DRAFT: {
        CardLifecycleEvent.VERIFICATION_PASSED: CardLifecycleState.VERIFIED,
        CardLifecycleEvent.VERIFICATION_FAILED: CardLifecycleState.REJECTED,
        CardLifecycleEvent.SCHEMA_INVALID: CardLifecycleState.REJECTED,
        CardLifecycleEvent.EXPLICIT_REJECT: CardLifecycleState.REJECTED,
    },
    CardLifecycleState.VERIFIED: {
        CardLifecycleEvent.ROUTED_TO_DECIDE: CardLifecycleState.ROUTED,
        CardLifecycleEvent.EXPLICIT_REJECT: CardLifecycleState.REJECTED,
    },
    CardLifecycleState.ROUTED: {
        CardLifecycleEvent.ACCEPTED: CardLifecycleState.ARCHIVED,
        CardLifecycleEvent.EXPLICIT_REJECT: CardLifecycleState.REJECTED,
    },
    CardLifecycleState.ARCHIVED: {},
    CardLifecycleState.REJECTED: {},
}

IMMUTABLE_AFTER_VERIFIED = frozenset({
    "schema_version", "card_type", "task_id", "source_agent", "objective",
})

IMMUTABLE_AFTER_ROUTED = IMMUTABLE_AFTER_VERIFIED | frozenset({
    "outcome", "key_facts", "actions_taken",
})


@dataclass
class LifecycleTransition:
    from_state: CardLifecycleState
    to_state: CardLifecycleState
    event: CardLifecycleEvent
    at: str
    reason: str = ""


@dataclass
class CardLifecycleRecord:
    state: CardLifecycleState
    task_id: str
    transitions: list[LifecycleTransition] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_card_lifecycle(card: OVICard) -> CardLifecycleRecord:
    record = CardLifecycleRecord(
        state=CardLifecycleState.DRAFT,
        task_id=card.task_id,
    )
    record.transitions.append(
        LifecycleTransition(
            from_state=CardLifecycleState.DRAFT,
            to_state=CardLifecycleState.DRAFT,
            event=CardLifecycleEvent.CREATED,
            at=_now_iso(),
        )
    )
    return record


def transition_card_lifecycle(
    record: CardLifecycleRecord,
    event: CardLifecycleEvent,
    reason: str = "",
) -> CardLifecycleRecord:
    mapping = CARD_LIFECYCLE_TRANSITIONS.get(record.state, {})
    next_state = mapping.get(event)
    if next_state is None:
        raise ValueError(f"Invalid card lifecycle transition: {record.state} + {event}")

    record.transitions.append(
        LifecycleTransition(
            from_state=record.state,
            to_state=next_state,
            event=event,
            at=_now_iso(),
            reason=reason,
        )
    )
    record.state = next_state
    return record


def _card_field(card: OVICard, key: str) -> Any:
    if hasattr(card, key):
        return getattr(card, key)
    if isinstance(card, dict):
        return card.get(key)
    return None


def assert_card_immutability(
    before: OVICard,
    after: OVICard,
    state: CardLifecycleState,
) -> list[str]:
    if state in (CardLifecycleState.ROUTED, CardLifecycleState.ARCHIVED):
        keys = IMMUTABLE_AFTER_ROUTED
    elif state in (CardLifecycleState.VERIFIED,):
        keys = IMMUTABLE_AFTER_VERIFIED
    else:
        return []

    violations: list[str] = []
    for key in keys:
        if _card_field(before, key) != _card_field(after, key):
            violations.append(f"Field '{key}' mutated after {state.value}")
    return violations


class CardLifecycleManager:
    """Tracks a single card through the lifecycle FSM."""

    def __init__(self, card: OVICard) -> None:
        # Deep-copy so the snapshot is immune to in-place mutation of the caller's
        # card. Storing the reference made the immutability gate a no-op whenever
        # the same OVICard instance was mutated and re-submitted (the common
        # agent-loop pattern).
        self._snapshot = self._freeze(card)
        self.record = create_card_lifecycle(card)

    @staticmethod
    def _freeze(card: OVICard) -> OVICard:
        if hasattr(card, "model_copy"):
            return card.model_copy(deep=True)
        if isinstance(card, dict):
            return copy.deepcopy(card)
        return copy.deepcopy(card)

    @property
    def state(self) -> CardLifecycleState:
        return self.record.state

    def on_schema_invalid(self, reason: str) -> CardLifecycleRecord:
        return transition_card_lifecycle(
            self.record, CardLifecycleEvent.SCHEMA_INVALID, reason,
        )

    def on_verification(self, passed: bool, reason: str = "") -> CardLifecycleRecord:
        event = (
            CardLifecycleEvent.VERIFICATION_PASSED
            if passed
            else CardLifecycleEvent.VERIFICATION_FAILED
        )
        return transition_card_lifecycle(self.record, event, reason)

    def on_route_to_decide(self, card: OVICard) -> CardLifecycleRecord:
        violations = assert_card_immutability(
            self._snapshot, card, CardLifecycleState.VERIFIED,
        )
        if violations:
            return transition_card_lifecycle(
                self.record,
                CardLifecycleEvent.EXPLICIT_REJECT,
                "; ".join(violations),
            )
        return transition_card_lifecycle(
            self.record, CardLifecycleEvent.ROUTED_TO_DECIDE,
        )

    def on_accepted(self) -> CardLifecycleRecord:
        return transition_card_lifecycle(
            self.record, CardLifecycleEvent.ACCEPTED,
        )
