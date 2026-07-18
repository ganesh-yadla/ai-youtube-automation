"""Unit tests for FFmpegVideoAssembler's pure text-handling logic.

Doesn't exercise the real ffmpeg subprocess calls (those need a real
ffmpeg binary and are covered by manual end-to-end verification instead) -
just the emoji-stripping helper. Word-wrap/caption-layout tests were
removed along with the burned-in-caption feature they tested - captions
are now uploaded as a real YouTube caption track (see PublishService)
instead of being rendered into the frame at all.
"""

from app.infrastructure.external.ffmpeg_assembler import FFmpegVideoAssembler


def test_strip_emoji_removes_emoji_but_keeps_text():
    result = FFmpegVideoAssembler._strip_emoji("3 Free AI Tools That Write Blog Posts for You 📝💻")

    assert result == "3 Free AI Tools That Write Blog Posts for You "
    assert "📝" not in result
    assert "💻" not in result


def test_strip_emoji_leaves_plain_text_unchanged():
    result = FFmpegVideoAssembler._strip_emoji("Plain text with no emoji at all.")

    assert result == "Plain text with no emoji at all."
