import pytest

from openbook.cast.utterance import (
    ANNOUNCEMENT,
    DIALOGUE,
    HOST,
    NARRATION,
    Utterance,
    Voice,
)
from openbook.errors import OpenBookError
from openbook.speech.audio import Audio
from openbook.speech.cache import key_of
from openbook.speech.engine import SilentEngine
from openbook.speech.routing import ByKind

VOICE = Voice("blook")


class Fake:
    """An engine that says which one it is, and how long it was asked for."""

    def __init__(self, name, *, rate=24000, limit=300):
        self.name = name
        self.version = f"{name}-1"
        self.rate = rate
        self.max_characters = limit
        self.said: list[tuple[str, str]] = []
        self.closed = False

    def voice_key(self, voice, *, kind=NARRATION, exaggeration=None):
        return f"{self.name}:{voice.key()}"

    def speak(self, text, voice, *, kind=NARRATION, exaggeration=None):
        self.said.append((kind, text))
        return Audio.silence(seconds=1.0, rate=self.rate)

    def close(self):
        self.closed = True


def utterance(kind, text="Anything at all."):
    return Utterance(text=text, voice=VOICE, kind=kind, speaker="BLK")


def test_a_kind_nobody_routed_goes_to_the_default():
    turbo, other = Fake("turbo"), Fake("other")
    engine = ByKind(turbo, by_kind={DIALOGUE: other})
    assert engine.for_kind(NARRATION) is turbo
    assert engine.for_kind(ANNOUNCEMENT) is turbo
    assert engine.for_kind(DIALOGUE) is other


def test_the_key_of_an_unrouted_line_does_not_change():
    """The whole point, and the thing that costs most to get wrong.

    A volume already rendered by one engine has to keep every line of the
    kinds nobody routed. If the key moved, putting a second engine in front of
    dialogue would quietly make the narration again, which for Soultale is
    four hours of it.
    """
    turbo = Fake("turbo")
    alone = turbo
    routed = ByKind(turbo, by_kind={DIALOGUE: Fake("other")})
    for kind in (NARRATION, ANNOUNCEMENT, "end matter"):
        said = utterance(kind)
        assert key_of(said, routed) == key_of(said, alone), kind


def test_the_key_of_a_routed_line_does_change():
    turbo = Fake("turbo")
    routed = ByKind(turbo, by_kind={DIALOGUE: Fake("other")})
    said = utterance(DIALOGUE)
    assert key_of(said, routed) != key_of(said, turbo)


def test_the_key_names_the_engine_that_speaks_and_not_the_holder():
    other = Fake("other")
    routed = ByKind(Fake("turbo"), by_kind={DIALOGUE: other})
    said = utterance(DIALOGUE)
    # The same key as if that engine had been asked on its own, so a line made
    # one way is found the other way round.
    assert key_of(said, routed) == key_of(said, other)


def test_a_line_is_spoken_by_the_engine_its_kind_names():
    turbo, other = Fake("turbo"), Fake("other")
    engine = ByKind(turbo, by_kind={DIALOGUE: other, HOST: other})
    engine.speak("Narration here.", VOICE, kind=NARRATION)
    engine.speak("Dialogue here.", VOICE, kind=DIALOGUE)
    engine.speak("Welcome back.", VOICE, kind=HOST)
    assert turbo.said == [(NARRATION, "Narration here.")]
    assert other.said == [(DIALOGUE, "Dialogue here."), (HOST, "Welcome back.")]


def test_the_voice_key_comes_from_the_engine_that_speaks():
    engine = ByKind(Fake("turbo"), by_kind={DIALOGUE: Fake("other")})
    assert engine.voice_key(VOICE, kind=NARRATION) == "turbo:blook"
    assert engine.voice_key(VOICE, kind=DIALOGUE) == "other:blook"


