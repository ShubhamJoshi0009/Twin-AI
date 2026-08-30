"""Generate frontend/public/favicon.ico matching the existing favicon.svg design.

Run from the repo root: .venv/bin/python scripts/gen_favicon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 32
OUT = Path("frontend/public/favicon.ico")


def make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Rounded-rect mask (rx=8, matching the SVG)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=8, fill=255)

    # Blue -> purple linear gradient (#3b82f6 -> #8b5cf6)
    grad = Image.new("RGBA", (size, size))
    gd = ImageDraw.Draw(grad)
    for x in range(size):
        t = x / (size - 1)
        r = round(59 + (139 - 59) * t)
        g = round(130 + (92 - 130) * t)
        b = round(246 + (246 - 246) * t)
        gd.line([(x, 0), (x, size - 1)], fill=(r, g, b, 255))
    img.paste(grad, (0, 0), mask)

    draw = ImageDraw.Draw(img)
    # Three white nodes
    for cx, cy in [(9, 9), (23, 9), (16, 23)]:
        draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(255, 255, 255, 230))
    # Connecting lines
    draw.line([(9, 9), (16, 23)], fill=(255, 255, 255, 140), width=2)
    draw.line([(23, 9), (16, 23)], fill=(255, 255, 255, 140), width=2)
    return img


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Multiple sizes so small favicon probes get a crisp icon
    make_icon(32).save(OUT, format="ICO", sizes=[(16, 16), (32, 32)])
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
