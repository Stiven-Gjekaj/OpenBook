"""One piece of audio.

The samples are 16 bit, signed, little endian, and one channel. This is what
the `wave` module of the standard library writes, so a piece of audio can be
saved and played without any dependency at all. A stage that needs to do sums
on the samples turns them into numbers itself.

Everything here refuses to mix two rates. Joining audio at 24000 with audio at
48000 gives a voice that speaks at the wrong speed, and that is a fault which
sounds like a choice.
"""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass
from pathlib import Path

from ..errors import OpenBookError

WIDTH = 2  # bytes for one sample
CHANNELS = 1


@dataclass(frozen=True)
class Audio:
    """Sound, as 16 bit samples of one channel."""

    samples: bytes
    rate: int

    def __post_init__(self) -> None:
        if self.rate <= 0:
            raise ValueError("the rate of a piece of audio must be above zero")
        if len(self.samples) % WIDTH:
            raise ValueError("the samples do not divide into whole 16 bit values")

    @property
    def seconds(self) -> float:
        return len(self.samples) / WIDTH / self.rate

    @classmethod
    def silence(cls, seconds: float, rate: int) -> Audio:
        """A piece of quiet of the length asked for."""
        if seconds < 0:
            raise ValueError("a silence cannot be shorter than nothing")
        return cls(samples=b"\x00" * (round(seconds * rate) * WIDTH), rate=rate)

    def join(self, other: Audio) -> Audio:
        """Put another piece of audio after this one."""
        if self.rate != other.rate:
            raise OpenBookError(
                f"two pieces of audio at {self.rate} and {other.rate} cannot join. "
                "Joining them would make one of the two speak at the wrong speed"
            )
        return Audio(samples=self.samples + other.samples, rate=self.rate)

    def to_wav(self) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as handle:
            handle.setnchannels(CHANNELS)
            handle.setsampwidth(WIDTH)
            handle.setframerate(self.rate)
            handle.writeframes(self.samples)
        return buffer.getvalue()

    def write(self, path: Path) -> None:
        """Write a wav file, and leave no half written file if it fails."""
        temporary = path.with_suffix(path.suffix + ".part")
        temporary.write_bytes(self.to_wav())
        temporary.replace(path)

    @classmethod
    def read(cls, path: Path) -> Audio:
        with wave.open(str(path), "rb") as handle:
            if handle.getsampwidth() != WIDTH or handle.getnchannels() != CHANNELS:
                raise OpenBookError(
                    f"{path}: OpenBook writes 16 bit audio of one channel, and "
                    "this file is not that"
                )
            return cls(
                samples=handle.readframes(handle.getnframes()),
                rate=handle.getframerate(),
            )


def join_all(pieces: list[Audio], rate: int) -> Audio:
    """Join many pieces, keeping the rate even when there are none."""
    joined = Audio(samples=b"", rate=rate)
    for piece in pieces:
        joined = joined.join(piece)
    return joined
