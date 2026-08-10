"""Makes a piece of audio a different length without changing its pitch.

There is one use for this: a line two characters say together. Two readings of
the same words are two different lengths, and laying them over each other
leaves the shorter one finished while the longer is still talking. Bringing
them to one length makes them speak together.

Nothing else in the project stretches audio, and nothing else should. Changing
how fast somebody talks is a change to their performance, and it is worth it
only where the alternative is two characters falling out of step in front of a
listener.

The pitch has to stay. Making a piece longer by playing it slower is one line
of arithmetic on the samples and it drops the voice with it, which turns a
character into a different person. ffmpeg holds the pitch and moves only the
tempo, so this asks ffmpeg.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from .audio import Audio
from .package import require_ffmpeg, run_ffmpeg

# The least a length has to be out before it is worth changing. Below this the
# stretch is inaudible and the loss of quality is not.
LEAST_DIFFERENCE = 0.02

# How far a tempo may be moved. A voice pushed further than this stops sounding
# like a reading and starts sounding like a machine, and a line that needs more
# than this is a line where the two readings disagree so much that holding them
# together is the wrong answer.
MOST_CHANGE = 0.25


def to_one_length(pieces: list[Audio]) -> list[Audio]:
    """Bring every piece to the same length, so they start and stop together.

    The target is the average and not the longest, so that no one reading
    carries the whole change. Two readings 0.6 seconds apart each move about
    0.3, and a tempo moved 7 percent is near the point where nobody hears it
    while 14 percent is not.
    """
    if len(pieces) < 2:
        return pieces

    lengths = [piece.seconds for piece in pieces]
    if min(lengths) <= 0:
        return pieces

    target = sum(lengths) / len(lengths)
    return [
        stretch(piece, target) if _worth_it(piece.seconds, target) else piece
        for piece in pieces
    ]


def _worth_it(length: float, target: float) -> bool:
    return abs(length - target) >= LEAST_DIFFERENCE


def stretch(audio: Audio, seconds: float) -> Audio:
    """Make one piece last the time asked for, at the pitch it already has."""
    if seconds <= 0 or audio.seconds <= 0:
        return audio

    tempo = audio.seconds / seconds
    # Refusing beats making something nobody would use. A reading that has to
    # move this far to meet another is not the same performance afterwards.
    tempo = max(1 - MOST_CHANGE, min(1 + MOST_CHANGE, tempo))

    require_ffmpeg()
    with tempfile.TemporaryDirectory() as directory:
        here = Path(directory)
        before, after = here / "before.wav", here / "after.wav"
        audio.write(before)
        run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(before),
                "-filter:a",
                f"atempo={tempo:.6f}",
                # The rate and the shape have to come back exactly as they went
                # in. A piece at another rate cannot be laid over the other.
                "-ar",
                str(audio.rate),
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(after),
            ]
        )
        return Audio.read(after)
