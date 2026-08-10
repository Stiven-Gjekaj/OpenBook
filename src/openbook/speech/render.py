"""Turns a plan into sound.

Every utterance goes through the cache. A render after a correction to one line
makes that line and takes the rest from the cache, so the second render of a
book costs almost nothing.

An engine that makes one word at a time sometimes repeats itself or stops
early, and raises rather than returning something wrong. This retries it a few
times before giving up, and says which line failed when it does.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ..cast.utterance import Silence, Utterance
from ..errors import OpenBookError
from ..plan.planner import Plan
from .audio import Audio, join_all
from .cache import Cache, key_of


@dataclass
class RenderReport:
    """What a render did, so that a person can see the cache working."""

    made: int = 0
    reused: int = 0
    retried: int = 0
    seconds: float = 0.0
    keys: set[str] = field(default_factory=set)

    @property
    def utterances(self) -> int:
        return self.made + self.reused


def render_plan(
    plan: Plan,
    engine,
    cache: Cache,
    *,
    retries: int = 2,
    on_utterance: Callable[[Utterance, str], None] | None = None,
) -> tuple[Audio, RenderReport]:
    """Make the audio for a plan, taking what the cache already holds."""
    report = RenderReport()
    pieces: list[Audio] = []

    for item in plan.items:
        if isinstance(item, Silence):
            pieces.append(Audio.silence(seconds=item.seconds, rate=engine.rate))
            continue

        key = key_of(item, engine)
        report.keys.add(key)
        audio = cache.get(key)
        if audio is None:
            audio = _speak(item, engine, retries, report)
            cache.put(key, audio)
            report.made += 1
        else:
            report.reused += 1
        if on_utterance is not None:
            on_utterance(item, key)
        pieces.append(audio)

    joined = join_all(pieces, engine.rate)
    report.seconds = joined.seconds
    return joined, report


def _speak(utterance: Utterance, engine, retries: int, report: RenderReport) -> Audio:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return engine.speak(utterance.text, utterance.voice)
        except OpenBookError:
            # An error a person can correct. Trying again gives the same
            # answer, so it goes straight up.
            raise
        except Exception as error:
            last = error
            if attempt < retries:
                report.retried += 1

    raise OpenBookError(
        f"the engine {engine.name!r} failed {retries + 1} times on the line "
        f"{utterance.text[:60]!r}, said by {utterance.speaker}. The last reason "
        f"was: {last}"
    ) from last
