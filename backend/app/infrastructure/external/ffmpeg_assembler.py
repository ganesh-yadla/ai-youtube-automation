"""ffmpeg-based implementation of VideoAssemblerInterface.

UNVERIFIED against a live run: ffmpeg is not installed on the machine this
was written on (confirmed via `ffmpeg -version` failing). The command
shapes below follow standard, well-documented ffmpeg practice, but the
exact drawtext font behavior in particular is environment-dependent (some
ffmpeg builds require an explicit `fontfile` or fail with "No font file
specified"). Treat this file as needing a real test render once ffmpeg is
available, not as verified the way the Gemini SDK calls are.

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
                caption_file.write_text(scene.caption_text, encoding="utf-8")

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
        fontfile_part = f":fontfile='{self._font_file}'" if self._font_file else ""
        drawtext = (
            f"drawtext=textfile='{caption_file.as_posix()}'{fontfile_part}:"
            "fontcolor=white:fontsize=56:borderw=3:bordercolor=black:"
            "x=(w-text_w)/2:y=h-300"
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
