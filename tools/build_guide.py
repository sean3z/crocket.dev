#!/usr/bin/env python3
"""Render guide/v0.5/*.md into static HTML and a C++ embed list.

Syntax highlighting is done here. The pages ship no inline script or style.
"""

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "guide" / "v0.5"
WEB = ROOT / "web" / "guide"
CPP = ROOT / "src" / "guide_assets.cpp"

# This site's repository. Edit links point at these files, not at sean3z/crocket.
EDIT_BASE = "https://origin.cursor.com/git/sean-wragg/tmp-df2bdaef10926a6b/blob/main"
COMMIT = "9b446f8c2423262ef1cbf3afe370a0ae2f81d181"
COMMIT_SHORT = "9b446f8"

# (slug, nav title, markdown filename). index.md is the introduction at /guide/v0.5/.
CHAPTERS = [
    ("index", "Introduction", "index.md"),
    ("quickstart", "Quickstart", "quickstart.md"),
    ("getting-started", "Getting started", "getting-started.md"),
    ("overview", "Overview", "overview.md"),
    ("requests", "Requests", "requests.md"),
    ("responses", "Responses", "responses.md"),
    ("state", "State", "state.md"),
    ("fairings", "Fairings", "fairings.md"),
    ("testing", "Testing", "testing.md"),
    ("configuration", "Configuration", "configuration.md"),
    ("openapi", "OpenAPI", "openapi.md"),
    ("grpc", "gRPC", "grpc.md"),
    ("deploying", "Deploying", "deploying.md"),
]

CPP_KEYWORDS = {
    "alignas", "alignof", "and", "and_eq", "asm", "auto", "bitand", "bitor", "bool",
    "break", "case", "catch", "char", "char8_t", "char16_t", "char32_t", "class",
    "compl", "concept", "const", "consteval", "constexpr", "constinit", "const_cast",
    "continue", "co_await", "co_return", "co_yield", "decltype", "default", "delete",
    "do", "double", "dynamic_cast", "else", "enum", "explicit", "export", "extern",
    "false", "float", "for", "friend", "goto", "if", "inline", "int", "long",
    "mutable", "namespace", "new", "noexcept", "not", "not_eq", "nullptr", "operator",
    "or", "or_eq", "private", "protected", "public", "register", "reinterpret_cast",
    "requires", "return", "short", "signed", "sizeof", "static", "static_assert",
    "static_cast", "struct", "switch", "template", "this", "thread_local", "throw",
    "true", "try", "typedef", "typeid", "typename", "union", "unsigned", "using",
    "virtual", "void", "volatile", "wchar_t", "while",
}

SH_KEYWORDS = {
    "if", "then", "else", "elif", "fi", "for", "in", "do", "done", "case", "esac",
    "while", "until", "function", "export", "set", "return", "local",
}


def slugify(text):
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text.strip())
    return text or "section"


def esc(text):
    return html.escape(text, quote=True)


def span(kind, text):
    if not text:
        return ""
    if not kind:
        return esc(text)
    return f'<span class="{kind}">{esc(text)}</span>'


def highlight(code, lang):
    lang = (lang or "").lower()
    if lang in {"cpp", "c++", "cxx", "h", "hpp"}:
        return highlight_cpp(code)
    if lang in {"sh", "bash", "shell"}:
        return highlight_shell(code)
    if lang == "json":
        return highlight_json(code)
    if lang in {"cmake", "text", "txt", "yaml", "yml", "dockerfile", ""}:
        return esc(code)
    return esc(code)


