#!/usr/bin/env python3
"""Render guide/v0.5/*.md into static HTML and a C++ embed list.

Syntax highlighting is done here. The pages ship no inline script or style.
"""

import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "guide" / "v0.5"
WEB = ROOT / "web" / "guide"
CPP = ROOT / "src" / "guide_assets.cpp"
HASHED = ROOT / "src" / "hashed"
PREVIEW = ROOT / "src" / "preview"
PARITY = ROOT / "data" / "parity-sizes.json"
BENCH = ROOT / "data" / "benchmarks.json"
FINGERPRINTS = {
    "/style.css": ROOT / "web" / "style.css",
    "/theme.js": ROOT / "web" / "theme.js",
    "/ai/exchange.js": ROOT / "web" / "ai" / "exchange.js",
    "/benchmarks/bench.css": ROOT / "web" / "benchmarks" / "bench.css",
    "/benchmarks/render.js": ROOT / "web" / "benchmarks" / "render.js",
}

# This site's repository. Edit links point at these files, not at sean3z/crocket.
EDIT_BASE = "https://github.com/sean3z/crocket.dev/edit/main"
# The patch release this site is pinned to. Guide URLs stay /guide/v0.5/.
VERSION_FILE = ROOT / "VERSION"
# Hand-written pages and guide prose use this token. The value lives only in VERSION.
RELEASE_TOKEN = "@release@"

SITE_ORIGIN = "https://crocket.dev"
OG_PNG = ROOT / "web" / "og.png"
OG_IMAGE_PATH = "/og.png"
OG_IMAGE = SITE_ORIGIN + OG_IMAGE_PATH
OG_IMAGE_ALT = "crocket: Handlers are functions. Reflection does the rest."
# 404 has no canonical URL; the others do.
HAND_PAGES = (
    (ROOT / "web" / "index.html", f"{SITE_ORIGIN}/"),
    (ROOT / "web" / "ai" / "index.html", f"{SITE_ORIGIN}/ai/"),
    (ROOT / "web" / "benchmarks" / "index.html", f"{SITE_ORIGIN}/benchmarks/"),
    (ROOT / "web" / "teapot.html", f"{SITE_ORIGIN}/teapot"),
    (ROOT / "web" / "404.html", None),
)


def load_release():
    if not VERSION_FILE.is_file():
        sys.exit("missing VERSION")
    release = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", release):
        sys.exit(f"VERSION must be one X.Y.Z line, got {release!r}")
    return release


RELEASE = load_release()


def apply_release(text):
    return text.replace(RELEASE_TOKEN, RELEASE)


def asset_versions():
    """Short content hashes so a long-cached CSS or JS URL changes when the file does."""
    versions = {}
    for url, path in FINGERPRINTS.items():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        versions[url] = digest
    return versions


def bust_assets(text, versions):
    for url, digest in versions.items():
        text = re.sub(
            rf'((?:href|src)="{re.escape(url)})(?:\?v=[0-9a-fA-F]*)?(")',
            rf"\1?v={digest}\2",
            text,
        )
    return text


def mb(nbytes):
    return f"{nbytes / 1_000_000:.1f}"

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
    ("scaling", "Scaling", "scaling.md"),
    ("migrate-express", "From Express", "migrate-express.md"),
    ("migrate-spring", "From Spring Boot", "migrate-spring.md"),
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

JS_KEYWORDS = {
    "import", "from", "export", "const", "let", "var", "function", "return", "if",
    "else", "new", "await", "async", "class", "this", "typeof", "throw", "try",
    "catch", "of",
}

CPP_TYPES = {
    "string", "string_view", "optional", "vector", "uint8_t", "uint16_t",
    "uint32_t", "uint64_t", "int8_t", "int16_t", "int32_t", "int64_t",
    "size_t", "ptrdiff_t", "byte", "string_view",
}

