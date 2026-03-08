"""Basic usage of the ovi-cards library.

Demonstrates creating, validating, and verifying an OVI card
through the full pipeline.
"""

from ovi_cards import builder, validate_card, verify_card
import json


def main():
    # 1. Create a RESULT card using the builder
    card = builder.result(
        task_id="code-review-42",
        source_agent="reviewer:gpt-4",
        objective="Review authentication module for SQL injection vulnerabilities",
        outcome="Found 2 SQL injection vulnerabilities in login handler, both patched with parameterized queries",
        key_facts=[
            "login_handler.py had unsanitized user input on lines 45, 67",
            "Both queries now use parameterized statements",
            "No other injection vectors found in auth module",
        ],
        actions_taken=[
            "Static analysis with bandit on auth/ directory",
            "Manual review of all SQL query construction",
            "Applied parameterized query fix to both locations",
        ],
        next_actions=[
            "Run integration tests to verify login still works",
        ],
        artifacts=["auth/login_handler.py"],
        confidence=0.92,
    )

    print("=== Created Card ===")
    print(json.dumps(card.model_dump(mode="json"), indent=2))
    print()

    # 2. Validate the card (schema + model)
    result = validate_card(card.model_dump(mode="json"))
    print(f"=== Validation: {'PASS' if result.valid else 'FAIL'} ===")
    if not result.valid:
        for err in result.errors:
            print(f"  - {err}")
    print()

    # 3. Run semantic verification (15 checks)
    verification = verify_card(card)
    print(f"=== Verification: {'PASS' if verification.passed else 'FAIL'} ===")
    print(f"  Checks passed: {len(verification.checks_passed)}")
    print(f"  Hard failures: {verification.hard_failures}")
    print(f"  Soft failures: {verification.soft_failures}")
    print(f"  Confidence: {card.confidence} -> {verification.adjusted_confidence} ({verification.confidence_delta:+.4f})")
    print(f"  Summary: {verification.summary}")
    print()

    # 4. Create an ERROR card with deliberately weak content
    weak_card = builder.error(
        task_id="deploy-99",
        source_agent="deployer:gpt-4",
        objective="Deploy v2.1.0 to production",
        outcome="Done.",
        key_facts=[],
        next_actions=[],
        confidence=0.5,
    )

    print("=== Weak ERROR Card ===")
    weak_verification = verify_card(weak_card)
    print(f"  Verification: {'PASS' if weak_verification.passed else 'FAIL'}")
    print(f"  Hard failures: {weak_verification.hard_failures}")
    print(f"  Soft failures: {weak_verification.soft_failures}")
    print(f"  Confidence: 0.5 -> {weak_verification.adjusted_confidence}")
    print(f"  Summary: {weak_verification.summary}")


if __name__ == "__main__":
    main()
