import pytest

from openbook.cast.utterance import BlendedVoice, Voice
from openbook.errors import OpenBookError
from openbook.speech.espeak import EspeakEngine, installed, installed_version

needs_espeak = pytest.mark.skipif(not installed(), reason="espeak-ng is not installed")


def test_the_engine_names_itself():
    assert EspeakEngine().name == "espeak"


def test_a_speed_that_is_not_above_zero_is_refused():
    with pytest.raises(ValueError, match="above zero"):
        EspeakEngine(speed=0)


def test_nothing_to_say_is_refused_before_the_program_is_run():
    # This holds whether espeak-ng is installed or not, which is the point:
    # an empty line is the caller's mistake and not the machine's.
    with pytest.raises(OpenBookError, match="given nothing to say"):
        EspeakEngine().speak("   ", Voice("en-us"))


def test_a_blended_voice_is_refused_with_what_to_use_instead():
    # espeak-ng has no style to average. Saying so, and naming the two modes
    # that do work, beats giving one of the two characters the whole line.
    with pytest.raises(OpenBookError, match="mix"):
        EspeakEngine().speak(
            "Stop.", BlendedVoice(parts=("en-us", "en-gb"), weights=(0.5, 0.5))
        )


@needs_espeak
def test_the_speed_is_part_of_the_version():
    # The pace changes the audio, so a render at a new pace must not take the
    # old audio out of the cache.
    assert EspeakEngine(speed=1.0).version != EspeakEngine(speed=1.2).version
    assert installed_version() in EspeakEngine().version


@needs_espeak
def test_it_speaks():
    audio = EspeakEngine().speak("Hello there, this is a test.", Voice("en-us"))
    # espeak-ng itself writes 22050 and has no setting for it. What comes back
    # is the rate every other engine gives, so this one can be routed beside
    # them, and the resampling happens on the way out.
    assert audio.rate == 24000
    assert 0.5 < audio.seconds < 5
    assert any(audio.samples), "the audio is not silent"


@needs_espeak
def test_a_longer_line_takes_longer():
    engine = EspeakEngine()
    short = engine.speak("One.", Voice("en-us"))
    long = engine.speak("One two three four five six seven eight.", Voice("en-us"))
    assert long.seconds > short.seconds


@needs_espeak
def test_a_faster_speed_takes_less_time():
    words = "One two three four five six seven eight nine ten."
    slow = EspeakEngine(speed=0.7).speak(words, Voice("en-us"))
    quick = EspeakEngine(speed=1.5).speak(words, Voice("en-us"))
    assert quick.seconds < slow.seconds


@needs_espeak
def test_two_voices_say_the_same_words_differently():
    words = "The same words, said twice."
    one = EspeakEngine().speak(words, Voice("en-us"))
    two = EspeakEngine().speak(words, Voice("en-us+Alicia"))
    assert one.samples != two.samples


@needs_espeak
def test_a_line_starting_with_a_dash_is_spoken_and_not_read_as_an_argument():
    # Ordinary dialogue. The words go in on the input for this reason.
    audio = EspeakEngine().speak("-- he said, quietly.", Voice("en-us"))
    assert audio.seconds > 0.2


@needs_espeak
def test_a_voice_that_does_not_exist_is_named_with_where_to_look():
    with pytest.raises(OpenBookError, match="--voices"):
        EspeakEngine().speak("Words.", Voice("no_such_voice"))
