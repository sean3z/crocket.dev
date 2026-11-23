#!/usr/bin/env python3
"""Every crocket code block in the migration pages must be copied from users.cpp."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "checks" / "snippets" / "users.cpp").read_text(encoding="utf-8")
PAGES = [
    ROOT / "guide" / "v0.5" / "migrate-express.md",
    ROOT / "guide" / "v0.5" / "migrate-spring.md",
]


def significant_lines(text):
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def contained(snippet, source):
    """True when snippet's lines appear in order, ignoring indentation."""
    need = significant_lines(snippet)
    have = significant_lines(source)
    if not need:
        return False
    for i in range(len(have) - len(need) + 1):
        if have[i : i + len(need)] == need:
            return True
    return False


def fences(text):
    """Yield (lang, code) for every fence, including those inside :::pair."""
    i = 0
    lines = text.splitlines()
    while i < len(lines):
        if lines[i].startswith("```"):
            lang = lines[i][3:].strip()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            yield lang, "\n".join(buf)
        i += 1


def main():
    missing = []
    checked = 0
    for path in PAGES:
        text = path.read_text(encoding="utf-8")
        if "CROCKET_" in text:
            missing.append(f"{path.name}: contains a CROCKET_ name")
        for lang, code in fences(text):
            if lang not in {"cpp", "c++", "cxx"}:
                continue
            checked += 1
            if not contained(code, SOURCE):
                missing.append(f"{path.name}: crocket snippet is not in users.cpp:\n{code}\n---")
    if not checked:
        sys.exit("no crocket snippets found")
    if missing:
        sys.exit("\n".join(missing))
    print(f"{checked} crocket snippets match checks/snippets/users.cpp")


if __name__ == "__main__":
    main()
