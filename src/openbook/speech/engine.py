"""What a speech engine has to offer, and the one that says nothing.

An engine is behind an interface so that the narrator and a character can use
different ones. The narrator reads most of the book in one voice and wants an
engine that does not drift over hundreds of thousands of words. A character
speaks in pieces of about thirteen words, where an engine that is less steady
is safe and a bad piece costs five seconds to make again.

The silent engine is not a poor voice. It is a clock. It gives back quiet of
the length the words would take, so every stage after this one can be built and
checked before any model is downloaded, and so a person can hear where the
pauses fall in a finished chapter without waiting for a real render.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..cast.utterance import BlendedVoice, VoiceRef
from ..errors import OpenBookError
from .audio import Audio

# How fast a narrator reads. The usual pace of an audiobook, and the number the
# silent engine uses to decide how long a piece of quiet must be.
WORDS_EACH_MINUTE = 155

# How much text an engine is handed at once. Every engine here takes the same
# amount, and it is named once because the number decides where a long line is
# divided, and a piece of a divided line is what a correction names. Two
# engines that disagreed about it would disagree about what a correction means.
MAX_CHARACTERS = 480


@runtime_checkable
class Engine(Protocol):
    """Anything that can turn text into sound."""

    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    @property
    def rate(self) -> int: ...

    @property
    def max_characters(self) -> int | None: ...

    def speak(self, text: str, voice: VoiceRef) -> Audio: ...


class SilentEngine:
    """Gives back quiet of the length the words would take.

    The result depends only on the text, so the same line always gives the same
    length, and a render can be compared with the one before it.
    """

    def __init__(
        self,
        *,
        rate: int = 24000,
        words_each_minute: int = WORDS_EACH_MINUTE,
        max_characters: int | None = MAX_CHARACTERS,
    ) -> None:
        if words_each_minute <= 0:
            raise ValueError("a pace must be above zero")
        self._rate = rate
        self._pace = words_each_minute
        self._max = max_characters

    @property
    def name(self) -> str:
        return "silent"

    @property
    def version(self) -> str:
        # The pace is part of the version. A render at a different pace gives
        # different audio, so it must not reuse what the cache already holds.
        return f"1-{self._pace}"

    @property
    def rate(self) -> int:
        return self._rate

    @property
    def max_characters(self) -> int | None:
        return self._max

    def speak(self, text: str, voice: VoiceRef) -> Audio:
        if not text.strip():
            raise OpenBookError("a speech engine was given nothing to say")
        if isinstance(voice, BlendedVoice) and not voice.parts:
            raise OpenBookError("a blended voice with no parts cannot speak")
        words = len(text.split())
        return Audio.silence(seconds=words / self._pace * 60, rate=self._rate)
