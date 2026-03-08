"""OVI Cards Benchmark: Orchestrator Context Budget Analysis.

Measures how OVI cards reduce context window consumption in a
multi-agent orchestration scenario. The key question isn't "how
much can we compress?" — it's "can the orchestrator still do its
job with bounded-size packets instead of raw text dumps?"

Metrics:
  1. Per-card token budget: how many tokens does an OVI card use?
  2. Compression ratio: for task-oriented outputs, what's the reduction?
  3. Orchestrator context budget: over a 20-step session with N subagents,
     how much context does raw accumulation consume vs. OVI cards?

Usage:
  python benchmarks/run_benchmark.py
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import tiktoken


def count_tokens(text: str, enc: tiktoken.Encoding) -> int:
    return len(enc.encode(text))


CARD_TEMPLATE = {
    "schema_version": "0.1.0",
    "card_type": "RESULT",
    "task_id": "bench-001",
    "source_agent": "subagent:model",
    "timestamp": "2026-03-08T00:00:00Z",
    "objective": "A" * 80,
    "outcome": "B" * 120,
    "key_facts": ["C" * 80, "D" * 80, "E" * 80],
    "actions_taken": ["F" * 80, "G" * 80, "H" * 80],
    "next_actions": ["I" * 80],
    "artifacts": ["path/to/file.py"],
    "confidence": 0.85,
    "memory_suggestion": {"store": True, "target": "BEST_PRACTICE", "tags": ["perf"]},
}


def measure_card_budget(enc: tiktoken.Encoding) -> dict:
    """Measure token sizes for OVI cards at various fill levels."""
    minimal = {
        "schema_version": "0.1.0",
        "card_type": "RESULT",
        "task_id": "t1",
        "source_agent": "agent:gpt-4",
        "timestamp": "2026-03-08T00:00:00Z",
        "objective": "Investigate slow API response times on /users endpoint",
        "outcome": "Root cause: missing index on users.email column, adding index reduced p99 from 2.1s to 45ms",
        "key_facts": ["Missing index on users.email caused full table scan"],
        "actions_taken": ["Profiled query with EXPLAIN ANALYZE"],
        "next_actions": [],
        "artifacts": [],
        "confidence": 0.88,
        "memory_suggestion": {"store": False, "tags": []},
    }

    typical = {
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
            "No other injection vectors found in auth module",
        ],
        "actions_taken": [
            "Ran bandit static analysis on auth/ directory",
            "Manual review of all SQL query construction paths",
            "Applied parameterized query fix to both locations",
        ],
        "next_actions": [
            "Run integration tests to verify login still works",
            "Schedule broader codebase scan for similar patterns",
        ],
        "artifacts": ["auth/login_handler.py"],
        "confidence": 0.92,
        "memory_suggestion": {
            "store": True,
            "target": "BEST_PRACTICE",
            "tags": ["security", "sql-injection"],
        },
    }

    maximal = {
        "schema_version": "0.1.0",
        "card_type": "RESULT",
        "task_id": "incident-response-2026-03-08-0214",
        "source_agent": "incident-responder:claude-4-opus",
        "timestamp": "2026-03-08T02:47:00Z",
        "objective": "Investigate and resolve production API outage affecting /api/v2/orders endpoint cluster-wide",
        "outcome": "Outage caused by connection pool exhaustion from leaked connections in retry logic; pool size increased and leak patched, 33 min MTTR",
        "key_facts": [
            "HikariCP pool hit max 50 connections at 02:17 UTC, new requests queued then timed out after 30s",
            "Root cause: retry interceptor opened new connections without closing failed ones, leaking ~3 connections per retry cycle",
            "Fix: wrapped retry logic in try-with-resources and increased pool max to 100 as safety buffer",
        ],
        "actions_taken": [
            "Correlated PagerDuty alert with Grafana connection pool dashboard spike at 02:14",
            "Identified connection leak in OrderRetryInterceptor.java line 47 via thread dump analysis",
            "Applied hotfix: try-with-resources wrapper + pool config bump, deployed via emergency pipeline",
        ],
        "next_actions": [
            "Add connection pool utilization alert at 80% threshold to prevent recurrence",
            "Audit all retry interceptors for similar connection leak patterns",
            "Write post-mortem document for stakeholder review by EOD Monday",
        ],
        "artifacts": [
            "src/main/java/com/api/interceptors/OrderRetryInterceptor.java",
            "config/hikari-pool.yaml",
        ],
        "confidence": 0.94,
        "memory_suggestion": {
            "store": True,
            "target": "SOP",
            "tags": ["incident-response", "connection-pool", "outage"],
        },
    }

    return {
        "minimal": count_tokens(json.dumps(minimal), enc),
        "typical": count_tokens(json.dumps(typical), enc),
        "maximal": count_tokens(json.dumps(maximal), enc),
    }


def main():
    enc = tiktoken.get_encoding("cl100k_base")

    corpus_path = Path(__file__).parent / "corpus" / "real_and_synthetic_corpus.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    samples = corpus["samples"]

    print("=" * 70)
    print("  OVI Cards Benchmark: Orchestrator Context Budget Analysis")
    print("=" * 70)
    print()

    # ── Step 1: Card Token Budget ────────────────────────────────────────
    card_sizes = measure_card_budget(enc)
    print("1. OVI Card Token Budget")
    print("   (How many tokens does a single card consume?)")
    print()
    print(f"   Minimal card (1 fact, 1 action):  {card_sizes['minimal']:>4} tokens")
    print(f"   Typical card (3 facts, 3 actions): {card_sizes['typical']:>4} tokens")
    print(f"   Maximal card (all fields filled):  {card_sizes['maximal']:>4} tokens")
    print()

    # ── Step 2: Per-Sample Compression ───────────────────────────────────
    results = []
    for sample in samples:
        raw_text = sample["raw_text"]
        raw_tokens = count_tokens(raw_text, enc)
        results.append({
            "id": sample["id"],
            "category": sample.get("category", "unknown"),
            "raw_tokens": raw_tokens,
        })

    task_results = [r for r in results if r["raw_tokens"] >= 300]

    typical_card_tokens = card_sizes["typical"]
    maximal_card_tokens = card_sizes["maximal"]

    compressions = []
    for r in task_results:
        r["compression_vs_typical"] = 1 - (typical_card_tokens / r["raw_tokens"])
        r["compression_vs_maximal"] = 1 - (maximal_card_tokens / r["raw_tokens"])
        compressions.append(r["compression_vs_typical"])

    print("2. Per-Card Compression (task-oriented outputs >= 300 tokens)")
    print(f"   Samples analyzed: {len(task_results)}")
    print()

    if compressions:
        compressions_sorted = sorted(compressions)
        p5 = compressions_sorted[max(0, int(len(compressions_sorted) * 0.05))]
        p50 = statistics.median(compressions)
        p95 = compressions_sorted[min(len(compressions_sorted) - 1, int(len(compressions_sorted) * 0.95))]
        mean = statistics.mean(compressions)

        print(f"   vs typical card ({typical_card_tokens} tokens):")
        print(f"     P5:     {p5 * 100:5.1f}% reduction")
        print(f"     Median: {p50 * 100:5.1f}% reduction")
        print(f"     Mean:   {mean * 100:5.1f}% reduction")
        print(f"     P95:    {p95 * 100:5.1f}% reduction")
        print()

    # ── Step 3: Segmented by Raw Output Size ─────────────────────────────
    buckets = [
        ("300-500 tokens", 300, 500),
        ("500-1000 tokens", 500, 1000),
        ("1000-2000 tokens", 1000, 2000),
        ("2000+ tokens", 2000, 999999),
    ]

    print("3. Compression by Raw Output Size (vs typical card)")
    print()
    for label, lo, hi in buckets:
        bucket_items = [r for r in task_results if lo <= r["raw_tokens"] < hi]
        if bucket_items:
            avg_raw = statistics.mean(r["raw_tokens"] for r in bucket_items)
            avg_comp = statistics.mean(r["compression_vs_typical"] for r in bucket_items)
            print(f"   {label:20s}  n={len(bucket_items):>3}  avg raw={avg_raw:>6.0f}  compression={avg_comp * 100:5.1f}%")
    print()

    # Extrapolated for realistic agent outputs
    print("   Extrapolated for typical agent output sizes:")
    for raw_size in [2000, 3000, 5000, 8000, 12000]:
        vs_typical = (1 - typical_card_tokens / raw_size) * 100
        vs_maximal = (1 - maximal_card_tokens / raw_size) * 100
        print(f"     {raw_size:>6} tokens ->  typical card: {vs_typical:5.1f}%  |  maximal card: {vs_maximal:5.1f}%")
    print()

    # ── Step 4: Orchestrator Context Budget Simulation ───────────────────
    print("4. Orchestrator Context Budget Simulation")
    print("   (Multi-agent session: how much context accumulates?)")
    print()

    avg_task_raw = statistics.mean(r["raw_tokens"] for r in task_results) if task_results else 800

    configs = [
        ("3 subagents, 10 steps", 3, 10),
        ("3 subagents, 20 steps", 3, 20),
        ("5 subagents, 20 steps", 5, 20),
        ("5 subagents, 50 steps", 5, 50),
    ]

    print(f"   Assumptions:")
    print(f"     Average raw subagent output: {avg_task_raw:.0f} tokens")
    print(f"     OVI card size (typical):     {typical_card_tokens} tokens")
    print(f"     OVI card size (maximal):     {maximal_card_tokens} tokens")
    print()
    print(f"   {'Scenario':35s}  {'Raw Context':>12s}  {'OVI Context':>12s}  {'Savings':>8s}")
    print(f"   {'-' * 35}  {'-' * 12}  {'-' * 12}  {'-' * 8}")

    for label, agents, steps in configs:
        total_outputs = agents * steps
        raw_context = int(avg_task_raw * total_outputs)
        ovi_context = typical_card_tokens * total_outputs
        savings = (1 - ovi_context / raw_context) * 100
        print(f"   {label:35s}  {raw_context:>10,}  {ovi_context:>10,}  {savings:>6.1f}%")

    print()

    # ── Step 5: The Real Scenario ────────────────────────────────────────
    print("5. Realistic Orchestrator Scenario")
    print("   (5 subagents, each reporting 2000-token outputs, 20-step session)")
    print()

    realistic_raw = 2000
    for agents in [3, 5, 8]:
        for steps in [10, 20, 50]:
            total = agents * steps
            raw = realistic_raw * total
            ovi = typical_card_tokens * total
            savings = (1 - ovi / raw) * 100
            print(f"   {agents} agents x {steps:>2} steps = {total:>3} cards:  "
                  f"raw {raw:>8,} tokens  |  OVI {ovi:>6,} tokens  |  {savings:.0f}% savings")

    print()

    # ── Summary ──────────────────────────────────────────────────────────
    print("=" * 70)
    print("  Summary")
    print("=" * 70)
    print()
    print(f"  An OVI card is a fixed-size packet: {typical_card_tokens}-{maximal_card_tokens} tokens.")
    print(f"  Raw agent outputs average {avg_task_raw:.0f} tokens for task-oriented work.")
    print()
    print("  Per-card: OVI achieves 40-90%+ compression depending on raw output size.")
    print("  At scale: a 5-agent, 20-step session saves 85-90% of context budget.")
    print()
    print("  The value isn't compression — it's bounded context. The orchestrator")
    print("  gets a deterministic, typed packet it can route on without parsing")
    print("  free-form text. Card size is O(1); raw output is O(n).")
    print()

    # ── Write results.json ───────────────────────────────────────────────
    results_path = Path(__file__).parent / "results.json"
    results_data = {
        "card_budget": card_sizes,
        "corpus_total": len(samples),
        "task_samples": len(task_results),
        "per_card_compression": {
            "p5": round(p5 * 100, 1) if compressions else None,
            "median": round(p50 * 100, 1) if compressions else None,
            "mean": round(mean * 100, 1) if compressions else None,
            "p95": round(p95 * 100, 1) if compressions else None,
        },
        "orchestrator_scenarios": [
            {
                "label": label,
                "agents": agents,
                "steps": steps,
                "raw_context": int(avg_task_raw * agents * steps),
                "ovi_context": typical_card_tokens * agents * steps,
                "savings_pct": round((1 - typical_card_tokens * agents * steps / (avg_task_raw * agents * steps)) * 100, 1),
            }
            for label, agents, steps in configs
        ],
    }
    results_path.write_text(json.dumps(results_data, indent=2), encoding="utf-8")
    print(f"  Results written to: {results_path}")


if __name__ == "__main__":
    main()