JAVA_KEYWORDS = {
    "package", "import", "public", "private", "protected", "class", "record",
    "interface", "extends", "implements", "return", "new", "if", "else", "static",
    "final", "void", "long", "int", "var", "throws", "try", "catch", "true", "false",
    "null",
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


def highlight_words(code, keywords):
    """Comments, strings, and a keyword set. Used for the migration pages."""
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
        ch = code[i]
        if ch in "\"'`":
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
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (code[j].isalnum() or code[j] == "_"):
                j += 1
            word = code[i:j]
            out.append(span("k", word) if word in keywords else esc(word))
            i = j
            continue
        out.append(esc(ch))
        i += 1
    return "".join(out)


def highlight(code, lang):
    lang = (lang or "").lower()
    if lang in {"cpp", "c++", "cxx", "h", "hpp"}:
        return highlight_cpp(code)
    if lang in {"sh", "bash", "shell"}:
        return highlight_shell(code)
    if lang == "json":
        return highlight_json(code)
    if lang in {"js", "javascript", "mjs"}:
        return highlight_words(code, JS_KEYWORDS)
    if lang in {"java"}:
        return highlight_words(code, JAVA_KEYWORDS)
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
        if ch.isdigit():
            j = i + 1
            while j < n and (code[j].isdigit() or code[j] in ".xXabcdefABCDEF"):
                j += 1
            out.append(span("n", code[i:j]))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (code[j].isalnum() or code[j] == "_"):
                j += 1
            word = code[i:j]
            if word in CPP_KEYWORDS:
                kind = "k"
            elif word in CPP_TYPES or (word[0].isupper() and word not in CPP_KEYWORDS):
                kind = "t"
            else:
                kind = ""
            out.append(span(kind, word))
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


def _read_fence(lines, i):
    if i >= len(lines) or not lines[i].startswith("```"):
        sys.exit("expected a code fence")
    lang = lines[i][3:].strip()
    i += 1
    buf = []
    while i < len(lines) and not lines[i].startswith("```"):
        buf.append(lines[i])
        i += 1
    if i >= len(lines):
        sys.exit(f"unclosed code fence ({lang or 'plain'})")
    i += 1
    return i, lang, "\n".join(buf)


def parse(md):
    lines = md.replace("\r\n", "\n").split("\n")
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith(":::pair"):
            label = re.match(r"^:::pair\s+(\S.*?)\s+\|\s+(\S.*?)\s*$", line)
            if not label:
                sys.exit(f"bad :::pair line: {line}")
            left_label, right_label = label.group(1), label.group(2)
            i += 1
            i, left_parts, right_parts = _read_pair(lines, i, left_label, right_label)
            blocks.append(("pair", left_label, left_parts, right_label, right_parts))
            continue
        if line.startswith(":::parity ") or line.startswith(":::numbers ") or line.startswith(":::cta"):
            kind, _, arg = line.strip().partition(" ")
            kind = kind[3:]
            i += 1
            body_lines = []
            if kind == "cta":
                while i < len(lines) and lines[i].strip() != ":::":
                    if lines[i].strip():
                        body_lines.append(lines[i].strip())
                    i += 1
                if i >= len(lines):
                    sys.exit(":::cta is missing its closing :::")
                i += 1
                blocks.append(("cta", body_lines))
            else:
                if lines[i - 1].strip() != f":::{kind} {arg}":
                    sys.exit(f"bad :::{kind} line: {line}")
                blocks.append((kind, arg.strip()))
            continue
        if line.startswith("```"):
            i, lang, code = _read_fence(lines, i)
            blocks.append(("code", lang, code))
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


def _read_pair(lines, i, left_label, right_label):
    """Fences until :::. A line that is only | starts the right column.

    Two fences and no | keep the original left, right order.
    """
    left, right = [], []
    side = left
    saw_break = False
    while i < len(lines) and lines[i].strip() != ":::":
        if not lines[i].strip():
            i += 1
            continue
        if lines[i].strip() == "|":
            if saw_break:
                sys.exit(f":::pair {left_label} | {right_label} has two column breaks")
            saw_break = True
            side = right
            i += 1
            continue
        if not lines[i].startswith("```"):
            sys.exit(f":::pair {left_label} | {right_label} expected a fence, got: {lines[i]}")
        i, lang, code = _read_fence(lines, i)
        side.append((lang, code))
    if i >= len(lines) or lines[i].strip() != ":::":
        sys.exit(f":::pair {left_label} | {right_label} is missing its closing :::")
    i += 1
    if not saw_break:
        if len(left) != 2:
            sys.exit(f":::pair {left_label} | {right_label} needs two fences, or a | between columns")
        right = [left[1]]
        left = [left[0]]
    if not left or not right:
        sys.exit(f":::pair {left_label} | {right_label} needs a fence on each side")
    return i, left, right


def _block_start(line):
    return (
        line.startswith("```")
        or line.startswith(":::")
        or line.startswith(">")
        or line.lstrip().startswith("|")
        or bool(re.match(r"^#{1,4}\s+", line))
        or line.strip() == "---"
        or bool(re.match(r"^[-*]\s+", line))
        or bool(re.match(r"^\d+\.\s+", line))
    )


def render_listing(label, lang, code):
    head = f"<header><span>{esc(label)}</span></header>" if label else ""
    return f'<figure class="listing">{head}<pre><code>{highlight(code, lang)}</code></pre></figure>'


def render_column(label, parts):
    chunks = []
    for n, (lang, code) in enumerate(parts):
        chunks.append(render_listing(label if n == 0 else "", lang, code))
    return '<div class="compare-col">' + "".join(chunks) + "</div>"


def load_json(path):
    if not path.is_file():
        sys.exit(f"missing {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def render_parity(which):
    data = load_json(PARITY)
    if which == "express":
        side = data["npm"]
        groups = []
        current = None
        for row in side["direct"]:
            if row["feature"] == "The framework":
                continue
            if current is None or current[0] != row["feature"]:
                current = [row["feature"], []]
                groups.append(current)
            current[1].append(row["name"])
        groups.append(["Static files and ETags", []])
        unit = "unpacked"
        total = side["total_unpacked_bytes"]
        count = side["package_count"]
        direct = side["direct_count"]
        label = (
            f"{direct} direct packages, {count} with the dependencies they pull in, "
            f"about {mb(total)} MB {unit}. Approx., from npm registry unpacked sizes, "
            f"{data['fetched']}. That total includes Express itself."
        )
    elif which == "spring":
        side = data["maven"]
        groups = []
        current = None
        for row in side["direct"]:
            if current is None or current[0] != row["feature"]:
                current = [row["feature"], []]
                groups.append(current)
            current[1].append(row["artifact"])
        groups.append(["Structured logging", []])
        groups.append(["CORS", []])
        groups.append(["Static files", []])
        total = side["total_jar_bytes"]
        count = side["artifact_count"]
        direct = side["direct_count"]
        label = (
            f"{direct} direct artifacts, {count} jars once the tree is deduped, "
            f"about {mb(total)} MB. Approx., from Maven Central jar sizes, {data['fetched']}."
        )
    else:
        sys.exit(f"unknown parity side: {which}")
    binary = data["crocket_binary"]
    rows = []
    for feature, names in groups:
        if names:
            shown = ", ".join(f"<code>{esc(name)}</code>" for name in names)
        elif feature == "Static files and ETags":
            shown = "none. <code>express.static</code> already does this"
        elif feature == "Static files":
            shown = "none. <code>spring-boot-starter-web</code> serves <code>classpath:/static</code>"
        elif feature == "CORS":
            shown = "none. Spring MVC already does this"
        elif feature == "Structured logging":
            shown = "none. Logback comes with <code>spring-boot-starter-web</code>"
        else:
            shown = "none"
        rows.append(f"<tr><td>{esc(feature)}</td><td>{shown}</td></tr>")
    note = (
        f"<p class=\"parity-total\">{esc(label)} "
        f"The crocket program on this page is a "
        f"{mb(binary['stripped_bytes'])} MB stripped Release binary, release {RELEASE}. "
        f"It still loads libstdc++ ({mb(binary['libstdcxx_bytes'])} MB in the GCC 16.2 toolchain).</p>"
    )
    return (
        '<div class="table-wrap"><table><thead><tr><th>Already in crocket</th>'
        "<th>What you add</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
        + note
    )


def render_numbers(rival_id):
    bench = load_json(BENCH)
    verify_benchmarks(bench)
    rival = bench["rivals"][rival_id]
    crocket = bench["crocket"]
    post = bench["post"]
    cards = [
        (
            f"{crocket['req_s']} <span>req/s</span>",
            f"vs {rival['label']}'s {rival['req_s']}",
            "Heroes CRUD, max throughput. " + rival["req_note"],
        ),
        (
            f"{crocket['peak_mb']} <span>MB</span>",
            f"vs {rival['peak_mb']} MB peak",
            f"Peak RSS. Idle was {crocket['idle_mb']} MB vs {rival['idle_mb']} MB.",
        ),
        (
            f"{crocket['cpu_us']} <span>µs</span>",
            f"vs {rival['cpu_us']} µs",
            "App CPU time per request at that max.",
        ),
        (
            f"{crocket['cores_at_4k']} <span>cores</span>",
            f"vs {rival['cores_at_4k']}",
            "Cores in use at 4,000 req/s.",
        ),
    ]
    articles = []
    for value, vs, caption in cards:
        articles.append(
            "<article class=\"stat\">"
            f"<p class=\"stat-value\">{value}</p>"
            f"<p class=\"stat-vs\">{esc(vs)}</p>"
            f"<p class=\"stat-caption\">{esc(caption)}</p>"
            "</article>"
        )
    return (
        '<div class="numbers">'
        + "".join(articles)
        + "</div>"
        + f"<p class=\"stat-foot\">{esc(bench['hardware'])} "
        + f"<a href=\"{esc(post)}\">See the full benchmark</a></p>"
    )


def verify_benchmarks(bench):
    """The homepage rotates these same strings. They have to match src/main.cpp."""
    source = (ROOT / "src" / "main.cpp").read_text(encoding="utf-8")
    needed = [
        f"{bench['crocket']['req_s']} ",
        f"{bench['crocket']['peak_mb']} <span>MB</span>",
        f"vs {bench['rivals']['node']['label']}'s {bench['rivals']['node']['req_s']}",
        f"vs {bench['rivals']['node']['label']}'s {bench['rivals']['node']['peak_mb']} MB",
        f"vs {bench['rivals']['spring']['label']}'s {bench['rivals']['spring']['req_s']}",
        f"vs {bench['rivals']['spring']['label']}'s {bench['rivals']['spring']['peak_mb']} MB",
        bench["rivals"]["node"]["req_note"],
        bench["rivals"]["spring"]["req_note"],
    ]
    missing = [item for item in needed if item not in source]
    if missing:
        sys.exit("benchmark figures drifted from src/main.cpp:\n" + "\n".join(missing))


def render_cta(lines):
    links = []
    for line in lines:
        primary = line.startswith("primary ")
        rest = line[len("primary ") :] if primary else line
        href, _, label = rest.partition(" ")
        if not href or not label:
            sys.exit(f"bad cta line: {line}")
        cls = "btn btn-primary" if primary else "btn"
        links.append(f'<a class="{cls}" href="{esc(href)}">{esc(label)}</a>')
    return '<div class="actions">' + "".join(links) + "</div>"


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
            body.append(render_listing(block[1], block[1], block[2]))
        elif kind == "pair":
            _, left_label, left_parts, right_label, right_parts = block
            body.append(
                '<div class="compare">'
                + render_column(left_label, left_parts)
                + render_column(right_label, right_parts)
                + "</div>"
            )
        elif kind == "parity":
            body.append(render_parity(block[1]))
        elif kind == "numbers":
            body.append(render_numbers(block[1]))
        elif kind == "cta":
            body.append(render_cta(block[1]))
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



def png_size(path):
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        sys.exit(f"{path} is not a PNG")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


def social_meta(title, description, canonical=None):
    """Open Graph and Twitter tags. Titles and descriptions come from the page."""
    lines = [
        f'  <meta property="og:title" content="{esc(title)}">',
        f'  <meta property="og:description" content="{esc(description)}">',
    ]
    if canonical:
        lines.append(f'  <meta property="og:url" content="{esc(canonical)}">')
    width, height = png_size(OG_PNG)
    lines += [
        '  <meta property="og:type" content="website">',
        f'  <meta property="og:image" content="{esc(OG_IMAGE)}">',
        f'  <meta property="og:image:width" content="{width}">',
        f'  <meta property="og:image:height" content="{height}">',
        f'  <meta property="og:image:alt" content="{esc(OG_IMAGE_ALT)}">',
        '  <meta name="twitter:card" content="summary_large_image">',
        f'  <meta name="twitter:title" content="{esc(title)}">',
        f'  <meta name="twitter:description" content="{esc(description)}">',
        f'  <meta name="twitter:image" content="{esc(OG_IMAGE)}">',
    ]
    return "\n".join(lines)


def html_plain(fragment):
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment or ""))
    return re.sub(r"\s+", " ", text).strip()


