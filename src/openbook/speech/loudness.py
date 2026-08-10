"""Brings a volume to the loudness an audiobook is expected to have.

A listener notices this before they notice anything else. A volume quieter than
the one before it means reaching for the dial at the start of every part, and
once a file is uploaded it cannot be corrected.

The measurement runs first and the change second. One pass cannot do both: it
has to guess at the level while it is still reading the beginning, and the guess
follows the speech about instead of holding one level for the whole volume.

The target is -19 LUFS with a true peak no higher than -3 dB. That sits inside
what ACX asks of an audiobook and is the usual place for speech.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..errors import OpenBookError
from .package import require_ffmpeg, run_ffmpeg

TARGET_LOUDNESS = -19.0
TARGET_PEAK = -3.0
TARGET_RANGE = 7.0

# The shortest piece of audio worth measuring. The measurement is made over a
# whole recording, and below about three seconds there is not enough of one to
# say anything, so ffmpeg refuses rather than guessing.
LEAST_SECONDS = 3.0

# Below this there is no speech, only quiet.
SILENCE_FLOOR = -70.0


@dataclass(frozen=True)
class Measurement:
    """What ffmpeg heard in a piece of audio."""

    loudness: float
    peak: float
    range: float
    threshold: float
    offset: float

    @property
    def silent(self) -> bool:
        """True when there is nothing here to measure.

        Quiet made by the silent engine is quiet exactly, and its loudness
        comes back as minus infinity. Levelling that would be raising nothing
        to a level, and ffmpeg refuses rather than trying.
        """
        return not math.isfinite(self.loudness) or self.loudness < SILENCE_FLOOR

    def __str__(self) -> str:
        if self.silent:
            return "silent"
        return f"{self.loudness:.1f} LUFS, peak {self.peak:.1f} dB"


def measure(path: Path) -> Measurement:
    """Listen to the whole file and say how loud it is."""
    require_ffmpeg()
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            f"loudnorm=I={TARGET_LOUDNESS}:TP={TARGET_PEAK}:LRA={TARGET_RANGE}"
            ":print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    # ffmpeg writes the numbers to the error stream, after everything else it
    # has to say, so the last object in it is the one wanted.
    found = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", result.stderr, re.S)
    if not found:
        said = result.stderr.strip().splitlines()
        reason = said[-1] if said else "it gave no reason"
        raise OpenBookError(f"{path}: ffmpeg measured no loudness. It said: {reason}")
    numbers = json.loads(found[-1])
    return Measurement(
        loudness=float(numbers["input_i"]),
        peak=float(numbers["input_tp"]),
        range=float(numbers["input_lra"]),
        threshold=float(numbers["input_thresh"]),
        offset=float(numbers["target_offset"]),
    )


def level(source: Path, out: Path, measured: Measurement | None = None) -> Measurement:
    """Bring a file to the target loudness, and say what it was before.

    The measurement is handed to ffmpeg so that it corrects by one amount for
    the whole file, rather than working the level out as it goes.
    """
    require_ffmpeg()
    measured = measured or measure(source)
    if measured.silent:
        raise OpenBookError(
            f"{source}: this audio is silent, so there is no level to bring it "
            "to. A render made with the silent engine cannot be levelled"
        )
    out.parent.mkdir(parents=True, exist_ok=True)

    settings = ":".join(
        [
            f"I={TARGET_LOUDNESS}",
            f"TP={TARGET_PEAK}",
            f"LRA={TARGET_RANGE}",
            f"measured_I={measured.loudness}",
            f"measured_TP={measured.peak}",
            f"measured_LRA={measured.range}",
            f"measured_thresh={measured.threshold}",
            f"offset={measured.offset}",
            "linear=true",
            "print_format=summary",
        ]
    )
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-af",
            f"loudnorm={settings}",
            # loudnorm works at 192000 inside itself and gives that back, so
            # the rate is set again here or the file comes out at the wrong one.
            "-ar",
            str(_rate(source)),
            "-c:a",
            "pcm_s16le",
            str(out),
        ]
    )
    return measured


def _rate(path: Path) -> int:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=sample_rate",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return int(result.stdout.strip())
    except ValueError as error:
        raise OpenBookError(f"{path}: ffprobe could not read a sample rate") from error
