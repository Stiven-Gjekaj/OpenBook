import pytest

from openbook.cast.utterance import BlendedVoice, MixedVoice, Voice
from openbook.errors import OpenBookError
from openbook.speech.chatterbox import (
    MAX_CHARACTERS,
    ChatterboxEngine,
    ChatterboxTurboEngine,
    Settings,
    TurboSettings,
    device,
    installed,
)

# Both models answer to the same questions, so the questions are asked of both
# and neither can drift away from the other.
BOTH = pytest.mark.parametrize(
    "family", [ChatterboxEngine, ChatterboxTurboEngine], ids=["chatterbox", "turbo"]
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


@pytest.fixture
def both(project):
    """One engine of each model, over the same project."""
    return [
        ChatterboxEngine(directory=project),
        ChatterboxTurboEngine(directory=project),
    ]


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
    # The sound is the file and not the path. Without the file in the name, a
    # better take written to the same path would be ignored for ever and
    # nothing would say so.
    voice = Voice("voices/blook.wav")
    before = engine.voice_key(voice)

    (project / "voices" / "blook.wav").write_bytes(b"RIFF....WAVEfmt a better take")
    after = engine.voice_key(voice)

    assert before != after
    # The path is not in the key, so that a rename costs nothing.
    assert "voices/blook.wav" not in before


def test_the_same_recording_gives_the_same_name(engine):
    voice = Voice("voices/blook.wav")
    assert engine.voice_key(voice) == engine.voice_key(voice)


def test_a_line_two_characters_share_names_both_recordings(engine, project):
    (project / "voices" / "ivy.wav").write_bytes(b"RIFF....WAVEfmt ivy")
    mixed = MixedVoice(parts=("voices/blook.wav", "voices/ivy.wav"), matched=True)
    made = engine.voice_key(mixed)

    # Both recordings are named, so a better take of either remakes the line.
    for part in mixed.parts:
        assert engine.voice_key(Voice(part)).split("@")[0] in made
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


def test_a_recording_under_another_name_is_the_same_voice(engine, project):
    """Renaming a clip must not throw away every line a character has.

    The key holds the recording and not the name of it. A better take written
    over the same path is a different voice and is made again. A file that
    only changed its name is the same voice and keeps its audio.
    """
    (project / "voices" / "narrator.wav").write_bytes(
        (project / "voices" / "blook.wav").read_bytes()
    )
    assert engine.voice_key(Voice("voices/blook.wav")) == engine.voice_key(
        Voice("voices/narrator.wav")
    )


def test_two_characters_given_one_recording_share_their_audio(engine, project):
    # The same words in the same voice are the same sound. Zero and the
    # nameless voice of a prologue are one recording and one set of audio.
    (project / "voices" / "nameless.wav").write_bytes(
        (project / "voices" / "blook.wav").read_bytes()
    )
    assert engine.voice_key(Voice("voices/nameless.wav")) == engine.voice_key(
        Voice("voices/blook.wav")
    )


def test_a_different_take_is_still_a_different_voice(engine, project):
    # The reason the recording is in the key at all.
    before = engine.voice_key(Voice("voices/blook.wav"))
    (project / "voices" / "blook.wav").write_bytes(b"RIFF....WAVEfmt a second take")
    assert engine.voice_key(Voice("voices/blook.wav")) != before


# The most expensive thing in this project to get wrong.
#
# A change to how a key is built throws away every piece of audio under the
# old one. Chapter 0 alone is thirty eight minutes of rendering and a volume is
# eight and a half hours, and nothing announces it: the render simply says it
# made everything again. These pin the shape of the key so that a change to it
# has to be deliberate.
#
# The version is left out of the pin because it carries the version of the
# package, and a package upgrade should remake the audio. What is pinned is
# the part this project decides.


def test_the_settings_key_has_not_moved():
    assert Settings().key() == "g0.5-t0.8"


def test_the_voice_key_has_not_moved(tmp_path):
    (tmp_path / "voices").mkdir()
    (tmp_path / "voices" / "one.wav").write_bytes(b"RIFF a fixed recording")
    engine = ChatterboxEngine(directory=tmp_path)
    said = engine.voice_key(Voice("voices/one.wav"), kind="narration")
    assert said == "104cfa97f1454236@e0.3"


def test_the_whole_key_has_not_moved(tmp_path):
    from openbook.speech.cache import key_for

    (tmp_path / "voices").mkdir()
    (tmp_path / "voices" / "one.wav").write_bytes(b"RIFF a fixed recording")
    engine = ChatterboxEngine(directory=tmp_path)
    said = engine.voice_key(Voice("voices/one.wav"), kind="narration")
    assert (
        key_for(
            "The light arrives like violence.", said, "chatterbox", "pinned-0.5-0.8"
        )
        == "ae6e70b94f7b33f29ab40b41135baafc551ce6a1c0db16c85f125cc7247b7323"
    )


# What both models must do the same way. A question asked of one and not the
# other is how two engines come apart.


@BOTH
def test_both_take_less_text_at_once_than_the_other_engines(family, project):
    from openbook.speech.engine import MAX_CHARACTERS as OTHERS

    assert family(directory=project).max_characters < OTHERS


@BOTH
def test_both_put_the_recording_in_the_key(family, project):
    engine = family(directory=project)
    voice = Voice("voices/blook.wav")
    before = engine.voice_key(voice)
    (project / "voices" / "blook.wav").write_bytes(b"RIFF....WAVEfmt another take")
    assert engine.voice_key(voice) != before


@BOTH
def test_both_leave_the_name_of_a_recording_out_of_the_key(family, project):
    engine = family(directory=project)
    (project / "voices" / "same.wav").write_bytes(
        (project / "voices" / "blook.wav").read_bytes()
    )
    assert engine.voice_key(Voice("voices/same.wav")) == engine.voice_key(
        Voice("voices/blook.wav")
    )


@BOTH
def test_both_name_a_recording_that_is_not_there(family, project):
    with pytest.raises(OpenBookError, match="no file there"):
        family(directory=project).reference_for("voices/nobody.wav")


@BOTH
def test_both_find_a_missing_recording_before_loading_a_model(
    family, project, monkeypatch
):
    engine = family(directory=project)

    def refuse():
        raise AssertionError("the model must not be loaded to check a file")

    monkeypatch.setattr(engine, "_loaded", refuse)
    with pytest.raises(OpenBookError, match="no file there"):
        engine.speak("Words.", Voice("voices/nobody.wav"))


@BOTH
def test_both_refuse_nothing_to_say(family, project):
    with pytest.raises(OpenBookError, match="given nothing to say"):
        family(directory=project).speak("   ", Voice("voices/blook.wav"))


@BOTH
def test_both_refuse_a_blended_voice_with_what_to_use_instead(family, project):
    with pytest.raises(OpenBookError, match="mix_matched"):
        family(directory=project).speak(
            "Stop.",
            BlendedVoice(
                parts=("voices/blook.wav", "voices/ivy.wav"), weights=(0.5, 0.5)
            ),
        )


@BOTH
def test_both_read_dialogue_with_more_feeling_than_narration(family, project):
    settings = family(directory=project)._settings
    assert settings.exaggeration("dialogue") > settings.exaggeration("narration")


@BOTH
def test_both_let_a_character_say_otherwise(family, project):
    settings = family(directory=project)._settings
    assert settings.exaggeration("narration", 0.9) == 0.9


# What tells the two apart.


def test_the_two_models_do_not_share_a_line(both, project):
    """Both readings of a chapter are held at once, so they can be compared.

    The name of the engine is in the key, so nothing had to be arranged for
    this. It is here because it is the reason the second model can be tried at
    all without losing the first.
    """
    from openbook.cast.utterance import Utterance
    from openbook.speech.cache import key_of

    said = Utterance(text="A line.", voice=Voice("voices/blook.wav"), kind="narration")
    plain, turbo = both
    assert key_of(said, plain) != key_of(said, turbo)


def test_turbo_starts_from_its_own_numbers():
    # Turbo reads flat at zero where the older model reads flat at one half,
    # so the numbers tuned for that one do not carry across.
    assert TurboSettings().narration != Settings().narration
    assert TurboSettings().guidance == 0.0
    assert TurboSettings().norm_loudness is True


def test_turbo_names_its_own_arguments_in_its_version():
    # Every one of them changes the audio without changing the words.
    plain = TurboSettings()
    for changed in (
        TurboSettings(min_p=0.1),
        TurboSettings(top_p=0.5),
        TurboSettings(top_k=50),
        TurboSettings(norm_loudness=False),
    ):
        assert changed.key() != plain.key()


def test_turbo_asks_the_model_for_the_things_only_it_takes(project):
    engine = ChatterboxTurboEngine(directory=project)
    asked = engine._arguments(0.4)
    assert asked["exaggeration"] == 0.4
    assert asked["norm_loudness"] is True
    assert "top_k" in asked


def test_the_older_model_asks_for_only_what_it_takes(project):
    # top_k and norm_loudness do not exist on it, and passing them would be a
    # TypeError inside the model rather than anything a person could read.
    asked = ChatterboxEngine(directory=project)._arguments(0.4)
    assert set(asked) == {"exaggeration", "cfg_weight", "temperature"}