def first_plain_paragraph(body_html):
    match = re.search(r"<p>(.*?)</p>", body_html, re.S)
    return html_plain(match.group(1)) if match else ""


def existing_attr(html_text, pattern):
    match = re.search(pattern, html_text, re.I | re.S)
    return html.unescape(match.group(1)) if match else ""


def visible_lede(html_text):
    for cls in ("lede", "tagline"):
        match = re.search(rf'<p class="{cls}">(.*?)</p>', html_text, re.S)
        if match:
            text = html_plain(match.group(1))
            if text:
                return text
    match = re.search(r"<h1[^>]*>.*?</h1>\s*<p[^>]*>(.*?)</p>", html_text, re.S)
    return html_plain(match.group(1)) if match else ""


SOCIAL_TAG_RE = re.compile(
    r'\n?\s*<meta\s+(?:property="og:[^"]+"|name="twitter:[^"]+")\s+content="[^"]*"\s*/?>',
    re.I,
)


def inject_social(html_text, canonical):
    """Add share tags to a hand-written page from its existing title and lede."""
    html_text = SOCIAL_TAG_RE.sub("", html_text)
    title = existing_attr(html_text, r"<title>(.*?)</title>")
    if not title:
        sys.exit("a hand-written page is missing a title")
    description = existing_attr(
        html_text, r'<meta\s+name="description"\s+content="([^"]*)"'
    )
    if not description:
        description = visible_lede(html_text)
    if not description:
        sys.exit(f"could not derive a description for {title!r}")
    if not existing_attr(html_text, r'<meta\s+name="description"\s+content="([^"]*)"'):
        html_text = re.sub(
            r"(<title>.*?</title>)",
            rf'\1\n  <meta name="description" content="{esc(description)}">',
            html_text,
            count=1,
            flags=re.S,
        )
    if canonical and not re.search(r'<link\s+rel="canonical"', html_text, re.I):
        html_text = html_text.replace(
            "</head>",
            f'  <link rel="canonical" href="{esc(canonical)}">\n</head>',
            1,
        )
    return html_text.replace("</head>", social_meta(title, description, canonical) + "\n</head>", 1)


