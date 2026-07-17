"""Unit tests for FFmpegVideoAssembler's pure caption-wrapping logic.

Doesn't exercise the real ffmpeg subprocess calls (those need a real
ffmpeg binary and are covered by manual end-to-end verification instead) -
just the word-wrap helper, which is a real bug found via a real render
(a long caption ran off the right edge of the frame, uncaught by any
fake-based test since fakes don't render text at all).
"""

from app.infrastructure.external.ffmpeg_assembler import FFmpegVideoAssembler


def test_wrap_caption_short_text_stays_on_one_line():
    result = FFmpegVideoAssembler._wrap_caption("Short caption.", max_chars_per_line=28)

    assert result == "Short caption."


def test_wrap_caption_breaks_at_word_boundaries():
    text = (
        "Your brain isn't broken; it's just cluttered. Here is the "
        "3-step digital minimalism reset to reclaim your focus."
    )

    result = FFmpegVideoAssembler._wrap_caption(text, max_chars_per_line=28)
    lines = result.split("\n")

    assert len(lines) > 1
    assert all(len(line) <= 28 for line in lines)
    assert " ".join(lines).replace("\n", "") == text.replace("\n", "")


def test_wrap_caption_never_splits_a_single_word_even_if_it_exceeds_the_limit():
    result = FFmpegVideoAssembler._wrap_caption(
        "supercalifragilisticexpialidocious is long", max_chars_per_line=10
    )
    lines = result.split("\n")

    assert lines[0] == "supercalifragilisticexpialidocious"


def test_wrap_caption_empty_string_returns_empty_string():
    result = FFmpegVideoAssembler._wrap_caption("", max_chars_per_line=28)

    assert result == ""
