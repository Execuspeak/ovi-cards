"""OVI Cards — Typed wire format for agent-to-orchestrator communication.

A structured protocol that replaces raw text dumps between AI agents
with bounded, schema-validated, semantically verified task cards.
"""

from .models import (
    CardType,
    MemorySuggestion,
    MemoryTarget,
    OVICard,
    VerificationCheck,
    VerificationContract,
    VerificationResult,
)
from .validation import validate_card, validate_schema, ValidationResult
from .verification import verify_card
from . import builder

__all__ = [
    "CardType",
    "MemorySuggestion",
    "MemoryTarget",
    "OVICard",
    "VerificationCheck",
    "VerificationContract",
    "VerificationResult",
    "ValidationResult",
    "validate_card",
    "validate_schema",
    "verify_card",
    "builder",
]

__version__ = "0.1.0"