def git_lastmod(path):
    try:
        rel = path.resolve().relative_to(ROOT.resolve())
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(rel)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        date = result.stdout.strip()
        if result.returncode == 0 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            return date
    except OSError:
        pass
    return None


def read_existing_lastmods():
    path = ROOT / "web" / "sitemap.xml"
    if not path.is_file():
        return {}
    return dict(
        re.findall(
            r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>",
            path.read_text(encoding="utf-8"),
        )
    )


def public_pages():
    """Canonical URLs that belong in the sitemap, with their source files."""
    pages = [
        (f"{SITE_ORIGIN}/", ROOT / "web" / "index.html"),
        (f"{SITE_ORIGIN}/ai/", ROOT / "web" / "ai" / "index.html"),
        (f"{SITE_ORIGIN}/benchmarks/", ROOT / "web" / "benchmarks" / "index.html"),
    ]
    for slug, _nav, filename in CHAPTERS:
        pages.append((SITE_ORIGIN + chapter_href(slug), GUIDE / filename))
    return pages


def write_robots():
    (ROOT / "web" / "robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {SITE_ORIGIN}/sitemap.xml\n",
        encoding="utf-8",
    )


def write_sitemap():
    previous = read_existing_lastmods()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url, source in public_pages():
        last = git_lastmod(source) or previous.get(url)
        lines.append("  <url>")
        lines.append(f"    <loc>{esc(url)}</loc>")
        if last:
            lines.append(f"    <lastmod>{esc(last)}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")
    (ROOT / "web" / "sitemap.xml").write_text("\n".join(lines), encoding="utf-8")


