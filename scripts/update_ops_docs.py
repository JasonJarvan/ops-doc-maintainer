#!/usr/bin/env python3
"""Cross-platform dispatcher for ops-doc-maintainer.

Detects the host OS and forwards all arguments to the platform-specific entry
script under ``scripts/linux/`` or ``scripts/windows/``.
"""
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def pick_platform() -> str:
    system = platform.system()
    if system == "Windows":
        return "windows"
    if system in ("Linux", "Darwin"):
        return "linux"
    raise SystemExit(f"Unsupported platform: {system}")


def main() -> int:
    target = SCRIPT_DIR / pick_platform() / "update_ops_docs.py"
    if not target.exists():
        raise SystemExit(f"Platform entry script not found: {target}")

    # Re-exec the platform script in-process so argparse handles --help/--focus
    # validation per-platform.
    sys.path.insert(0, str(target.parent))
    sys.argv[0] = str(target)
    code = compile(target.read_text(encoding="utf-8"), str(target), "exec")
    ns: dict = {"__name__": "__main__", "__file__": str(target)}
    exec(code, ns)  # noqa: S102 — intentional dispatch
    return 0


if __name__ == "__main__":
    sys.exit(main())
