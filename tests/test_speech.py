import pytest

from openbook.cast.utterance import BlendedVoice, Utterance, Voice
from openbook.errors import OpenBookError
from openbook.speech import Audio, Cache, SilentEngine, key_for
from openbook.speech.cache import key_of


def test_silence_has_the_length_asked_for():
    audio = Audio.silence(seconds=1.5, rate=1000)
    assert audio.seconds == 1.5
    assert len(audio.samples) == 3000


def test_a_rate_of_nothing_is_refused():
    with pytest.raises(ValueError, match="above zero"):
        Audio(samples=b"", rate=0)


def test_a_silence_shorter_than_nothing_is_refused():
    with pytest.raises(ValueError, match="shorter than nothing"):
        Audio.silence(seconds=-1, rate=1000)


def test_joining_adds_the_lengths():
    one = Audio.silence(seconds=1, rate=1000)
    two = Audio.silence(seconds=2, rate=1000)
    assert one.join(two).seconds == 3


def test_two_rates_refuse_to_join():
    # Joining these would make one of the two speak at the wrong speed, which
    # sounds like a choice rather than a fault.
    with pytest.raises(OpenBookError, match="wrong speed"):
        Audio.silence(1, 24000).join(Audio.silence(1, 48000))


def test_audio_survives_a_trip_through_a_file(tmp_path):
    audio = Audio.silence(seconds=0.25, rate=8000)
    path = tmp_path / "one.wav"
    audio.write(path)
    assert Audio.read(path) == audio


def test_writing_leaves_no_half_written_file(tmp_path):
    path = tmp_path / "one.wav"
    Audio.silence(seconds=0.1, rate=8000).write(path)
    assert [p.name for p in tmp_path.iterdir()] == ["one.wav"]


def test_the_silent_engine_gives_the_length_the_words_would_take():
    engine = SilentEngine(words_each_minute=60, rate=1000)
    audio = engine.speak("one two three", Voice("v"))
    assert audio.seconds == pytest.approx(3.0)


def test_the_silent_engine_gives_the_same_answer_every_time():
    engine = SilentEngine()
    voice = Voice("v")
    assert engine.speak("a line", voice) == engine.speak("a line", voice)


def test_an_engine_refuses_to_say_nothing():
    with pytest.raises(OpenBookError, match="given nothing to say"):
        SilentEngine().speak("   ", Voice("v"))


def test_the_pace_is_part_of_the_version():
    # A render at a different pace is different audio, so it must not reuse
    # what the cache already holds.
    assert SilentEngine(words_each_minute=155).version != (
        SilentEngine(words_each_minute=170).version
    )


def test_the_key_changes_when_the_text_changes():
    voice = Voice("v")
    assert key_for("one", voice, "e", "1") != key_for("two", voice, "e", "1")


def test_the_key_changes_when_the_voice_changes():
    assert key_for("x", Voice("a"), "e", "1") != key_for("x", Voice("b"), "e", "1")


def test_the_key_changes_when_the_engine_or_its_version_changes():
    voice = Voice("v")
    assert key_for("x", voice, "a", "1") != key_for("x", voice, "b", "1")
    assert key_for("x", voice, "e", "1") != key_for("x", voice, "e", "2")


def test_the_key_changes_when_a_blend_weight_changes():
    one = BlendedVoice(parts=("a", "b"), weights=(0.5, 0.5))
    two = BlendedVoice(parts=("a", "b"), weights=(0.7, 0.3))
    assert key_for("x", one, "e", "1") != key_for("x", two, "e", "1")


def test_the_key_does_not_change_when_nothing_changes():
    voice = Voice("v")
    assert key_for("x", voice, "e", "1") == key_for("x", voice, "e", "1")


def test_the_parts_of_a_key_cannot_run_into_each_other():
    # Without a length in front of each part, a voice "a" with text "bc" and a
    # voice "ab" with text "c" would share one piece of audio.
    assert key_for("bc", Voice("a"), "e", "1") != key_for("c", Voice("ab"), "e", "1")


def test_the_key_ignores_where_a_line_sits_in_the_book():
    one = Utterance(text="Yes.", voice=Voice("v"), kind="dialogue", speaker="IVY")
    two = Utterance(text="Yes.", voice=Voice("v"), kind="narration", speaker="LEA")
    engine = SilentEngine()
    assert key_of(one, engine) == key_of(two, engine)


def test_the_cache_gives_back_what_it_was_given(tmp_path):
    cache = Cache(tmp_path)
    audio = Audio.silence(seconds=0.5, rate=8000)
    cache.put("abcdef", audio)
    assert cache.holds("abcdef")
    assert cache.get("abcdef") == audio


def test_the_cache_gives_nothing_for_a_key_it_does_not_hold(tmp_path):
    assert Cache(tmp_path).get("missing") is None


def test_the_cache_spreads_its_files_over_directories(tmp_path):
    cache = Cache(tmp_path)
    cache.put("ab1234", Audio.silence(0.1, 8000))
    assert (tmp_path / "ab" / "ab1234.wav").exists()


def test_the_cache_counts_and_measures_what_it_holds(tmp_path):
    cache = Cache(tmp_path)
    cache.put("aa1", Audio.silence(0.1, 8000))
    cache.put("bb2", Audio.silence(0.1, 8000))
    assert cache.keys() == {"aa1", "bb2"}
    assert cache.size() > 0


def test_the_cache_removes_what_nothing_points_at(tmp_path):
    cache = Cache(tmp_path)
    cache.put("keep", Audio.silence(0.1, 8000))
    cache.put("drop", Audio.silence(0.1, 8000))
    assert cache.prune({"keep"}) == 1
    assert cache.keys() == {"keep"}


def test_pruning_leaves_no_empty_directory(tmp_path):
    cache = Cache(tmp_path)
    cache.put("drop", Audio.silence(0.1, 8000))
    cache.prune(set())
    assert list(tmp_path.iterdir()) == []