def check_social(paths):
    """Every HTML page that ships should carry the share tags from social_meta."""
    problems = []
    required = (
        'property="og:title"',
        'property="og:description"',
        'property="og:type"',
        'property="og:image"',
        'property="og:image:width"',
        'property="og:image:height"',
        'property="og:image:alt"',
        'name="twitter:card"',
        'name="twitter:title"',
        'name="twitter:description"',
        'name="twitter:image"',
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        where = path.relative_to(ROOT)
        for needle in required:
            if needle not in text:
                problems.append(f"{where}: missing {needle}")
        if f'content="{OG_IMAGE}"' not in text:
            problems.append(f"{where}: og:image is not {OG_IMAGE}")
        if 'content="summary_large_image"' not in text:
            problems.append(f"{where}: twitter:card is not summary_large_image")
        if path.name != "404.html" and 'rel="canonical"' not in text:
            problems.append(f"{where}: missing canonical")
        canonical = existing_attr(text, r'<link\s+rel="canonical"\s+href="([^"]*)"')
        if canonical and f'property="og:url" content="{esc(canonical)}"' not in text:
            problems.append(f"{where}: og:url does not match canonical")
        if path.name == "404.html" and 'property="og:url"' in text:
            problems.append(f"{where}: 404 should not set og:url")
    return problems


def require_og_image():
    if not OG_PNG.is_file():
        sys.exit("missing web/og.png; run tools/gen_og.py")
    width, height = png_size(OG_PNG)
    if (width, height) != (1200, 630):
        sys.exit(f"{OG_PNG} is {width}x{height}, expected 1200x630")


def render_page(title, body, toc, chapters, index, edit_path, canonical, description):
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
  <meta name="description" content="{esc(description)}">
  <meta name="theme-color" content="#f4f0e6">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="canonical" href="{esc(canonical)}">
{social_meta(f"{title}, crocket guide", description, canonical)}
  <link rel="stylesheet" href="/style.css">
  <link rel="alternate" type="text/plain" href="/llms.txt">
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
        <a href="/ai/">AI</a>
        <a href="/benchmarks/">Benchmarks</a>
        <a href="https://github.com/sean3z/crocket/releases/tag/{RELEASE}">{RELEASE}</a>
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
      <p>Served by crocket. This guide was checked against the <a href="https://github.com/sean3z/crocket/releases/tag/{RELEASE}">{RELEASE}</a> release. <a href="/llms.txt">llms.txt</a> for assistants. Built with ❤️ and a little AI help</p>
      <p><a href="https://github.com/sean3z/crocket/blob/{RELEASE}/LICENSE">MIT</a></p>
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
    for extra in (
        ROOT / "web" / "index.html",
        ROOT / "web" / "404.html",
        ROOT / "web" / "teapot.html",
        ROOT / "web" / "ai" / "index.html",
        ROOT / "web" / "benchmarks" / "index.html",
    ):
        if extra.exists():
            known[extra] = collect_ids(extra.read_text(encoding="utf-8"))
    broken = []
    targets = [
        ROOT / "web" / "index.html",
        ROOT / "web" / "404.html",
        ROOT / "web" / "teapot.html",
        ROOT / "web" / "ai" / "index.html",
        ROOT / "web" / "benchmarks" / "index.html",
        *pages.keys(),
    ]
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
            url = url.split("?", 1)[0]
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
    if candidate.is_dir():
        return candidate / "index.html"
    return candidate


def highlight_static_cpp(path):
    """Highlight hand-written cpp listings in place. Tags are stripped first, so this is idempotent."""
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(<header><span>cpp</span></header>\s*<pre><code>)(.*?)(</code></pre>)",
        re.S,
    )

    def repl(match):
        plain = html.unescape(re.sub(r"<[^>]+>", "", match.group(2)))
        return match.group(1) + highlight_cpp(plain) + match.group(3)

    updated, count = pattern.subn(repl, text)
    if count and updated != text:
        path.write_text(updated, encoding="utf-8")
    return count


