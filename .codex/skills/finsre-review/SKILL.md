# FinSRE Review Skill

Use this skill when reviewing FinSRE changes.

## Review Focus

1. Structure
   - `cli.py` only parses arguments.
   - Cloud/API logic stays in `connectors/`.
   - SKU routing and questions stay in `discovery/`.
   - LangGraph and LLM behavior stays behind `agents/` and `llm/`.
   - Expected failures use `finsre.errors`.

2. Tests
   - Tests are unit-only.
   - Tests are bound to the changed module.
   - Tests are small and behavior-focused.
   - No live GCP, OpenAI, LangGraph, network, or filesystem side effects beyond local temp/fakes.
   - Optional dependencies are tested through fakes or injected ports.

3. Implementation Size
   - Prefer minimal code.
   - Avoid adding frameworks, globals, persistence, or background workers unless the change needs them now.
   - Avoid future-provider enums or statuses before they are used.

4. Evidence
   - Investigation/recommendation code should carry source facts, confidence, missing context, and questions.
   - Human approval is required before LLM calls.

## Expected Checks

```bash
python3 -m compileall src tests
pre-commit run --all-files
```

If `pre-commit` is unavailable, report that and run the available checks.
