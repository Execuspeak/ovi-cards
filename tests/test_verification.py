"""Tests for the 15 semantic verification checks."""

import pytest

from ovi_cards import builder, verify_card


class TestUniversalChecks:
    def test_good_result_card_passes_all(self):
        card = builder.result(
            task_id="test-001",
            source_agent="tester:gpt-4",
            objective="Review authentication module for SQL injection vulnerabilities",
            outcome="Found 2 SQL injection vulnerabilities in login handler, both patched with parameterized queries",
            key_facts=[
                "login_handler.py had unsanitized user input on lines 45 and 67",
                "Both queries now use parameterized statements via sqlalchemy",
                "No other injection vectors found in auth module",
            ],
            actions_taken=[
                "Ran bandit static analysis on auth/ directory",
                "Manual review of all SQL query construction paths",
                "Applied parameterized query fix to both locations",
            ],
            next_actions=["Run integration tests to verify login still works"],
            confidence=0.92,
        )
        result = verify_card(card)
        assert result.passed
        assert len(result.hard_failures) == 0

    def test_empty_outcome_fails_hard(self):
        card = builder.result(
            task_id="test-002",
            source_agent="tester:gpt-4",
            objective="Analyze database performance",
            outcome="Done.",
            key_facts=["Query was slow"],
            actions_taken=["Looked at it"],
            confidence=0.8,
        )
        result = verify_card(card)
        assert "outcome_not_empty" in result.hard_failures

    def test_generic_outcome_soft_fail(self):
        card = builder.result(
            task_id="test-003",
            source_agent="tester:gpt-4",
            objective="Review the authentication module thoroughly",
            outcome="Completed successfully",
            key_facts=["Authentication module reviewed"],
            actions_taken=["Reviewed code"],
            confidence=0.8,
        )
        result = verify_card(card)
        assert "outcome_not_generic" in result.soft_failures

    def test_default_confidence_soft_fail(self):
        card = builder.result(
            task_id="test-004",
            source_agent="tester:gpt-4",
            objective="Check for memory leaks in the connection pool",
            outcome="Identified 3 connection objects not being returned to pool after timeout",
            key_facts=["Pool exhaustion after ~200 requests"],
            actions_taken=["Profiled with memory tracker"],
            confidence=0.5,
        )
        result = verify_card(card)
        assert "confidence_not_default" in result.soft_failures


class TestResultChecks:
    def test_result_missing_key_facts(self):
        card = builder.result(
            task_id="test-010",
            source_agent="tester:gpt-4",
            objective="Analyze server response time degradation",
            outcome="Server response p99 increased from 200ms to 1.2s due to unindexed JOIN",
            key_facts=[],
            actions_taken=["Profiled database queries"],
            confidence=0.85,
        )
        result = verify_card(card)
        assert "result_has_key_facts" in result.soft_failures

    def test_result_missing_actions(self):
        card = builder.result(
            task_id="test-011",
            source_agent="tester:gpt-4",
            objective="Investigate API rate limiting behavior",
            outcome="Rate limiter correctly enforces 100 req/min per API key with sliding window",
            key_facts=["Sliding window algorithm working correctly"],
            actions_taken=[],
            confidence=0.9,
        )
        result = verify_card(card)
        assert "result_has_actions" in result.soft_failures


class TestErrorChecks:
    def test_error_card_all_checks_pass(self):
        card = builder.error(
            task_id="test-020",
            source_agent="deployer:gpt-4",
            objective="Deploy v2.1.0 to production cluster",
            outcome="Deployment failed: container health check timeout after 30s on 3/5 pods",
            key_facts=[
                "Health check endpoint /health returning 503 due to missing DB connection",
                "DB connection string env var not set in new deployment config",
            ],
            actions_taken=["Initiated rolling deployment via kubectl"],
            next_actions=[
                "Add DATABASE_URL to production secrets",
                "Re-deploy with corrected config",
            ],
            confidence=0.75,
        )
        result = verify_card(card)
        assert result.passed
        assert len(result.hard_failures) == 0

    def test_error_missing_diagnosis_hard_fail(self):
        card = builder.error(
            task_id="test-021",
            source_agent="deployer:gpt-4",
            objective="Deploy v2.1.0 to production cluster",
            outcome="Deployment failed: unknown error occurred during rollout",
            key_facts=[],
            next_actions=["Retry deployment"],
            confidence=0.3,
        )
        result = verify_card(card)
        assert not result.passed
        assert "error_has_diagnosis" in result.hard_failures

    def test_error_missing_next_actions_hard_fail(self):
        card = builder.error(
            task_id="test-022",
            source_agent="deployer:gpt-4",
            objective="Deploy v2.1.0 to production cluster",
            outcome="Deployment failed: OOM kill on worker nodes",
            key_facts=["Memory limit set to 256MB, app requires 512MB"],
            next_actions=[],
            confidence=0.6,
        )
        result = verify_card(card)
        assert not result.passed
        assert "error_has_next_actions" in result.hard_failures


