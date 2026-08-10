"""The espeak-ng engine.

This is not the voice a book ships in. It is a formant synthesiser from the
1990s and it sounds like one.

It is here because it is the only engine in this project that a person always
has. espeak-ng is already needed by the word finder, it needs no model, no
download, and no Python package, and it runs on every machine the tests run on.
That makes it the engine that proves the interface takes a second one, and it
makes it useful in its own right: it says real words at real lengths, so the
captions, the chapter marks and the cards of a whole volume can be checked
against real speech in seconds rather than in the twenty three minutes a model
takes.

Between the two engines already here it is the middle. The silent engine is a
clock and says nothing. Kokoro says it well and is slow. This says it badly and
is quick.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from ..cast.utterance import BlendedVoice, Voice, VoiceRef
from ..errors import OpenBookError
from .audio import Audio
from .engine import MAX_CHARACTERS

PROGRAM = "espeak-ng"

# What espeak-ng writes. Every voice built into it gives this, and a voice that
# gives something else is refused by name rather than joined at the wrong speed.
RATE = 22050

# The pace espeak-ng reads at when nothing says otherwise, in words each
# minute. A speed of 1.0 means this.
WORDS_EACH_MINUTE = 175

_VERSION = re.compile(r"(\d+\.\d+(?:\.\d+)?)")


class EspeakEngine:
    """Speaks with espeak-ng.

    A voice is written the way espeak-ng writes one: a language, and a variant
    after a plus. `en-us`, `en-gb-x-rp`, `en-us+Alicia`. `espeak-ng --voices`
    lists the languages and `espeak-ng --voices=variant` lists the variants.
    """

    def __init__(
        self, *, speed: float = 1.0, max_characters: int | None = MAX_CHARACTERS
    ) -> None:
        if speed <= 0:
            raise ValueError("a speed must be above zero")
        self._speed = speed
        self._max = max_characters
        self._version: str | None = None

    @property
    def name(self) -> str:
        return "espeak"

    @property
    def version(self) -> str:
        # The pace changes the audio, so it belongs in the version and the
        # cache must not reuse across a change of it.
        if self._version is None:
            self._version = f"{installed_version()}-{self._speed:g}"
        return self._version

    @property
    def rate(self) -> int:
        return RATE

    @property
    def max_characters(self) -> int | None:
        return self._max

    def speak(self, text: str, voice: VoiceRef) -> Audio:
        if not text.strip():
            raise OpenBookError("a speech engine was given nothing to say")
        if isinstance(voice, BlendedVoice):
            raise OpenBookError(
                "espeak-ng cannot blend two voices, because it has no style to "
                "average. For a line two characters say together, use the mix "
                "mode, which speaks it once in each voice, or primary, which "
                "gives it to the first of them"
            )

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "said.wav"
            self._run(text, _name_of(voice), out)
            audio = Audio.read(out)

        if audio.rate != RATE:
            raise OpenBookError(
                f"the voice {_name_of(voice)!r} gave audio at {audio.rate} "
                f"where every other voice gives {RATE}. Joining the two would "
                "make one of them speak at the wrong speed"
            )
        return audio

    def _run(self, text: str, voice: str, out: Path) -> None:
        """Say one line into a file.

        The words go in on the input rather than as an argument. A line that
        starts with a dash is an argument to a program and a perfectly ordinary
        piece of dialogue, and this is the only way to keep it the second one.
        """
        pace = round(WORDS_EACH_MINUTE * self._speed)
        try:
            done = subprocess.run(
                [PROGRAM, "-v", voice, "-s", str(pace), "-w", str(out)],
                input=text,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as error:
            raise OpenBookError(
                f"{PROGRAM} is not installed. On macOS 'brew install espeak-ng', "
                "on Debian or Ubuntu 'apt install espeak-ng'"
            ) from error

        if done.returncode != 0 or not out.exists():
            said = (done.stderr or done.stdout or "").strip().rstrip(".")
            raise OpenBookError(
                f"{PROGRAM} refused the voice {voice!r}: {said or 'no reason given'}. "
                f"'{PROGRAM} --voices' lists the languages and "
                f"'{PROGRAM} --voices=variant' lists the variants"
            )


def _name_of(voice: VoiceRef) -> str:
    if isinstance(voice, Voice):
        return voice.name
    raise OpenBookError(f"espeak-ng was given a voice it cannot read: {voice!r}")


def installed_version() -> str:
    """Which espeak-ng is here. Part of the cache key, so it must be exact."""
    try:
        done = subprocess.run(
            [PROGRAM, "--version"], capture_output=True, text=True, check=False
        )
    except FileNotFoundError as error:
        raise OpenBookError(
            f"{PROGRAM} is not installed. On macOS 'brew install espeak-ng', "
            "on Debian or Ubuntu 'apt install espeak-ng'"
        ) from error

    found = _VERSION.search(done.stdout or "")
    if found is None:
        # A build that does not say. The audio it makes is still its own, so
        # this must not read as the same version as one that does.
        return "unknown"
    return found.group(1)


def installed() -> bool:
    try:
        return (
            subprocess.run(
                [PROGRAM, "--version"], capture_output=True, check=False
            ).returncode
            == 0
        )
    except FileNotFoundError:
        return False
