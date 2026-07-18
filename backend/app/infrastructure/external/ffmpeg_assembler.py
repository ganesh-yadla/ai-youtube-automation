"""ffmpeg-based implementation of VideoAssemblerInterface.

Verified against a real ffmpeg 8.1.2 render on Windows (5-segment script,
real Gemini images + real Gemini TTS audio -> a valid 1080x1920 h264/aac
mp4). Three real bugs were found and fixed during that verification, not
just theorized:

1. Windows absolute paths (e.g. C:/Users/...) break ffmpeg's filtergraph
   parser even inside single-quoted option values, because ':' is a
   filtergraph delimiter and the drive-letter colon isn't protected by the
   quoting the way a mid-string colon would be. `_escape_filter_path`
   escapes ':' as '\\:' for any path embedded in a filter string
   (`textfile=`, `fontfile=`) - not needed for paths passed as plain -i
   arguments, which aren't parsed as filtergraph syntax.
2. This ffmpeg build has Fontconfig enabled but unconfigured on Windows,
   so drawtext's automatic default-font resolution crashes the process
   outright ("Fontconfig error: Cannot load default config file") instead
   of failing gracefully. An explicit `font_file` is required on such
   platforms - wired via `Settings.video_font_file` - and left unset on
   platforms where ffmpeg resolves a default font on its own (most Linux
   builds via a working fontconfig).
3. drawtext never wraps long lines on its own - a full-sentence caption
   ran off the right edge of the frame, cut off mid-word. `_wrap_caption`
   greedily wraps at word boundaries before the text ever reaches ffmpeg,
   and `y=h-text_h-100` (rather than a fixed y) anchors the block's bottom
   margin so it grows upward as more lines are added instead of overflowing
   past the bottom of the frame.

`render_thumbnail` exists because AI-generated images render text as pixel
shapes, not real typography - a real thumbnail generated with "isn't" in
the prompt came back as "IS'N'T". VideoService now generates a clean
background image with no text requested, then this method burns the real,
correctly-spelled title onto it via drawtext, reusing the same
_wrap_caption/_escape_filter_path helpers already proven reliable above.

Security: builds the argument list for asyncio.create_subprocess_exec
directly (never shell=True, never a shell string), so there is no shell-
injection surface regardless of what an AI-generated caption contains.
Caption text is written to a temp file and referenced via drawtext's
`textfile` parameter rather than embedded in the filter string - ffmpeg's
filtergraph syntax treats colons, single quotes, and backslashes as
delimiters, and natural-language captions routinely contain all three.

In-video captions highlight numbers/emphasis words in a different color
(the pattern that's actually winning on competing thumbnails - bold
colored numbers, not uniform white text). A single `drawtext` filter can
only paint one fontcolor, so this started as one drawtext filter per word
with pre-computed pixel positions - but a real render caught a real bug:
per-word drawtext filters don't share a baseline. Each word's `y` positions
that word's own ink bounding box, and a word with no ascenders/descenders
(e.g. "one") gets a visibly smaller box than a neighboring word with tall
letters (e.g. "week"), so it renders smaller and higher - not a fixed
offset, so there's no per-word fudge that fixes it in general. Captions are
now composited instead: `_render_caption_overlay` draws every word onto one
transparent PNG via Pillow, anchored to a shared font baseline
(`anchor="ls"`), and that PNG is overlaid onto the scaled frame with
ffmpeg's `overlay` filter. Bonus: caption text no longer touches ffmpeg's
filtergraph parser at all, which removes an entire class of escaping bugs
(see bug #1 below) for this path.

`_layout_caption` still does the pixel-accurate word-wrap/positioning math
(via the same font metrics), it just feeds Pillow now instead of feeding
one drawtext filter per word.
"""

import asyncio
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.infrastructure.external.interfaces.video_assembler import VideoScene

_VIDEO_WIDTH = 1080
_VIDEO_HEIGHT = 1920
_CAPTION_FONTSIZE = 56
_CAPTION_COLOR = (255, 255, 255, 255)
_CAPTION_HIGHLIGHT_COLOR = (0, 224, 255, 255)  # brand accent cyan - numbers/emphasis words
_CAPTION_STROKE_COLOR = (0, 0, 0, 255)
_CAPTION_STROKE_WIDTH = 3
_CAPTION_SIDE_MARGIN = 60
_CAPTION_BOTTOM_MARGIN = 100
_THUMBNAIL_FONTSIZE = 90
_THUMBNAIL_MAX_CHARS_PER_LINE = 16
_HIGHLIGHT_PATTERN = re.compile(r"\d|%|\$")
# Arial (and most system fonts we'd point `font_file` at) has no emoji
# glyphs - a real generated title containing "📝💻" rendered as visible tofu
# boxes on the thumbnail (confirmed via a real render, not theorized). LLMs
# routinely add emoji for YouTube-style flair, so strip them before any text
# reaches drawtext/Pillow rather than relying on the prompt to never ask.
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001f300-\U0001faff"  # pictographs, emoticons, transport, supplemental symbols
    "\U00002600-\U000027bf"  # misc symbols and dingbats
    "\U0001f1e6-\U0001f1ff"  # regional indicator letters (flag emoji)
    "\U0000fe00-\U0000fe0f"  # variation selectors
    "]+"
)


