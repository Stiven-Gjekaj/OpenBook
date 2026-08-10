from pathlib import Path

import pytest

from openbook.config.grammar import load_grammar
from openbook.parse import (
    Action,
    Dialogue,
    EndMatter,
    Narration,
    SceneBreak,
    Speech,
    parse_chapter,
)
from openbook.source.epub import Chapter

EXAMPLE = (
    Path(__file__).resolve().parent.parent / "examples" / "soultale" / "grammar.toml"
)


@pytest.fixture
def grammar():
    return load_grammar(EXAMPLE)


def parse(body: str, grammar, number: int = 230):
    chapter = Chapter(
        number=number, volume="Volume 7", title="A Title.", body=body, source="x.epub"
    )
    return parse_chapter(chapter, grammar)


def test_a_paragraph_of_prose_is_narration(grammar):
    result = parse("<p>She walked Leah home. It was not deliberate.</p>", grammar)
    assert result.segments == (
        Narration(text="She walked Leah home. It was not deliberate."),
    )


def test_a_bold_code_and_a_colon_is_dialogue(grammar):
    result = parse("<p><strong>LEA</strong>: My papa will ask.</p>", grammar)
    (segment,) = result.segments
    assert isinstance(segment, Dialogue)
    assert segment.speakers == ("LEA",)
    assert segment.text == "My papa will ask."


def test_both_bold_elements_mark_a_speaker(grammar):
    result = parse("<p><b>IVY</b>: One.</p><p><strong>IVY</strong>: Two.</p>", grammar)
    assert [s.text for s in result.segments] == ["One.", "Two."]


def test_a_paragraph_divides_at_every_line_break(grammar):
    # This is the shape that most of the dialogue of the book arrives in. A
    # reader that treats the paragraph as one unit gets one segment here.
    body = (
        "<p><strong>JHN</strong>: Did you feel that?<br/>"
        "<strong>JHN</strong>: Everyone felt that.<br/>"
        "<strong>JHN</strong>: It was Astra.</p>"
    )
    result = parse(body, grammar)
    assert len(result.segments) == 3
    assert all(isinstance(s, Dialogue) for s in result.segments)
    assert result.segments[2].text == "It was Astra."


def test_bold_inside_a_sentence_is_not_a_speaker(grammar):
    # Bold marks emphasis as well as a speaker code. Only bold at the front of
    # a line, with a colon after it, is a speaker.
    body = "<p>She said it with a <b>certainty</b>: it surprised her.</p>"
    (segment,) = parse(body, grammar).segments
    assert isinstance(segment, Narration)


def test_italic_is_removed_and_its_words_are_kept(grammar):
    body = "<p>He was <em>certain</em> of it.</p>"
    (segment,) = parse(body, grammar).segments
    assert segment == Narration(text="He was certain of it.")


def test_an_action_inside_a_line_becomes_its_own_piece(grammar):
    body = "<p><strong>RMI</strong>: You want to try that again? *circling warily*</p>"
    (segment,) = parse(body, grammar).segments
    assert segment.pieces == (
        Speech(text="You want to try that again?"),
        Action(text="circling warily"),
    )
    assert segment.text == "You want to try that again?"
    assert segment.actions == (Action(text="circling warily"),)


def test_an_action_in_the_middle_leaves_speech_on_both_sides(grammar):
    body = "<p><strong>IVY</strong>: I am fine *cough* really.</p>"
    (segment,) = parse(body, grammar).segments
    assert segment.pieces == (
        Speech(text="I am fine"),
        Action(text="cough"),
        Speech(text="really."),
    )


def test_an_asterisk_with_no_pair_is_reported(grammar):
    # The editor made half of some pairs into italic text and left the other
    # half behind. The one that stayed must not reach a voice unremarked.
    body = "<p><strong>IVY</strong>: You did well grin*</p>"
    result = parse(body, grammar)
    assert len(result.notes) == 1
    assert result.notes[0].kind == "lone asterisk"
    assert "chapter 230" in result.notes[0].detail


def test_a_lone_asterisk_in_narration_is_reported_too(grammar):
    # The only place in Soultale where this happens is narration, so a check on
    # dialogue alone would find nothing and call the book clean.
    result = parse(
        "<p>She compressed. The wind gathered *and she was moving.</p>", grammar
    )
    assert len(result.notes) == 1
    assert "narration" in result.notes[0].detail


def test_a_line_with_no_asterisk_is_not_reported(grammar):
    result = parse("<p><strong>IVY</strong>: I am fine *cough* really.</p>", grammar)
    assert result.notes == ()


def test_two_characters_speaking_together(grammar):
    body = "<p><strong>NER &amp; SHN</strong>: We are not doing that.</p>"
    (segment,) = parse(body, grammar).segments
    assert segment.speakers == ("NER", "SHN")
    assert segment.is_unison


def test_an_entity_is_decoded_before_the_rules_run(grammar):
    # The unison separator arrives as an entity. Without decoding it first, the
    # whole code becomes one unknown speaker.
    body = "<p>Virtues &amp; Sins, she thought.</p>"
    (segment,) = parse(body, grammar).segments
    assert segment.text == "Virtues & Sins, she thought."


def test_a_speaker_code_that_is_not_letters(grammar):
    body = (
        "<p><strong>???</strong>: Heroes.</p>"
        "<p><strong>///</strong>: I do not have a name.</p>"
        "<p><strong>KID #1</strong>: Look!</p>"
    )
    codes = [s.speakers[0] for s in parse(body, grammar).segments]
    assert codes == ["???", "///", "KID #1"]


def test_a_line_of_dashes_is_a_scene_break(grammar):
    body = "<p>Before.</p><p>---</p><p>After.</p>"
    kinds = [type(s).__name__ for s in parse(body, grammar).segments]
    assert kinds == ["Narration", "SceneBreak", "Narration"]
    assert parse(body, grammar).segments[1] == SceneBreak()


def test_the_end_matter_is_known_by_its_element(grammar):
    body = "<p>The last line.</p><p><u>End of Chapter 230</u></p>"
    segments = parse(body, grammar).segments
    assert isinstance(segments[-1], EndMatter)
    assert segments[-1].text == "End of Chapter 230"


def test_a_chapter_with_no_dialogue_gives_only_narration(grammar):
    # 61 chapters of the book are like this.
    body = "<p>One.</p><p>Two.</p><p>Three.</p>"
    result = parse(body, grammar)
    assert all(isinstance(s, Narration) for s in result.segments)
    assert result.speakers() == ()


def test_the_speakers_of_a_chapter_come_back_in_order_of_first_use(grammar):
    body = (
        "<p><strong>IVY</strong>: One.</p>"
        "<p><strong>LEA</strong>: Two.</p>"
        "<p><strong>IVY</strong>: Three.</p>"
    )
    assert parse(body, grammar).speakers() == ("IVY", "LEA")


def test_an_empty_paragraph_gives_no_segment(grammar):
    assert parse("<p></p><p>   </p><p>Real.</p>", grammar).segments == (
        Narration(text="Real."),
    )


def test_whitespace_across_elements_becomes_one_space(grammar):
    body = "<p>One\n  two   <em>three</em>\tfour.</p>"
    (segment,) = parse(body, grammar).segments
    assert segment.text == "One two three four."


def test_an_element_that_closes_without_opening_does_not_stop_the_parse(grammar):
    body = "<p>Text</em> more text.</p><p>Another.</p>"
    kinds = [type(s).__name__ for s in parse(body, grammar).segments]
    assert kinds == ["Narration", "Narration"]
