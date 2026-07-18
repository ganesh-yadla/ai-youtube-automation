"""Builds SRT (SubRip) caption file content from a script's segment text
and the matching narration's per-segment durations.

Exists because captions are no longer burned into video frames (see
ffmpeg_assembler.py's module docstring for why - a real rendering-
correctness bug for complex scripts like Telugu). Instead, the script's
own text is uploaded as a real YouTube caption track (see PublishService),
which sidesteps that bug entirely by having YouTube's own renderer draw
the text - and lets viewers use YouTube's auto-translate on top of it.

Plain SRT, not VTT: simpler format, YouTube accepts both, and matches
segment timing exactly since each script segment corresponds 1:1 to a
narration segment with a known duration - no need for VTT-only features
(styling cues, positioning) here.
"""

from app.domain.models.script import Script
from app.domain.models.voice import VoiceNarration


def build_srt(script: Script, narration: VoiceNarration) -> str:
    entries: list[str] = []
    cursor_seconds = 0.0
    for index, (script_segment, voice_segment) in enumerate(
        zip(script.segments, narration.segments, strict=True), start=1
    ):
        start_seconds = cursor_seconds
        end_seconds = cursor_seconds + voice_segment.duration_seconds
        entries.append(
            f"{index}\n"
            f"{_format_timestamp(start_seconds)} --> {_format_timestamp(end_seconds)}\n"
            f"{script_segment.text}\n"
        )
        cursor_seconds = end_seconds
    return "\n".join(entries)


def _format_timestamp(total_seconds: float) -> str:
    total_milliseconds = round(total_seconds * 1000)
    hours, remainder_ms = divmod(total_milliseconds, 3_600_000)
    minutes, remainder_ms = divmod(remainder_ms, 60_000)
    seconds, milliseconds = divmod(remainder_ms, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
