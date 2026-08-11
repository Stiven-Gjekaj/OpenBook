import re
from pathlib import Path

import pytest

from openbook.cast import (
    BlendedVoice,
    MixedVoice,
    Silence,
    Utterance,
    Voice,
    resolve_chapter,
)
from openbook.config.cast import load_cast
from openbook.config.grammar import load_grammar
from openbook.errors import CastError
from openbook.parse import parse_chapter
from openbook.source.epub import Chapter

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "soultale"

CAST = """
[narrator]
voice = "af_heart"

[cast.IVY]
name = "Ivy"
voice = "bf_emma"

[cast.LEA]
name = "Leah"
voice = "af_sky"

[cast.NER]
name = "Ner"
voice = "am_adam"

[cast.SHN]
name = "Shn"
voice = "am_onyx"

[cast.MUTE]
name = "Not cast yet"
voice = ""
"""


@pytest.fixture
def grammar():
    return load_grammar(EXAMPLES / "grammar.toml")


@pytest.fixture
def cast(tmp_path):
    path = tmp_path / "cast.toml"
    path.write_text(CAST, encoding="utf-8")
    return load_cast(path)


def items(body, grammar, cast, *, number=230, volume="Volume 7"):
    chapter = Chapter(
        number=number, volume=volume, title="A Title.", body=body, source="x.epub"
    )
    return resolve_chapter(parse_chapter(chapter, grammar), grammar, cast)


def spoken(result):
    return [i for i in result if isinstance(i, Utterance)]


def test_narration_takes_the_narrator(grammar, cast):
    result = spoken(items("<p>She walked home.</p>", grammar, cast))
    assert result[-1] == Utterance(
        text="She walked home.", voice=Voice("af_heart"), kind="narration"
    )


def test_dialogue_takes_the_voice_of_its_character(grammar, cast):
    result = spoken(items("<p><strong>IVY</strong>: No.</p>", grammar, cast))
    assert result[-1].voice == Voice("bf_emma")
    assert result[-1].speaker == "IVY"
    assert result[-1].kind == "dialogue"


def test_a_chapter_is_announced_in_the_narrator_voice(grammar, cast):
    result = items("<p>Text.</p>", grammar, cast)
    assert result[0] == Utterance(
        text="Chapter 230. A Title.", voice=Voice("af_heart"), kind="announcement"
    )


def test_a_prologue_chapter_is_announced_by_its_number(grammar, cast):
    # Soultale gives both announcement forms the same words, so that the card
    # under the title can say the same number the narrator says.
    result = items("<p>Text.</p>", grammar, cast, number=0, volume="Prologue")
    assert result[0].text == "Chapter 0. A Title."


def test_a_volume_that_is_a_word_can_use_its_own_announcement(grammar, cast, tmp_path):
    # The mechanism is still there for a book that wants it.
    text = (EXAMPLES / "grammar.toml").read_text(encoding="utf-8")
    text = text.replace(
        'chapter_announcement_named = "Chapter {NUMBER}. {TITLE}"',
        'chapter_announcement_named = "{VOLUME}. {TITLE}"',
    )
    path = tmp_path / "grammar.toml"
    path.write_text(text, encoding="utf-8")
    other = load_grammar(path)
    result = items("<p>Text.</p>", other, cast, number=0, volume="Prologue")
    assert result[0].text == "Prologue. A Title."


def test_a_code_with_no_voice_stops_the_build(grammar, cast):
    # The case that must never pass in silence. A line with no voice would
    # become narration, and nobody hears that it went wrong.
    with pytest.raises(CastError, match="gives it no voice"):
        items("<p><strong>MUTE</strong>: Hello.</p>", grammar, cast)


def test_a_code_the_cast_does_not_have_stops_the_build(grammar, cast):
    with pytest.raises(CastError, match="chapter 230 uses the speaker code 'KRN'"):
        items("<p><strong>KRN</strong>: Hello.</p>", grammar, cast)


def test_a_book_with_no_narrator_stops_the_build(grammar, tmp_path):
    path = tmp_path / "cast.toml"
    path.write_text('[narrator]\nvoice = ""\n', encoding="utf-8")
    with pytest.raises(CastError, match="narrator speaks most of this book"):
        items("<p>Text.</p>", grammar, load_cast(path))


def unison(tmp_path, mode):
    """The example grammar, asking for one of the other unison modes."""
    text = (EXAMPLES / "grammar.toml").read_text(encoding="utf-8")
    path = tmp_path / "grammar.toml"
    path.write_text(text.replace('mode = "mix_matched"', f'mode = "{mode}"'), "utf-8")
    return load_grammar(path)


def test_two_characters_together_can_be_made_one_voice(cast, tmp_path):
    # The other way. One voice comes out and it is neither of theirs, so the
    # two cannot come apart in time at all.
    result = spoken(
        items(
            "<p><strong>NER &amp; SHN</strong>: Stop.</p>",
            unison(tmp_path, "voice_blend"),
            cast,
        )
    )
    voice = result[-1].voice
    assert isinstance(voice, BlendedVoice)
    assert voice.parts == ("am_adam", "am_onyx")
    assert voice.weights == (0.5, 0.5)
    assert voice.key() == "am_adam:0.500+am_onyx:0.500"


