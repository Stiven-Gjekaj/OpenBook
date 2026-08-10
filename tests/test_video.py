import pytest

from openbook.errors import OpenBookError
from openbook.speech.package import Mark, have_ffmpeg
from openbook.speech.video import Music, timestamp, write_video, youtube_description

needs_ffmpeg = pytest.mark.skipif(not have_ffmpeg(), reason="ffmpeg is not installed")


def marks(count=3, each=600.0):
    return [
        Mark(title=f"Chapter {i}.", start=i * each, end=(i + 1) * each)
        for i in range(count)
    ]


def test_a_time_under_an_hour_has_no_hour():
    assert timestamp(0) == "0:00"
    assert timestamp(65) == "1:05"
    assert timestamp(3599) == "59:59"


def test_a_time_over_an_hour_carries_it():
    assert timestamp(3600) == "1:00:00"
    assert timestamp(13567) == "3:46:07"


def test_a_time_before_the_start_becomes_zero():
    assert timestamp(-5) == "0:00"


def test_the_description_starts_at_zero():
    # YouTube makes no chapter list at all unless the first time is 0:00, so a
    # silence in front of the first chapter must not push it later.
    late = [
        Mark("One.", 1.0, 600.0),
        Mark("Two.", 600.0, 1200.0),
        Mark("Three.", 1200.0, 1800.0),
    ]
    assert (
        youtube_description(late, title="Volume 1").splitlines()[2].startswith("0:00 ")
    )


def test_the_description_holds_a_line_for_each_chapter():
    text = youtube_description(marks(4), title="Volume 1")
    assert text.count("Chapter ") == 4
    assert "Volume 1" in text


def test_the_description_can_carry_words_before_the_times():
    text = youtube_description(marks(), title="Volume 1", before="A story about souls.")
    assert text.startswith("A story about souls.")


def test_too_few_chapters_is_refused():
    with pytest.raises(OpenBookError, match="at least 3 chapters"):
        youtube_description(marks(2), title="Volume 1")


def test_a_chapter_shorter_than_ten_seconds_is_refused():
    short = [*marks(3), Mark("Tiny.", 1800.0, 1805.0)]
    with pytest.raises(OpenBookError, match="at least 10"):
        youtube_description(short, title="Volume 1")


def test_a_music_level_outside_the_range_is_refused(tmp_path):
    with pytest.raises(ValueError, match="above 0 and at most 1"):
        Music(path=tmp_path / "m.mp3", level=0)
    with pytest.raises(ValueError, match="above 0 and at most 1"):
        Music(path=tmp_path / "m.mp3", level=1.5)


def test_a_picture_that_is_not_there_is_named(tmp_path):
    with pytest.raises(OpenBookError, match="the picture does not exist"):
        write_video(tmp_path / "a.wav", tmp_path / "absent.png", tmp_path / "out.mp4")


@needs_ffmpeg
def test_a_volume_longer_than_youtube_takes_is_refused_before_encoding(tmp_path):
    # The refusal has to come before the encode, not after an hour of it.
    picture = tmp_path / "p.png"
    _make_picture(picture)
    long = [Mark("One.", 0.0, 13 * 3600.0)]
    with pytest.raises(OpenBookError, match="YouTube takes 12 at the most"):
        write_video(tmp_path / "a.wav", picture, tmp_path / "out.mp4", marks=long)


def _make_picture(path):
    from openbook.speech.package import run_ffmpeg

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
            "color=c=black:s=1280x720:d=1",
            "-frames:v",
            "1",
            str(path),
        ]
    )


@needs_ffmpeg
def test_a_still_picture_and_sound_become_one_file(tmp_path):
    from openbook.speech.audio import Audio

    picture = tmp_path / "p.png"
    _make_picture(picture)
    sound = tmp_path / "a.wav"
    Audio.silence(seconds=3.0, rate=24000).write(sound)

    out = write_video(sound, picture, tmp_path / "v.mp4", marks=marks())
    assert out.exists()
    assert out.stat().st_size > 0
