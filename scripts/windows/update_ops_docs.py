#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import win_ops_doc_lib


def main() -> int:
    parser = argparse.ArgumentParser(description="Update shared Windows ops documentation.")
    parser.add_argument("--reason", default=None, help="Optional reason for this update.")
    parser.add_argument(
        "--focus",
        action="append",
        default=[],
        choices=["network", "services", "software"],
        help="Optional focus area(s). Omit to run all.",
    )
    args = parser.parse_args()
    result = win_ops_doc_lib.update_docs(reason=args.reason, focus=args.focus)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
