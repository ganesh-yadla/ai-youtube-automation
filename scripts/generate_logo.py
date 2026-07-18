"""One-off script: generates the AI World channel logo (profile picture).

Renders at full 800x800 (YouTube's recommended profile picture size) directly
with Pillow, so there's no CSS-shrink-then-rasterize trap like the banner had
earlier. Design is a monogram "AI" + orbit ring so it stays legible once
YouTube crops it to a circle and shrinks it to ~48px in the UI.
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 800
CENTER = SIZE // 2
OUTPUT_PATH = Path(__file__).parent.parent / "ai_world_logo.png"

# Deep violet -> vivid magenta, diagonal. Bold/high-contrast on purpose -
# matches what actually wins in the trending-thumbnail comparison (saturated
# color, not a muted pastel "startup" gradient).
COLOR_START = (45, 12, 90)  # deep violet
COLOR_END = (255, 32, 130)  # vivid magenta
RING_COLOR = (255, 255, 255, 140)
SATELLITE_COLOR = (0, 224, 255)  # electric cyan accent
LETTER_COLOR = (255, 255, 255, 255)
SHADOW_COLOR = (0, 0, 0, 90)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\ariblk.ttf",  # Arial Black
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\impact.ttf",
]


def _load_bold_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _draw_diagonal_gradient(size: int) -> Image.Image:
    base = Image.new("RGB", (size, size))
    pixels = base.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size)
            r = int(COLOR_START[0] + (COLOR_END[0] - COLOR_START[0]) * t)
            g = int(COLOR_START[1] + (COLOR_END[1] - COLOR_START[1]) * t)
            b = int(COLOR_START[2] + (COLOR_END[2] - COLOR_START[2]) * t)
            pixels[x, y] = (r, g, b)
    return base.convert("RGBA")


def main() -> None:
    image = _draw_diagonal_gradient(SIZE)
    draw = ImageDraw.Draw(image, "RGBA")

    # Orbit ring - kept inside the circular-crop safe zone (< ~radius 380).
    ring_radius = 300
    draw.ellipse(
        [CENTER - ring_radius, CENTER - ring_radius - 30, CENTER + ring_radius, CENTER + ring_radius + 30],
        outline=RING_COLOR,
        width=10,
    )

    # Satellite dot riding the ring, upper-right.
    angle = math.radians(-35)
    satellite_x = CENTER + ring_radius * math.cos(angle)
    satellite_y = CENTER + (ring_radius + 30) * math.sin(angle) * 0.55
    dot_r = 22
    draw.ellipse(
        [satellite_x - dot_r, satellite_y - dot_r, satellite_x + dot_r, satellite_y + dot_r],
        fill=SATELLITE_COLOR,
    )

    # Monogram "AI", centered, with a soft drop shadow for depth.
    font = _load_bold_font(320)
    text = "AI"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    text_x = CENTER - text_w / 2 - bbox[0]
    text_y = CENTER - text_h / 2 - bbox[1]

    draw.text((text_x + 8, text_y + 10), text, font=font, fill=SHADOW_COLOR)
    draw.text((text_x, text_y), text, font=font, fill=LETTER_COLOR)

    image.save(OUTPUT_PATH)
    print(f"Saved logo to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
