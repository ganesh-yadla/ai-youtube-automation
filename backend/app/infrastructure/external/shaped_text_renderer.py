"""Complex-script text rendering via HarfBuzz (shaping) + FreeType
(rasterization), used specifically because neither Pillow nor this
project's ffmpeg build render Telugu (and other complex/Indic scripts)
correctly.

Confirmed via direct, isolated testing, not assumed:
- Pillow's ImageDraw.text() has no complex-script shaping at all on this
  install (PIL.features.check("raqm") is False) - it substitutes glyphs
  per-codepoint with no reordering/conjunct-formation, which silently
  produces wrong-but-still-Telugu-looking output for any word with a
  consonant cluster (extremely common in ordinary Telugu, not an edge
  case). A real screenshot showed "షేన్ వార్న్" (Shane Warne) rendered as
  "ఏవన్ వరన్" - readable-looking, entirely wrong.
- ffmpeg's drawtext filter was suspected to handle this correctly (this
  build has --enable-libharfbuzz --enable-libfribidi, and text_shaping
  defaults to true) - tested directly with both the default and explicit
  text_shaping=1, and both produced the identical wrong output. Also
  tested with a second, unrelated font (Noto Sans Telugu) to rule out a
  font-specific bug - same wrong result. So ffmpeg's shaping integration
  for this script is not usable here, only its font/glyph loading is.
- Calling HarfBuzz directly via uharfbuzz (bypassing both of the above)
  shapes the exact same text correctly: 37 input codepoints produce 24
  correctly-clustered output glyphs, with real conjunct substitution
  visible in the glyph info (e.g. two glyphs sharing one input cluster).
  This module rasterizes exactly those HarfBuzz-selected glyphs via
  FreeType (a separate binding from Pillow's built-in font handling, so it
  isn't subject to the same raqm gap) rather than trusting either Pillow
  or ffmpeg to shape the text themselves.

Only used for the thumbnail background's title text. In-video captions no
longer burn text into the frame at all (see FFmpegVideoAssembler) - they
upload as a real YouTube caption track instead, which sidesteps this
entire class of bug by having YouTube's own renderer draw the text.
"""

from dataclasses import dataclass

import freetype
import uharfbuzz as hb
from PIL import Image

_LINE_HEIGHT_MULTIPLIER = 1.3


@dataclass
class _ShapedGlyph:
    bitmap_image: Image.Image
    x: float
    y: float


