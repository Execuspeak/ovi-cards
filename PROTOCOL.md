# OVI Card Protocol Specification

**Version 0.1.0**

## 1. Overview

An OVI (Orchestration Vector Interface) card is the atomic unit of communication between a subagent and an orchestration layer. It replaces unbounded text output with a fixed-size, typed, schema-validated packet.

Every card answers five questions:
1. What was the objective?
2. What happened?
3. What are the key facts?
4. What should happen next?
5. How confident is the agent?

## 2. Card Types

| Type | Semantics |
|------|-----------|
| `RESULT` | The subagent completed its assigned task. |
| `ERROR` | The subagent failed to complete its task. |
| `PLAN` | The subagent proposes an approach but has not executed it. |
| `PATCH` | The subagent made a modification to an existing artifact. |
| `NOTE` | The subagent observed something worth recording but took no action. |

## 3. Field Specifications

### 3.1 Metadata Fields

| Field | Type | Constraint | Description |
|-------|------|-----------|-------------|
| `schema_version` | string | semver (`^\d+\.\d+\.\d+$`) | Protocol version this card conforms to. |
| `card_type` | enum | RESULT, ERROR, PLAN, PATCH, NOTE | Communication intent. |
| `task_id` | string | non-empty | Identifier linking this card to a task assignment. |
| `source_agent` | string | non-empty | Identifier of the producing agent (`{type}:{model}`). |
| `timestamp` | string | ISO 8601 datetime | When the card was produced. |

### 3.2 Content Fields

| Field | Type | Constraint | Description |
|-------|------|-----------|-------------|
| `objective` | string | 1-256 chars | What the agent was asked to do. |
| `outcome` | string | 1-256 chars | What actually happened. |
| `key_facts` | string[] | 0-3 items, each 1-256 chars | Most important facts from execution. |
| `actions_taken` | string[] | 0-3 items, each 1-256 chars | Concrete actions the agent performed. |
| `next_actions` | string[] | 0-3 items, each 1-256 chars | Recommended follow-up actions. |
| `artifacts` | string[] | 0-10 items | References to files, URLs, or resources. |

### 3.3 Quality Fields

| Field | Type | Constraint | Description |
|-------|------|-----------|-------------|
| `confidence` | float | 0.0-1.0 | Agent's self-assessed confidence in the outcome. |
| `memory_suggestion` | object | see below | Routing hint for downstream memory systems. |

### 3.4 Memory Suggestion

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `store` | boolean | always | Whether this card's content should be persisted. |
| `target` | enum | when store=true | SOP, BEST_PRACTICE, SHORT_TERM, LONG_TERM, KV |
| `tags` | string[] | always | Lowercase kebab-case routing tags. |

## 4. Constraints

The bounded structure is the core design constraint. These limits are intentional:

- **3 items max** for key_facts, actions_taken, and next_actions forces the agent to prioritize.
- **256 chars max** per string prevents unbounded prose in individual fields.
- **10 artifacts max** keeps file references manageable.
- **Confidence 0.0-1.0** gives the orchestrator a numeric signal to route on (retry at < 0.5, accept at > 0.8, etc.).

A well-formed card should be 150-400 tokens. This is the fixed cost the orchestrator budgets per subagent output.

## 5. Card-Type Contracts

Each card type has specific semantic requirements enforced by the verification engine.

### RESULT
- MUST have at least one `key_fact`.
- SHOULD have at least one `actions_taken`.
- `outcome` MUST describe what was accomplished, not just "done."

### ERROR
- MUST have at least one `key_fact` (the diagnosis).
- MUST have at least one `next_action` (the recovery plan).
- `outcome` MUST use failure language (error, failed, unable, etc.).

### PLAN
- MUST have at least one `next_action` (what's proposed).
- `outcome` SHOULD use propositional language (should, will, propose, recommend).

### PATCH
- MUST have at least one `artifact` (what was modified).
- MUST have at least one `actions_taken` (what was done).
- SHOULD have at least one `key_fact` describing the nature of the change.

### NOTE
- SHOULD NOT have `actions_taken` (notes are observational, not active).

## 6. Verification Checks

The verification engine runs 15 checks organized into two severity levels:

**HARD failures** — the card is rejected. The orchestrator should not route on it.
**SOFT failures** — the card is accepted with reduced confidence.

### Universal Checks (all types)

| Check | Severity | Rule |
|-------|----------|------|
| `outcome_not_empty` | HARD | Outcome must be > 10 characters. |
| `outcome_not_generic` | SOFT | Rejects generic phrases ("completed successfully", "done", etc.). |
| `objective_outcome_alignment` | SOFT | Outcome must share significant words with objective. |
| `confidence_not_default` | SOFT | Confidence must not be exactly 0.5 (likely unset). |
| `timestamp_recent` | SOFT | Timestamp should be within 24 hours. |

### Type-Specific Checks

Documented in detail per card type in Section 5.

### Confidence Adjustment

Each failed check adjusts confidence downward:
- HARD failure: -0.25
- SOFT failure: -0.10

Adjusted confidence is clamped to [0.0, 1.0].

## 7. Tiered Access Pattern

OVI cards implement a two-tier information architecture:

- **Tier 1 (the card)**: Bounded summary for orchestrator routing and comprehension. This is what stays in the context window.
- **Tier 2 (external storage)**: Full raw output, logs, diffs, and detailed analysis. Referenced via `artifacts` field. Retrieved on demand for user drill-down or audit.

The orchestrator operates on Tier 1. Users access Tier 2 when they want detail.

## 8. Worked Example

### Input: Raw subagent output (~1,200 tokens of verbose analysis)

### Output: OVI RESULT card

```json
{
  "schema_version": "0.1.0",
  "card_type": "RESULT",
  "task_id": "code-review-42",
  "source_agent": "reviewer:gpt-4",
  "timestamp": "2026-03-08T12:00:00Z",
  "objective": "Review authentication module for SQL injection vulnerabilities",
  "outcome": "Found 2 SQL injection vulnerabilities in login handler, both patched with parameterized queries",
  "key_facts": [
    "login_handler.py had unsanitized user input on lines 45 and 67",
    "Both queries now use parameterized statements via sqlalchemy",
    "No other injection vectors found in auth module"
  ],
  "actions_taken": [
    "Ran bandit static analysis on auth/ directory",
    "Manual review of all SQL query construction paths",
    "Applied parameterized query fix to both locations"
  ],
  "next_actions": [
    "Run integration tests to verify login still works",
    "Schedule broader codebase scan for similar patterns"
  ],
  "artifacts": ["auth/login_handler.py"],
  "confidence": 0.92,
  "memory_suggestion": {
    "store": true,
    "target": "BEST_PRACTICE",
    "tags": ["security", "sql-injection"]
  }
}
```

This card is ~244 tokens. The orchestrator knows: the task succeeded, what was found, what was fixed, what should happen next, and how confident the agent is. That's enough to route. The full 1,200-token analysis is available via the artifact reference if anyone needs it.
