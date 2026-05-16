"""Compatibility module for older drafts.

The MVP is a CLI agent. Use `finsre.cli:main` or the `finsre` console script.
"""


def run() -> None:
    raise SystemExit("FinSRE is a CLI agent. Run `finsre --help`.")