class ShapedTextRenderer:
    """Shapes and rasterizes text in one font/size, reusing the loaded
    HarfBuzz/FreeType font objects across multiple render() calls (font
    loading/parsing has real overhead - avoid repeating it per line).
    """

    def __init__(self, font_file: str, font_size: int) -> None:
        with open(font_file, "rb") as f:
            font_data = f.read()
        self._hb_face = hb.Face(font_data)
        self._hb_font = hb.Font(self._hb_face)
        upem = self._hb_face.upem
        self._hb_font.scale = (upem, upem)
        self._scale = font_size / upem

        self._ft_face = freetype.Face(font_file)
        self._ft_face.set_char_size(font_size * 64)
        self._ascender = self._ft_face.size.ascender / 64
        self._descender = -self._ft_face.size.descender / 64  # FreeType descender is negative

    @property
    def line_height(self) -> float:
        return (self._ascender + self._descender) * _LINE_HEIGHT_MULTIPLIER

    def _shape(self, text: str) -> list[tuple[object, object]]:
        if not text:
            # buf.guess_segment_properties() can't infer a script/direction
            # for an empty buffer, which otherwise surfaces as a confusing
            # TypeError deep inside hb.shape() - short-circuit instead.
            return []
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self._hb_font, buf)
        return list(zip(buf.glyph_infos, buf.glyph_positions, strict=True))

    def text_width(self, text: str) -> float:
        return sum(pos.x_advance for _, pos in self._shape(text)) * self._scale

    def wrap(self, text: str, max_width: float) -> list[str]:
        """Greedy word-wrap using HarfBuzz-shaped pixel widths (not
        Pillow's textlength) - splits only at word boundaries, so wrapping
        never breaks a word's internal shaping context.
        """
        words = text.split()
        if not words:
            return []
        space_width = self.text_width(" ")
        lines: list[str] = []
        current_words: list[str] = []
        current_width = 0.0
        for word in words:
            word_width = self.text_width(word)
            added_width = word_width + (space_width if current_words else 0)
            if current_words and current_width + added_width > max_width:
                lines.append(" ".join(current_words))
                current_words, current_width = [word], word_width
            else:
                current_words.append(word)
                current_width += added_width
        if current_words:
            lines.append(" ".join(current_words))
        return lines

    def render(
        self,
        text: str,
        canvas_size: tuple[int, int],
        max_width: float,
        fill: tuple[int, int, int, int] = (255, 255, 255, 255),
        stroke: tuple[int, int, int, int] = (0, 0, 0, 255),
        stroke_width: int = 3,
        bottom_margin: float | None = None,
    ) -> Image.Image:
        """Renders word-wrapped, centered text onto a transparent canvas.
        Vertically centered in the canvas if bottom_margin is None,
        otherwise bottom-anchored (block grows upward as lines are added).
        """
        lines = self.wrap(text, max_width)
        canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        if not lines:
            return canvas

        block_height = len(lines) * self.line_height
        start_y = (
            canvas_size[1] - bottom_margin - block_height
            if bottom_margin is not None
            else (canvas_size[1] - block_height) / 2
        )

        for line_index, line_text in enumerate(lines):
            shaped = self._shape(line_text)
            line_width = sum(pos.x_advance for _, pos in shaped) * self._scale
            line_x = (canvas_size[0] - line_width) / 2
            baseline_y = start_y + line_index * self.line_height + self._ascender
            self._draw_shaped_line(canvas, shaped, line_x, baseline_y, fill, stroke, stroke_width)
        return canvas

    def _draw_shaped_line(
        self,
        canvas: Image.Image,
        shaped: list[tuple[object, object]],
        start_x: float,
        baseline_y: float,
        fill: tuple[int, int, int, int],
        stroke: tuple[int, int, int, int],
        stroke_width: int,
    ) -> None:
        glyphs: list[_ShapedGlyph] = []
        cursor_x = start_x
        for info, pos in shaped:
            self._ft_face.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER)
            glyph_slot = self._ft_face.glyph
            bitmap = glyph_slot.bitmap
            if bitmap.width > 0 and bitmap.rows > 0:
                glyph_image = Image.frombytes("L", (bitmap.width, bitmap.rows), bytes(bitmap.buffer))
                glyph_x = cursor_x + glyph_slot.bitmap_left + pos.x_offset * self._scale
                glyph_y = baseline_y - glyph_slot.bitmap_top - pos.y_offset * self._scale
                glyphs.append(_ShapedGlyph(glyph_image, glyph_x, glyph_y))
            cursor_x += pos.x_advance * self._scale

        # Poor-man's outline: paste each glyph's coverage mask, offset in a
        # ring, in the stroke color first - simpler and lower-risk than
        # FreeType's FT_Stroker API, and the visual result matches what
        # Pillow's stroke_width parameter produced in the previous renderer.
        if stroke_width > 0:
            for dx, dy in self._ring_offsets(stroke_width):
                for glyph in glyphs:
                    canvas.paste(stroke, (round(glyph.x + dx), round(glyph.y + dy)), glyph.bitmap_image)
        for glyph in glyphs:
            canvas.paste(fill, (round(glyph.x), round(glyph.y)), glyph.bitmap_image)

    @staticmethod
    def _ring_offsets(width: int) -> list[tuple[int, int]]:
        return [
            (dx, dy)
            for dx in range(-width, width + 1)
            for dy in range(-width, width + 1)
            if (dx, dy) != (0, 0) and dx * dx + dy * dy <= width * width + 1
        ]
