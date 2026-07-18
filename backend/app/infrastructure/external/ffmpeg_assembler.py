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
"""

import asyncio
import tempfile
from pathlib import Path

from app.infrastructure.external.interfaces.video_assembler import VideoScene

_VIDEO_WIDTH = 1080
_VIDEO_HEIGHT = 1920
_CAPTION_FONTSIZE = 56
_CAPTION_MAX_CHARS_PER_LINE = 28
_THUMBNAIL_FONTSIZE = 90
_THUMBNAIL_MAX_CHARS_PER_LINE = 16


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
                caption_file = tmp_path / f"caption_{index}.txt"
                wrapped_caption = self._wrap_caption(scene.caption_text, _CAPTION_MAX_CHARS_PER_LINE)
                caption_file.write_text(wrapped_caption, encoding="utf-8")

                clip_path = tmp_path / f"clip_{index}.mp4"
                await self._render_scene(scene, caption_file, clip_path)
                clip_paths.append(clip_path)

            concat_list_path = tmp_path / "concat_list.txt"
            concat_list_path.write_text(
                "\n".join(f"file '{clip.as_posix()}'" for clip in clip_paths), encoding="utf-8"
            )

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            await self._concatenate(concat_list_path, Path(output_path))

    async def _render_scene(self, scene: VideoScene, caption_file: Path, output_path: Path) -> None:
        caption_path = self._escape_filter_path(caption_file.as_posix())
        fontfile_part = f":fontfile='{self._escape_filter_path(self._font_file)}'" if self._font_file else ""
        drawtext = (
            f"drawtext=textfile='{caption_path}'{fontfile_part}:"
            f"fontcolor=white:fontsize={_CAPTION_FONTSIZE}:borderw=3:bordercolor=black:"
            "x=(w-text_w)/2:y=h-text_h-100"
        )
        video_filter = (
            f"scale={_VIDEO_WIDTH}:{_VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={_VIDEO_WIDTH}:{_VIDEO_HEIGHT},{drawtext}"
        )
        args = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            scene.image_path,
            "-i",
            scene.audio_path,
            "-vf",
            video_filter,
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

    async def render_thumbnail(self, image_path: str, text: str, output_path: str) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            text_file = tmp_path / "thumbnail_text.txt"
            wrapped_text = self._wrap_caption(text, _THUMBNAIL_MAX_CHARS_PER_LINE)
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
