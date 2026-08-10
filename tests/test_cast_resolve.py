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


def test_an_action_becomes_a_silence_by_default(grammar, cast):
    result = items(
        "<p><strong>IVY</strong>: I am fine *cough* really.</p>", grammar, cast
    )
    kinds = [type(i).__name__ for i in result[1:]]
    assert kinds == ["Utterance", "Silence", "Utterance"]
    assert result[2] == Silence(seconds=0.5, reason="action: cough")


def test_an_action_can_be_spoken_by_the_narrator(grammar, cast, tmp_path):
    text = (EXAMPLES / "grammar.toml").read_text(encoding="utf-8")
    text = text.replace('action          = "pause"', 'action          = "narrator"')
    path = tmp_path / "grammar.toml"
    path.write_text(text, encoding="utf-8")
    other = load_grammar(path)
    result = items("<p><strong>IVY</strong>: Fine *cough* really.</p>", other, cast)
    action = [i for i in result if getattr(i, "kind", None) == "action"]
    assert action[0] == Utterance(text="cough", voice=Voice("af_heart"), kind="action")


def test_an_action_can_be_dropped(grammar, cast, tmp_path):
    text = (EXAMPLES / "grammar.toml").read_text(encoding="utf-8")
    text = text.replace('action          = "pause"', 'action          = "drop"')
    path = tmp_path / "grammar.toml"
    path.write_text(text, encoding="utf-8")
    other = load_grammar(path)
    result = items("<p><strong>IVY</strong>: Fine *cough* really.</p>", other, cast)
    assert not [i for i in result if isinstance(i, Silence)]
    assert len(spoken(result)) == 3


def test_a_scene_break_becomes_a_silence(grammar, cast):
    result = items("<p>One.</p><p>---</p><p>Two.</p>", grammar, cast)
    breaks = [i for i in result if isinstance(i, Silence)]
    assert breaks == [Silence(seconds=2.0, reason="scene break")]


def test_the_end_matter_is_left_out_by_default(grammar, cast):
    result = items("<p>Last.</p><p><u>End of Chapter 230</u></p>", grammar, cast)
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
