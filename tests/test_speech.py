import itertools
from array import array

import pytest

from openbook.cast.utterance import BlendedVoice, MixedVoice, Utterance, Voice
from openbook.errors import OpenBookError
from openbook.speech import Audio, Cache, SilentEngine, key_for, overlay
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


def test_the_kokoro_engine_reports_itself_without_loading_a_model():
    # Building the engine must not download anything. The model arrives the
    # first time something is spoken, and not before.
    from openbook.speech.kokoro import KokoroEngine

    engine = KokoroEngine()
    assert engine.name == "kokoro"
    assert engine.rate == 24000
    assert engine.max_characters == 480


def test_the_speed_is_part_of_the_kokoro_version():
    from openbook.speech.kokoro import KokoroEngine

    assert KokoroEngine(speed=1.0).version != KokoroEngine(speed=1.1).version


def test_a_speed_of_nothing_is_refused():
    from openbook.speech.kokoro import KokoroEngine

    with pytest.raises(ValueError, match="above zero"):
        KokoroEngine(speed=0)


def test_kokoro_refuses_a_voice_whose_language_it_cannot_tell():
    from openbook.speech.kokoro import KokoroEngine

    with pytest.raises(OpenBookError, match="names a language"):
        KokoroEngine().speak("hello", Voice("zz_nobody"))


def test_kokoro_refuses_to_say_nothing():
    from openbook.speech.kokoro import KokoroEngine

    with pytest.raises(OpenBookError, match="given nothing to say"):
        KokoroEngine().speak("  ", Voice("af_heart"))


def test_kokoro_not_being_installed_is_reported_and_not_retried(monkeypatch):
    # Not installed is something a person fixes. Without this it is tried three
    # times and reported as a fault in whichever line was being spoken.
    import builtins

    from openbook.speech.kokoro import KokoroEngine

    real = builtins.__import__

    def refuse(name, *rest, **kw):
        if name == "kokoro":
            raise ImportError("No module named 'kokoro'")
        return real(name, *rest, **kw)

    monkeypatch.setattr(builtins, "__import__", refuse)
    with pytest.raises(OpenBookError, match="uv sync --extra speech"):
        KokoroEngine().speak("hello", Voice("af_heart"))


def test_overlay_is_as_long_as_the_longest_piece():
    # Two people saying one line do not finish together. Stretching either to
    # fit would change what the engine said.
    short = Audio(samples=b"\x00\x00" * 10, rate=100)
    long = Audio(samples=b"\x00\x00" * 30, rate=100)
    assert len(overlay([short, long], 100).samples) == 60


def test_overlay_adds_the_samples():
    one = Audio(samples=array("h", [100, 200]).tobytes(), rate=100)
    two = Audio(samples=array("h", [10, 20]).tobytes(), rate=100)
    made = array("h")
    made.frombytes(overlay([one, two], 100).samples)
    assert list(made) == [110, 220]


def test_overlay_brings_a_sum_down_rather_than_letting_it_wrap():
    # A sum that wraps around does not sound loud. It sounds broken.
    loud = Audio(samples=array("h", [30000]).tobytes(), rate=100)
    made = array("h")
    made.frombytes(overlay([loud, loud], 100).samples)
    assert list(made) == [32767]


def test_overlay_keeps_the_weight_of_two_voices():
    # Two people saying one line are louder than one, so the samples are added
    # and not averaged. The one moment that wants weight must not be the
    # quietest in the chapter.
    one = Audio(samples=array("h", [1000]).tobytes(), rate=100)
    made = array("h")
    made.frombytes(overlay([one, one], 100).samples)
    assert list(made) == [2000]


def test_overlay_refuses_two_rates():
    one = Audio(samples=b"\x00\x00", rate=24000)
    two = Audio(samples=b"\x00\x00", rate=48000)
    with pytest.raises(OpenBookError, match="wrong speed"):
        overlay([one, two], 24000)


def test_a_mixed_voice_makes_the_engine_speak_once_for_each_part():
    from openbook.speech.render import _say

    class Counting(SilentEngine):
        def __init__(self):
            super().__init__()
            self.said = []

        def speak(self, text, voice, **rest):
            self.said.append(voice.name)
            return super().speak(text, voice, **rest)

    engine = Counting()
    audio = _say(engine, "one two", MixedVoice(parts=("a", "b")))
    assert engine.said == ["a", "b"]
    assert audio.seconds > 0


def test_a_mix_and_a_blend_of_the_same_voices_are_different_audio():
    mixed = MixedVoice(parts=("a", "b"))
    blended = BlendedVoice(parts=("a", "b"), weights=(0.5, 0.5))
    assert key_for("x", mixed, "e", "1") != key_for("x", blended, "e", "1")


def test_a_mixed_voice_needs_two_parts():
    with pytest.raises(ValueError, match="at least two parts"):
        MixedVoice(parts=("a",))


def test_a_matched_mix_is_not_the_same_audio_as_a_plain_one():
    plain = MixedVoice(parts=("a", "b"))
    matched = MixedVoice(parts=("a", "b"), matched=True)
    assert key_for("x", plain, "e", "1") != key_for("x", matched, "e", "1")


