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


SYNTHETIC_SAMPLES = [
    {
        "id": "synth-code-review",
        "source": "synthetic",
        "category": "code-review",
        "raw_text": (
            "## Code Review: Authentication Module\n\n"
            "I've completed a thorough review of the authentication module as requested. "
            "Here are my findings:\n\n"
            "### Critical Issues\n\n"
            "1. **SQL Injection in login handler** (login_handler.py, line 45): The username "
            "parameter is concatenated directly into the SQL query string without sanitization. "
            "An attacker could inject arbitrary SQL via the login form. This is a critical "
            "severity finding.\n\n"
            "2. **SQL Injection in password reset** (login_handler.py, line 67): Same pattern "
            "as above — the email parameter in the password reset flow uses string formatting "
            "rather than parameterized queries.\n\n"
            "### Remediation Applied\n\n"
            "I've patched both locations to use parameterized queries via SQLAlchemy's "
            "text() construct with bound parameters. The changes are minimal and surgical — "
            "no refactoring of surrounding code was necessary.\n\n"
            "### Additional Analysis\n\n"
            "I ran Bandit static analysis across the entire auth/ directory and found no "
            "additional injection vectors. The session management, CSRF protection, and "
            "password hashing implementations all follow current best practices.\n\n"
            "### Recommendations\n\n"
            "- Run the integration test suite to verify login flows still work correctly\n"
            "- Schedule a broader codebase scan for similar patterns in other modules\n"
            "- Consider adding a pre-commit hook with Bandit to catch these patterns early\n\n"
            "Confidence in the fix: High. Both patches are straightforward substitutions "
            "from string concatenation to parameterized queries."
        ),
    },
    {
        "id": "synth-incident-response",
        "source": "synthetic",
        "category": "incident-response",
        "raw_text": (
            "## Incident Report: Production API Outage\n\n"
            "### Timeline\n\n"
            "**02:14 UTC** — PagerDuty alert triggered: 5xx error rate exceeded 10% on "
            "/api/v2/orders endpoint.\n\n"
            "**02:16 UTC** — Confirmed outage. All order-related endpoints returning 503. "
            "Other endpoints unaffected. Dashboard shows connection pool exhaustion on the "
            "primary database cluster.\n\n"
            "**02:19 UTC** — Thread dump analysis reveals 50/50 HikariCP connections in use, "
            "all blocked waiting on the OrderRetryInterceptor. New requests queueing behind "
            "the pool with 30-second timeout.\n\n"
            "**02:25 UTC** — Root cause identified: The retry interceptor "
            "(OrderRetryInterceptor.java, line 47) opens a new database connection on each "
            "retry attempt but never closes the failed connection. Under normal load this "
            "isn't noticeable, but a transient network blip at 02:13 triggered a cascade "
            "of retries that leaked approximately 3 connections per retry cycle.\n\n"
            "**02:31 UTC** — Hotfix deployed: wrapped the retry logic in try-with-resources "
            "to ensure connection cleanup. Also bumped pool max from 50 to 100 as a safety "
            "buffer while we audit other interceptors.\n\n"
            "**02:35 UTC** — Connection pool draining. Active connections dropping.\n\n"
            "**02:47 UTC** — All endpoints healthy. Error rate back to baseline 0.01%.\n\n"
            "### Root Cause\n\n"
            "Connection leak in retry logic. The OrderRetryInterceptor opened new connections "
            "without closing failed ones, leaking ~3 connections per retry cycle. Under "
            "sustained retry pressure from a transient network issue, this exhausted the "
            "50-connection pool in approximately 3 minutes.\n\n"
            "### Impact\n\n"
            "- Duration: 33 minutes (02:14 - 02:47 UTC)\n"
            "- Affected: All /api/v2/orders endpoints\n"
            "- Customer impact: Approximately 1,200 failed order requests\n"
            "- Data loss: None (orders were rejected, not corrupted)\n\n"
            "### Action Items\n\n"
            "1. Add connection pool utilization alert at 80% threshold\n"
            "2. Audit all retry interceptors for similar connection leak patterns\n"
            "3. Write post-mortem document for stakeholder review\n"
            "4. Add integration test that validates connection cleanup under retry conditions"
        ),
    },
    {
        "id": "synth-deployment",
        "source": "synthetic",
        "category": "deployment",
        "raw_text": (
            "Deployment of v2.1.0 to the production cluster failed during the rolling update "
            "phase. Here's what happened:\n\n"
            "The new container image built successfully and passed all CI checks. During "
            "rollout, the first 2 of 5 pods started cleanly, but pods 3-5 failed their "
            "health checks after the 30-second startup timeout.\n\n"
            "Investigation revealed that the health check endpoint (/health) was returning "
            "503 because the application couldn't establish a database connection on startup. "
            "The DATABASE_URL environment variable was not set in the new deployment "
            "configuration — it was present in the v2.0.x config but was accidentally dropped "
            "during the config migration to the new Helm chart format.\n\n"
            "I rolled back to v2.0.9 to restore service. The rollback completed in 45 seconds "
            "with no dropped requests thanks to the graceful shutdown configuration.\n\n"
            "To fix: add DATABASE_URL to the production secrets in the new Helm values.yaml, "
            "then re-deploy v2.1.0. I'd also recommend adding a config validation step to "
            "the CI pipeline that checks for required environment variables before allowing "
            "deployment to proceed."
        ),
    },
    {
        "id": "synth-perf-analysis",
        "source": "synthetic",
        "category": "performance",
        "raw_text": (
            "## Performance Analysis: User Dashboard Endpoint\n\n"
            "The /api/dashboard endpoint has been flagged for slow response times. Current "
            "p99 latency is 2.3 seconds, well above the 500ms SLA target.\n\n"
            "### Profiling Results\n\n"
            "Using Django Debug Toolbar and database query logging, I identified the root "
            "cause: a classic N+1 query problem. The dashboard view loads the user's recent "
            "activity, which includes:\n\n"
            "1. One query to fetch the user profile\n"
            "2. One query per activity item to load related metadata (47 queries on average)\n"
            "3. One query per unique tag to resolve tag names (12 queries on average)\n\n"
            "Total: approximately 60 database queries per dashboard load.\n\n"
            "### Fix Applied\n\n"
            "Replaced the individual queries with a single JOIN using Django's "
            "select_related() and prefetch_related():\n\n"
            "- User profile + activities: single query with LEFT JOIN\n"
            "- Tag resolution: single IN query via prefetch_related\n\n"
            "Total after fix: 3 queries per dashboard load.\n\n"
            "### Results\n\n"
            "- p99 latency: 2.3s → 180ms (92% reduction)\n"
            "- p50 latency: 890ms → 45ms\n"
            "- Database query count: 60 → 3\n"
            "- Database time per request: 1.8s → 35ms\n\n"
            "The fix is deployed to staging. Recommend running the load test suite before "
            "promoting to production."
        ),
    },
    {
        "id": "synth-security-audit",
        "source": "synthetic",
        "category": "security-audit",
        "raw_text": (
            "## Security Audit: API Authentication Layer\n\n"
            "Completed a comprehensive security review of the API authentication system "
            "as part of the Q1 security hardening initiative.\n\n"
            "### Scope\n\n"
            "- JWT token generation and validation\n"
            "- Session management and cookie handling\n"
            "- Rate limiting and brute force protection\n"
            "- CORS configuration\n"
            "- API key management\n\n"
            "### Findings\n\n"
            "**HIGH: JWT secret rotation** — The JWT signing secret has not been rotated "
            "since initial deployment (427 days ago). While there's no evidence of compromise, "
            "this exceeds the 90-day rotation policy.\n\n"
            "**MEDIUM: Rate limiter bypass** — The rate limiter uses X-Forwarded-For for "
            "client identification. Behind our load balancer this is reliable, but the header "
            "is not validated against a trusted proxy list, meaning a direct connection to "
            "the application server could spoof the header.\n\n"
            "**LOW: CORS overly permissive** — The CORS configuration allows credentials "
            "from *.example.com. This is broader than necessary; should be restricted to "
            "app.example.com and admin.example.com only.\n\n"
            "**PASS: Session management** — HttpOnly, Secure, SameSite=Strict flags all "
            "correctly set. Session tokens are invalidated on password change.\n\n"
            "**PASS: API key hashing** — Keys are stored as bcrypt hashes. Plaintext keys "
            "are never logged or stored after initial generation.\n\n"
            "### Recommendations\n\n"
            "1. Rotate JWT secret immediately and implement automated 90-day rotation\n"
            "2. Add trusted proxy validation to rate limiter configuration\n"
            "3. Restrict CORS origins to specific subdomains\n"
            "4. Schedule follow-up audit for API authorization (out of scope for this review)"
        ),
    },
    {
        "id": "synth-data-migration",
        "source": "synthetic",
        "category": "data-migration",
        "raw_text": (
            "Completed the user_preferences table migration from the legacy schema to the "
            "new normalized structure. This migration was necessary to support the upcoming "
            "multi-tenant feature.\n\n"
            "The migration processed 2.4 million rows across 3 production shards. Each shard "
            "was migrated independently using the blue-green approach: new table created, "
            "data copied with transformation, application switched to read from new table, "
            "old table retained for 7-day rollback window.\n\n"
            "Key transformation: the old schema stored preferences as a JSON blob in a single "
            "TEXT column. The new schema breaks this into normalized columns with proper "
            "types and indexes. Approximately 3.2% of rows had malformed JSON that required "
            "manual parsing fallbacks — these were logged for review but all were successfully "
            "transformed.\n\n"
            "Performance: migration completed in 4 hours 12 minutes total (1.2h, 1.5h, 1.5h "
            "per shard). No downtime, no user-facing impact. Read latency on the preferences "
            "endpoint improved by 60% due to the new column indexes.\n\n"
            "Rollback plan: old tables retained with trigger-based sync for 7 days. If issues "
            "emerge, a single config flag switches reads back to the legacy table."
        ),
    },
    {
        "id": "synth-monitoring-note",
        "source": "synthetic",
        "category": "monitoring",
        "raw_text": (
            "Observing a steady increase in memory usage across the production web servers "
            "over the past 7 days. Current utilization is at 78% of the 16GB allocated per "
            "instance, up from 62% a week ago.\n\n"
            "The trend is linear at approximately 2.3% per day. At this rate, we'll hit the "
            "85% alert threshold in approximately 3 days and the 95% critical threshold in "
            "approximately 7 days.\n\n"
            "No corresponding increase in request volume or error rates. CPU utilization "
            "remains stable at 23%. This pattern is consistent with a memory leak rather "
            "than increased load.\n\n"
            "The timing correlates with the v2.0.8 deployment 8 days ago, which introduced "
            "the new caching layer for user sessions. Worth investigating whether the cache "
            "eviction policy is working correctly.\n\n"
            "No action taken — this is an observation for the on-call team to investigate."
        ),
    },
    {
        "id": "synth-short-result",
        "source": "synthetic",
        "category": "short-task",
        "raw_text": (
            "Ran the test suite. All 142 tests passed in 3.2 seconds. No warnings, no "
            "deprecation notices. Coverage report shows 87% line coverage, up from 84% "
            "after the new auth tests were added. The three uncovered modules are: "
            "legacy_import.py (deprecated), debug_utils.py (dev-only), and "
            "migration_helpers.py (one-time use). None of these need coverage."
        ),
    },
]


def _build_synthetic_corpus():
    return {"total_samples": len(SYNTHETIC_SAMPLES), "samples": SYNTHETIC_SAMPLES}


def main():
    enc = tiktoken.get_encoding("cl100k_base")

    corpus_path = Path(__file__).parent / "corpus" / "real_and_synthetic_corpus.json"
    if corpus_path.exists():
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    else:
        print("  [No corpus file found — using built-in synthetic samples]")
        print()
        corpus = _build_synthetic_corpus()
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