def highlight_cpp(code):
    out = []
    i = 0
    n = len(code)
    while i < n:
        if code.startswith("//", i):
            j = code.find("\n", i)
            j = n if j < 0 else j
            out.append(span("c", code[i:j]))
            i = j
            continue
        if code.startswith("/*", i):
            j = code.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(span("c", code[i:j]))
            i = j
            continue
        if code.startswith("[[", i):
            j = code.find("]]", i + 2)
            j = n if j < 0 else j + 2
            out.append(span("a", code[i:j]))
            i = j
            continue
        ch = code[i]
        if ch in "\"'":
            j = i + 1
            while j < n:
                if code[j] == "\\":
                    j += 2
                    continue
                if code[j] == ch:
                    j += 1
                    break
                if code[j] == "\n":
                    break
                j += 1
            out.append(span("s", code[i:j]))
            i = j
            continue
        if ch == "#" and (i == 0 or code[i - 1] == "\n"):
            j = code.find("\n", i)
            j = n if j < 0 else j
            out.append(span("a", code[i:j]))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (code[j].isalnum() or code[j] == "_"):
                j += 1
            word = code[i:j]
            out.append(span("k" if word in CPP_KEYWORDS else "", word))
            i = j
            continue
        out.append(esc(ch))
        i += 1
    return "".join(out)


def highlight_shell(code):
    out = []
    i = 0
    n = len(code)
    while i < n:
        ch = code[i]
        if ch == "#" and (i == 0 or code[i - 1] in " \t\n"):
            j = code.find("\n", i)
            j = n if j < 0 else j
            out.append(span("c", code[i:j]))
            i = j
            continue
        if ch in "\"'":
            j = i + 1
            while j < n and code[j] != ch and code[j] != "\n":
                if code[j] == "\\" and ch == "\"":
                    j += 2
                    continue
                j += 1
            if j < n and code[j] == ch:
                j += 1
            out.append(span("s", code[i:j]))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (code[j].isalnum() or code[j] == "_"):
                j += 1
            word = code[i:j]
            out.append(span("k" if word in SH_KEYWORDS else "", word))
            i = j
            continue
        out.append(esc(ch))
        i += 1
    return "".join(out)


def highlight_json(code):
    out = []
    i = 0
    n = len(code)
    while i < n:
        ch = code[i]
        if ch == "\"":
            j = i + 1
            while j < n:
                if code[j] == "\\":
                    j += 2
                    continue
                if code[j] == "\"":
                    j += 1
                    break
                j += 1
            out.append(span("s", code[i:j]))
            i = j
            continue
        if ch.isdigit() or (ch == "-" and i + 1 < n and code[i + 1].isdigit()):
            j = i + 1
            while j < n and code[j] in "0123456789.eE+-":
                j += 1
            out.append(span("k", code[i:j]))
            i = j
            continue
        if code.startswith(("true", "false", "null"), i):
            word = next(w for w in ("true", "false", "null") if code.startswith(w, i))
            out.append(span("k", word))
            i += len(word)
            continue
        out.append(esc(ch))
        i += 1
    return "".join(out)


def inline(text):
    parts = re.split(r"(`[^`]*`)", text)
    rendered = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) >= 2:
            rendered.append(f"<code>{esc(part[1:-1])}</code>")
            continue
        rendered.append(inline_rich(part))
    return "".join(rendered)


def inline_rich(text):
    out = []
    i = 0
    while i < len(text):
        if text.startswith("**", i):
            j = text.find("**", i + 2)
            if j > 0:
                out.append(f"<strong>{inline_rich(text[i + 2:j])}</strong>")
                i = j + 2
                continue
        if text[i] == "*" and not text.startswith("**", i):
            j = text.find("*", i + 1)
            if j > 0:
                out.append(f"<em>{inline_rich(text[i + 1:j])}</em>")
                i = j + 1
                continue
        m = re.match(r"\[([^\]]+)\]\(([^)\s]+)\)", text[i:])
        if m:
            label, url = m.group(1), m.group(2)
            out.append(f'<a href="{esc(url)}">{inline_rich(label)}</a>')
            i += m.end()
            continue
        out.append(esc(text[i]))
        i += 1
    return "".join(out)


