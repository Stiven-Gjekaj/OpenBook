import pytest

from openbook.cast.utterance import Silence, Utterance, Voice
from openbook.errors import OpenBookError
from openbook.plan.planner import Plan
from openbook.speech import Audio, Cache, SilentEngine
from openbook.speech.render import render_plan

VOICE = Voice("af_heart")


def line(text="one two three"):
    return Utterance(text=text, voice=VOICE, kind="narration")


class Counting(SilentEngine):
    """A silent engine that says how many times it was asked to speak."""

    def __init__(self, **rest):
        super().__init__(**rest)
        self.calls = 0

    def speak(self, text, voice):
        self.calls += 1
        return super().speak(text, voice)


class Failing(SilentEngine):
    """Fails a set number of times before it works."""

    def __init__(self, failures, **rest):
        super().__init__(**rest)
        self.left = failures
        self.calls = 0

    def speak(self, text, voice):
        self.calls += 1
        if self.left:
            self.left -= 1
            raise RuntimeError("the model stopped early")
        return super().speak(text, voice)


def test_a_plan_becomes_audio(tmp_path):
    engine = SilentEngine(words_each_minute=60, rate=1000)
    plan = Plan(items=(line("one two three"),))
    audio, report = render_plan(plan, engine, Cache(tmp_path))
    assert audio.seconds == pytest.approx(3.0)
    assert report.made == 1
    assert report.reused == 0


def test_a_silence_takes_the_length_the_plan_asked_for(tmp_path):
    engine = SilentEngine(words_each_minute=60, rate=1000)
    plan = Plan(items=(Silence(seconds=2.0, reason="scene break"),))
    audio, _ = render_plan(plan, engine, Cache(tmp_path))
    assert audio.seconds == pytest.approx(2.0)


def test_the_second_render_takes_everything_from_the_cache(tmp_path):
    # The whole reason the cache exists. The engine must not be asked twice.
    engine = Counting(words_each_minute=60, rate=1000)
    cache = Cache(tmp_path)
    plan = Plan(items=(line("one"), line("two")))
    render_plan(plan, engine, cache)
    assert engine.calls == 2

    again = Counting(words_each_minute=60, rate=1000)
    _, report = render_plan(plan, again, cache)
    assert again.calls == 0
    assert report.reused == 2
    assert report.made == 0


def test_a_correction_to_one_line_makes_only_that_line(tmp_path):
    engine = Counting(words_each_minute=60, rate=1000)
    cache = Cache(tmp_path)
    render_plan(Plan(items=(line("one"), line("two"))), engine, cache)

    fixed = Counting(words_each_minute=60, rate=1000)
    plan = Plan(items=(line("one"), line("two corrected")))
    _, report = render_plan(plan, fixed, cache)
    assert fixed.calls == 1
    assert report.made == 1
    assert report.reused == 1


def test_the_same_words_in_the_same_voice_are_made_one_time(tmp_path):
    engine = Counting(words_each_minute=60, rate=1000)
    plan = Plan(items=(line("yes"), line("yes")))
    _, report = render_plan(plan, engine, Cache(tmp_path))
    assert engine.calls == 1
    assert report.made == 1
    assert report.reused == 1


def test_a_change_of_voice_makes_the_line_again(tmp_path):
    engine = Counting(words_each_minute=60, rate=1000)
    cache = Cache(tmp_path)
    render_plan(Plan(items=(line("yes"),)), engine, cache)

    other = Counting(words_each_minute=60, rate=1000)
    recast = Utterance(text="yes", voice=Voice("am_michael"), kind="narration")
    _, report = render_plan(Plan(items=(recast,)), other, cache)
    assert other.calls == 1
    assert report.made == 1


def test_an_engine_that_fails_is_tried_again(tmp_path):
    engine = Failing(failures=2, words_each_minute=60, rate=1000)
    _, report = render_plan(
        Plan(items=(line("one"),)), engine, Cache(tmp_path), retries=2
    )
    assert engine.calls == 3
    assert report.retried == 2
    assert report.made == 1


def test_an_engine_that_keeps_failing_names_the_line(tmp_path):
    engine = Failing(failures=9, words_each_minute=60, rate=1000)
    plan = Plan(
        items=(
            Utterance(text="a hard line", voice=VOICE, kind="dialogue", speaker="IVY"),
        )
    )
    with pytest.raises(OpenBookError, match="failed 3 times on the line 'a hard line'"):
        render_plan(plan, engine, Cache(tmp_path), retries=2)


def test_an_error_a_person_can_correct_is_not_retried(tmp_path):
    # Trying again gives the same answer, so it goes straight up.
    engine = Counting(words_each_minute=60, rate=1000)
    plan = Plan(items=(Utterance(text="   ", voice=VOICE, kind="narration"),))
    with pytest.raises(OpenBookError, match="given nothing to say"):
        render_plan(plan, engine, Cache(tmp_path), retries=5)
    assert engine.calls == 1


def test_the_report_names_every_key_the_render_used(tmp_path):
    engine = SilentEngine(words_each_minute=60, rate=1000)
    cache = Cache(tmp_path)
    _, report = render_plan(Plan(items=(line("one"), line("two"))), engine, cache)
    assert report.keys == cache.keys()


def test_the_keys_of_a_render_are_what_pruning_keeps(tmp_path):
    engine = SilentEngine(words_each_minute=60, rate=1000)
    cache = Cache(tmp_path)
    render_plan(Plan(items=(line("old"),)), engine, cache)
    _, report = render_plan(Plan(items=(line("new"),)), engine, cache)
    assert cache.prune(report.keys) == 1
    assert cache.keys() == report.keys


def test_an_empty_plan_gives_audio_of_no_length(tmp_path):
    engine = SilentEngine(rate=1000)
    audio, report = render_plan(Plan(items=()), engine, Cache(tmp_path))
    assert audio.seconds == 0
    assert audio.rate == 1000
    assert report.utterances == 0


def test_the_caller_is_told_about_each_utterance(tmp_path):
    engine = SilentEngine(words_each_minute=60, rate=1000)
    seen = []
    render_plan(
        Plan(items=(line("one"), line("two"))),
        engine,
        Cache(tmp_path),
        on_utterance=lambda utterance, key: seen.append(utterance.text),
    )
    assert seen == ["one", "two"]


def test_audio_from_the_cache_matches_what_was_made(tmp_path):
    engine = SilentEngine(words_each_minute=60, rate=8000)
    cache = Cache(tmp_path)
    plan = Plan(items=(line("one two"),))
    first, _ = render_plan(plan, engine, cache)
    second, _ = render_plan(plan, engine, cache)
    assert first == second
    assert isinstance(first, Audio)