class TestPlanChecks:
    def test_plan_card_passes(self):
        card = builder.plan(
            task_id="test-030",
            source_agent="architect:gpt-4",
            objective="Design caching strategy for product catalog",
            outcome="Propose a two-tier cache with Redis L1 (TTL 60s) and CDN L2 (TTL 300s)",
            key_facts=["Current p50 latency is 450ms, target is sub-100ms"],
            next_actions=[
                "Implement Redis cache wrapper with TTL config",
                "Add cache invalidation on product update webhook",
                "Set up CDN cache headers for catalog endpoints",
            ],
            confidence=0.7,
        )
        result = verify_card(card)
        assert result.passed

    def test_plan_missing_next_actions(self):
        card = builder.plan(
            task_id="test-031",
            source_agent="architect:gpt-4",
            objective="Design caching strategy for product catalog",
            outcome="Should implement a Redis-based caching layer",
            key_facts=["High latency on catalog queries"],
            next_actions=[],
            confidence=0.6,
        )
        result = verify_card(card)
        assert not result.passed
        assert "plan_has_next_actions" in result.hard_failures


class TestPatchChecks:
    def test_patch_card_passes(self):
        card = builder.patch(
            task_id="test-040",
            source_agent="coder:gpt-4",
            objective="Fix N+1 query in user dashboard endpoint",
            outcome="Replaced 47 individual queries with a single JOIN + prefetch, cutting load time from 2.3s to 180ms",
            artifacts=["src/api/dashboard.py", "src/models/user.py"],
            key_facts=["N+1 detected via django-debug-toolbar"],
            actions_taken=["Added select_related and prefetch_related to queryset"],
            confidence=0.9,
        )
        result = verify_card(card)
        assert result.passed

    def test_patch_missing_actions_hard_fail(self):
        card = builder.patch(
            task_id="test-041",
            source_agent="coder:gpt-4",
            objective="Fix N+1 query in user dashboard endpoint",
            outcome="Fixed the N+1 query issue by optimizing the queryset",
            artifacts=["src/api/dashboard.py"],
            key_facts=["Query was slow"],
            actions_taken=[],
            confidence=0.8,
        )
        result = verify_card(card)
        assert not result.passed
        assert "patch_has_actions" in result.hard_failures


class TestNoteChecks:
    def test_note_card_passes(self):
        card = builder.note(
            task_id="test-050",
            source_agent="monitor:gpt-4",
            objective="Monitor memory usage trend on production cluster",
            outcome="Memory usage has been steadily increasing 2% per day over the past week, currently at 78% of allocated",
            key_facts=[
                "7-day trend shows linear 2%/day increase",
                "Current usage: 78% of 16GB allocated",
            ],
            next_actions=["Investigate if recent deploy introduced a memory leak"],
            confidence=0.8,
        )
        result = verify_card(card)
        assert result.passed

    def test_note_with_actions_soft_fail(self):
        card = builder.result(
            task_id="test-051",
            source_agent="monitor:gpt-4",
            objective="Monitor memory usage trend on production cluster",
            outcome="Memory usage is stable at 45% capacity across all nodes",
            key_facts=["Memory stable"],
            actions_taken=["Checked dashboard"],
            confidence=0.8,
        )
        card.card_type = builder.CardType.NOTE
        result = verify_card(card)
        assert "note_actions_empty" in result.soft_failures


class TestConfidenceAdjustment:
    def test_hard_penalty_applied(self):
        card = builder.error(
            task_id="test-060",
            source_agent="deployer:gpt-4",
            objective="Deploy service to staging",
            outcome="Deployment failed: container crashed on startup",
            key_facts=[],
            next_actions=[],
            confidence=0.9,
        )
        result = verify_card(card)
        assert result.adjusted_confidence < card.confidence
        assert result.confidence_delta < 0

    def test_soft_penalty_applied(self):
        card = builder.result(
            task_id="test-061",
            source_agent="tester:gpt-4",
            objective="Review authentication module for security issues",
            outcome="Completed successfully",
            key_facts=["Module reviewed"],
            actions_taken=["Reviewed code"],
            confidence=0.5,
        )
        result = verify_card(card)
        assert result.adjusted_confidence < card.confidence

    def test_confidence_floors_at_zero(self):
        card = builder.error(
            task_id="test-062",
            source_agent="deployer:gpt-4",
            objective="Deploy service to production",
            outcome="Done.",
            key_facts=[],
            next_actions=[],
            confidence=0.1,
        )
        result = verify_card(card)
        assert result.adjusted_confidence >= 0.0