def test_engines_that_disagree_about_the_rate_are_refused():
    # Two rates meeting is refused where the pieces are joined, which is well
    # into a volume. Saying so before anything is spoken is the whole point.
    with pytest.raises(OpenBookError, match="different rates"):
        ByKind(Fake("turbo"), by_kind={DIALOGUE: Fake("other", rate=22050)})


def test_a_kind_that_does_not_exist_is_refused():
    with pytest.raises(OpenBookError, match="no kind of line called 'dialog'"):
        ByKind(Fake("turbo"), by_kind={"dialog": Fake("other")})


def test_it_takes_the_least_text_any_of_them_takes():
    # The planner divides a line once, before anything is spoken, so the cut
    # has to suit whichever engine ends up saying it.
    engine = ByKind(
        Fake("turbo", limit=480), by_kind={DIALOGUE: Fake("other", limit=300)}
    )
    assert engine.max_characters == 300


def test_it_holds_one_rate_and_names_the_route():
    engine = ByKind(Fake("turbo"), by_kind={DIALOGUE: Fake("other")})
    assert engine.rate == 24000
    assert "turbo" in engine.name and "dialogue=other" in engine.name


def test_routing_nothing_is_the_engine_it_was_given():
    turbo = Fake("turbo")
    engine = ByKind(turbo)
    assert engine.for_kind(DIALOGUE) is turbo
    assert engine.name == "turbo"
    said = utterance(DIALOGUE)
    assert key_of(said, engine) == key_of(said, turbo)


def test_closing_lets_go_of_every_engine_once():
    turbo, other = Fake("turbo"), Fake("other")
    ByKind(turbo, by_kind={DIALOGUE: other, HOST: other}).close()
    assert turbo.closed and other.closed


def test_an_engine_with_nothing_to_close_is_not_a_problem():
    ByKind(SilentEngine(), by_kind={DIALOGUE: SilentEngine()}).close()


# The command line is where a person writes this, so what it refuses matters
# as much as what it accepts. A misspelled kind accepted in silence routes
# nothing and gives back the render somebody was trying not to make.


class Options:
    def __init__(self, **fields):
        self.__dict__.update(fields)


def options(**named):
    fields = {"project": ".", "engine": "silent", "engine_for": []}
    fields.update(named)
    return Options(**fields)


def test_the_command_line_builds_the_route():
    from openbook.cli import _engine_for

    # Neither engine is loaded here. Building one only remembers what it was
    # told, and the model arrives when a line is first spoken.
    made = _engine_for(options(engine_for=["dialogue=chatterbox-turbo"]))
    assert made.for_kind(DIALOGUE).name == "chatterbox-turbo"
    assert made.for_kind(NARRATION).name == "silent"


def test_espeak_can_be_routed_beside_the_others():
    """It writes 22050 and gives back 24000, so it joins the rest.

    Skimming a volume for its pacing at espeak speed while still hearing the
    real character voices is the reason to want this.
    """
    from openbook.cli import _engine_for

    made = _engine_for(
        options(engine="chatterbox-turbo", engine_for=["narration=espeak"])
    )
    assert made.for_kind("narration").name == "espeak"
    assert made.rate == 24000


def test_asking_for_no_route_gives_one_plain_engine():
    from openbook.cli import _engine_for

    made = _engine_for(options())
    assert made.name == "silent"
    assert not hasattr(made, "for_kind")


@pytest.mark.parametrize(
    "pair, complaint",
    [
        ("dialogue", "takes KIND=ENGINE"),
        ("=espeak", "takes KIND=ENGINE"),
        ("dialogue=", "takes KIND=ENGINE"),
        ("dialog=espeak", "no kind of line called"),
        ("dialogue=festival", "no engine called"),
    ],
)
def test_the_command_line_says_which_part_is_wrong(pair, complaint):
    from openbook.cli import _engine_for

    with pytest.raises(OpenBookError, match=complaint):
        _engine_for(options(engine_for=[pair]))
