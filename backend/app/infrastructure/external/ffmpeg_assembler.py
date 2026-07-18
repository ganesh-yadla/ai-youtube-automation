"""ffmpeg-based implementation of VideoAssemblerInterface.

Verified against a real ffmpeg 8.1.2 render on Windows (5-segment script,
real Gemini images + real Gemini TTS audio -> a valid 1080x1920 h264/aac
mp4). Two real bugs were found and fixed during that verification, not
just theorized:

1. Windows absolute paths (e.g. C:/Users/...) break ffmpeg's filtergraph
   parser even inside single-quoted option values, because ':' is a
   filtergraph delimiter and the drive-letter colon isn't protected by the
   quoting the way a mid-string colon would be. No longer a live concern
   in this file specifically - every path here is now passed as a plain
   -i argument or built into a filter_complex via numbered stream labels
   ([0:v], [1:v]), never interpolated into a filter option string - but
   worth remembering if a future change adds one back.
2. This ffmpeg build has Fontconfig enabled but unconfigured on Windows,
   so drawtext's automatic default-font resolution crashes the process
   outright ("Fontconfig error: Cannot load default config file") instead
   of failing gracefully. An explicit `font_file` is required on such
   platforms - wired via `Settings.video_font_file`.

In-video captions are NOT burned into the frame (a previous version did
this - removed). They're uploaded as a real YouTube caption track instead
(see PublishService), which sidesteps a real rendering-correctness bug
found in this burned-in approach: Telugu (and other complex/Indic scripts)
requires proper text shaping that neither Pillow nor this project's ffmpeg
build provide correctly - see shaped_text_renderer.py's docstring for the
direct testing that confirmed this. `_render_scene` is now just
scale+crop, no text compositing.

`render_thumbnail` still burns text in, because a thumbnail IS a single
image with a title baked into its pixels - that's unavoidable, unlike
captions. It uses `ShapedTextRenderer` (HarfBuzz shaping + FreeType
rasterization) rather than ffmpeg's drawtext, for the same complex-script
correctness reason above. The rendered text is composited onto the
background via a transparent PNG overlay and ffmpeg's `overlay` filter,
not embedded in a filtergraph string.

Security: builds the argument list for asyncio.create_subprocess_exec
directly (never shell=True, never a shell string), so there is no shell-
injection surface regardless of what an AI-generated title contains.
"""

import asyncio
import re
import tempfile
from pathlib import Path

from app.infrastructure.external.interfaces.video_assembler import VideoScene
from app.infrastructure.external.shaped_text_renderer import ShapedTextRenderer

_VIDEO_WIDTH = 1080
_VIDEO_HEIGHT = 1920
_THUMBNAIL_FONTSIZE = 90
_THUMBNAIL_SIDE_MARGIN = 60
_THUMBNAIL_STROKE_WIDTH = 6
# Arial (and most system fonts we'd point `font_file` at) has no emoji
# glyphs - a real generated title containing "📝💻" rendered as visible tofu
# boxes on the thumbnail (confirmed via a real render, not theorized). LLMs
# routinely add emoji for YouTube-style flair, so strip them before any text
# reaches the renderer rather than relying on the prompt to never ask.
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
                await self._render_scene(scene, clip_path)
                clip_paths.append(clip_path)

            concat_list_path = tmp_path / "concat_list.txt"
            concat_list_path.write_text(
                "\n".join(f"file '{clip.as_posix()}'" for clip in clip_paths), encoding="utf-8"
            )

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            await self._concatenate(concat_list_path, Path(output_path))

    async def _render_scene(self, scene: VideoScene, output_path: Path) -> None:
        video_filter = (
            f"scale={_VIDEO_WIDTH}:{_VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={_VIDEO_WIDTH}:{_VIDEO_HEIGHT}"
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
        # ffmpeg drawtext (even with text_shaping=1, HarfBuzz built in) does
        # not correctly shape complex scripts like Telugu - see
        # shaped_text_renderer.py's docstring for the direct testing that
        # confirmed this. A real font file is required (unlike the old
        # drawtext path, which could fall back to fontconfig's default);
        # this project only ever runs with VIDEO_FONT_FILE set, so this is
        # not a new practical constraint.
        if not self._font_file:
            raise RuntimeError(
                "render_thumbnail requires an explicit font_file (Settings.video_font_file) - "
                "ShapedTextRenderer needs a real font path, unlike ffmpeg's old fontconfig fallback."
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            renderer = ShapedTextRenderer(self._font_file, _THUMBNAIL_FONTSIZE)
            overlay = renderer.render(
                self._strip_emoji(text),
                canvas_size=(_VIDEO_WIDTH, _VIDEO_HEIGHT),
                max_width=_VIDEO_WIDTH - 2 * _THUMBNAIL_SIDE_MARGIN,
                stroke_width=_THUMBNAIL_STROKE_WIDTH,
            )
            overlay_path = tmp_path / "thumbnail_text_overlay.png"
            overlay.save(overlay_path)

            filter_complex = (
                f"[0:v]scale={_VIDEO_WIDTH}:{_VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={_VIDEO_WIDTH}:{_VIDEO_HEIGHT}[bg];[bg][1:v]overlay=0:0[outv]"
            )
            resolved_output_path = Path(output_path)
            resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
            args = [
                "ffmpeg",
                "-y",
                "-i",
                image_path,
                "-i",
                str(overlay_path),
                "-filter_complex",
                filter_complex,
                "-map",
                "[outv]",
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
    def _strip_emoji(text: str) -> str:
        return _EMOJI_PATTERN.sub("", text)

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
