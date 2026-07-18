"""Unit tests for build_srt - pure text/timing formatting, no I/O."""

from datetime import UTC, datetime
from uuid import uuid4

from app.domain.models.script import Script, ScriptSegment
from app.domain.models.voice import VoiceNarration, VoiceSegment
from app.infrastructure.external.srt_builder import build_srt


def _make_script(texts: list[str]) -> Script:
    return Script(
        id=uuid4(),
        search_id=uuid4(),
        video_idea="idea",
        title="title",
        hook=texts[0] if texts else "hook",
        segments=[ScriptSegment(text=text, visual_description="visual") for text in texts],
        cta="cta",
        ai_model_used="gemini-3.5-flash",
        created_at=datetime.now(UTC),
    )


def _make_narration(script_id, durations: list[float]) -> VoiceNarration:
    return VoiceNarration(
        id=uuid4(),
        script_id=script_id,
        segments=[
            VoiceSegment(segment_index=i, audio_file_path=f"audio/x/segment_{i}.wav", duration_seconds=d)
            for i, d in enumerate(durations)
        ],
        voice_name="Kore",
        created_at=datetime.now(UTC),
    )


def test_build_srt_produces_sequentially_numbered_entries():
    script = _make_script(["First line.", "Second line.", "Third line."])
    narration = _make_narration(script.id, [2.0, 3.0, 1.5])

    result = build_srt(script, narration)

    assert "1\n" in result
    assert "2\n" in result
    assert "3\n" in result
    assert "First line." in result
    assert "Second line." in result
    assert "Third line." in result


def test_build_srt_timestamps_are_cumulative_not_reset_per_segment():
    script = _make_script(["First.", "Second."])
    narration = _make_narration(script.id, [2.5, 3.0])

    result = build_srt(script, narration)

    assert "00:00:00,000 --> 00:00:02,500" in result
    assert "00:00:02,500 --> 00:00:05,500" in result


def test_build_srt_formats_hours_and_minutes_for_long_cumulative_time():
    # A segment starting past the 1-hour mark (via one long prior segment)
    # should format as HH:MM:SS, not overflow minutes/seconds.
    script = _make_script(["Filler.", "Late segment."])
    narration = _make_narration(script.id, [3661.0, 5.0])

    result = build_srt(script, narration)

    assert "01:01:01,000 --> 01:01:06,000" in result


def test_build_srt_empty_segments_returns_empty_string():
    script = _make_script([])
    narration = _make_narration(script.id, [])

    result = build_srt(script, narration)

    assert result == ""
