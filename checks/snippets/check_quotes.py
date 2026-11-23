#!/usr/bin/env python3
"""Crocket listings in the migration pages and /ai/ must be copied from the snippet sources."""

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USERS = (ROOT / "checks" / "snippets" / "users.cpp").read_text(encoding="utf-8")
ORDERS = (ROOT / "checks" / "snippets" / "orders.cpp").read_text(encoding="utf-8")
MIGRATION = [
    ROOT / "guide" / "v0.5" / "migrate-express.md",
    ROOT / "guide" / "v0.5" / "migrate-spring.md",
]
AI_PAGE = ROOT / "web" / "ai" / "index.html"


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


def html_listings(text):
    """Text of each <pre><code> whose header says cpp."""
    chunks = re.findall(
        r'<header><span>cpp</span></header>\s*<pre><code>(.*?)</code></pre>',
        text,
        flags=re.S,
    )
    for chunk in chunks:
        plain = re.sub(r"<[^>]+>", "", chunk)
        yield html.unescape(plain)


def main():
    missing = []
    checked = 0
    for path in MIGRATION:
        text = path.read_text(encoding="utf-8")
        if "CROCKET_" in text:
            missing.append(f"{path.name}: contains a CROCKET_ name")
        for lang, code in fences(text):
            if lang not in {"cpp", "c++", "cxx"}:
                continue
            checked += 1
            if not contained(code, USERS):
                missing.append(f"{path.name}: crocket snippet is not in users.cpp:\n{code}\n---")
    ai = AI_PAGE.read_text(encoding="utf-8")
    if "CROCKET_" in ai:
        missing.append("ai/index.html: contains a CROCKET_ name")
    listings = list(html_listings(ai))
    if not listings:
        missing.append("ai/index.html: no cpp listing")
    for code in listings:
        checked += 1
        if not contained(code, ORDERS):
            missing.append(f"ai/index.html: listing is not in orders.cpp:\n{code}\n---")
    if not checked:
        sys.exit("no crocket snippets found")
    if missing:
        sys.exit("\n".join(missing))
    print(f"{checked} crocket snippets match the snippet sources")


if __name__ == "__main__":
    main()
