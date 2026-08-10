"""Makes the file that goes to YouTube, and the words that go beside it.

YouTube takes video and not sound, so a volume becomes a picture with the
audiobook behind it. YouTube also builds its own chapter list out of times
written in the description, and the render already knows where every chapter
starts, so that costs nothing to produce.

Music under a voice has to move out of the way of the voice. A bed held at one
level fights the narration and is tiring long before the end of a volume, so
the music is compressed against the speech: loud where nobody talks, low where
somebody does.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..errors import OpenBookError
from .package import Mark, require_ffmpeg, run_ffmpeg, write_metadata

# The longest video that YouTube accepts.
YOUTUBE_LIMIT_SECONDS = 12 * 3600

# YouTube needs at least this many times in a description before it makes a
# chapter list, and no chapter shorter than ten seconds.
LEAST_MARKS = 3
LEAST_MARK_SECONDS = 10


@dataclass(frozen=True)
class Music:
    """A bed to put under the speech."""

    path: Path
    level: float = 0.15
    threshold: float = 0.03
    ratio: float = 8.0
    attack: float = 20.0
    release: float = 500.0

    def __post_init__(self) -> None:
        if not 0 < self.level <= 1:
            raise ValueError("the level of the music must be above 0 and at most 1")


def timestamp(seconds: float) -> str:
    """A time in the form YouTube reads in a description."""
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, second = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{second:02d}"
    return f"{minutes}:{second:02d}"


def youtube_description(
    marks: list[Mark],
    *,
    title: str,
    before: str = "",
    credits: list[str] | None = None,
) -> str:
    """Write the description, with a time for each chapter.

    The first time has to be 0:00 or YouTube makes no chapter list at all, so
    the first mark is moved to zero if a silence pushed it later.
    """
    if len(marks) < LEAST_MARKS:
        raise OpenBookError(
            f"YouTube needs at least {LEAST_MARKS} chapters before it makes a "
            f"chapter list, and this volume has {len(marks)}"
        )
    short = [m for m in marks if m.end - m.start < LEAST_MARK_SECONDS]
    if short:
        raise OpenBookError(
            f"YouTube needs every chapter to last at least {LEAST_MARK_SECONDS} "
            f"seconds, and {short[0].title!r} lasts {short[0].end - short[0].start:.0f}"
        )

    lines = [before.strip(), "", title, ""] if before.strip() else [title, ""]
    for index, mark in enumerate(marks):
        at = 0.0 if index == 0 else mark.start
        lines.append(f"{timestamp(at)} {mark.title}")

    # A font or a piece of music can carry a condition that the work is named.
    # Putting the credits in here means they cannot be forgotten on the ninth
    # volume after being remembered on the first.
    if credits:
        lines += ["", "Credits", *credits]
    return "\n".join(lines).strip() + "\n"


def opening_words(chapter, count: int) -> str:
    """The first words of a volume, for a sneak peek in the description.

    Taken from the opening and not from anywhere later, so it cannot give away
    something a listener has not reached. It ends at the end of a sentence
    rather than in the middle of one.
    """
    from ..parse import Narration

    said = " ".join(
        segment.text for segment in chapter.segments if isinstance(segment, Narration)
    )
    words = said.split()
    if not words or count <= 0:
        return ""

    piece = " ".join(words[:count])
    # Back up to the last sentence that finished, so the peek does not stop in
    # the middle of a thought.
    for mark in (". ", "! ", "? "):
        if mark in piece:
            piece = piece[: piece.rfind(mark) + 1]
            break
    return piece.strip()


def mix_music(speech: Path, music: Music, out: Path) -> Path:
    """Put a bed under the speech, and make it move out of the way.

    The bed is looped to the length of the speech, lowered, then compressed
    with the speech as the key. Where somebody talks the music drops; where
    nobody talks it comes back.
    """
    if not music.path.exists():
        raise OpenBookError(f"{music.path}: the music file does not exist")
    require_ffmpeg()

    graph = (
        f"[1:a]volume={music.level}[bed];"
        f"[bed][0:a]sidechaincompress="
        f"threshold={music.threshold}:ratio={music.ratio}:"
        f"attack={music.attack}:release={music.release}[duck];"
        # normalize=0 keeps the speech at the level it arrived at. Without it
        # amix halves everything and the narration comes out quiet.
        f"[0:a][duck]amix=inputs=2:duration=first:normalize=0[out]"
    )
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(speech),
            "-stream_loop",
            "-1",
            "-i",
            str(music.path),
            "-filter_complex",
            graph,
            "-map",
            "[out]",
            "-c:a",
            "pcm_s16le",
            str(out),
        ]
    )
    return out


def write_video(
    audio: Path,
    visual: Path,
    out: Path,
    *,
    marks: list[Mark] | None = None,
    framerate: int = 1,
    bitrate: str = "128k",
    sample_rate: int = 48000,
    channels: int = 2,
) -> Path:
    """Join a picture and the sound into one file for YouTube.

    The picture can be a still or a short piece of video. A still costs almost
    nothing to encode however long the volume is, because every frame is the
    same. A loop costs real time, so measure before choosing a long one.
    """
    if not visual.exists():
        raise OpenBookError(f"{visual}: the picture does not exist")
    require_ffmpeg()

    # Before the encode and not after it. Learning that a volume is too long
    # once an hour of encoding has gone by helps nobody.
    _refuse_if_too_long(marks)
    out.parent.mkdir(parents=True, exist_ok=True)

    still = visual.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    visual_input = (
        ["-loop", "1", "-framerate", str(framerate), "-i", str(visual)]
        if still
        else ["-stream_loop", "-1", "-i", str(visual)]
    )

    # An odd width or height cannot be encoded as yuv420p, which every player
    # expects, so the picture is padded up to an even size rather than refused.
    scale = "scale=trunc(iw/2)*2:trunc(ih/2)*2"

    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            *visual_input,
            "-i",
            str(audio),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            f"{scale},format=yuv420p",
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-r",
            str(framerate),
            "-c:a",
            "aac",
            "-b:a",
            bitrate,
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-movflags",
            "+faststart",
            "-shortest",
            str(out),
        ]
    )

    return out


def write_video_from_cards(
    concat_list: Path,
    audio: Path,
    out: Path,
    *,
    marks: list[Mark] | None = None,
    framerate: int = 1,
    bitrate: str = "128k",
    sample_rate: int = 48000,
    channels: int = 2,
) -> Path:
    """Join a list of cards and the sound into one file.

    Each card is held from the start of its chapter to the start of the next.
    The output is given a steady frame rate, because the concat reader gives an
    uneven one and YouTube would have to correct it.

    The length is fixed to the length of the sound. The concat reader needs the
    last file written a second time or it drops the final card, and that repeat
    adds the whole duration of that card to the end. Without the limit below,
    Volume 1 came out seven and a half minutes longer than its audio, all of it
    a still picture over silence.
    """
    require_ffmpeg()
    _refuse_if_too_long(marks)
    out.parent.mkdir(parents=True, exist_ok=True)
    seconds = probe_seconds(audio)

    # The marks go in as well. YouTube reads the description instead, so these
    # are for a player that is not YouTube.
    chapters = out.parent / f".{out.stem}.chapters.txt"
    extra: list[str] = []
    if marks:
        chapters.write_text(
            write_metadata(marks, title=out.stem, author=""), encoding="utf-8"
        )
        extra = ["-i", str(chapters), "-map_metadata", "2"]
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-i",
            str(audio),
            *extra,
            "-t",
            f"{seconds:.3f}",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            f"fps={framerate},format=yuv420p",
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            bitrate,
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-movflags",
            "+faststart",
            "-shortest",
            str(out),
        ]
    )
    chapters.unlink(missing_ok=True)
    return out


def _refuse_if_too_long(marks: list[Mark] | None) -> None:
    if marks and marks[-1].end > YOUTUBE_LIMIT_SECONDS:
        raise OpenBookError(
            f"this volume runs {marks[-1].end / 3600:.1f} hours, and YouTube "
            f"takes {YOUTUBE_LIMIT_SECONDS / 3600:.0f} at the most. Divide it"
        )


def probe_seconds(path: Path) -> float:
    """How long a media file runs."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return float(result.stdout.strip())
    except ValueError as error:
        raise OpenBookError(f"{path}: ffprobe could not read a length") from error
