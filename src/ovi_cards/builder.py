"""Ergonomic builder for OVI Cards.

Provides factory methods for each card type with sensible defaults
for metadata fields (schema_version, timestamp, memory_suggestion).
"""

from __future__ import annotations

from datetime import datetime, timezone

from .models import CardType, MemorySuggestion, MemoryTarget, OVICard


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_memory(store: bool = False, target: MemoryTarget | None = None) -> MemorySuggestion:
    return MemorySuggestion(store=store, target=target, tags=[])


def result(
    *,
    task_id: str,
    source_agent: str,
    objective: str,
    outcome: str,
    key_facts: list[str] | None = None,
    actions_taken: list[str] | None = None,
    next_actions: list[str] | None = None,
    artifacts: list[str] | None = None,
    confidence: float = 0.8,
    memory_suggestion: MemorySuggestion | None = None,
    timestamp: str | None = None,
    schema_version: str = "0.1.0",
) -> OVICard:
    """Create a RESULT card — the subagent completed its assigned task."""
    return OVICard(
        schema_version=schema_version,
        card_type=CardType.RESULT,
        task_id=task_id,
        source_agent=source_agent,
        timestamp=timestamp or _now_iso(),
        objective=objective,
        outcome=outcome,
        key_facts=key_facts or [],
        actions_taken=actions_taken or [],
        next_actions=next_actions or [],
        artifacts=artifacts or [],
        confidence=confidence,
        memory_suggestion=memory_suggestion or _default_memory(),
    )


def error(
    *,
    task_id: str,
    source_agent: str,
    objective: str,
    outcome: str,
    key_facts: list[str] | None = None,
    actions_taken: list[str] | None = None,
    next_actions: list[str] | None = None,
    artifacts: list[str] | None = None,
    confidence: float = 0.7,
    memory_suggestion: MemorySuggestion | None = None,
    timestamp: str | None = None,
    schema_version: str = "0.1.0",
) -> OVICard:
    """Create an ERROR card — the subagent failed to complete its task."""
    return OVICard(
        schema_version=schema_version,
        card_type=CardType.ERROR,
        task_id=task_id,
        source_agent=source_agent,
        timestamp=timestamp or _now_iso(),
        objective=objective,
        outcome=outcome,
        key_facts=key_facts or [],
        actions_taken=actions_taken or [],
        next_actions=next_actions or [],
        artifacts=artifacts or [],
        confidence=confidence,
        memory_suggestion=memory_suggestion or _default_memory(store=True, target=MemoryTarget.SOP),
    )


def plan(
    *,
    task_id: str,
    source_agent: str,
    objective: str,
    outcome: str,
    key_facts: list[str] | None = None,
    actions_taken: list[str] | None = None,
    next_actions: list[str] | None = None,
    artifacts: list[str] | None = None,
    confidence: float = 0.6,
    memory_suggestion: MemorySuggestion | None = None,
    timestamp: str | None = None,
    schema_version: str = "0.1.0",
) -> OVICard:
    """Create a PLAN card — proposed approach, not yet executed."""
    return OVICard(
        schema_version=schema_version,
        card_type=CardType.PLAN,
        task_id=task_id,
        source_agent=source_agent,
        timestamp=timestamp or _now_iso(),
        objective=objective,
        outcome=outcome,
        key_facts=key_facts or [],
        actions_taken=actions_taken or [],
        next_actions=next_actions or [],
        artifacts=artifacts or [],
        confidence=confidence,
        memory_suggestion=memory_suggestion or _default_memory(),
    )


def patch(
    *,
    task_id: str,
    source_agent: str,
    objective: str,
    outcome: str,
    artifacts: list[str],
    key_facts: list[str] | None = None,
    actions_taken: list[str] | None = None,
    next_actions: list[str] | None = None,
    confidence: float = 0.85,
    memory_suggestion: MemorySuggestion | None = None,
    timestamp: str | None = None,
    schema_version: str = "0.1.0",
) -> OVICard:
    """Create a PATCH card — a modification was made. Artifacts required."""
    return OVICard(
        schema_version=schema_version,
        card_type=CardType.PATCH,
        task_id=task_id,
        source_agent=source_agent,
        timestamp=timestamp or _now_iso(),
        objective=objective,
        outcome=outcome,
        key_facts=key_facts or [],
        actions_taken=actions_taken or [],
        next_actions=next_actions or [],
        artifacts=artifacts,
        confidence=confidence,
        memory_suggestion=memory_suggestion or _default_memory(
            store=True, target=MemoryTarget.BEST_PRACTICE
        ),
    )


def note(
    *,
    task_id: str,
    source_agent: str,
    objective: str,
    outcome: str,
    key_facts: list[str] | None = None,
    next_actions: list[str] | None = None,
    artifacts: list[str] | None = None,
    confidence: float = 0.7,
    memory_suggestion: MemorySuggestion | None = None,
    timestamp: str | None = None,
    schema_version: str = "0.1.0",
) -> OVICard:
    """Create a NOTE card — observational, no actions taken."""
    return OVICard(
        schema_version=schema_version,
        card_type=CardType.NOTE,
        task_id=task_id,
        source_agent=source_agent,
        timestamp=timestamp or _now_iso(),
        objective=objective,
        outcome=outcome,
        key_facts=key_facts or [],
        actions_taken=[],
        next_actions=next_actions or [],
        artifacts=artifacts or [],
        confidence=confidence,
        memory_suggestion=memory_suggestion or _default_memory(),
    )
