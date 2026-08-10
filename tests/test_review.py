import json

from openbook.cast.utterance import Utterance, Voice
from openbook.lexicon import EMPTY, Lexicon
from openbook.review import (
    LONG_CHARACTERS,
    Row,
    reasons_to_hear,
    rows_from,
    write_page,
)
from openbook.speech.package import Mark

VOICE = Voice("af_heart")
KNOWN = {"she", "walked", "home", "yes", "no", "the", "and"}


def line(text, kind="narration", speaker="narrator"):
    return Utterance(text=text, voice=VOICE, kind=kind, speaker=speaker)


def why(utterance, *, first_time=False, lexicon=EMPTY):
    return reasons_to_hear(
        utterance, first_time=first_time, lexicon=lexicon, known=KNOWN
    )


def test_an_ordinary_line_is_not_worth_hearing_first():
    assert why(line("She walked home.")) == []


def test_a_long_line_is_worth_hearing():
    assert "long" in why(line("she " * (LONG_CHARACTERS // 2)))


def test_the_first_line_of_a_character_is_worth_hearing():
    said = line("Yes.", kind="dialogue", speaker="BLK")
    assert "first line by this character" in why(said, first_time=True)
    assert "first line by this character" not in why(said, first_time=False)


def test_a_line_with_a_number_is_worth_hearing():
    # A voice says a number in whichever way it chooses, and it is often wrong.
    assert "holds a number" in why(line("She walked 7 miles home."))


def test_a_line_with_capitals_is_worth_hearing():
    assert "holds capitals" in why(line("She walked HOME."))


def test_a_stray_asterisk_is_worth_hearing():
    assert "holds an asterisk" in why(line("She walked home *"))


def test_a_word_with_no_lexicon_entry_is_worth_hearing():
    reasons = why(line("Vazroth walked home."))
    assert any("words with no entry" in reason for reason in reasons)
    assert any("vazroth" in reason.lower() for reason in reasons)


def test_a_word_the_lexicon_answers_is_not_reported():
    lexicon = Lexicon(entries={"Vazroth": "Vaz-roth"})
    reasons = why(line("Vazroth walked home."), lexicon=lexicon)
    assert not any("words with no entry" in reason for reason in reasons)


def test_a_row_is_made_for_each_piece_of_speech():
    timeline = [(line("One."), 0.0, 2.0), (line("Two."), 2.0, 4.0)]
    rows = rows_from(
        timeline,
        [Mark("A.", 0.0, 4.0)],
        names={},
        lexicon=EMPTY,
        known=KNOWN,
        keys={0: "aaa", 1: "bbb"},
    )
    assert [row.text for row in rows] == ["One.", "Two."]
    assert rows[0].audio == "aaa"


def test_a_row_carries_the_name_of_the_character_and_not_the_code():
    said = line("Yes.", kind="dialogue", speaker="BLK")
    rows = rows_from(
        [(said, 0.0, 1.0)],
        [Mark("A.", 0.0, 1.0)],
        names={"BLK": "Blook"},
        lexicon=EMPTY,
        known=KNOWN,
        keys={},
    )
    assert rows[0].speaker == "Blook"


def test_a_row_knows_which_chapter_it_is_in():
    marks = [Mark("One.", 0.0, 10.0), Mark("Two.", 10.0, 20.0)]
    timeline = [(line("a"), 1.0, 2.0), (line("b"), 12.0, 13.0)]
    rows = rows_from(timeline, marks, names={}, lexicon=EMPTY, known=KNOWN, keys={})
    assert rows[0].chapter_title == "One."
    assert rows[1].chapter_title == "Two."


def test_the_page_holds_its_rows_and_needs_nothing_fetched(tmp_path):
    # A review that needs a server started is a review that does not happen.
    rows = rows_from(
        [(line("Vazroth walked home."), 0.0, 2.0)],
        [Mark("One.", 0.0, 2.0)],
        names={},
        lexicon=EMPTY,
        known=KNOWN,
        keys={0: "abc123"},
    )
    out = write_page(
        rows, tmp_path / "r.html", title="Volume 1", cache=tmp_path / "cache"
    )
    text = out.read_text(encoding="utf-8")
    assert "Vazroth walked home." in text
    assert "abc123" in text
    assert "<script" in text
    assert "http://" not in text and "https://" not in text


def test_the_rows_in_the_page_are_valid_json(tmp_path):
    rows = rows_from(
        [(line('He said "no".'), 0.0, 2.0)],
        [Mark("One.", 0.0, 2.0)],
        names={},
        lexicon=EMPTY,
        known=KNOWN,
        keys={},
    )
    out = write_page(rows, tmp_path / "r.html", title="V", cache=tmp_path / "c")
    text = out.read_text(encoding="utf-8")
    start = text.index("const ROWS = ") + len("const ROWS = ")
    end = text.index(", CACHE =", start)
    assert json.loads(text[start:end])[0]["t"] == 'He said "no".'


def test_a_title_with_markup_in_it_cannot_reach_the_page(tmp_path):
    out = write_page(
        [], tmp_path / "r.html", title="<script>bad()</script>", cache=tmp_path / "c"
    )
    assert "<script>bad()" not in out.read_text(encoding="utf-8")


def test_one_control_starts_and_stops_a_line(tmp_path):
    """One button, not two. It says play, and says pause while that line
    sounds, so a person reviewing has one thing to aim at."""
    rows = [
        Row(
            order=0,
            chapter=1,
            chapter_title="One.",
            speaker="Ink",
            voice="am_adam",
            kind="dialogue",
            text="A line.",
            start=0.0,
            audio="abcdef",
        ),
        Row(
            order=1,
            chapter=1,
            chapter_title="One.",
            speaker="Zero",
            voice="bm_george",
            kind="dialogue",
            text="Another.",
            start=2.0,
            audio="123456",
        ),
    ]
    out = write_page(
        rows, tmp_path / "review.html", title="T", cache=tmp_path / "cache"
    )
    page = out.read_text(encoding="utf-8")

    # One control for hearing a line, and it carries both words.
    assert page.count('play.className = "hear"') == 1
    assert '"pause" : "play"' in page
    # Starting a second line stops the first, or two lines say nothing about
    # either.
    assert "function silence()" in page
    assert "sounding = row.n" in page


def test_the_page_reaches_its_audio_from_wherever_it_is_opened(tmp_path):
    """A relative path works both ways and an absolute one does not.

    A page served over http cannot fetch an address beginning file: at all.
    The browser refuses it, says nothing in the page, and every button does
    nothing. Opened as a file, a relative path resolves to exactly the same
    place the absolute form named.
    """
    from urllib.parse import urljoin

    out = tmp_path / "out" / "review.html"
    cache = tmp_path / "cache"
    (cache / "ab").mkdir(parents=True)
    (cache / "ab" / "abcdef.wav").write_bytes(b"RIFF")

    rows = [
        Row(
            order=0,
            chapter=1,
            chapter_title="One.",
            speaker="Ink",
            voice="am_adam",
            kind="dialogue",
            text="A line.",
            start=0.0,
            audio="abcdef",
        )
    ]
    write_page(rows, out, title="T", cache=cache)
    page = out.read_text(encoding="utf-8")

    assert 'CACHE = "../cache"' in page
    assert "file:" not in page.split("const ROWS")[1][:200]

    # What a browser makes of it when the page is opened as a file.
    asked = urljoin(out.resolve().as_uri(), "../cache/ab/abcdef.wav")
    assert asked == (cache / "ab" / "abcdef.wav").resolve().as_uri()


def test_a_cache_on_another_disk_keeps_the_only_address_there_is(tmp_path, monkeypatch):
    # No relative path exists between two drives on Windows. The file: form is
    # worse, and it is better than nothing at all.
    import openbook.review as review

    def refuse(*_):
        raise ValueError("paths are on different drives")

    monkeypatch.setattr(review.os.path, "relpath", refuse)
    said = review.where_the_audio_is(tmp_path / "review.html", tmp_path / "cache")
    assert said.startswith("file:")
