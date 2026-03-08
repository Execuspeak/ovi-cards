"""Semantic verification for OVI Cards.

Evaluates cards against "definition of done" contracts — 15 checks
across 5 universal rules and per-card-type requirements. Produces a
VerificationResult with pass/fail, confidence adjustment, and a
human-readable summary of what's missing.

This is the quality gate that sits between card creation and pipeline
ingestion. A card that passes schema validation but fails verification
is structurally valid but semantically weak.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .models import (
    CardType,
    OVICard,
    VerificationCheck,
    VerificationContract,
    VerificationResult,
)

DEFAULT_HARD_PENALTY = 0.25
DEFAULT_SOFT_PENALTY = 0.1

_GENERIC_OUTCOMES = re.compile(
    r"^(completed?\s*successfully|done|task\s*complete[d]?|finished|success|ok|"
    r"no\s*issues?\s*found|everything\s*looks?\s*good)\.?$",
    re.IGNORECASE,
)

_PROPOSITIONAL_LANGUAGE = re.compile(
    r"\b(should|will|plan|propose|recommend|suggest|could|would|intend|approach)\b",
    re.IGNORECASE,
)

_ERROR_LANGUAGE = re.compile(
    r"\b(error|fail|crash|exception|timeout|refused|denied|broken|"
    r"unable|cannot|could\s*not|couldn'?t|did\s*not|didn'?t|missing|"
    r"invalid|corrupt|unreachable|rejected)\b",
    re.IGNORECASE,
)


@dataclass
class CheckResult:
    check_id: str
    passed: bool
    reason: str = ""


def _significant_words(text: str, min_len: int = 4) -> set[str]:
    stop = {
        "that", "this", "with", "from", "have", "been", "were", "they",
        "them", "what", "when", "where", "which", "will", "would", "could",
        "should", "about", "into", "more", "some", "than", "then", "also",
        "just", "very", "each", "make", "made", "like", "over", "such",
        "only", "your", "most", "does",
    }
    return {
        w.lower()
        for w in re.findall(r"[a-zA-Z]+", text)
        if len(w) >= min_len and w.lower() not in stop
    }


# ---------------------------------------------------------------------------
# Individual check implementations
# ---------------------------------------------------------------------------

def _check_outcome_not_empty(card: OVICard) -> CheckResult:
    ok = len(card.outcome.strip()) > 10
    return CheckResult("outcome_not_empty", ok,
                        "" if ok else "Outcome is too short or empty.")


def _check_outcome_not_generic(card: OVICard) -> CheckResult:
    ok = not _GENERIC_OUTCOMES.match(card.outcome.strip())
    return CheckResult("outcome_not_generic", ok,
                        "" if ok else "Outcome appears to be a generic success phrase.")


def _check_objective_outcome_alignment(card: OVICard) -> CheckResult:
    obj_words = _significant_words(card.objective)
    if len(obj_words) < 2:
        return CheckResult("objective_outcome_alignment", True,
                            "Skipped: objective too short for meaningful alignment check.")
    outcome_words = _significant_words(card.outcome)
    kf_words: set[str] = set()
    for kf in card.key_facts:
        kf_words |= _significant_words(kf)
    overlap = obj_words & (outcome_words | kf_words)
    ok = len(overlap) > 0
    return CheckResult("objective_outcome_alignment", ok,
                        "" if ok else "Outcome and key_facts share no significant words with objective.")


def _check_confidence_not_default(card: OVICard) -> CheckResult:
    ok = card.confidence != 0.5
    return CheckResult("confidence_not_default", ok,
                        "" if ok else "Confidence is exactly 0.5 (likely a default value).")


def _check_timestamp_recent(card: OVICard) -> CheckResult:
    import time
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(card.timestamp.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        ok = age_hours < 24
    except Exception:
        ok = True
    return CheckResult("timestamp_recent", ok,
                        "" if ok else "Card timestamp is older than 24 hours.")


def _check_result_has_key_facts(card: OVICard) -> CheckResult:
    ok = len(card.key_facts) > 0
    return CheckResult("result_has_key_facts", ok,
                        "" if ok else "RESULT card has no key_facts.")


def _check_result_has_actions(card: OVICard) -> CheckResult:
    ok = len(card.actions_taken) > 0
    return CheckResult("result_has_actions", ok,
                        "" if ok else "RESULT card has no actions_taken.")


def _check_error_has_diagnosis(card: OVICard) -> CheckResult:
    ok = len(card.key_facts) > 0
    return CheckResult("error_has_diagnosis", ok,
                        "" if ok else "ERROR card has no diagnostic key_facts.")


def _check_error_has_next_actions(card: OVICard) -> CheckResult:
    ok = len(card.next_actions) > 0
    return CheckResult("error_has_next_actions", ok,
                        "" if ok else "ERROR card has no recovery next_actions.")


def _check_error_outcome_describes_failure(card: OVICard) -> CheckResult:
    ok = bool(_ERROR_LANGUAGE.search(card.outcome))
    return CheckResult("error_outcome_describes_failure", ok,
                        "" if ok else "ERROR outcome doesn't use failure language.")


def _check_patch_has_artifacts(card: OVICard) -> CheckResult:
    ok = len(card.artifacts) > 0
    return CheckResult("patch_has_artifacts", ok,
                        "" if ok else "PATCH card has no artifacts.")


def _check_patch_has_actions(card: OVICard) -> CheckResult:
    ok = len(card.actions_taken) > 0
    return CheckResult("patch_has_actions", ok,
                        "" if ok else "PATCH card has no actions_taken.")


def _check_patch_key_facts(card: OVICard) -> CheckResult:
    ok = len(card.key_facts) > 0
    return CheckResult("patch_key_facts_describe_change", ok,
                        "" if ok else "PATCH card has no key_facts describing the change.")


def _check_plan_has_next_actions(card: OVICard) -> CheckResult:
    ok = len(card.next_actions) > 0
    return CheckResult("plan_has_next_actions", ok,
                        "" if ok else "PLAN card has no proposed next_actions.")


def _check_plan_outcome_is_proposal(card: OVICard) -> CheckResult:
    ok = bool(_PROPOSITIONAL_LANGUAGE.search(card.outcome))
    return CheckResult("plan_outcome_is_proposal", ok,
                        "" if ok else "PLAN outcome doesn't use propositional language.")


def _check_note_actions_empty(card: OVICard) -> CheckResult:
    ok = len(card.actions_taken) == 0
    return CheckResult("note_actions_empty", ok,
                        "" if ok else "NOTE card has actions_taken (notes should be observational).")


# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------

_UNIVERSAL_CHECKS: list[tuple[str, str, Callable]] = [
    ("outcome_not_empty", "HARD", _check_outcome_not_empty),
    ("outcome_not_generic", "SOFT", _check_outcome_not_generic),
    ("objective_outcome_alignment", "SOFT", _check_objective_outcome_alignment),
    ("confidence_not_default", "SOFT", _check_confidence_not_default),
    ("timestamp_recent", "SOFT", _check_timestamp_recent),
]

_CARD_TYPE_CHECKS: dict[str, list[tuple[str, str, Callable]]] = {
    "RESULT": [
        ("result_has_key_facts", "SOFT", _check_result_has_key_facts),
        ("result_has_actions", "SOFT", _check_result_has_actions),
    ],
    "ERROR": [
        ("error_has_diagnosis", "HARD", _check_error_has_diagnosis),
        ("error_has_next_actions", "HARD", _check_error_has_next_actions),
        ("error_outcome_describes_failure", "SOFT", _check_error_outcome_describes_failure),
    ],
    "PATCH": [
        ("patch_has_artifacts", "HARD", _check_patch_has_artifacts),
        ("patch_has_actions", "HARD", _check_patch_has_actions),
        ("patch_key_facts_describe_change", "SOFT", _check_patch_key_facts),
    ],
    "PLAN": [
        ("plan_has_next_actions", "HARD", _check_plan_has_next_actions),
        ("plan_outcome_is_proposal", "SOFT", _check_plan_outcome_is_proposal),
    ],
    "NOTE": [
        ("note_actions_empty", "SOFT", _check_note_actions_empty),
    ],
}


# ---------------------------------------------------------------------------
# Default contracts
# ---------------------------------------------------------------------------

def _build_default_contract(card_type: str) -> VerificationContract:
    checks: list[VerificationCheck] = []
    for check_id, severity, _ in _UNIVERSAL_CHECKS:
        checks.append(VerificationCheck(check_id=check_id, description=check_id, severity=severity))
    for check_id, severity, _ in _CARD_TYPE_CHECKS.get(card_type, []):
        checks.append(VerificationCheck(check_id=check_id, description=check_id, severity=severity))
    return VerificationContract(
        contract_id=f"{card_type.lower()}-default",
        card_type=card_type,
        checks=checks,
    )


DEFAULT_CONTRACTS: dict[str, VerificationContract] = {
    ct: _build_default_contract(ct) for ct in ("RESULT", "ERROR", "PLAN", "PATCH", "NOTE")
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_card(
    card: OVICard,
    *,
    hard_penalty: float = DEFAULT_HARD_PENALTY,
    soft_penalty: float = DEFAULT_SOFT_PENALTY,
) -> VerificationResult:
    """Run semantic verification checks against an OVI card.

    Returns a VerificationResult with pass/fail status, confidence
    adjustment, and a human-readable summary.
    """
    contract = DEFAULT_CONTRACTS.get(
        card.card_type.value,
        _build_default_contract(card.card_type.value),
    )

    hard_failures: list[str] = []
    soft_failures: list[str] = []
    checks_passed: list[str] = []
    failure_reasons: list[str] = []

    all_checks = _UNIVERSAL_CHECKS + _CARD_TYPE_CHECKS.get(card.card_type.value, [])
    check_map: dict[str, tuple[str, Callable]] = {
        cid: (sev, fn) for cid, sev, fn in all_checks
    }

    for check in contract.checks:
        entry = check_map.get(check.check_id)
        if entry is None:
            checks_passed.append(check.check_id)
            continue

        _, fn = entry
        result = fn(card)
        if result.passed:
            checks_passed.append(check.check_id)
        elif check.severity == "HARD":
            hard_failures.append(check.check_id)
            if result.reason:
                failure_reasons.append(result.reason)
        else:
            soft_failures.append(check.check_id)
            if result.reason:
                failure_reasons.append(result.reason)

    penalty = (len(hard_failures) * hard_penalty) + (len(soft_failures) * soft_penalty)
    adjusted = max(0.0, min(1.0, card.confidence - penalty))
    delta = adjusted - card.confidence

    passed = len(hard_failures) == 0
    summary = " ".join(failure_reasons) if failure_reasons else "All checks passed."

    return VerificationResult(
        contract_id=contract.contract_id,
        passed=passed,
        hard_failures=hard_failures,
        soft_failures=soft_failures,
        checks_passed=checks_passed,
        adjusted_confidence=round(adjusted, 4),
        confidence_delta=round(delta, 4),
        summary=summary,
    )