def write_llms_full():
    """One markdown file of every chapter, in guide order, from the same sources."""
    parts = [
        "# crocket guide v0.5\n\n",
        "Generated from `guide/v0.5`, in the same order as the guide. ",
        f"The samples match the `{RELEASE}` release.\n",
    ]
    for _slug, _nav, filename in CHAPTERS:
        body = apply_release((GUIDE / filename).read_text(encoding="utf-8").rstrip())
        parts.append("\n\n")
        parts.append(body)
        parts.append("\n")
    out = ROOT / "web" / "llms-full.txt"
    out.write_text("".join(parts), encoding="utf-8")
    return out


def site_file(path):
    """A built page for a site path, or None."""
    path = path.split("#", 1)[0]
    if path in ("/teapot", "/teapot/"):
        return ROOT / "web" / "teapot.html"
    if path in ("/llms.txt", "/llms-full.txt"):
        return ROOT / "web" / path.lstrip("/")
    attempts = [path]
    if path != "/" and not path.endswith("/"):
        attempts.append(path + "/")
    for attempt in attempts:
        found = url_to_file(attempt)
        if found is not None and found.is_file():
            return found
        index = ROOT / "web" / attempt.strip("/") / "index.html"
        if index.is_file():
            return index
    return None


def check_llms_links():
    """Every on-site link in the llms files must be a built page."""
    broken = []
    for name in ("llms.txt", "llms-full.txt"):
        text = (ROOT / "web" / name).read_text(encoding="utf-8")
        hrefs = re.findall(r"\]\(([^)\s]+)\)", text)
        hrefs += re.findall(r"https://crocket\.dev(/[^\s)\"]*)", text)
        for href in hrefs:
            if href.startswith(("http://", "https://")) and not href.startswith("https://crocket.dev"):
                continue
            path = href.removeprefix("https://crocket.dev") if href.startswith("https://") else href
            if not path.startswith("/"):
                continue
            if site_file(path) is None:
                broken.append(f"{name}: missing {href}")
    return broken


