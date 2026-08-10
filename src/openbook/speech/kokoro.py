"""The Kokoro engine.

Kokoro is small, permissively licensed, and not autoregressive. That last part
is why it reads the narration: a model that makes one word at a time can loop,
drop a word, or trail off, and over three hundred thousand words of narration
it will do all three. Kokoro cannot. Its failure is a wrong sound for a word,
which the lexicon corrects, and not a wrong number of words, which nothing
finds except listening.

A voice name says which accent it is. A name starting with a or b is American
or British, and the phonemizer needs to be told which, because the same letters
are said differently in the two.
"""

from __future__ import annotations

from ..cast.utterance import NARRATION, BlendedVoice, Voice, VoiceRef
from ..errors import OpenBookError
from .audio import Audio
from .engine import MAX_CHARACTERS

RATE = 24000

# The first letter of a voice name gives its language for the phonemizer.
LANGUAGES = {"a": "a", "b": "b"}


class KokoroEngine:
    """Speaks with Kokoro."""

    def __init__(
        self, *, speed: float = 1.0, max_characters: int | None = MAX_CHARACTERS
    ) -> None:
        if speed <= 0:
            raise ValueError("a speed must be above zero")
        self._speed = speed
        self._max = max_characters
        self._pipelines: dict[str, object] = {}
        self._version: str | None = None

    @property
    def name(self) -> str:
        return "kokoro"

    @property
    def version(self) -> str:
        # The speed changes the audio, so it belongs in the version and the
        # cache must not reuse across a change of it.
        if self._version is None:
            self._version = f"{_installed_version()}-{self._speed:g}"
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
        return voice.key()

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

        name = _first_name(voice)
        pipeline = self._pipeline_for(name)
        samples = _samples(
            pipeline, text, self._voice_for(voice, pipeline), self._speed
        )
        if samples is None:
            raise RuntimeError(f"kokoro gave back nothing for {text[:60]!r}")
        return Audio(samples=_to_bytes(samples), rate=RATE)

    def _pipeline_for(self, name: str):
        language = LANGUAGES.get(name[:1])
        if language is None:
            raise OpenBookError(
                f"the voice {name!r} does not start with a letter that names a "
                "language. A Kokoro voice starts with a for American English or "
                "b for British English"
            )
        if language not in self._pipelines:
            # Not installed is something a person fixes, not something that
            # works on a second attempt. Without this it is tried three times
            # and then reported as a fault in the line being spoken.
            try:
                from kokoro import KPipeline
            except ImportError as error:
                raise OpenBookError(
                    "kokoro is not installed, so nothing can be spoken with it. "
                    "Add it with 'uv sync --extra speech'"
                ) from error
            self._pipelines[language] = KPipeline(lang_code=language)
        return self._pipelines[language]

    def _voice_for(self, voice: VoiceRef, pipeline):
        """A name for one voice, or a mixed style for a blended one.

        Kokoro keeps a voice as a tensor of style. A weighted average of two of
        them is a third voice that is steady and always the same, which is what
        a line spoken by two characters together needs.
        """
        if isinstance(voice, Voice):
            return voice.name

        import torch

        mixed = None
        for part, weight in zip(voice.parts, voice.weights, strict=True):
            style = pipeline.load_voice(part)
            piece = style * weight
            mixed = piece if mixed is None else mixed + piece
        if mixed is None:
            raise OpenBookError("a blended voice with no parts cannot speak")
        return torch.as_tensor(mixed)


def _first_name(voice: VoiceRef) -> str:
    if isinstance(voice, Voice):
        return voice.name
    if isinstance(voice, BlendedVoice) and voice.parts:
        return voice.parts[0]
    raise OpenBookError("this voice names nothing that Kokoro can speak with")


def _samples(pipeline, text: str, voice, speed: float):
    """Join everything Kokoro gives back for one piece of text."""
    import numpy

    pieces = []
    for result in pipeline(text, voice=voice, speed=speed):
        audio = result[2] if isinstance(result, tuple) else result.audio
        if audio is None:
            continue
        pieces.append(numpy.asarray(_detach(audio), dtype=numpy.float32))
    if not pieces:
        return None
    return numpy.concatenate(pieces)


def _detach(audio):
    return audio.detach().cpu().numpy() if hasattr(audio, "detach") else audio


def _to_bytes(samples) -> bytes:
    """Turn float samples between -1 and 1 into 16 bit values.

    The values are held inside the range first. A model can give back a little
    over 1, and letting that wrap around makes a loud click.
    """
    import numpy

    held = numpy.clip(samples, -1.0, 1.0)
    return (held * 32767.0).astype("<i2").tobytes()


def _installed_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("kokoro")
    except PackageNotFoundError:  # pragma: no cover
        return "unknown"
