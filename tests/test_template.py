import pytest

from openbook.config.template import compile_regex, compile_template
from openbook.errors import ConfigError

CHAPTER = "(Chapter {NUMBER} || {VOLUME}) {TITLE}"
PATTERNS = {"NUMBER": r"-?\d+", "VOLUME": r"[^)]+"}


def test_captures_a_real_chapter_title():
    template = compile_template(CHAPTER, PATTERNS)
    found = template.match("(Chapter 230 || Volume 7) The Poison Chooses.")
    assert found == {
        "NUMBER": "230",
        "VOLUME": "Volume 7",
        "TITLE": "The Poison Chooses.",
    }


def test_accepts_a_negative_chapter_number():
    template = compile_template(CHAPTER, PATTERNS)
    found = template.match("(Chapter -1 || Archive) The Continuity.")
    assert found is not None
    assert found["NUMBER"] == "-1"
    assert found["VOLUME"] == "Archive"


def test_accepts_a_volume_that_is_a_word():
    template = compile_template(CHAPTER, PATTERNS)
    found = template.match("(Chapter 0 || Prologue) Point - Null.")
    assert found is not None
    assert found["VOLUME"] == "Prologue"
    assert found["TITLE"] == "Point - Null."


def test_the_literal_text_is_not_a_regular_expression():
    # The brackets and the vertical bars are ordinary characters. A template
    # that treated them as regular expression syntax would match almost
    # anything.
    template = compile_template(CHAPTER, PATTERNS)
    assert template.match("Chapter 230  Volume 7 The Poison Chooses.") is None


def test_a_pattern_constrains_what_a_name_accepts():
    template = compile_template(CHAPTER, PATTERNS)
    assert template.match("(Chapter seven || Volume 7) A Title.") is None


def test_a_name_without_a_pattern_stops_at_the_literal_text():
    template = compile_template("{SPEAKER}: {TEXT}")
    found = template.match("LEA: Tell him the truth: all of it.")
    assert found == {"SPEAKER": "LEA", "TEXT": "Tell him the truth: all of it."}


def test_the_template_must_match_the_whole_line():
    template = compile_template("{SPEAKER}: {TEXT}")
    # A trailing newline is not part of the line, and nothing may follow the
    # end of the template.
    assert template.match("LEA: Hello\nIVY: Goodbye") is None


def test_a_repeated_name_is_refused():
    with pytest.raises(ConfigError, match="more than one time"):
        compile_template("{TEXT} and {TEXT}")


def test_a_template_that_captures_nothing_is_refused():
    with pytest.raises(ConfigError, match="captures nothing"):
        compile_template("End of Chapter")


def test_a_lone_brace_is_refused():
    with pytest.raises(ConfigError, match="brace that no name uses"):
        compile_template("{SPEAKER}: {TEXT")


def test_a_bad_pattern_names_the_configuration_key():
    with pytest.raises(ConfigError, match=r"grammar\.toml, in dialogue"):
        compile_template(
            "{SPEAKER}: {TEXT}",
            {"SPEAKER": "[A-Z"},
            key="dialogue",
            path="grammar.toml",
        )


def test_compile_regex_reports_a_bad_pattern():
    with pytest.raises(ConfigError, match="not a valid regular expression"):
        compile_regex("(unclosed", key="scene_break", path="grammar.toml")


def test_compile_regex_returns_a_usable_pattern():
    pattern = compile_regex(r"^\s*-{3,}\s*$")
    assert pattern.match("  ---  ")
    assert not pattern.match("--")
