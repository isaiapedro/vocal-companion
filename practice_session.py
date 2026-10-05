#!/usr/bin/env python3
"""Practice-only local entry point.

Use this only after profile_intake.py has produced a routine-generation prompt
and an LLM (or the user) has saved a JSON routine proposal. It delegates to the
same immutable archive contract as vocal_practice.py, while keeping the practice
workflow separate from profile discovery.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import vocal_practice


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=vocal_practice.canonical_archive_root(),
                        help="fixed canonical Personal archive; other paths are rejected")
    parser.add_argument("--at")
    parser.add_argument("command", choices=["start", "log-block", "finish", "recovery", "weekly-review", "verify-archive"])
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    delegated = ["--data-dir", str(args.data_dir)]
    if args.at:
        delegated.extend(["--at", args.at])
    delegated.extend([args.command, *args.arguments])
    return vocal_practice.main(delegated)


if __name__ == "__main__":
    raise SystemExit(main())
