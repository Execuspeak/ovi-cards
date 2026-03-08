# OVI Cards

**A typed wire format for agent-to-orchestrator communication.**

OVI (Orchestration Vector Interface) cards are fixed-size, schema-validated packets that replace raw text dumps between AI subagents and orchestration layers. Think of it as TCP/IP for multi-agent systems: instead of passing unbounded prose between agents, every output is packetized into a deterministic structure the orchestrator can route on, verify, and store — without parsing free-form text.

## The Problem

In a multi-agent system, subagents produce verbose, unstructured text. The orchestrator needs to:

1. Understand what happened (did the task succeed?)
2. Route the result (store it? retry? escalate?)
3. Report to the user (what are the key facts?)
4. Maintain context (without blowing the context window)

Raw text dumps fail at all four. The orchestrator either truncates (losing information) or accumulates (blowing the context budget). There's no typed structure to route on and no quality signal to trust.

## The Solution

Every subagent output becomes an OVI card: a bounded packet with typed fields.

```python
from ovi_cards import builder, verify_card

card = builder.result(
    task_id="code-review-42",
    source_agent="reviewer:gpt-4",
    objective="Review auth module for SQL injection vulnerabilities",
    outcome="Found 2 SQL injection vulns in login handler, both patched",
    key_facts=[
        "login_handler.py had unsanitized input on lines 45, 67",
        "Both queries now use parameterized statements",
        "No other injection vectors found in auth module",
    ],
    actions_taken=[
        "Static analysis with bandit on auth/ directory",
        "Manual review of all SQL query construction",
        "Applied parameterized query fix to both locations",
    ],
    next_actions=["Run integration tests to verify login still works"],
    artifacts=["auth/login_handler.py"],
    confidence=0.92,
)

# 15 semantic checks — is this card actually useful?
result = verify_card(card)
print(result.passed)              # True
print(result.adjusted_confidence) # 0.92
```

## What's In The Box

- **5 card types**: `RESULT`, `ERROR`, `PLAN`, `PATCH`, `NOTE` — covers the full lifecycle of a subagent task
- **JSON Schema validation** — structural conformance enforced at the wire level
- **Pydantic models** — type-safe Python objects with business rule validation
- **15 semantic verification checks** — "definition of done" quality gates (5 universal + per-card-type contracts)
- **Builder functions** — ergonomic card construction with sensible defaults
- **MCP server** — plug directly into Cursor, Claude Desktop, or any MCP client

## Install

```bash
pip install ovi-cards
```

For MCP server support:

```bash
pip install ovi-cards[mcp]
```

## Card Types

| Type | Intent | Required Signals |
|------|--------|-----------------|
| `RESULT` | Task completed | key_facts, actions_taken |
| `ERROR` | Task failed | diagnosis (key_facts), recovery plan (next_actions) |
| `PLAN` | Proposed approach | next_actions with propositional language |
| `PATCH` | Modification made | artifacts (what changed), actions_taken |
| `NOTE` | Observation only | No actions_taken (purely informational) |

## Verification Engine

Every card passes through 15 semantic checks organized as HARD (must pass) and SOFT (penalize confidence) failures:

**Universal checks (all card types):**
- `outcome_not_empty` — outcome must be substantive (HARD)
- `outcome_not_generic` — rejects "completed successfully" and similar (SOFT)
- `objective_outcome_alignment` — outcome must relate to the stated objective (SOFT)
- `confidence_not_default` — flags lazy 0.5 defaults (SOFT)
- `timestamp_recent` — card shouldn't be stale (SOFT)

**Per-type contracts** add 2-3 additional checks each. For example, ERROR cards must include a diagnosis (`key_facts`) and recovery plan (`next_actions`) as HARD requirements.

Failed checks adjust confidence downward: -0.25 per HARD failure, -0.10 per SOFT failure.

```python
from ovi_cards import builder, verify_card

weak_card = builder.error(
    task_id="deploy-99",
    source_agent="deployer:gpt-4",
    objective="Deploy v2.1.0 to production",
    outcome="Done.",           # Too short, generic, no failure language
    key_facts=[],              # No diagnosis
    next_actions=[],           # No recovery plan
    confidence=0.5,            # Lazy default
)

result = verify_card(weak_card)
# result.passed = False
# result.hard_failures = ['outcome_not_empty', 'error_has_diagnosis', 'error_has_next_actions']
# result.soft_failures = ['outcome_not_generic', 'objective_outcome_alignment',
#                         'confidence_not_default', 'error_outcome_describes_failure']
# result.adjusted_confidence = 0.0
```

## Orchestrator Context Budget

The real value of OVI cards emerges at scale. A single card is 164-376 tokens depending on content. Raw agent outputs are typically 1,000-5,000+ tokens.

```
Per-card compression (17 task-oriented samples):
  Median: 69.5% reduction
  Mean:   66.3% reduction

Orchestrator context budget (realistic scenario):
  5 agents x 20 steps, 2000-token raw outputs:
    Raw accumulation:   200,000 tokens
    OVI cards:           24,400 tokens
    Savings:                 88%
```

Card size is O(1). Raw output is O(n). Over a multi-agent session, that's the difference between fitting in a 128k context window and not.

Run the benchmark yourself:

```bash
python benchmarks/run_benchmark.py
```

## MCP Server

OVI Cards ships an MCP server with three tools:

| Tool | Description |
|------|-------------|
| `create_card` | Build a validated card from parameters |
| `validate_card` | Check raw JSON against schema + model rules |
| `verify_card` | Run 15 semantic checks, get adjusted confidence |

### Cursor / Claude Desktop Setup

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "ovi-cards": {
      "command": "python",
      "args": ["-m", "ovi_cards"],
      "env": {}
    }
  }
}
```

## Card Schema

Every OVI card contains these fields:

| Field | Type | Constraint |
|-------|------|-----------|
| `schema_version` | string | semver format |
| `card_type` | enum | RESULT, ERROR, PLAN, PATCH, NOTE |
| `task_id` | string | non-empty |
| `source_agent` | string | format: `{type}:{model}` |
| `timestamp` | string | ISO 8601 |
| `objective` | string | max 256 chars |
| `outcome` | string | max 256 chars |
| `key_facts` | string[] | max 3 items, max 256 chars each |
| `actions_taken` | string[] | max 3 items, max 256 chars each |
| `next_actions` | string[] | max 3 items, max 256 chars each |
| `artifacts` | string[] | max 10 items |
| `confidence` | float | 0.0 - 1.0 |
| `memory_suggestion` | object | store, target, tags |

These constraints are intentional. The bounded structure is the feature — it forces compression at the source and gives the orchestrator a predictable packet size to budget for.

## Design Philosophy

OVI cards are not a compression algorithm. They're a communication protocol.

The orchestrator doesn't need the subagent's full 3,000-word analysis. It needs: what was the objective, what happened, what are the key facts, what should happen next, and how confident is the agent. That's a routing decision, not a summarization task.

For cases where full detail is needed (user drill-down, audit trail, debugging), the raw output can be stored separately and referenced via `artifacts`. The card is Tier 1 (routing and comprehension); the raw output is Tier 2 (on-demand detail).

## License

MIT