class FFmpegVideoAssembler:
    def __init__(self, font_file: str | None = None) -> None:
        # None omits `fontfile` from the drawtext filter, relying on
        # ffmpeg's own default font resolution (fontconfig on most Linux
        # builds). Pass an explicit path here if that doesn't work when
        # ffmpeg is actually installed and tested.
        self._font_file = font_file

    async def assemble(self, scenes: list[VideoScene], output_path: str) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            clip_paths: list[Path] = []

            for index, scene in enumerate(scenes):
                clip_path = tmp_path / f"clip_{index}.mp4"
                await self._render_scene(scene, tmp_path, index, clip_path)
                clip_paths.append(clip_path)

            concat_list_path = tmp_path / "concat_list.txt"
            concat_list_path.write_text(
                "\n".join(f"file '{clip.as_posix()}'" for clip in clip_paths), encoding="utf-8"
            )

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            await self._concatenate(concat_list_path, Path(output_path))

    async def _render_scene(self, scene: VideoScene, tmp_path: Path, index: int, output_path: Path) -> None:
        overlay_path = tmp_path / f"caption_overlay_{index}.png"
        self._render_caption_overlay(scene.caption_text, self._font_file, _CAPTION_FONTSIZE, overlay_path)

        filter_complex = (
            f"[0:v]scale={_VIDEO_WIDTH}:{_VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={_VIDEO_WIDTH}:{_VIDEO_HEIGHT}[bg];[bg][1:v]overlay=0:0[outv]"
        )
        args = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            scene.image_path,
            "-i",
            str(overlay_path),
            "-i",
            scene.audio_path,
            "-filter_complex",
            filter_complex,
            "-map",
            "[outv]",
            "-map",
            "2:a",
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            str(output_path),
        ]
        await self._run(args)

    @staticmethod
    def _render_caption_overlay(text: str, font_file: str | None, font_size: int, output_path: Path) -> None:
        placements = FFmpegVideoAssembler._layout_caption(
            text,
            font_file=font_file,
            font_size=font_size,
            max_width=_VIDEO_WIDTH - 2 * _CAPTION_SIDE_MARGIN,
            bottom_margin=_CAPTION_BOTTOM_MARGIN,
        )
        image = Image.new("RGBA", (_VIDEO_WIDTH, _VIDEO_HEIGHT), (0, 0, 0, 0))
        if placements:
            font = (
                ImageFont.truetype(font_file, font_size)
                if font_file
                else ImageFont.load_default(font_size)
            )
            draw = ImageDraw.Draw(image)
            ascent, _descent = font.getmetrics()
            for word, x, line_top_y, is_highlight in placements:
                color = _CAPTION_HIGHLIGHT_COLOR if is_highlight else _CAPTION_COLOR
                draw.text(
                    (x, line_top_y + ascent),
                    word,
                    font=font,
                    fill=color,
                    stroke_width=_CAPTION_STROKE_WIDTH,
                    stroke_fill=_CAPTION_STROKE_COLOR,
                    anchor="ls",
                )
        image.save(output_path)

    async def render_thumbnail(self, image_path: str, text: str, output_path: str) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            text_file = tmp_path / "thumbnail_text.txt"
            wrapped_text = self._wrap_caption(self._strip_emoji(text), _THUMBNAIL_MAX_CHARS_PER_LINE)
            text_file.write_text(wrapped_text, encoding="utf-8")

            text_path = self._escape_filter_path(text_file.as_posix())
            escaped_font_file = self._escape_filter_path(self._font_file) if self._font_file else None
            fontfile_part = f":fontfile='{escaped_font_file}'" if escaped_font_file else ""
            drawtext = (
                f"drawtext=textfile='{text_path}'{fontfile_part}:"
                f"fontcolor=white:fontsize={_THUMBNAIL_FONTSIZE}:borderw=6:bordercolor=black:"
                "x=(w-text_w)/2:y=(h-text_h)/2"
            )
            video_filter = (
                f"scale={_VIDEO_WIDTH}:{_VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={_VIDEO_WIDTH}:{_VIDEO_HEIGHT},{drawtext}"
            )

            resolved_output_path = Path(output_path)
            resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
            args = [
                "ffmpeg",
                "-y",
                "-i",
                image_path,
                "-vf",
                video_filter,
                "-frames:v",
                "1",
                str(resolved_output_path),
            ]
            await self._run(args)

    async def _concatenate(self, concat_list_path: Path, output_path: Path) -> None:
        args = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list_path),
            "-c",
            "copy",
            str(output_path),
        ]
        await self._run(args)

    @staticmethod
    def _layout_caption(
        text: str,
        font_file: str | None,
        font_size: int,
        max_width: int,
        bottom_margin: int,
    ) -> list[tuple[str, int, int, bool]]:
        """Lays out `text` into (word, x, y, is_highlight) placements, wrapped
        to `max_width` pixels and bottom-anchored so the block grows upward
        as lines are added - the same anchoring `_render_scene` used to get
        from ffmpeg's `y=h-text_h-100`, now computed here since ffmpeg can no
        longer measure the whole block itself (each word is its own filter).
        """
        font = ImageFont.truetype(font_file, font_size) if font_file else ImageFont.load_default(font_size)
        measure_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        space_width = measure_draw.textlength(" ", font=font)
        ascent, descent = font.getmetrics()
        line_height = int((ascent + descent) * 1.3)

        lines: list[list[str]] = [[]]
        line_widths: list[float] = [0.0]
        for word in FFmpegVideoAssembler._strip_emoji(text).split():
            word_width = measure_draw.textlength(word, font=font)
            current_words = lines[-1]
            added_width = (space_width if current_words else 0) + word_width
            if current_words and line_widths[-1] + added_width > max_width:
                lines.append([word])
                line_widths.append(word_width)
            else:
                current_words.append(word)
                line_widths[-1] += added_width

        if not lines[0]:
            return []

        block_height = len(lines) * line_height
        start_y = _VIDEO_HEIGHT - bottom_margin - block_height

        placements: list[tuple[str, int, int, bool]] = []
        for line_index, words in enumerate(lines):
            line_y = start_y + line_index * line_height
            cursor_x = (_VIDEO_WIDTH - line_widths[line_index]) / 2
            for word in words:
                is_highlight = FFmpegVideoAssembler._is_highlight_word(word)
                placements.append((word, round(cursor_x), round(line_y), is_highlight))
                cursor_x += measure_draw.textlength(word, font=font) + space_width
        return placements

    @staticmethod
    def _strip_emoji(text: str) -> str:
        return _EMOJI_PATTERN.sub("", text)

    @staticmethod
    def _is_highlight_word(word: str) -> bool:
        # Numbers/currency/percent (the pattern that's actually winning on
        # competing thumbnails - "$77,675", "22,000", "4000 Watch Hours")
        # plus ALL-CAPS words the script deliberately emphasized.
        stripped = word.strip(".,!?;:\"'()")
        if _HIGHLIGHT_PATTERN.search(stripped):
            return True
        # 3+ letters, not 2 - excludes common short acronyms like "AI"/"TV"
        # that would otherwise get flagged on nearly every caption in this
        # niche, diluting the highlight into meaninglessness.
        return len(stripped) >= 3 and stripped.isalpha() and stripped.isupper()

    @staticmethod
    def _wrap_caption(text: str, max_chars_per_line: int) -> str:
        # drawtext never wraps long lines on its own - without this, a
        # caption longer than the frame width just runs off the right edge
        # (confirmed via a real render: "3-step digital minimali..." was
        # cut off mid-word). Greedy word wrap, paired with y=h-text_h-100
        # in _render_scene so the block grows upward instead of overflowing
        # the bottom of the frame as more lines are added.
        lines: list[str] = []
        current_line = ""
        for word in text.split():
            candidate = f"{current_line} {word}".strip()
            if len(candidate) > max_chars_per_line and current_line:
                lines.append(current_line)
                current_line = word
            else:
                current_line = candidate
        if current_line:
            lines.append(current_line)
        return "\n".join(lines)

    @staticmethod
    def _escape_filter_path(path: str) -> str:
        # ffmpeg's filtergraph parser treats ':' as a delimiter even inside
        # single-quoted option values - a real problem on Windows, where
        # every absolute path starts with a drive letter followed by ':'
        # (e.g. C:/Users/...). Confirmed via a real failing run: without
        # this escape, ffmpeg's parser cuts the value off right after the
        # drive letter and fails with "No option name near ...".
        return path.replace(":", "\\:")

    @staticmethod
    async def _run(args: list[str]) -> None:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            error_output = stderr.decode(errors="replace")[-2000:]
            raise RuntimeError(f"ffmpeg failed (exit {process.returncode}): {error_output}")