def reading_actions(tmp_path, mode: str):
    """The example grammar, with the action mode set to the one being tested.

    Each of these three tests is about one mode, and the value in the example
    file is a decision about Soultale that can change. Taking the mode from
    the file makes a change of mind about the book fail a test of the code,
    and worse, it once made the test for 'drop' pass by writing nothing
    because the file already said it.
    """
    text = (EXAMPLES / "grammar.toml").read_text(encoding="utf-8")
    text, changed = re.subn(
        r'(?m)^action(\s*)= "(?:pause|narrator|drop)"$',
        rf'action\g<1>= "{mode}"',
        text,
    )
    assert changed == 1, "the example grammar no longer sets the action mode"
    path = tmp_path / "grammar.toml"
    path.write_text(text, encoding="utf-8")
    return load_grammar(path)


def test_an_action_becomes_a_silence_where_the_mode_is_pause(cast, tmp_path):
    other = reading_actions(tmp_path, "pause")
    result = items(
        "<p><strong>IVY</strong>: I am fine *cough* really.</p>", other, cast
    )
    kinds = [type(i).__name__ for i in result[1:]]
    assert kinds == ["Utterance", "Silence", "Utterance"]
    assert result[2] == Silence(seconds=0.5, reason="action: cough")


def test_an_action_can_be_spoken_by_the_narrator(cast, tmp_path):
    other = reading_actions(tmp_path, "narrator")
    result = items("<p><strong>IVY</strong>: Fine *cough* really.</p>", other, cast)
    action = [i for i in result if getattr(i, "kind", None) == "action"]
    assert action[0] == Utterance(text="cough", voice=Voice("af_heart"), kind="action")


def test_an_action_can_be_dropped(cast, tmp_path):
    other = reading_actions(tmp_path, "drop")
    result = items("<p><strong>IVY</strong>: Fine *cough* really.</p>", other, cast)
    assert not [i for i in result if isinstance(i, Silence)]
    assert len(spoken(result)) == 3


def test_a_scene_break_becomes_a_silence(grammar, cast):
    result = items("<p>One.</p><p>---</p><p>Two.</p>", grammar, cast)
    breaks = [i for i in result if isinstance(i, Silence)]
    assert breaks == [Silence(seconds=2.0, reason="scene break")]


def test_the_end_matter_is_read_when_the_book_asks_for_it(grammar, cast):
    # Soultale closes every chapter with its number, its title, and a line
    # that comments on it. Reading only the last of the three left the closing
    # line arriving with nothing in front of it.
    result = items("<p>Last.</p><p><u>End of Chapter 230</u></p>", grammar, cast)
    said = [i for i in spoken(result) if i.kind == "end matter"]
    assert [i.text for i in said] == ["End of Chapter 230"]


def test_the_end_matter_can_be_left_out(grammar, cast, tmp_path):
    text = (EXAMPLES / "grammar.toml").read_text(encoding="utf-8")
    path = tmp_path / "grammar.toml"
    path.write_text(
        text.replace("read_end_matter    = true", "read_end_matter    = false"), "utf-8"
    )
    result = items(
        "<p>Last.</p><p><u>End of Chapter 230</u></p>", load_grammar(path), cast
    )
    assert not [i for i in spoken(result) if i.kind == "end matter"]


def test_two_characters_together_are_both_heard(cast, tmp_path):
    # The line is spoken once in each voice and the two are laid over each
    # other, so both characters keep their own voice.
    result = spoken(
        items(
            "<p><strong>NER &amp; SHN</strong>: Stop.</p>",
            unison(tmp_path, "mix"),
            cast,
        )
    )
    voice = result[-1].voice
    assert isinstance(voice, MixedVoice)
    assert voice.parts == ("am_adam", "am_onyx")
    assert voice.key() == "am_adam&am_onyx"


def test_two_characters_together_are_held_in_step(grammar, cast):
    # What this book asks for. Both voices are heard, and both are brought to
    # one length first, so they speak together from the first word to the last.
    result = spoken(
        items("<p><strong>NER &amp; SHN</strong>: Stop.</p>", grammar, cast)
    )
    voice = result[-1].voice
    assert isinstance(voice, MixedVoice)
    assert voice.matched
    # The two make different audio out of the same voices, so they must not
    # share a piece of it in the cache.
    assert voice.key() != MixedVoice(parts=voice.parts).key()


def test_a_number_written_for_a_character_reaches_the_line(grammar, cast, tmp_path):
    # The cast file says how much feeling one character is read with, and the
    # line carries it to whichever engine ends up speaking.
    path = tmp_path / "cast.toml"
    path.write_text(
        '[narrator]\nvoice = "af_heart"\nexaggeration = 0.25\n\n'
        '[cast.IVY]\nname = "Ivy"\nvoice = "bf_emma"\nexaggeration = 0.85\n',
        encoding="utf-8",
    )
    told = load_cast(path)
    result = items("<p>Prose.</p><p><strong>IVY</strong>: Stop.</p>", grammar, told)
    said = [i for i in result if isinstance(i, Utterance)]

    assert said[0].exaggeration == 0.25, "the announcement is the narrator"
    assert [i.exaggeration for i in said if i.kind == "narration"] == [0.25]
    assert [i.exaggeration for i in said if i.kind == "dialogue"] == [0.85]


def test_a_character_with_no_number_carries_none(grammar, cast):
    # Nothing written down means the engine chooses from the kind of the line.
    result = items("<p><strong>IVY</strong>: Stop.</p>", grammar, cast)
    said = [i for i in result if isinstance(i, Utterance)]
    assert all(i.exaggeration is None for i in said)


def test_an_exaggeration_outside_the_range_is_refused():
    with pytest.raises(ValueError, match="between 0 and 2"):
        Utterance(text="x", voice=Voice("a"), kind="narration", exaggeration=5.0)
