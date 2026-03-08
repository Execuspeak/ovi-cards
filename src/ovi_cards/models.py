"""Pydantic models for OVI Cards.

These models define the typed wire format for agent-to-orchestrator
communication. Every field is required, every constraint is enforced,
and every card is self-describing.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_serializer, model_validator


class CardType(str, Enum):
    """Communication intent of the card."""
    RESULT = "RESULT"
    ERROR = "ERROR"
    PLAN = "PLAN"
    PATCH = "PATCH"
    NOTE = "NOTE"


class MemoryTarget(str, Enum):
    """Logical storage tier for the memory system."""
    SOP = "SOP"
    BEST_PRACTICE = "BEST_PRACTICE"
    SHORT_TERM = "SHORT_TERM"
    LONG_TERM = "LONG_TERM"
    KV = "KV"


class MemorySuggestion(BaseModel):
    """Subagent's proposal for whether and where to store this card's content."""
    store: bool
    target: Optional[MemoryTarget] = None
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def target_required_when_store(self):
        if self.store and self.target is None:
            raise ValueError("target is required when store is true")
        return self

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        d = handler(self)
        if d.get("target") is None:
            d.pop("target", None)
        return d


class OVICard(BaseModel):
    """The atomic unit of agent-to-orchestrator communication.

    A bounded, typed, schema-valid packet that replaces raw text dumps
    between subagents and the orchestration layer.
    """
    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    card_type: CardType
    task_id: str = Field(min_length=1)
    source_agent: str = Field(min_length=1)
    timestamp: str
    objective: str = Field(min_length=1, max_length=256)
    outcome: str = Field(min_length=1, max_length=256)
    key_facts: list[str] = Field(default_factory=list, max_length=3)
    actions_taken: list[str] = Field(default_factory=list, max_length=3)
    next_actions: list[str] = Field(default_factory=list, max_length=3)
    artifacts: list[str] = Field(default_factory=list, max_length=10)
    confidence: float = Field(ge=0.0, le=1.0)
    memory_suggestion: MemorySuggestion

    @model_validator(mode="after")
    def patch_requires_artifacts(self):
        if self.card_type == CardType.PATCH and len(self.artifacts) == 0:
            raise ValueError("PATCH cards must have at least one artifact")
        return self


# ---------------------------------------------------------------------------
# Verification result models
# ---------------------------------------------------------------------------

class VerificationCheck(BaseModel):
    check_id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=256)
    severity: str = Field(pattern=r"^(HARD|SOFT)$")


class VerificationContract(BaseModel):
    contract_id: str = Field(min_length=1, max_length=64)
    card_type: str = Field(pattern=r"^(RESULT|ERROR|PLAN|PATCH|NOTE)$")
    task_type: Optional[str] = None
    checks: list[VerificationCheck] = Field(default_factory=list)


class VerificationResult(BaseModel):
    contract_id: str
    passed: bool
    hard_failures: list[str] = Field(default_factory=list)
    soft_failures: list[str] = Field(default_factory=list)
    checks_passed: list[str] = Field(default_factory=list)
    adjusted_confidence: float = Field(ge=0.0, le=1.0)
    confidence_delta: float
    summary: str
