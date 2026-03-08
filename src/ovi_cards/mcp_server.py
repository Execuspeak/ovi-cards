"""MCP server exposing OVI Card tools.

Three tools:
  - create_card: Build a validated OVI card from parameters
  - validate_card: Check raw JSON against schema + model rules
  - verify_card: Run 15 semantic checks against a valid card

Run with: python -m ovi_cards.mcp_server
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from . import builder
from .models import CardType, MemorySuggestion, MemoryTarget
from .validation import validate_card as _validate_card
from .verification import verify_card as _verify_card

mcp = FastMCP(
    "ovi-cards",
    instructions="Typed wire format for agent-to-orchestrator communication. "
    "Use create_card to build cards, validate_card to check schema conformance, "
    "and verify_card to run semantic quality checks.",
)


@mcp.tool()
def create_card(
    card_type: str,
    task_id: str,
    source_agent: str,
    objective: str,
    outcome: str,
    key_facts: list[str] | None = None,
    actions_taken: list[str] | None = None,
    next_actions: list[str] | None = None,
    artifacts: list[str] | None = None,
    confidence: float = 0.8,
    store_memory: bool = False,
    memory_target: str | None = None,
    memory_tags: list[str] | None = None,
) -> dict[str, Any]:
    """Create a validated OVI card.

    card_type: RESULT, ERROR, PLAN, PATCH, or NOTE
    """
    mem_target = MemoryTarget(memory_target) if memory_target else None
    mem = MemorySuggestion(
        store=store_memory,
        target=mem_target,
        tags=memory_tags or [],
    )

    factory = {
        "RESULT": builder.result,
        "ERROR": builder.error,
        "PLAN": builder.plan,
        "PATCH": builder.patch,
        "NOTE": builder.note,
    }

    ct = card_type.upper()
    if ct not in factory:
        return {"error": f"Unknown card_type: {card_type}. Must be one of: {', '.join(factory)}"}

    kwargs: dict[str, Any] = {
        "task_id": task_id,
        "source_agent": source_agent,
        "objective": objective,
        "outcome": outcome,
        "key_facts": key_facts,
        "next_actions": next_actions,
        "confidence": confidence,
        "memory_suggestion": mem,
    }

    if ct == "NOTE":
        pass
    else:
        kwargs["actions_taken"] = actions_taken

    if ct == "PATCH":
        kwargs["artifacts"] = artifacts or []
    else:
        kwargs["artifacts"] = artifacts

    try:
        card = factory[ct](**kwargs)
        return card.model_dump(mode="json")
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def validate_card(card_json: dict[str, Any]) -> dict[str, Any]:
    """Validate raw JSON against the OVI Card schema and model rules.

    Returns {valid: true, card: {...}} or {valid: false, errors: [...]}.
    """
    result = _validate_card(card_json)
    if result.valid:
        return {"valid": True, "card": result.card.model_dump(mode="json")}
    return {"valid": False, "errors": result.errors}


@mcp.tool()
def verify_card(card_json: dict[str, Any]) -> dict[str, Any]:
    """Run 15 semantic verification checks against a valid OVI card.

    Returns pass/fail status, failed checks, adjusted confidence, and summary.
    """
    vr = _validate_card(card_json)
    if not vr.valid:
        return {"error": "Card failed validation", "validation_errors": vr.errors}

    result = _verify_card(vr.card)
    return result.model_dump(mode="json")


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
