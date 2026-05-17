# FinSRE Claude Rules

Follow the same project rules as `AGENTS.md`.

Short version:

- Keep implementation minimal and modular.
- Keep tests unit-only and bound to the module under change.
- Use `finsre.errors` for expected failures.
- Do not call live cloud APIs, LLM providers, or network in tests.
- Use fakes/injected transports for GCP, LangGraph, and OpenAI.
- Keep `cli.py` as parser-only; put behavior in `cli_commands.py` or the relevant module.
- Ask humans only when missing context changes the recommendation or investigation.

Run available checks before finishing:

```bash
python3 -m compileall src tests
pre-commit run --all-files
```
