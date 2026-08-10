"""The Chatterbox engine.

Chatterbox takes a short recording of a voice and reads the book in that voice.
That is the whole reason it is here: a voice chosen from a list of twenty eight
is a voice somebody else has already used, and a voice taken from a recording
is the character.

It is autoregressive, and that is the thing to know about it. It makes a token
at a time, so it can repeat itself, drop a word, or trail off, and Kokoro
cannot. Over three hundred thousand words it will do all three some number of
times. Two things hold that down. The planner already cuts everything into
pieces of a few hundred characters, and a short piece wanders far less than a
long one. And the limit here is lower than the one the other engines use, for
the same reason.

None of that finds a dropped word. Nothing does except listening, which is what
the review page is for. This engine is the reason that page exists.

A voice is the path to a recording, written in cast.toml and read relative to
the project directory:

    [cast.BLK]
    name  = "Blook"
    voice = "voices/blook.wav"

Ten to twenty seconds of clean speech is enough. What is in the recording is
what comes out: the accent, the pace, the room it was recorded in, and any
noise behind it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..cast.utterance import (
    DIALOGUE,
    NARRATION,
    BlendedVoice,
    MixedVoice,
    Voice,
    VoiceRef,
)
from ..errors import OpenBookError
from .audio import Audio

RATE = 24000

# Shorter than the limit the other engines take. A model that makes a token at
# a time wanders further the longer it is left running, and the cut falls at
# the end of a sentence either way, so a lower limit costs nothing but a few
# more pieces and buys back the failure that is hardest to find.
MAX_CHARACTERS = 300

# How much the reading leans on the feeling in the reference recording.
#
# Narration and dialogue do not want the same amount. A narrator states what
# happened and holds a level tone for hours, and a character in a fantasy is
# frightened or lying or giving an order. One value for both gives either a
# theatrical narrator or a flat cast, and the book has 79 percent of the first
# and all of the second.
NARRATION_EXAGGERATION = 0.3
DIALOGUE_EXAGGERATION = 0.7

# How closely the reading holds to the reference, and how much the model is
# allowed to wander. Neither depends on what a line is for, so both are the
# same everywhere and both belong in the version.
GUIDANCE = 0.5
TEMPERATURE = 0.8


@dataclass(frozen=True)
class Settings:
    """What to ask of the model. Part of the cache key, so it is written out."""

    narration: float = NARRATION_EXAGGERATION
    dialogue: float = DIALOGUE_EXAGGERATION
    guidance: float = GUIDANCE
    temperature: float = TEMPERATURE

    def exaggeration(self, kind: str, asked: float | None = None) -> float:
        """How much feeling to read one line with.

        A number the cast file gives for a character wins, because somebody
        wrote it down about that character. With nothing written down the kind
        of the line decides.

        Only dialogue is dialogue. An action that the narrator speaks, a
        chapter announcement and the end matter are all the narrator talking,
        and they are read the way the narration is read.
        """
        if asked is not None:
            return asked
        return self.dialogue if kind == DIALOGUE else self.narration

    def key(self) -> str:
        """What every line shares. The exaggeration is not here.

        The exaggeration changes with the kind of the line, so it goes into
        the key of each line instead. Then a change to how the cast is read
        remakes the cast and leaves three hundred thousand words of narration
        where they are.
        """
        return f"g{self.guidance:g}-t{self.temperature:g}"


class ChatterboxEngine:
    """Speaks in the voice of a recording."""

    def __init__(
        self,
        *,
        directory: Path | None = None,
        settings: Settings | None = None,
        device: str | None = None,
        max_characters: int | None = MAX_CHARACTERS,
    ) -> None:
        self._directory = Path(directory) if directory else Path()
        self._settings = settings or Settings()
        self._device = device
        self._max = max_characters
        self._model = None
        self._version: str | None = None

    @property
    def name(self) -> str:
        return "chatterbox"

    @property
    def version(self) -> str:
        # Everything that changes the audio without changing the words belongs
        # here, so a change to any of it makes the audio again rather than
        # taking the old sound out of the cache.
        if self._version is None:
            self._version = f"{installed_version()}-{self._settings.key()}"
        return self._version

    @property
    def rate(self) -> int:
        return RATE

    @property
    def max_characters(self) -> int | None:
        return self._max

    def voice_key(
        self,
        voice: VoiceRef,
        *,
        kind: str = NARRATION,
        exaggeration: float | None = None,
    ) -> str:
        """The name of the voice, the recording, and how it is read.

        The name is a path and the sound is the file. A better take of the same
        character is written to the same path, and without the file in the key
        every line she has would come back in the old voice for ever, without
        a word about it anywhere.

        The exaggeration is here and not in the version, because it is chosen
        by the kind of the line. In the version it would remake the whole book
        every time the cast was tuned.
        """
        said = _named(voice, lambda name: f"{name}#{self._fingerprint(name)}")
        return f"{said}@e{self._settings.exaggeration(kind, exaggeration):g}"

    def speak(
        self,
        text: str,
        voice: VoiceRef,
        *,
        kind: str = NARRATION,
        exaggeration: float | None = None,
    ) -> Audio:
        if not text.strip():
            raise OpenBookError("a speech engine was given nothing to say")
        if isinstance(voice, BlendedVoice):
            raise OpenBookError(
                "Chatterbox cannot blend two voices, because a voice here is a "
                "recording and not a style that can be averaged. For a line two "
                "characters say together use mix or mix_matched, which speak it "
                "once in each voice, or primary, which gives it to the first"
            )
        if not isinstance(voice, Voice):
            raise OpenBookError(
                f"Chatterbox was given a voice it cannot read: {voice!r}"
            )

        # The recording is the caller's own file, so whether it is there is
        # answered before the model is asked for. Loading a model to find out
        # that a file is missing reports the wrong problem and takes a minute.
        reference = self.reference_for(voice.name)

        model = self._loaded()
        self._seed(text, voice)
        wave = model.generate(
            text,
            audio_prompt_path=str(reference),
            exaggeration=self._settings.exaggeration(kind, exaggeration),
            cfg_weight=self._settings.guidance,
            temperature=self._settings.temperature,
        )
        return Audio(samples=_to_bytes(wave), rate=RATE)

    def reference_for(self, name: str) -> Path:
        """The recording a voice is taken from, named the way a person wrote it."""
        path = Path(name)
        if not path.is_absolute():
            path = self._directory / path
        if not path.exists():
            raise OpenBookError(
                f"the voice {name!r} is the recording {path}, and there is no "
                "file there. A Chatterbox voice is a path to a recording of the "
                "character, written in cast.toml and read from the project "
                "directory"
            )
        return path

    def _fingerprint(self, name: str) -> str:
        """Enough of the recording to tell one take from another."""
        path = self.reference_for(name)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return digest[:16]

    def _seed(self, text: str, voice: VoiceRef) -> None:
        """Make the same words in the same voice come out the same way.

        The model reads with a temperature, so left alone it says a line
        differently every time. A book is made over days and in pieces, and a
        line remade next week has to match the chapter it sits in, so the
        starting point comes from the words and the voice and nothing else.
        """
        import torch

        seed = hashlib.sha256(f"{voice.key()}\x1f{text}".encode()).digest()
        torch.manual_seed(int.from_bytes(seed[:8], "big"))

    def _loaded(self):
        if self._model is None:
            try:
                from chatterbox.tts import ChatterboxTTS
            except ImportError as error:
                # Not installed is something a person fixes, not something that
                # works on a second attempt. Without this it is tried three
                # times and then reported as a fault in the line being spoken.
                raise OpenBookError(
                    "chatterbox is not installed, so nothing can be spoken with "
                    "it. Add it with 'uv sync --extra chatterbox', or use "
                    "'--engine kokoro'"
                ) from error
            self._model = ChatterboxTTS.from_pretrained(device=self._device or device())
        return self._model


def _named(voice: VoiceRef, rename) -> str:
    """Put a new name on each voice inside a voice, and keep the shape."""
    if isinstance(voice, Voice):
        return rename(voice.name)
    if isinstance(voice, MixedVoice):
        parts = tuple(rename(part) for part in voice.parts)
        return type(voice)(parts=parts, matched=voice.matched).key()
    return voice.key()


def device() -> str:
    """Where the model runs. The fastest thing this machine has."""
    try:
        import torch
    except ImportError:  # pragma: no cover
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _to_bytes(wave) -> bytes:
    """Turn what the model gives back into 16 bit samples of one channel.

    The values are held inside the range first. A model can give back a little
    over 1, and letting that wrap around makes a loud click.
    """
    import numpy

    samples = wave.detach().cpu().numpy() if hasattr(wave, "detach") else wave
    samples = numpy.asarray(samples, dtype=numpy.float32).reshape(-1)
    held = numpy.clip(samples, -1.0, 1.0)
    return (held * 32767.0).astype("<i2").tobytes()


def installed_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    for name in ("chatterbox-tts", "chatterbox"):
        try:
            return version(name)
        except PackageNotFoundError:
            continue
    return "unknown"


def installed() -> bool:
    from importlib.util import find_spec

    try:
        return find_spec("chatterbox.tts") is not None
    except (ImportError, ValueError):  # pragma: no cover
        return False
