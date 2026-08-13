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


class FakeChapterWithText:
    def __init__(self, texts):
        from openbook.parse import Narration

        self.segments = [Narration(text=t) for t in texts]


def test_a_peek_comes_from_the_opening_of_the_volume():
    # From the opening and nowhere later, so it cannot give away something a
    # listener has not reached.
    from openbook.speech.video import opening_words

    chapter = FakeChapterWithText(["One two three. Four five six. Seven eight."])
    assert opening_words(chapter, 6) == "One two three."


def test_a_peek_ends_at_the_end_of_a_sentence():
    from openbook.speech.video import opening_words

    chapter = FakeChapterWithText(
        ["A short one. And then a much longer one that runs on"]
    )
    peek = opening_words(chapter, 8)
    assert peek.endswith(".")


def test_no_peek_is_asked_for():
    from openbook.speech.video import opening_words

    assert opening_words(FakeChapterWithText(["Words here."]), 0) == ""


def test_a_chapter_with_no_narration_gives_no_peek():
    from openbook.speech.video import opening_words

    assert opening_words(FakeChapterWithText([]), 50) == ""


@needs_font
@needs_pillow
def test_a_card_stacks_the_volume_above_the_title(tmp_path):
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
    with_volume = make_card(
        style,
        tmp_path / "a.png",
        volume_name="Volume 1",
        volume_title="The Ascension",
        chapter="Chapter 3 of 22",
        subtitle="Wandering Spirit.",
    )
    without = make_card(
        style,
        tmp_path / "b.png",
        chapter="Chapter 3 of 22",
        subtitle="Wandering Spirit.",
    )
    assert Image.open(with_volume).tobytes() != Image.open(without).tobytes()


@needs_font
@needs_pillow
def test_a_card_with_no_chapter_line_still_draws(tmp_path):
    # An intro has no chapter, and its card is the volume and the work only.
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
        style,
        tmp_path / "c.png",
        volume_name="Volume 1",
        volume_title="The Ascension",
        subtitle="Introduction",
    )
    assert path.exists()


@needs_font
@needs_pillow
def test_a_mark_carries_the_label_its_card_shows(tmp_path):
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
    labelled = [
        Mark("Introduction", 0.0, 20.0),
        Mark("One.", 20.0, 620.0),
        Mark("Two.", 620.0, 1220.0, label="Chapter 4 of 22"),
    ]
    cards = make_chapter_cards(labelled, style, tmp_path / "cards", total=1220.0)
    assert len(cards) == 3


def test_the_intro_and_the_outro_get_no_time_of_their_own():
    # They are not chapters. Their time is not lost either: the first chapter
    # reads 0:00, so an intro in front of it belongs to that chapter as far as
    # a viewer clicking the list is concerned.
    marks = [
        Mark("Introduction", 0.0, 20.0, host=True),
        Mark("One.", 23.0, 600.0),
        Mark("Two.", 603.0, 1200.0),
        Mark("Three.", 1203.0, 1800.0),
        Mark("Afterword", 1803.0, 1820.0, host=True),
    ]
    text = youtube_description(marks, title="Volume 1")
    times = [line for line in text.splitlines() if line[:1].isdigit()]
    assert len(times) == 3
    assert times[0] == "0:00 One."
    assert "Introduction" not in text
    assert "Afterword" not in text


def test_a_volume_of_two_chapters_is_refused_even_with_an_intro():
    # The intro used to make the count. YouTube counts chapters, so a volume
    # that has too few of them has to be told so rather than be given a list
    # that YouTube silently ignores.
    marks = [
        Mark("Introduction", 0.0, 20.0, host=True),
        Mark("One.", 23.0, 600.0),
        Mark("Two.", 603.0, 1200.0),
        Mark("Afterword", 1203.0, 1220.0, host=True),
    ]
    with pytest.raises(OpenBookError, match="at least 3 chapters"):
        youtube_description(marks, title="Volume 1")


@needs_font
@needs_pillow
def test_the_host_card_says_nothing_about_a_chapter(tmp_path):
    # The intro speaks to the viewer and not about a place in the book, so its
    # card carries the name of the work and nothing else. It still gets a card,
    # because every moment of the video needs a picture.
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
    made = [
        Mark("Introduction", 0.0, 20.0, host=True),
        Mark("One.", 20.0, 600.0, label="Chapter 1 of 2"),
        Mark("Afterword", 600.0, 620.0, host=True),
    ]
    cards = make_chapter_cards(made, style, tmp_path / "cards", total=620.0)
    assert len(cards) == 3, "a card for every mark, host or not"

    plain = make_chapter_cards(
        [Mark("Introduction", 0.0, 20.0, host=True)],
        style,
        tmp_path / "plain",
        total=20.0,
    )
    blank = make_chapter_cards(
        [Mark("", 0.0, 20.0)], style, tmp_path / "blank", total=20.0, labels=[""]
    )
    assert plain[0][0].read_bytes() == blank[0][0].read_bytes(), (
        "a host card draws the same as a card with no volume, chapter or title"
    )


def test_a_fade_of_zero_leaves_the_picture_alone():
    from openbook.speech.video import _picture_fade

    assert _picture_fade(0.0, 600.0) == ""
    assert _picture_fade(3.0, 0.0) == ""


def test_the_picture_comes_out_of_black_and_goes_back_into_it():
    # The fade out is placed from the end, so it lands on the last seconds of
    # the volume rather than at a time somebody had to work out.
    from openbook.speech.video import _picture_fade

    made = _picture_fade(3.0, 600.0)
    assert "fade=t=in:st=0:d=3" in made
    assert "fade=t=out:st=597.000:d=3" in made


def test_a_fade_longer_than_the_video_does_not_start_before_it():
    from openbook.speech.video import _picture_fade

    assert "st=0.000" in _picture_fade(30.0, 10.0)


def test_the_music_carries_its_own_fade():
    # The bed is looped to a length nobody chose, so without this it begins
    # and ends mid phrase.
    from pathlib import Path

    from openbook.speech.video import Music

    assert Music(path=Path("m.flac")).fade == 0.0
    assert Music(path=Path("m.flac"), fade=3.0).fade == 3.0
