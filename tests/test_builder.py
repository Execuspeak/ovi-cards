"""Tests for the builder factory functions."""

import pytest
from datetime import datetime, timezone

from ovi_cards import builder
from ovi_cards.models import CardType, MemoryTarget


class TestResultBuilder:
    def test_creates_result_card(self):
        card = builder.result(
            task_id="build-001",
            source_agent="coder:gpt-4",
            objective="Implement user registration endpoint",
            outcome="Registration endpoint created with email validation and password hashing",
        )
        assert card.card_type == CardType.RESULT
        assert card.schema_version == "0.1.0"
        assert card.task_id == "build-001"

    def test_auto_fills_timestamp(self):
        card = builder.result(
            task_id="build-002",
            source_agent="coder:gpt-4",
            objective="Add logging middleware",
            outcome="Request logging middleware added with correlation IDs",
        )
        ts = datetime.fromisoformat(card.timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        assert (now - ts).total_seconds() < 5

    def test_custom_timestamp_preserved(self):
        ts = "2026-01-15T10:00:00Z"
        card = builder.result(
            task_id="build-003",
            source_agent="coder:gpt-4",
            objective="Fix database migration",
            outcome="Migration 042 corrected to handle nullable columns",
            timestamp=ts,
        )
        assert card.timestamp == ts

    def test_default_confidence(self):
        card = builder.result(
            task_id="build-004",
            source_agent="coder:gpt-4",
            objective="Add input validation",
            outcome="Added Pydantic validators to all API request models",
        )
        assert card.confidence == 0.8

    def test_default_memory_suggestion(self):
        card = builder.result(
            task_id="build-005",
            source_agent="coder:gpt-4",
            objective="Refactor utils module",
            outcome="Extracted 3 helper functions into separate utility files",
        )
        assert card.memory_suggestion.store is False


class TestErrorBuilder:
    def test_creates_error_card(self):
        card = builder.error(
            task_id="build-010",
            source_agent="deployer:gpt-4",
            objective="Deploy to production",
            outcome="Deployment failed: health check timeout",
            key_facts=["Pod crashed due to missing env var"],
            next_actions=["Add missing DATABASE_URL secret"],
        )
        assert card.card_type == CardType.ERROR

    def test_error_defaults_to_store(self):
        card = builder.error(
            task_id="build-011",
            source_agent="deployer:gpt-4",
            objective="Run database migration",
            outcome="Migration failed: column already exists",
            key_facts=["Duplicate migration detected"],
            next_actions=["Remove duplicate migration file"],
        )
        assert card.memory_suggestion.store is True
        assert card.memory_suggestion.target == MemoryTarget.SOP


class TestPlanBuilder:
    def test_creates_plan_card(self):
        card = builder.plan(
            task_id="build-020",
            source_agent="architect:gpt-4",
            objective="Design notification system",
            outcome="Propose event-driven architecture with SNS/SQS for decoupled notification delivery",
            next_actions=[
                "Set up SNS topic for notification events",
                "Create SQS queues for email, SMS, push channels",
            ],
        )
        assert card.card_type == CardType.PLAN
        assert card.confidence == 0.6


class TestPatchBuilder:
    def test_creates_patch_card(self):
        card = builder.patch(
            task_id="build-030",
            source_agent="coder:gpt-4",
            objective="Fix XSS vulnerability in comment renderer",
            outcome="Escaped all user-generated HTML content in comment display component",
            artifacts=["src/components/Comment.tsx"],
            actions_taken=["Added DOMPurify sanitization to comment body rendering"],
        )
        assert card.card_type == CardType.PATCH

    def test_patch_requires_artifacts_arg(self):
        with pytest.raises(TypeError):
            builder.patch(
                task_id="build-031",
                source_agent="coder:gpt-4",
                objective="Fix bug",
                outcome="Fixed the bug in the thing",
            )

    def test_patch_defaults_to_store_best_practice(self):
        card = builder.patch(
            task_id="build-032",
            source_agent="coder:gpt-4",
            objective="Optimize database query",
            outcome="Added composite index reducing query time from 2s to 50ms",
            artifacts=["migrations/043_add_composite_index.sql"],
            actions_taken=["Created composite index on (user_id, created_at)"],
        )
        assert card.memory_suggestion.store is True
        assert card.memory_suggestion.target == MemoryTarget.BEST_PRACTICE


class TestNoteBuilder:
    def test_creates_note_card(self):
        card = builder.note(
            task_id="build-040",
            source_agent="monitor:gpt-4",
            objective="Check system health",
            outcome="All services healthy, CPU at 23%, memory at 45%",
        )
        assert card.card_type == CardType.NOTE
        assert card.actions_taken == []

    def test_note_always_has_empty_actions(self):
        card = builder.note(
            task_id="build-041",
            source_agent="monitor:gpt-4",
            objective="Review error rates",
            outcome="Error rate at 0.02% which is within normal bounds",
            key_facts=["0.02% error rate", "99.98% success rate"],
        )
        assert card.actions_taken == []
