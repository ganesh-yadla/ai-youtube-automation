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


def test_is_highlight_word_flags_numbers_currency_and_percent():
    assert FFmpegVideoAssembler._is_highlight_word("22,000")
    assert FFmpegVideoAssembler._is_highlight_word("$77,675.45")
    assert FFmpegVideoAssembler._is_highlight_word("50%")
    assert FFmpegVideoAssembler._is_highlight_word("4000")


def test_is_highlight_word_flags_all_caps_emphasis():
    assert FFmpegVideoAssembler._is_highlight_word("NEVER")
    assert FFmpegVideoAssembler._is_highlight_word("FREE.")


def test_is_highlight_word_ignores_ordinary_words():
    assert not FFmpegVideoAssembler._is_highlight_word("tools")
    # 2-letter acronyms like "AI" are common noise in this niche, not emphasis
    assert not FFmpegVideoAssembler._is_highlight_word("AI")
    assert not FFmpegVideoAssembler._is_highlight_word("Automate")


def test_layout_caption_places_every_word_and_flags_highlights():
    placements = FFmpegVideoAssembler._layout_caption(
        "I saved $500 in one week",
        font_file=None,
        font_size=40,
        max_width=900,
        bottom_margin=100,
    )

    words = [word for word, _, _, _ in placements]
    assert words == ["I", "saved", "$500", "in", "one", "week"]
    highlight_flags = {word: is_highlight for word, _, _, is_highlight in placements}
    assert highlight_flags["$500"] is True
    assert highlight_flags["saved"] is False


def test_layout_caption_wraps_to_multiple_lines_when_too_wide():
    long_text = "This is a fairly long caption that should not fit on a single line at this width"
    placements = FFmpegVideoAssembler._layout_caption(
        long_text, font_file=None, font_size=40, max_width=200, bottom_margin=100
    )

    y_values = {y for _, _, y, _ in placements}
    assert len(y_values) > 1  # multiple distinct line y-positions means it actually wrapped


def test_strip_emoji_removes_emoji_but_keeps_text():
    result = FFmpegVideoAssembler._strip_emoji("3 Free AI Tools That Write Blog Posts for You 📝💻")

    assert result == "3 Free AI Tools That Write Blog Posts for You "
    assert "📝" not in result
    assert "💻" not in result


def test_layout_caption_strips_emoji_before_layout():
    placements = FFmpegVideoAssembler._layout_caption(
        "Try this 🔥 tool now", font_file=None, font_size=40, max_width=900, bottom_margin=100
    )

    words = [word for word, _, _, _ in placements]
    assert words == ["Try", "this", "tool", "now"]


def test_layout_caption_empty_text_returns_no_placements():
    result = FFmpegVideoAssembler._layout_caption(
        "", font_file=None, font_size=40, max_width=900, bottom_margin=100
    )

    assert result == []