def parse(md):
    lines = md.replace("\r\n", "\n").split("\n")
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            lang = line[3:].strip()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            blocks.append(("code", lang, "\n".join(buf)))
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            blocks.append(("h", len(m.group(1)), m.group(2).strip()))
            i += 1
            continue
        if line.strip() == "---":
            blocks.append(("hr",))
            i += 1
            continue
        if line.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            blocks.append(("quote", " ".join(buf)))
            continue
        if line.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            blocks.append(("table", rows))
            continue
        if re.match(r"^[-*]\s+", line) or re.match(r"^\d+\.\s+", line):
            ordered = bool(re.match(r"^\d+\.\s+", line))
            items = []
            while i < len(lines) and (re.match(r"^[-*]\s+", lines[i]) or re.match(r"^\d+\.\s+", lines[i])):
                items.append(re.sub(r"^([-*]|\d+\.)\s+", "", lines[i]))
                i += 1
            blocks.append(("list", ordered, items))
            continue
        buf = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not _block_start(lines[i]):
            buf.append(lines[i])
            i += 1
        blocks.append(("p", " ".join(x.strip() for x in buf)))
    return blocks


def _block_start(line):
    return (
        line.startswith("```")
        or line.startswith(">")
        or line.lstrip().startswith("|")
        or bool(re.match(r"^#{1,4}\s+", line))
        or line.strip() == "---"
        or bool(re.match(r"^[-*]\s+", line))
        or bool(re.match(r"^\d+\.\s+", line))
    )


def render_blocks(blocks):
    title = ""
    body = []
    toc = []
    ids = {}
    seen = {}

    def unique(base):
        n = seen.get(base, 0)
        seen[base] = n + 1
        return base if n == 0 else f"{base}-{n + 1}"

    for block in blocks:
        kind = block[0]
        if kind == "h":
            level, text = block[1], block[2]
            sid = unique(slugify(text))
            ids[sid] = True
            if level == 1 and not title:
                title = text
                continue
            if level in (2, 3):
                toc.append((level, sid, text))
            body.append(f'<h{level} id="{sid}">{inline(text)}</h{level}>')
        elif kind == "p":
            body.append(f"<p>{inline(block[1])}</p>")
        elif kind == "code":
            lang, code = block[1], block[2]
            label = esc(lang) if lang else ""
            head = f"<header><span>{label}</span></header>" if label else ""
            body.append(
                f'<figure class="listing">{head}<pre><code>{highlight(code, lang)}</code></pre></figure>'
            )
        elif kind == "list":
            ordered, items = block[1], block[2]
            tag = "ol" if ordered else "ul"
            lis = "".join(f"<li>{inline(item)}</li>" for item in items)
            body.append(f"<{tag}>{lis}</{tag}>")
        elif kind == "quote":
            body.append(f"<blockquote><p>{inline(block[1])}</p></blockquote>")
        elif kind == "hr":
            body.append("<hr>")
        elif kind == "table":
            body.append(render_table(block[1]))
    return title, "\n".join(body), toc, ids


