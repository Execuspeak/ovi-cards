# AGENTS.md

## Cursor Cloud specific instructions

`ovi-cards` is a small, self-contained Python library (the OVI card protocol:
models, validation, verification, builder) plus an optional MCP server. It has no
external services and no heavy dependencies.

### Environment
- Python `>=3.10`. Use a virtualenv at `.venv/` (repo root).
- Build backend is hatchling. Install editable with extras:
  ```bash
  python3 -m venv .venv
  .venv/bin/pip install -e ".[dev,mcp]"
  ```
  - `dev` adds `pytest` + `tiktoken` (benchmarks); `mcp` adds the MCP server dep.

### Run / test
- Tests: `.venv/bin/pytest tests/`
- Example: `.venv/bin/python examples/basic_usage.py`
- MCP server (stdio): `.venv/bin/python -m ovi_cards`
- Benchmark: `.venv/bin/python benchmarks/run_benchmark.py` (needs the `dev` extra)

### Notes
- No lint tooling is configured.
- No environment variables or secrets are required.
