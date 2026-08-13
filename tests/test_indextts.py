import pytest

from openbook.cast.utterance import BlendedVoice, MixedVoice, Voice
from openbook.errors import OpenBookError
from openbook.speech.chatterbox import ChatterboxTurboEngine
from openbook.speech.indextts import (
    FEELINGS,
    MAX_CHARACTERS,
    MEANINGS,
    STRENGTH,
    IndexTtsEngine,
    feeling_for,
    installed,
)

needs_indextts = pytest.mark.skipif(
    not installed(), reason="there is no Python with IndexTTS in it"
)


@pytest.fixture
def project(tmp_path):
    """A project directory holding one recording to take a voice from."""
    (tmp_path / "voices").mkdir()
    (tmp_path / "voices" / "zero.wav").write_bytes(b"RIFF....WAVEfmt the first take")
    return tmp_path


@pytest.fixture
def engine(project):
    return IndexTtsEngine(directory=project)


def test_the_engine_names_itself(engine):
    assert engine.name == "indextts"
    # Not the 24000 the other engines give back. A stage that assumed one rate
    # for every engine would resample this one without saying so.
    assert engine.rate == 22050
    assert engine.max_characters == MAX_CHARACTERS


def test_it_takes_the_same_text_at_once_as_chatterbox():
    # The limit decides where a long line is divided, and a correction names a
    # piece of a divided line. Two engines that disagreed about it would
    # disagree about what a correction means.
    from openbook.speech.chatterbox import MAX_CHARACTERS as TURBO

    assert MAX_CHARACTERS == TURBO


def test_the_vector_is_eight_long_and_in_the_order_the_model_reads():
    # The model does not check this. Getting it wrong makes a frightened
    # character sound pleased and nothing reports it.
    assert FEELINGS == (
        "happy",
        "angry",
        "sad",
        "afraid",
        "disgusted",
        "melancholic",
        "surprised",
        "calm",
    )


def test_a_line_without_a_tag_is_read_flat():
    said, feeling = feeling_for("These connections...")
    assert said == "These connections..."
    assert feeling is None


def test_a_tag_chooses_a_feeling_and_leaves_the_words():
    said, feeling = feeling_for("[angry] No!")
    assert said == "No!"
    assert feeling is not None
    assert len(feeling) == len(FEELINGS)
    assert feeling[FEELINGS.index("angry")] == STRENGTH
    assert sum(feeling) == pytest.approx(STRENGTH)


def test_every_meaning_names_a_feeling_the_model_has():
    # A meaning pointing at a name the model does not know would put the
    # strength nowhere, and the line would read flat with nothing said.
    for tag, feeling in MEANINGS.items():
        assert feeling in FEELINGS, tag


def test_a_tag_the_model_has_no_feeling_for_still_leaves_the_words():
    # [cough] says what to do rather than how to feel. It is taken out like
    # any other tag, because a model handed the brackets reads them aloud.
    said, feeling = feeling_for("[cough] Right, then.")
    assert said == "Right, then."
    assert feeling is None


def test_a_tag_anywhere_in_the_line_is_found():
    said, feeling = feeling_for("Wait. [surprised] You came back?")
    assert said == "Wait. You came back?"
    assert feeling[FEELINGS.index("surprised")] == STRENGTH


def test_a_line_that_is_nothing_but_tags_is_refused(engine):
    with pytest.raises(OpenBookError, match="nothing but tags"):
        engine.speak("[laugh]", Voice("voices/zero.wav"))


def test_an_empty_line_is_refused(engine):
    with pytest.raises(OpenBookError, match="given nothing to say"):
        engine.speak("   ", Voice("voices/zero.wav"))


def test_the_recording_is_in_the_key_and_not_its_name(engine, project):
    # A better take written over the same path is a different voice and has to
    # be made again. A file that only changed its name is the same voice.
    before = engine.voice_key(Voice("voices/zero.wav"))
    (project / "voices" / "zero.wav").write_bytes(b"RIFF....WAVEfmt a second take")
    assert engine.voice_key(Voice("voices/zero.wav")) != before


def test_two_names_for_one_recording_share_their_audio(engine, project):
    (project / "voices" / "copy.wav").write_bytes(
        (project / "voices" / "zero.wav").read_bytes()
    )
    assert engine.voice_key(Voice("voices/zero.wav")) == engine.voice_key(
        Voice("voices/copy.wav")
    )


