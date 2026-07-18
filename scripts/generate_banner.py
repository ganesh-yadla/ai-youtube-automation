"""One-off script: generates the AI World YouTube channel banner (channel art).

Rendered directly with Pillow/numpy at YouTube's max recommended banner size
(2560x1440), with the logo + wordmark kept inside the "safe area" (the
center 1546x423 box) since YouTube crops the banner differently across TV,
desktop, and mobile - anything outside that box can get cut off.
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 2560, 1440
CENTER_X, CENTER_Y = WIDTH // 2, HEIGHT // 2
SAFE_W, SAFE_H = 1546, 423
OUTPUT_PATH = Path(__file__).parent.parent / "ai_world_banner.png"

# Same palette as the logo, for a consistent brand.
COLOR_START = np.array([45, 12, 90])  # deep violet
COLOR_END = np.array([255, 32, 130])  # vivid magenta
RING_COLOR = (255, 255, 255, 160)
SATELLITE_COLOR = (0, 224, 255)
TEXT_COLOR = (255, 255, 255, 255)
SHADOW_COLOR = (0, 0, 0, 90)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\ariblk.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\impact.ttf",
]


def _load_bold_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _diagonal_gradient(width: int, height: int) -> Image.Image:
    x = np.linspace(0, 1, width)
    y = np.linspace(0, 1, height)
    xv, yv = np.meshgrid(x, y)
    t = ((xv + yv) / 2)[:, :, None]
    rgb = (COLOR_START + (COLOR_END - COLOR_START) * t).astype(np.uint8)
    return Image.fromarray(rgb, mode="RGB").convert("RGBA")


def main() -> None:
    image = _diagonal_gradient(WIDTH, HEIGHT)
    draw = ImageDraw.Draw(image, "RGBA")

    safe_left = CENTER_X - SAFE_W // 2
    safe_right = CENTER_X + SAFE_W // 2
    safe_top = CENTER_Y - SAFE_H // 2
    safe_bottom = CENTER_Y + SAFE_H // 2

    # Icon: small AI-monogram medallion, left side of the safe area.
    icon_r = SAFE_H // 2 - 10
    icon_cx = safe_left + icon_r + 20
    icon_cy = CENTER_Y

    ring_r = icon_r - 8
    draw.ellipse(
        [icon_cx - ring_r, icon_cy - ring_r, icon_cx + ring_r, icon_cy + ring_r],
        outline=RING_COLOR,
        width=6,
    )
    dot_r = 14
    dot_x, dot_y = icon_cx + ring_r * 0.7, icon_cy - ring_r * 0.6
    draw.ellipse([dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r], fill=SATELLITE_COLOR)

    icon_font = _load_bold_font(int(icon_r * 1.1))
    icon_bbox = draw.textbbox((0, 0), "AI", font=icon_font)
    icon_w, icon_h = icon_bbox[2] - icon_bbox[0], icon_bbox[3] - icon_bbox[1]
    icon_x = icon_cx - icon_w / 2 - icon_bbox[0]
    icon_y = icon_cy - icon_h / 2 - icon_bbox[1]
    draw.text((icon_x + 3, icon_y + 4), "AI", font=icon_font, fill=SHADOW_COLOR)
    draw.text((icon_x, icon_y), "AI", font=icon_font, fill=TEXT_COLOR)

    # Wordmark: "AI WORLD", right of the icon, vertically centered in the safe area.
    wordmark_font = _load_bold_font(150)
    text = "AI WORLD"
    text_bbox = draw.textbbox((0, 0), text, font=wordmark_font)
    text_w, text_h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
    text_x = icon_cx + icon_r + 50
    text_y = CENTER_Y - text_h / 2 - text_bbox[1]
    draw.text((text_x + 5, text_y + 6), text, font=wordmark_font, fill=SHADOW_COLOR)
    draw.text((text_x, text_y), text, font=wordmark_font, fill=TEXT_COLOR)

    image.convert("RGB").save(OUTPUT_PATH)
    print(f"Saved banner to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
