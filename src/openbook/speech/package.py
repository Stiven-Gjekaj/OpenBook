"""Writes the finished audio as a file that an audiobook player understands.

An M4B is an MP4 file with a chapter list inside it. A player uses that list to
show the chapters and to remember where the listener stopped, which is the only
real difference between an audiobook and a long piece of music.

ffmpeg does the encoding. It is not a Python dependency, so this checks that it
is there and says what to install when it is not, rather than failing inside a
process that the person cannot see.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..errors import OpenBookError
from .audio import Audio


@dataclass(frozen=True)
class Mark:
    """One chapter inside a finished file."""

    title: str
    start: float
    end: float


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def require_ffmpeg() -> None:
    if not have_ffmpeg():
        raise OpenBookError(
            "ffmpeg is not on this machine, and OpenBook needs it to write an "
            "audiobook file. Install it with 'brew install ffmpeg' on macOS, or "
            "with the package manager of your system"
        )


def write_metadata(marks: list[Mark], *, title: str, author: str) -> str:
    """Build the chapter list in the form ffmpeg reads.

    The times are in milliseconds. A title can hold a character that ffmpeg
    treats as syntax, so each one is escaped.
    """
    lines = [";FFMETADATA1", f"title={_escape(title)}", f"artist={_escape(author)}"]
    for mark in marks:
        lines += [
            "",
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={round(mark.start * 1000)}",
            f"END={round(mark.end * 1000)}",
            f"title={_escape(mark.title)}",
        ]
    return "\n".join(lines) + "\n"


def audio_arguments(sample_rate: int | None, channels: int | None) -> list[str]:
    """Tell ffmpeg to change the rate and the number of channels.

    Nothing is added when neither is asked for, and the sound then keeps the
    form the engine made it in.

    Raising 24000 to 48000 adds no information to speech. It is worth doing on
    the way to a place that will change the rate anyway, because the change
    then happens one time and with a good filter, rather than twice.
    """
    arguments: list[str] = []
    if sample_rate:
        arguments += ["-ar", str(sample_rate)]
    if channels:
        arguments += ["-ac", str(channels)]
    return arguments


def write_m4b(
    audio: Audio,
    marks: list[Mark],
    path: Path,
    *,
    title: str,
    author: str,
    bitrate: str = "64k",
    sample_rate: int | None = None,
    channels: int | None = None,
) -> Path:
    """Write one volume as an M4B with its chapters in it."""
    require_ffmpeg()
    path.parent.mkdir(parents=True, exist_ok=True)

    work = path.parent / f".{path.stem}.work"
    work.mkdir(exist_ok=True)
    source = work / "audio.wav"
    metadata = work / "chapters.txt"
    try:
        audio.write(source)
        metadata.write_text(
            write_metadata(marks, title=title, author=author), encoding="utf-8"
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
                "-i",
                str(metadata),
                "-map_metadata",
                "1",
                "-c:a",
                "aac",
                "-b:a",
                bitrate,
                *audio_arguments(sample_rate, channels),
                "-movflags",
                "+faststart",
                "-f",
                "mp4",
                str(path),
            ]
        )
    finally:
        for leftover in (source, metadata):
            leftover.unlink(missing_ok=True)
        if work.exists():
            work.rmdir()
    return path


def write_opus(audio: Audio, path: Path, *, bitrate: str = "32k") -> Path:
    """Write one chapter as Opus, which is what a web player wants.

    A volume is hours long in one file, and a browser has to fetch a large part
    of it to start in the middle. One file for each chapter does not.
    """
    require_ffmpeg()
    path.parent.mkdir(parents=True, exist_ok=True)
    source = path.parent / f".{path.stem}.wav"
    try:
        audio.write(source)
        run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-c:a",
                "libopus",
                "-b:a",
                bitrate,
                str(path),
            ]
        )
    finally:
        source.unlink(missing_ok=True)
    return path


def run_ffmpeg(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        return
    said = result.stderr.strip().splitlines()
    reason = said[-1] if said else "it gave no reason"
    raise OpenBookError(f"ffmpeg refused to write the file. It said: {reason}")


def _escape(text: str) -> str:
    for character in ("\\", "=", ";", "#", "\n"):
        text = text.replace(character, "\\" + character)
    return text
