"""Tiny logging shim so every module logs in the same style without pulling
in a heavyweight logging config. Honors `NO_COLOR` and non-tty stdout.
"""

from __future__ import annotations

import os
import sys

_ENABLE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _wrap(code: str, msg: str) -> str:
    return f"\033[{code}m{msg}\033[0m" if _ENABLE_COLOR else msg


def info(msg: str) -> None:
    print(f"{_wrap('1;34', '[localcaption]')} {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"{_wrap('1;33', '[warning    ]')} {msg}", file=sys.stderr, flush=True)


def error(msg: str) -> None:
    print(f"{_wrap('1;31', '[error      ]')} {msg}", file=sys.stderr, flush=True)
