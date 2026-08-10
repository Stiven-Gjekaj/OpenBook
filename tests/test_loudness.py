import subprocess

import pytest

from openbook.errors import OpenBookError
from openbook.speech.loudness import TARGET_LOUDNESS, level, measure
from openbook.speech.package import have_ffmpeg, run_ffmpeg

needs_ffmpeg = pytest.mark.skipif(not have_ffmpeg(), reason="ffmpeg is not installed")


def tone(path, *, volume, seconds=6, rate=24000):
    """A tone of a known level, so the measurement can be checked."""
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=300:duration={seconds}:sample_rate={rate}",
            "-af",
            f"volume={volume}",
            "-c:a",
            "pcm_s16le",
            str(path),
        ]
    )
    return path


@needs_ffmpeg
def test_a_quiet_tone_measures_quiet(tmp_path):
    quiet = measure(tone(tmp_path / "quiet.wav", volume=0.05))
    loud = measure(tone(tmp_path / "loud.wav", volume=0.5))
    assert quiet.loudness < loud.loudness


@needs_ffmpeg
def test_levelling_brings_a_quiet_file_up_to_the_target(tmp_path):
    # The number that matters. A volume quieter than the one before it is the
    # first thing a listener notices.
    source = tone(tmp_path / "quiet.wav", volume=0.03)
    out = tmp_path / "levelled.wav"
    before = level(source, out)
    after = measure(out)
    assert before.loudness < TARGET_LOUDNESS - 3
    assert abs(after.loudness - TARGET_LOUDNESS) < 1.5


@needs_ffmpeg
def test_levelling_brings_a_loud_file_down_to_the_target(tmp_path):
    source = tone(tmp_path / "loud.wav", volume=0.9)
    out = tmp_path / "levelled.wav"
    level(source, out)
    assert abs(measure(out).loudness - TARGET_LOUDNESS) < 1.5


@needs_ffmpeg
def test_two_files_of_different_levels_end_up_the_same(tmp_path):
    # Two volumes recorded at different levels must not sound different.
    one, two = tmp_path / "a.wav", tmp_path / "b.wav"
    level(tone(tmp_path / "q.wav", volume=0.05), one)
    level(tone(tmp_path / "l.wav", volume=0.7), two)
    assert abs(measure(one).loudness - measure(two).loudness) < 1.0


@needs_ffmpeg
def test_the_sample_rate_survives_levelling(tmp_path):
    # loudnorm works at 192000 inside itself and gives that back unless told
    # otherwise, which would leave the file at the wrong rate.
    source = tone(tmp_path / "in.wav", volume=0.4, rate=24000)
    out = tmp_path / "out.wav"
    level(source, out)
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
            str(out),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "24000"


@needs_ffmpeg
def test_the_peak_stays_under_the_ceiling(tmp_path):
    source = tone(tmp_path / "hot.wav", volume=1.0)
    out = tmp_path / "out.wav"
    level(source, out)
    assert measure(out).peak <= -2.0


def test_a_file_that_is_not_audio_is_named(tmp_path):
    if not have_ffmpeg():
        pytest.skip("ffmpeg is not installed")
    bad = tmp_path / "bad.wav"
    bad.write_text("not audio", encoding="utf-8")
    with pytest.raises(OpenBookError, match="measured no loudness"):
        measure(bad)
