#!/usr/bin/env python3
"""Write web/og.png, the 1200x630 share image.

Uses the site's light paper colors, the header mark, the crocket wordmark,
and the homepage tagline. No stats. Not run during the Docker build;
regenerate here and commit the PNG when the lockup should change.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "og.png"

# Light theme tokens from web/style.css :root
BG = (244, 240, 230, 255)  # --bg #f4f0e6
INK = (28, 25, 20, 255)  # --ink #1c1914
MUTED = (92, 86, 76, 255)  # --muted #5c564c
ACCENT = (12, 95, 90, 255)  # --accent #0c5f5a
WARM = (138, 61, 22, 255)  # --warm #8a3d16

WIDTH, HEIGHT = 1200, 630
TAGLINE = "Handlers are functions. Reflection does the rest."
WORDMARK = "crocket"

def find_inter() -> Path:
    """Prefer a variable Inter TTF from fontconfig, then a few known paths."""
    try:
        result = subprocess.run(
            ["fc-list", "Inter:style=Regular", "file"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            path = Path(line.split(":")[0].strip())
            if path.is_file() and "Variable" in path.name:
                return path
            if path.is_file() and path.suffix.lower() in {".ttf", ".otf"}:
                variable = path.parent / "Inter-VariableFont_opsz,wght.ttf"
                if variable.is_file():
                    return variable
    except OSError:
        pass
    for candidate in (
        Path("/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf"),
        Path("/usr/share/fonts/truetype/inter/Inter-VariableFont_opsz,wght.ttf"),
        Path.home() / ".local/share/fonts/Inter-VariableFont_opsz,wght.ttf",
    ):
        if candidate.is_file():
            return candidate
    sys.exit("need a variable Inter font to regenerate web/og.png")


def inter(size: float, weight: int) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(find_inter()), size=size)
    # opsz, wght. Optical size 32 is Inter's display range.
    font.set_variation_by_axes([32, weight])
    return font


def cubic(p0, p1, p2, p3, t):
    u = 1 - t
    return (
        u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
    )


def densify(pts, spacing):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        dist = (dx * dx + dy * dy) ** 0.5
        if dist == 0:
            continue
        n = max(1, int(dist / spacing))
        for i in range(1, n + 1):
            t = i / n
            out.append((a[0] + dx * t, a[1] + dy * t))
    return out


def render_mark(size: int) -> Image.Image:
    """The header mark (viewBox 0 0 32 32) at `size` px, light-theme colors.

    ImageMagick's SVG renderer drops this cubic, so the stroke is drawn
    directly and then downsampled.
    """
    supersample = 8
    s = 32 * supersample
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Path M6 23c5.5-11 11-12 20-6, stroke 2.4, round caps.
    p0, p1, p2, p3 = (6, 23), (11.5, 12), (17, 11), (26, 17)
    pts = [
        tuple(c * supersample for c in cubic(p0, p1, p2, p3, i / 400))
        for i in range(401)
    ]
    pts = densify(pts, spacing=0.35)
    r = (2.4 * supersample) / 2
    for x, y in pts:
        d.ellipse((x - r, y - r, x + r, y + r), fill=ACCENT)
    cx, cy, cr = 25 * supersample, 16.2 * supersample, 2.1 * supersample
    d.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=WARM)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def letter_spacing(
    draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, text: str, tracking_em: float
):
    """(glyph, x-offset) pairs. tracking_em is CSS letter-spacing in em."""
    size = font.size
    delta = tracking_em * size
    x = 0.0
    out = []
    for ch in text:
        out.append((ch, round(x)))
        x += draw.textlength(ch, font=font) + delta
    return out



def main() -> None:
    img = Image.new("RGBA", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    mark_size = 120
    mark = render_mark(mark_size)
    name_font = inter(108, 700)
    line_font = inter(36, 500)

    gap = 28
    name_bbox = draw.textbbox((0, 0), WORDMARK, font=name_font)
    name_h = name_bbox[3] - name_bbox[1]
    tag_bbox = draw.textbbox((0, 0), TAGLINE, font=line_font)
    tag_h = tag_bbox[3] - tag_bbox[1]
    row_h = max(mark_size, name_h)
    between = 36
    group_h = row_h + between + tag_h

    left = 120
    top = (HEIGHT - group_h) // 2

    mark_y = top + (row_h - mark_size) // 2
    img.alpha_composite(mark, (left, mark_y))

    name_x = left + mark_size + gap
    name_y = top + (row_h - name_h) // 2 - name_bbox[1]
    for ch, ox in letter_spacing(draw, name_font, WORDMARK, -0.04):
        draw.text((name_x + ox, name_y), ch, font=name_font, fill=INK)

    tag_x = left
    tag_y = top + row_h + between - tag_bbox[1]
    draw.text((tag_x, tag_y), TAGLINE, font=line_font, fill=MUTED)

    rgb = img.convert("RGB")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # A palette PNG stays tiny. Floyd–Steinberg keeps the antialiased stroke.
    rgb.quantize(
        colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG
    ).save(OUT, format="PNG", optimize=True)
    size = OUT.stat().st_size
    with Image.open(OUT) as check:
        w, h = check.size
        if (w, h) != (WIDTH, HEIGHT):
            sys.exit(f"{OUT} is {w}x{h}, expected {WIDTH}x{HEIGHT}")
    if size >= 300 * 1024:
        sys.exit(f"{OUT} is {size} bytes, over the 300 KB cap")
    print(f"wrote {OUT.relative_to(ROOT)} {w}x{h} {size} bytes")


if __name__ == "__main__":
    main()
