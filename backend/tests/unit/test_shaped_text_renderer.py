"""Unit tests for ShapedTextRenderer's wrap/measurement logic.

Uses a real Windows system font (guaranteed present, unlike a bundled test
fixture) since HarfBuzz/FreeType both need to read real font bytes to
shape/rasterize anything - there's no meaningful way to fake this at the
unit level, matching the pattern already used elsewhere in this codebase
for other real-font/real-infra dependent code (piper_client, etc).

Doesn't re-test Telugu-specific shaping correctness here - that was
verified via direct, visual, real-render comparison against the exact
phrase that was previously broken (see project history / PR description),
not something a pixel-diff-free unit test can meaningfully assert.
"""

from app.infrastructure.external.shaped_text_renderer import ShapedTextRenderer

_FONT_PATH = "C:/Windows/Fonts/arial.ttf"


def _renderer(font_size: int = 40) -> ShapedTextRenderer:
    return ShapedTextRenderer(_FONT_PATH, font_size)


def test_text_width_increases_with_more_characters():
    renderer = _renderer()

    assert renderer.text_width("hi") < renderer.text_width("hello there")


def test_text_width_empty_string_is_zero():
    renderer = _renderer()

    assert renderer.text_width("") == 0


def test_wrap_short_text_stays_on_one_line():
    renderer = _renderer()

    lines = renderer.wrap("Short caption.", max_width=2000)

    assert lines == ["Short caption."]


def test_wrap_long_text_breaks_into_multiple_lines_preserving_words():
    renderer = _renderer()
    text = "This is a fairly long caption that should not fit on a single line at this width"

    lines = renderer.wrap(text, max_width=200)

    assert len(lines) > 1
    assert " ".join(lines) == text


def test_wrap_never_splits_a_single_word_even_if_it_exceeds_the_limit():
    renderer = _renderer()

    lines = renderer.wrap("supercalifragilisticexpialidocious is long", max_width=10)

    assert lines[0] == "supercalifragilisticexpialidocious"


def test_wrap_empty_string_returns_no_lines():
    renderer = _renderer()

    assert renderer.wrap("", max_width=2000) == []


def test_render_produces_canvas_of_requested_size_with_visible_pixels():
    renderer = _renderer(font_size=60)

    image = renderer.render("Hello world", canvas_size=(800, 400), max_width=700)

    assert image.size == (800, 400)
    assert image.mode == "RGBA"
    # Something was actually drawn - not every pixel fully transparent.
    alpha_channel = image.getchannel("A")
    assert alpha_channel.getextrema()[1] > 0


def test_render_empty_text_returns_fully_transparent_canvas():
    renderer = _renderer()

    image = renderer.render("", canvas_size=(400, 200), max_width=300)

    alpha_channel = image.getchannel("A")
    assert alpha_channel.getextrema() == (0, 0)