def test_a_plain_mix_asks_for_no_stretching(monkeypatch):
    # ffmpeg is only needed by the mode that asks for it. A book using the
    # plain mix must not start needing a program it never needed.
    import openbook.speech.stretch as stretching
    from openbook.speech.render import _say

    def refuse(*_):
        raise AssertionError("a plain mix must not stretch anything")

    monkeypatch.setattr(stretching, "to_one_length", refuse)
    audio = _say(SilentEngine(), "one two", MixedVoice(parts=("a", "b")))
    assert audio.seconds > 0


def test_a_matched_mix_needs_no_ffmpeg_when_the_lengths_already_agree():
    # The silent engine gives back a length that depends on the words alone,
    # so two readings of one line are already the same length and there is
    # nothing to stretch. A quick check of the pauses and the chapter marks
    # keeps working on a machine with nothing installed.
    from openbook.speech.render import _say

    audio = _say(
        SilentEngine(), "one two three", MixedVoice(parts=("a", "b"), matched=True)
    )
    assert audio.seconds > 0


def test_the_key_an_ordinary_engine_makes_did_not_change():
    """The engine names the voice now. For every engine but one, that is the
    name the voice already had, and audio made before the change must not be
    thrown away by it."""
    engine = SilentEngine()
    said = Utterance(text="one two", voice=Voice("af_heart"), kind="narration")
    assert key_of(said, engine) == key_for(
        "one two", Voice("af_heart"), engine.name, engine.version
    )


def test_the_cache_asks_the_engine_what_to_call_a_voice():
    # An engine whose voice lives in a file says so, and the cache follows it
    # rather than the name alone.
    class Fingerprinting(SilentEngine):
        def voice_key(self, voice, **rest):
            return f"{voice.key()}#take-two"

    said = Utterance(text="one two", voice=Voice("ivy.wav"), kind="narration")
    assert key_of(said, Fingerprinting()) != key_of(said, SilentEngine())


def test_a_key_names_the_engine_that_will_really_speak_the_line():
    """An engine holding several has to key on the one it hands out.

    Keying on the holder would give narration and dialogue the same engine in
    their keys. Then putting a second engine in front of one kind would serve
    the audio made by the other, and nothing would say so.
    """

    class Chooses:
        name, version, rate, max_characters = "holder", "1", 24000, 300

        def __init__(self, by_kind):
            self._by_kind = by_kind

        def for_kind(self, kind):
            return self._by_kind.get(kind, self)

        def voice_key(self, voice, *, kind="narration", exaggeration=None):
            return f"holder:{voice.key()}"

    inner = SilentEngine()
    holder = Chooses({"dialogue": inner})
    said = Utterance(text="Yes.", voice=Voice("v"), kind="dialogue", speaker="IVY")
    assert key_of(said, holder) == key_of(said, inner)


def test_a_key_is_unchanged_for_an_engine_that_chooses_nothing():
    # Every engine but one has no for_kind at all, and their keys must stay
    # exactly where they were.
    engine = SilentEngine()
    said = Utterance(text="Yes.", voice=Voice("v"), kind="narration", speaker="IVY")
    assert key_of(said, engine) == key_for(
        "Yes.", engine.voice_key(Voice("v")), engine.name, engine.version
    )


def test_resampling_keeps_the_length_of_the_sound():
    # The number of samples changes and the seconds do not. Getting this wrong
    # is a voice that speaks too fast, which sounds like a choice.
    from openbook.speech.audio import resampled

    audio = Audio(samples=bytes(2 * 22050), rate=22050)
    made = resampled(audio, 24000)
    assert made.rate == 24000
    assert made.seconds == pytest.approx(audio.seconds, abs=0.001)
    assert len(made.samples) // 2 == 24000


def test_resampling_to_the_rate_it_already_has_changes_nothing():
    from openbook.speech.audio import resampled

    audio = Audio(samples=b"\x01\x00\x02\x00", rate=24000)
    assert resampled(audio, 24000) is audio


def test_resampling_nothing_gives_nothing():
    from openbook.speech.audio import resampled

    assert resampled(Audio(samples=b"", rate=22050), 24000).samples == b""


def test_a_rate_of_nothing_is_refused_by_the_resampler():
    from openbook.speech.audio import resampled

    with pytest.raises(ValueError, match="above zero"):
        resampled(Audio(samples=b"\x01\x00", rate=22050), 0)


def test_resampling_follows_the_shape_of_the_sound():
    """A ramp stays a ramp, which a wrong index or a wrong step would break."""
    from openbook.speech.audio import bytes_of, resampled, values_of

    ramp = [round(-8000 + 16000 * i / 99) for i in range(100)]
    made = resampled(Audio(samples=bytes_of(ramp), rate=1000), 2000)
    values = values_of(made.samples)
    assert len(values) == 200
    assert values[0] == ramp[0]
    assert values[-1] == pytest.approx(ramp[-1], abs=200)
    # Rising all the way, with no step backwards anywhere in it.
    assert all(b >= a for a, b in itertools.pairwise(values))
