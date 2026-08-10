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


def _fonts():
    """A font that every machine has, so the tests do not need the real ones."""
    from pathlib import Path

    for candidate in (
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if candidate.exists():
            return candidate
    return None


needs_font = pytest.mark.skipif(_fonts() is None, reason="no system font to draw with")
needs_pillow = pytest.mark.skipif(
    __import__("importlib").util.find_spec("PIL") is None, reason="Pillow not installed"
)


def test_a_font_that_is_not_there_is_named(tmp_path):
    from openbook.speech.cards import Style

    with pytest.raises(OpenBookError, match="the font file does not exist"):
        Style(title_font=tmp_path / "absent.ttf", body_font=tmp_path / "absent.ttf")


@needs_font
def test_a_card_of_an_odd_size_is_refused():
    from openbook.speech.cards import Style

    with pytest.raises(OpenBookError, match="even width and height"):
        Style(title_font=_fonts(), body_font=_fonts(), width=1921, height=1080)


@needs_font
@needs_pillow
def test_a_card_is_drawn_at_the_size_asked_for(tmp_path):
    from PIL import Image

    from openbook.speech.cards import Style, make_card

    style = Style(
        title_font=_fonts(),
        body_font=_fonts(),
        width=640,
        height=360,
        title_size=60,
        body_size=24,
        faint_size=16,
    )
    path = make_card(
        style, tmp_path / "c.png", chapter="Chapter 1 of 3", subtitle="A Title."
    )
    with Image.open(path) as image:
        assert image.size == (640, 360)


@needs_font
@needs_pillow
def test_one_card_is_drawn_for_each_chapter(tmp_path):
    from openbook.speech.cards import Style, make_chapter_cards

    style = Style(
        title_font=_fonts(),
        body_font=_fonts(),
        width=320,
        height=180,
        title_size=30,
        body_size=14,
        faint_size=10,
    )
    cards = make_chapter_cards(marks(4), style, tmp_path / "cards")
    assert len(cards) == 4
    assert all(path.exists() for path, _ in cards)
    assert [round(seconds) for _, seconds in cards] == [600, 600, 600, 600]


def test_the_concat_list_repeats_the_last_card(tmp_path):
    # The concat reader of ffmpeg drops the final card without this.
    from openbook.speech.cards import write_concat_list

    one, two = tmp_path / "a.png", tmp_path / "b.png"
    one.touch()
    two.touch()
    path = write_concat_list([(one, 5.0), (two, 7.5)], tmp_path / "list.txt")
    lines = path.read_text().splitlines()
    assert lines[-1].endswith("b.png'")
    assert "duration 7.500" in lines
    assert lines.count("file '" + two.resolve().as_posix() + "'") == 2


def test_a_list_with_no_cards_is_refused(tmp_path):
    from openbook.speech.cards import write_concat_list

    with pytest.raises(OpenBookError, match="no cards to show"):
        write_concat_list([], tmp_path / "list.txt")


def test_the_description_carries_the_credits():
    text = youtube_description(
        marks(3), title="Volume 1", credits=["A font, CC BY 3.0."]
    )
    assert "Credits" in text
    assert "A font, CC BY 3.0." in text


@needs_font
@needs_pillow
def test_a_card_is_held_until_the_next_chapter_starts(tmp_path):
    # A silence sits between two chapters and belongs to the card in front of
    # it. Using the length of the audio instead loses that silence from every
    # card, and the picture then changes early by the end of the volume.
    from openbook.speech.cards import Style, make_chapter_cards

    gapped = [
        Mark("One.", 0.0, 100.0),
        Mark("Two.", 101.0, 200.0),
        Mark("Three.", 201.0, 300.0),
    ]
    style = Style(
        title_font=_fonts(),
        body_font=_fonts(),
        width=320,
        height=180,
        title_size=30,
        body_size=14,
        faint_size=10,
    )
    cards = make_chapter_cards(gapped, style, tmp_path / "c", total=300.0)
    assert [round(seconds) for _, seconds in cards] == [101, 100, 99]
    assert round(sum(seconds for _, seconds in cards)) == 300


@needs_font
@needs_pillow
def test_a_card_carries_the_number_the_book_gives_a_chapter(tmp_path):
    # The narrator says the number of the book. A card counting its place in
    # the volume says 22 where the voice says 21, and the two disagree in front
    # of the listener.
    from PIL import Image

    from openbook.speech.cards import Style, make_chapter_cards

    style = Style(
        title_font=_fonts(),
        body_font=_fonts(),
        width=320,
        height=180,
        title_size=30,
        body_size=14,
        faint_size=10,
    )
    with_numbers = make_chapter_cards(
        marks(3), style, tmp_path / "a", numbers=[0, 1, 2]
    )
    without = make_chapter_cards(marks(3), style, tmp_path / "b")
    # The two runs draw different pictures, which is the point of the change.
    first = Image.open(with_numbers[0][0]).tobytes()
    other = Image.open(without[0][0]).tobytes()
    assert first != other