def main():
    require_og_image()
    missing = [name for _s, _n, name in CHAPTERS if not (GUIDE / name).exists()]
    if missing:
        sys.exit("missing guide markdown: " + ", ".join(missing))
    if WEB.exists():
        for old in WEB.rglob("*.html"):
            old.unlink()
    pages = {}
    assets = []
    for index, (slug, _nav, filename) in enumerate(CHAPTERS):
        md = apply_release((GUIDE / filename).read_text(encoding="utf-8"))
        title, body, toc, _ids = render_blocks(parse(md))
        if not title:
            sys.exit(f"{filename} needs an h1")
        href = chapter_href(slug)
        canonical = SITE_ORIGIN + href
        edit = f"guide/v0.5/{filename}"
        description = first_plain_paragraph(body)
        if not description:
            sys.exit(f"{filename} needs a lead paragraph for the page description")
        page = bust_assets(
            render_page(title, body, toc, CHAPTERS, index, edit, canonical, description),
            asset_versions(),
        )
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
    for static_page in (
        ROOT / "web" / "ai" / "index.html",
        ROOT / "web" / "teapot.html",
    ):
        if static_page.exists():
            highlight_static_cpp(static_page)
    versions = asset_versions()
    HASHED.mkdir(parents=True, exist_ok=True)
    hashed_pages = {
        ROOT / "web" / "index.html": HASHED / "index.html",
        ROOT / "web" / "404.html": HASHED / "404.html",
        ROOT / "web" / "teapot.html": HASHED / "teapot.html",
        ROOT / "web" / "ai" / "index.html": HASHED / "ai" / "index.html",
        ROOT / "web" / "benchmarks" / "index.html": HASHED / "benchmarks" / "index.html",
    }
    hand_canonical = {src.resolve(): canon for src, canon in HAND_PAGES}
    for src, dest in hashed_pages.items():
        dest.parent.mkdir(parents=True, exist_ok=True)
        filled = apply_release(bust_assets(src.read_text(encoding="utf-8"), versions))
        filled = inject_social(filled, hand_canonical[src.resolve()])
        dest.write_text(filled, encoding="utf-8")
    llms_out = HASHED / "llms.txt"
    llms_out.write_text(
        apply_release((ROOT / "web" / "llms.txt").read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    print(
        "asset fingerprints "
        + " ".join(f"{url}?v={digest}" for url, digest in versions.items())
    )
    write_llms_full()
    broken = check_links(pages)
    broken.extend(check_llms_links())
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
    write_robots()
    write_sitemap()
    write_preview()
    social_paths = list(pages.keys()) + [dest for _src, dest in hashed_pages.items()]
    social_problems = check_social(social_paths)
    if social_problems:
        sys.exit("share tags missing:\n" + "\n".join(social_problems))
    audit_release()
    print(f"rendered {len(CHAPTERS)} chapters, {len(assets)} html files, release {RELEASE}")


def write_preview():
    """Static tree for `python3 -m http.server --directory src/preview`.

    The hand-written pages keep @release@ in git. This copy is what a browser
    should open, with the same text the binary embeds.
    """
    if PREVIEW.exists():
        shutil.rmtree(PREVIEW)
    shutil.copytree(ROOT / "web", PREVIEW)
    for path in PREVIEW.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".html", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8")
        if RELEASE_TOKEN in text:
            path.write_text(apply_release(text), encoding="utf-8")
    for src, canon in HAND_PAGES:
        dest = PREVIEW / src.relative_to(ROOT / "web")
        dest.write_text(
            inject_social(dest.read_text(encoding="utf-8"), canon),
            encoding="utf-8",
        )


def audit_release():
    """VERSION is the only definition of the patch release.

    Guide URLs stay on the v0.5 series. Benchmark charts may still name the
    crocket build that produced a number. npm's `fresh` package is unrelated.
    """
    prior = "0." + "5.2"
    caveats = (
        "un" + "released",
        "queued " + "for",
        "on " + "main",
        "main " + "branch",
        "ships " + "in",
    )
    generated_roots = (WEB, HASHED, PREVIEW)
    # Measured crocket builds, plus the npm package that happens to share a number.
    # Copies under src/hashed and src/preview keep those same chart labels.
    literal_ok_files = {
        VERSION_FILE.resolve(),
        (ROOT / "web" / "llms-full.txt").resolve(),
        (ROOT / "web" / "benchmarks" / "data.json").resolve(),
    }
    problems = []
    skip_parts = {".git", "build", ".cache", "__pycache__"}

    def generated(path):
        resolved = path.resolve()
        return any(resolved.is_relative_to(root.resolve()) for root in generated_roots)

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_parts for part in path.parts):
            continue
        if path.suffix.lower() not in {
            ".md", ".html", ".txt", ".py", ".json", ".cmake", ""
        } and path.name not in {"CMakeLists.txt", "Dockerfile", "VERSION"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        where = path.relative_to(ROOT)
        if generated(path) or path.name == "llms-full.txt":
            if RELEASE_TOKEN in text:
                problems.append(f"{where} still has {RELEASE_TOKEN}")
        elif RELEASE in text and path.resolve() not in literal_ok_files:
            problems.append(f"{where} hardcodes {RELEASE}; use {RELEASE_TOKEN} or VERSION")
        rel = where.as_posix()
        prior_ok = rel in {
            "data/parity-sizes.json",
            "web/benchmarks/data.json",
            "web/benchmarks/index.html",
        } or rel.endswith("benchmarks/index.html") or rel.endswith("benchmarks/data.json")
        if prior in text and not prior_ok:
            problems.append(f"{where} still names the previous patch release")
        for needle in caveats:
            if needle in text and path.name != "build_guide.py":
                problems.append(f"{where} still has a release caveat ({needle})")
    quick = WEB / "v0.5" / "quickstart" / "index.html"
    if quick.is_file() and RELEASE not in quick.read_text(encoding="utf-8"):
        problems.append("guide quickstart was rendered without the release")
    if problems:
        sys.exit("release pin drifted:\n" + "\n".join(problems))


if __name__ == "__main__":
    main()
