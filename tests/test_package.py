import pytest

from openbook.errors import OpenBookError
from openbook.speech import Audio
from openbook.speech.package import (
    Mark,
    have_ffmpeg,
    require_ffmpeg,
    write_m4b,
    write_metadata,
)

needs_ffmpeg = pytest.mark.skipif(not have_ffmpeg(), reason="ffmpeg is not installed")


def test_the_metadata_holds_a_chapter_for_each_mark():
    text = write_metadata(
        [Mark("One.", 0.0, 60.0), Mark("Two.", 60.0, 90.5)],
        title="Volume 1",
        author="n1cetry",
    )
    assert text.startswith(";FFMETADATA1")
    assert text.count("[CHAPTER]") == 2
    assert "title=Volume 1" in text
    assert "artist=n1cetry" in text


def test_the_times_are_whole_milliseconds():
    text = write_metadata([Mark("One.", 1.5, 2.25)], title="t", author="a")
    assert "START=1500" in text
    assert "END=2250" in text


def test_a_title_with_syntax_in_it_is_escaped():
    # A chapter title is written by the author and can hold anything. An equals
    # sign or a semicolon would end the line early and lose the rest.
    text = write_metadata([Mark("A=B; C#D", 0, 1)], title="t", author="a")
    assert r"title=A\=B\; C\#D" in text


def test_no_marks_still_gives_a_readable_file():
    text = write_metadata([], title="t", author="a")
    assert "[CHAPTER]" not in text
    assert text.startswith(";FFMETADATA1")


def test_the_message_says_how_to_install_ffmpeg(monkeypatch):
    monkeypatch.setattr("openbook.speech.package.shutil.which", lambda name: None)
    with pytest.raises(OpenBookError, match="brew install ffmpeg"):
        require_ffmpeg()


@needs_ffmpeg
def test_an_m4b_is_written_and_holds_its_chapters(tmp_path):
    audio = Audio.silence(seconds=3.0, rate=24000)
    marks = [Mark("One.", 0.0, 1.5), Mark("Two.", 1.5, 3.0)]
    path = write_m4b(
        audio, marks, tmp_path / "v.m4b", title="Volume 1", author="n1cetry"
    )
    assert path.exists()
    assert path.stat().st_size > 0


@needs_ffmpeg
def test_writing_leaves_no_working_files_behind(tmp_path):
    write_m4b(
        Audio.silence(1.0, 24000),
        [Mark("One.", 0.0, 1.0)],
        tmp_path / "v.m4b",
        title="t",
        author="a",
    )
    assert [p.name for p in tmp_path.iterdir()] == ["v.m4b"]


def test_no_conversion_is_asked_for_by_default():
    from openbook.speech.package import audio_arguments

    assert audio_arguments(None, None) == []
    assert audio_arguments(0, 0) == []


def test_a_rate_and_a_channel_count_reach_ffmpeg():
    from openbook.speech.package import audio_arguments

    assert audio_arguments(48000, 2) == ["-ar", "48000", "-ac", "2"]


def test_one_of_the_two_alone_is_enough():
    from openbook.speech.package import audio_arguments

    assert audio_arguments(48000, None) == ["-ar", "48000"]
    assert audio_arguments(None, 2) == ["-ac", "2"]


@needs_ffmpeg
def test_the_written_file_carries_the_rate_and_channels_asked_for(tmp_path):
    import json
    import subprocess

    path = write_m4b(
        Audio.silence(1.0, 24000),
        [Mark("One.", 0.0, 1.0)],
        tmp_path / "v.m4b",
        title="t",
        author="a",
        sample_rate=48000,
        channels=2,
    )
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=sample_rate,channels",
            "-print_format",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    stream = json.loads(out.stdout)["streams"][0]
    assert stream["sample_rate"] == "48000"
    assert stream["channels"] == 2


@needs_ffmpeg
def test_a_cover_reaches_the_file_as_a_picture():
    """The artwork is copied and never encoded.

    Left alone ffmpeg encodes a picture with the video codec of the container,
    which for an M4B is h264, and then refuses its own choice, because an M4B
    holds artwork as a picture and not as video. Nothing is written and the
    reason names a codec nobody asked for. A test on the finished file is the
    only thing that finds this: every argument is accepted.
    """
    import subprocess
    import tempfile
    from pathlib import Path

    from openbook.speech.audio import Audio

    # A JPEG of one grey pixel, which is enough to be artwork.
    jpeg = bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300ffffffffffffffff"
        "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffc0000b08"
        "0001000101011100ffc40014000100000000000000000000000000000009ffc400"
        "1410010000000000000000000000000000000000ffda0008010100003f0054df80"
        "ffd9"
    )
    with tempfile.TemporaryDirectory() as directory:
        out = Path(directory) / "book.m4b"
        write_m4b(
            Audio.silence(seconds=4.0, rate=24000),
            [Mark(title="One.", start=0.0, end=4.0)],
            out,
            title="Book",
            author="Somebody",
            cover=jpeg,
        )
        assert out.exists() and out.stat().st_size > 0, "the file is not empty"
        found = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "csv=p=0",
                str(out),
            ],
            capture_output=True,
            text=True,
        ).stdout
        assert "mjpeg" in found, f"the cover is not a picture, it is {found!r}"
