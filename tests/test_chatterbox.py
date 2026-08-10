import pytest

from openbook.cast.utterance import BlendedVoice, MixedVoice, Voice
from openbook.errors import OpenBookError
from openbook.speech.chatterbox import (
    MAX_CHARACTERS,
    ChatterboxEngine,
    Settings,
    device,
    installed,
)

needs_chatterbox = pytest.mark.skipif(
    not installed(), reason="chatterbox is not installed"
)


@pytest.fixture
def project(tmp_path):
    """A project directory holding one recording to take a voice from."""
    (tmp_path / "voices").mkdir()
    (tmp_path / "voices" / "blook.wav").write_bytes(b"RIFF....WAVEfmt the first take")
    return tmp_path


@pytest.fixture
def engine(project):
    return ChatterboxEngine(directory=project)


def test_the_engine_names_itself(engine):
    assert engine.name == "chatterbox"
    assert engine.rate == 24000
    assert engine.max_characters == MAX_CHARACTERS


def test_it_takes_less_text_at_once_than_the_others():
    # A model that makes a token at a time wanders further the longer it is
    # left running, and the cut falls at the end of a sentence either way.
    from openbook.speech.engine import MAX_CHARACTERS as OTHERS

    assert MAX_CHARACTERS < OTHERS


def test_the_recording_is_part_of_the_name_the_cache_uses(engine, project):
    # The name of a voice is a path and the sound is the file. Without the
    # file in the name, a better take written to the same path would be
    # ignored for ever and nothing would say so.
    voice = Voice("voices/blook.wav")
    before = engine.voice_key(voice)

    (project / "voices" / "blook.wav").write_bytes(b"RIFF....WAVEfmt a better take")
    after = engine.voice_key(voice)

    assert before != after
    assert before.startswith("voices/blook.wav#")


def test_the_same_recording_gives_the_same_name(engine):
    voice = Voice("voices/blook.wav")
    assert engine.voice_key(voice) == engine.voice_key(voice)


def test_a_line_two_characters_share_names_both_recordings(engine, project):
    (project / "voices" / "ivy.wav").write_bytes(b"RIFF....WAVEfmt ivy")
    mixed = MixedVoice(parts=("voices/blook.wav", "voices/ivy.wav"), matched=True)
    made = engine.voice_key(mixed)

    assert made.count("#") == 2
    # The shape of the voice survives, so a matched mix and a plain one still
    # do not share a piece of audio.
    assert made != engine.voice_key(MixedVoice(parts=mixed.parts))


def test_a_recording_that_is_not_there_is_named_with_what_it_is_for(engine):
    with pytest.raises(OpenBookError, match="no file there"):
        engine.reference_for("voices/nobody.wav")


def test_a_missing_recording_is_found_before_the_model_is_loaded(engine, monkeypatch):
    # Loading a model to find out that a file is missing reports the wrong
    # problem and takes a minute doing it.
    def refuse():
        raise AssertionError("the model must not be loaded to check a file")

    monkeypatch.setattr(engine, "_loaded", refuse)
    with pytest.raises(OpenBookError, match="no file there"):
        engine.speak("Words.", Voice("voices/nobody.wav"))


def test_nothing_to_say_is_refused(engine):
    with pytest.raises(OpenBookError, match="given nothing to say"):
        engine.speak("   ", Voice("voices/blook.wav"))


def test_a_blended_voice_is_refused_with_what_to_use_instead(engine):
    # There is no style to average. A voice here is a recording.
    with pytest.raises(OpenBookError, match="mix_matched"):
        engine.speak(
            "Stop.",
            BlendedVoice(
                parts=("voices/blook.wav", "voices/ivy.wav"), weights=(0.5, 0.5)
            ),
        )


def test_the_settings_every_line_shares_are_part_of_the_version(project):
    # A change to how the model reads makes different audio out of the same
    # words, so the cache must not hand back the old sound.
    plain = ChatterboxEngine(directory=project)
    loose = ChatterboxEngine(directory=project, settings=Settings(temperature=1.1))
    assert plain.version != loose.version


def test_dialogue_is_read_with_more_feeling_than_narration(project):
    # A narrator states what happened and holds one level for hours. A
    # character in a fantasy is frightened, or lying, or giving an order.
    settings = Settings()
    assert settings.exaggeration("dialogue") > settings.exaggeration("narration")
    assert settings.exaggeration("narration") == 0.3
    assert settings.exaggeration("dialogue") == 0.7


def test_the_narrator_reads_everything_that_is_not_dialogue_the_same_way(project):
    # An action the narrator speaks, a chapter announcement and the end matter
    # are all the narrator talking.
    settings = Settings()
    for kind in ("narration", "action", "announcement", "end matter"):
        assert settings.exaggeration(kind) == settings.narration


def test_a_number_written_for_a_character_wins(project):
    settings = Settings()
    assert settings.exaggeration("dialogue", 0.15) == 0.15
    assert settings.exaggeration("narration", 0.9) == 0.9


def test_how_a_line_is_read_is_part_of_its_key_and_not_the_version(project):
    # The exaggeration changes with the kind of the line, so it cannot live in
    # the version. There it would remake three hundred thousand words of
    # narration every time somebody tuned the cast.
    engine = ChatterboxEngine(directory=project)
    voice = Voice("voices/blook.wav")
    assert engine.voice_key(voice, kind="narration") != engine.voice_key(
        voice, kind="dialogue"
    )
    assert engine.voice_key(voice, kind="dialogue") != engine.voice_key(
        voice, kind="dialogue", exaggeration=0.9
    )


def test_tuning_the_cast_leaves_the_narration_alone(project):
    plain = ChatterboxEngine(directory=project)
    louder = ChatterboxEngine(directory=project, settings=Settings(dialogue=0.9))
    voice = Voice("voices/blook.wav")
    assert plain.voice_key(voice, kind="narration") == louder.voice_key(
        voice, kind="narration"
    )
    assert plain.voice_key(voice, kind="dialogue") != louder.voice_key(
        voice, kind="dialogue"
    )


def test_the_device_is_one_this_machine_has():
    assert device() in ("cuda", "mps", "cpu")


@needs_chatterbox
def test_the_version_names_the_package():
    from openbook.speech.chatterbox import installed_version

    assert installed_version() != "unknown"