def split_row(row):
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def render_table(rows):
    if len(rows) < 2:
        return ""
    header = split_row(rows[0])
    body_rows = [split_row(r) for r in rows[2:]] if re.match(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$", rows[1]) else [split_row(r) for r in rows[1:]]
    if re.match(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$", rows[1]):
        pass
    else:
        header = None
        body_rows = [split_row(r) for r in rows]
    thead = ""
    if header:
        thead = "<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead>"
    tbody = "<tbody>" + "".join(
        "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>" for row in body_rows
    ) + "</tbody>"
    return f'<div class="table-wrap"><table>{thead}{tbody}</table></div>'


def chapter_href(slug):
    if slug == "index":
        return "/guide/v0.5/"
    return f"/guide/v0.5/{slug}/"


def render_page(title, body, toc, chapters, index, edit_path, canonical):
    side_links = []
    for i, (slug, nav, _fn) in enumerate(chapters):
        current = " aria-current=\"page\"" if i == index else ""
        side_links.append(f'<a href="{chapter_href(slug)}"{current}>{esc(nav)}</a>')
    side = "\n".join(side_links)
    toc_html = ""
    if toc:
        items = []
        for level, sid, text in toc:
            cls = "toc-h3" if level == 3 else "toc-h2"
            items.append(f'<a class="{cls}" href="#{sid}">{inline(text)}</a>')
        toc_html = '<nav class="guide-toc" aria-label="On this page"><p>On this page</p>' + "".join(items) + "</nav>"
    prev_html = ""
    next_html = ""
    if index > 0:
        slug, nav, _fn = chapters[index - 1]
        prev_html = f'<a class="pager-prev" href="{chapter_href(slug)}"><span>Previous</span>{esc(nav)}</a>'
    if index + 1 < len(chapters):
        slug, nav, _fn = chapters[index + 1]
        next_html = f'<a class="pager-next" href="{chapter_href(slug)}"><span>Next</span>{esc(nav)}</a>'
    edit = f"{EDIT_BASE}/{edit_path}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}, crocket guide</title>
  <meta name="description" content="{esc(title)} in the crocket v0.5 guide.">
  <meta name="theme-color" content="#f4f0e6">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="stylesheet" href="/style.css">
  <script src="/theme.js"></script>
</head>
<body>
  <a class="skip" href="#content">Skip to content</a>
  <header class="site-header">
    <div class="wrap top">
      <a class="brand" href="/">
        <svg class="mark" viewBox="0 0 32 32" aria-hidden="true">
          <path class="arc" d="M6 23c5.5-11 11-12 20-6"/>
          <circle class="dot" cx="25" cy="16.2" r="2.1"/>
        </svg>
        crocket
      </a>
      <nav class="nav" aria-label="Site">
        <a href="/#features">Features</a>
        <a href="/guide/" aria-current="page">Guide</a>
        <a href="https://github.com/sean3z/crocket/releases/tag/0.5.1">0.5.1</a>
        <a href="https://todo.crocket.dev">Demo</a>
        <a href="https://github.com/sean3z/crocket">GitHub</a>
        <button type="button" id="theme" aria-pressed="false">Dark mode</button>
      </nav>
    </div>
  </header>
  <div class="guide-shell" id="content">
    <nav class="guide-side" aria-label="Chapters">
      <p class="guide-version">Guide v0.5</p>
      {side}
    </nav>
    <details class="guide-side-mobile">
      <summary>Chapters</summary>
      <nav aria-label="Chapters">
        {side}
      </nav>
    </details>
    {toc_html}
    <article class="guide-main">
      <p class="kicker">Guide · v0.5</p>
      <h1>{inline(title)}</h1>
      {body}
      <nav class="pager" aria-label="Chapter">{prev_html}{next_html}</nav>
      <p class="edit"><a href="{esc(edit)}">Edit this page</a></p>
    </article>
  </div>
  <footer class="site-footer">
    <div class="wrap">
      <p>Served by crocket. This guide was checked against commit <a href="https://github.com/sean3z/crocket/commit/{COMMIT}">{COMMIT_SHORT}</a>.</p>
      <p><a href="https://github.com/sean3z/crocket/blob/{COMMIT}/LICENSE">MIT</a></p>
    </div>
  </footer>
</body>
</html>
"""


def write_cpp(assets):
    """assets: list of (url_path, file_path relative to src/)."""
    lines = [
        "// Generated by tools/build_guide.py. Do not edit.",
        '#include "guide_assets.hpp"',
        "",
        "namespace site_assets {",
        "",
    ]
    for i, (_url, rel) in enumerate(assets):
        lines.append(f"static constexpr unsigned char g{i}[] = {{")
        lines.append(f'#embed "{rel}"')
        lines.append("};")
        lines.append("")
    lines.append("void add_guide(std::vector<crocket::Asset>& assets,")
    lines.append("               std::vector<crocket::HeaderRule>& headers,")
    lines.append("               const std::string& csp) {")
    for i, (url, _rel) in enumerate(assets):
        lines.append(f'  assets.push_back(crocket::asset("{url}", g{i}));')
    globs = sorted({glob_for(url) for url, _rel in assets})
    for glob in globs:
        lines.append("  headers.push_back(crocket::HeaderRule{")
        lines.append(f'      "{glob}",')
        lines.append('      {{"content-security-policy", csp}}});')
    lines.append("}")
    lines.append("")
    lines.append("}  // namespace site_assets")
    lines.append("")
    CPP.parent.mkdir(parents=True, exist_ok=True)
    CPP.write_text("\n".join(lines), encoding="utf-8")


def glob_for(url_path):
    parent, name = url_path.rsplit("/", 1) if "/" in url_path else ("", url_path)
    if not parent:
        return f"*.{name.rsplit('.', 1)[-1]}"
    return f"{parent}/*.{name.rsplit('.', 1)[-1]}"


def collect_ids(html_text):
    return set(re.findall(r'\sid="([^"]+)"', html_text))


def check_links(pages):
    """pages: path -> html text. Also scan the hand-written site pages."""
    known = {}
    for path, text in pages.items():
        known[path] = collect_ids(text)
    for extra in (ROOT / "web" / "index.html", ROOT / "web" / "404.html"):
        if extra.exists():
            known[extra] = collect_ids(extra.read_text(encoding="utf-8"))
    broken = []
    targets = [ROOT / "web" / "index.html", ROOT / "web" / "404.html", *pages.keys()]
    for path in targets:
        text = path.read_text(encoding="utf-8") if path.exists() else pages.get(path, "")
        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            if href.startswith("#"):
                anchor = href[1:]
                if anchor and anchor not in known.get(path, ()):
                    broken.append(f"{path}: missing anchor {href}")
                continue
            url, _, anchor = href.partition("#")
            if not url.startswith("/"):
                broken.append(f"{path}: relative link {href}")
                continue
            file = url_to_file(url)
            if file is None or not file.exists():
                broken.append(f"{path}: missing {href}")
                continue
            if anchor and anchor not in known.get(file, collect_ids(file.read_text(encoding="utf-8"))):
                broken.append(f"{path}: missing anchor {href}")
    return broken


def url_to_file(url):
    if url == "/":
        return ROOT / "web" / "index.html"
    path = url[1:]
    if path.startswith("guide/"):
        rel = path[len("guide/"):]
        if rel.endswith("/") or rel == "":
            return WEB / rel / "index.html"
        return WEB / rel
    candidate = ROOT / "web" / path
    return candidate


def main():
    missing = [name for _s, _n, name in CHAPTERS if not (GUIDE / name).exists()]
    if missing:
        sys.exit("missing guide markdown: " + ", ".join(missing))
    if WEB.exists():
        for old in WEB.rglob("*.html"):
            old.unlink()
    pages = {}
    assets = []
    for index, (slug, _nav, filename) in enumerate(CHAPTERS):
        md = (GUIDE / filename).read_text(encoding="utf-8")
        title, body, toc, _ids = render_blocks(parse(md))
        if not title:
            sys.exit(f"{filename} needs an h1")
        href = chapter_href(slug)
        canonical = "https://crocket.dev" + href
        edit = f"guide/v0.5/{filename}"
        page = render_page(title, body, toc, CHAPTERS, index, edit, canonical)
        rel = "v0.5/index.html" if slug == "index" else f"v0.5/{slug}/index.html"
        out = WEB / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        pages[out] = page
        assets.append((f"guide/{rel}", "../web/guide/" + rel))
        if slug == "index":
            home = WEB / "index.html"
            home.write_text(page, encoding="utf-8")
            pages[home] = page
            assets.append(("guide/index.html", "../web/guide/index.html"))
    write_cpp(assets)
    broken = check_links(pages)
    if broken:
        print("\n".join(broken), file=sys.stderr)
        sys.exit(f"{len(broken)} broken internal link(s)")
    # The pages must not carry inline scripts or style attributes.
    for path, text in pages.items():
        if re.search(r"<style[\s>]|style=", text):
            sys.exit(f"{path} has an inline style")
        scripts = re.findall(r"<script\b([^>]*)>", text)
        for attrs in scripts:
            if "src=" not in attrs:
                sys.exit(f"{path} has an inline script")
    print(f"rendered {len(CHAPTERS)} chapters, {len(assets)} html files")


if __name__ == "__main__":
    main()