def test_the_key_has_no_exaggeration_in_it(engine):
    # This engine takes its feeling from the words, and the words are in the
    # key of the line already. An exaggeration here would divide the cache in
    # two for a number that changes nothing.
    voice = Voice("voices/zero.wav")
    assert engine.voice_key(voice, kind="narration") == engine.voice_key(
        voice, kind="dialogue"
    )
    assert engine.voice_key(voice, exaggeration=0.9) == engine.voice_key(voice)


def test_it_gives_a_different_key_from_turbo(project):
    # Both readings of a chapter can be held at once, so one can be compared
    # with the other by ear rather than by replacing it.
    voice = Voice("voices/zero.wav")
    here = IndexTtsEngine(directory=project)
    there = ChatterboxTurboEngine(directory=project)
    assert here.voice_key(voice) != there.voice_key(voice)
    assert here.name != there.name


def test_a_missing_recording_is_named_before_anything_loads(engine):
    # Starting the worker to find out that a file is missing reports the wrong
    # problem and takes eighteen seconds.
    with pytest.raises(OpenBookError, match="there is no file there"):
        engine.reference_for("voices/nobody.wav")


def test_a_missing_recording_is_named_when_a_line_is_spoken(engine):
    with pytest.raises(OpenBookError, match="there is no file there"):
        engine.speak("Anything at all.", Voice("voices/nobody.wav"))


def test_a_blended_voice_is_refused_and_the_answer_is_named(engine):
    with pytest.raises(OpenBookError, match="mix or mix_matched"):
        engine.speak(
            "Together now.",
            BlendedVoice(parts=("a", "b"), weights=(0.5, 0.5)),
        )


def test_a_mixed_voice_keeps_its_shape_in_the_key(engine):
    # mix speaks a line once in each voice, so the key is the pair and not one
    # of them. It is not a recording, so it keeps the name it already had.
    both = MixedVoice(parts=("voices/zero.wav", "voices/ink.wav"), matched=False)
    assert engine.voice_key(both) == both.key()


def test_the_version_carries_what_the_tags_mean(engine, monkeypatch):
    # Change what a tag means and the lines carrying it are made again. Every
    # untagged line in the book stays where it is, which is most of the book.
    before = engine.version
    monkeypatch.setitem(MEANINGS, "angry", "sad")
    assert engine.version != before


def test_an_interpreter_that_is_not_there_is_named(project):
    engine = IndexTtsEngine(directory=project, python="/nowhere/python")
    with pytest.raises(OpenBookError, match="OPENBOOK_INDEXTTS_PYTHON"):
        engine.speak("Anything at all.", Voice("voices/zero.wav"))


def test_a_model_directory_that_is_not_there_is_named(project, tmp_path):
    engine = IndexTtsEngine(
        directory=project,
        python=str(tmp_path / "python"),
        model_dir="/nowhere/weights",
    )
    (tmp_path / "python").write_text("")
    with pytest.raises(OpenBookError, match="OPENBOOK_INDEXTTS_MODEL"):
        engine.speak("Anything at all.", Voice("voices/zero.wav"))


def test_the_cli_offers_it(project):
    from openbook.cli import ENGINES, _engine_for

    assert "indextts" in ENGINES
    made = _engine_for(_Options(engine="indextts", project=project))
    assert isinstance(made, IndexTtsEngine)
    assert made.name == "indextts"


class _Options:
    def __init__(self, **named):
        self.__dict__.update(named)


@needs_indextts
def test_it_speaks_a_line_and_a_feeling_makes_it_louder(project, tmp_path):
    """The reason this engine is here, asked of the engine itself.

    Everything above this runs without the model. This one needs it, and it
    is the only claim that matters: that a tag changes how hard a line is
    said. Turbo reads the same pair 0.3 dB apart.
    """
    import array
    import math
    import shutil

    real = "examples/soultale/voices/zero.wav"
    shutil.copyfile(real, project / "voices" / "zero.wav")
    voice = Voice("voices/zero.wav")

    def loudness(audio):
        values = array.array("h")
        values.frombytes(audio.samples)
        square = sum(float(v) * v for v in values) / len(values)
        return 20 * math.log10(math.sqrt(square) / 32768.0)

    with IndexTtsEngine(directory=project) as engine:
        flat = engine.speak("I am the true strongest!", voice, kind="dialogue")
        loud = engine.speak("[angry] I am the true strongest!", voice, kind="dialogue")
    assert flat.rate == 22050
    assert flat.seconds > 0.5 and loud.seconds > 0.5
    assert loudness(loud) > loudness(flat) + 3.0
