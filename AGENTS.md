# FinSRE Agent Rules

FinSRE is a Python-first CLI agent for cloud cost investigation. Keep the product small, modular, and evidence-driven.

## Goal

Build a cost investigation tool that starts from billing/SKU signals, plans read-only discovery, records context facts, asks humans only when intent is missing, and uses LangGraph-backed agents only after explicit approval.

## Implementation Rules

- Prefer the fewest lines that make the behavior clear.
- Keep modules narrow:
  - `cli.py`: argument parsing only.
  - `cli_commands.py`: command handlers.
  - `core/`: events, manifests, ports, serialization, time, cost-series normalization.
  - `connectors/`: provider API integration; emit `CostLineItem` rows.
  - `detectors/`: anomaly detection over `CostSeries`.
  - `discovery/`: SKU classification, probe planning, facts, questions.
  - `agents/`: LangGraph/agent orchestration behind interfaces; agents consume `InvestigationContext`.
  - `memory/`: retrieval and memory interfaces.
  - `tracker/`: investigation/recommendation state.
- Do not add abstractions unless a second use is visible or the boundary is already part of the design.
- Use FinSRE-owned exceptions from `finsre.errors` for expected failures.
- Do not call live cloud APIs, LLMs, or network in unit tests.
- Do not store secrets. Read API keys from environment variables and fail clearly when missing.

## Test Rules

- Tests must be unit tests unless an explicit integration-test path exists.
- Bind tests to the module they cover: `src/finsre/discovery/sku.py` should be covered in `tests/test_discovery.py` or a similarly scoped file.
- Write to-the-point tests for behavior and edge cases; avoid broad snapshot-style tests.
- Prefer a small number of meaningful assertions over many brittle assertions.
- For optional providers like LangGraph/OpenAI/GCP, use fakes and injected transports.

## Before Finishing

Run:

```bash
python3 -m compileall src tests
pre-commit run --all-files
```

If a tool is not installed locally, say that explicitly and still run the checks that are available.
