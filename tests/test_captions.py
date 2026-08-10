import itertools

import pytest

from openbook.cast.utterance import Utterance, Voice
from openbook.speech.captions import (
    Cue,
    break_text,
    cues_from_timeline,
    label_for,
    stamp,
    to_srt,
)

VOICE = Voice("af_heart")


def line(text, kind="narration", speaker="narrator"):
    return Utterance(text=text, voice=VOICE, kind=kind, speaker=speaker)


def test_a_time_is_written_the_way_srt_wants_it():
    assert stamp(0) == "00:00:00,000"
    assert stamp(1.5) == "00:00:01,500"
    assert stamp(3661.25) == "01:01:01,250"


def test_a_time_before_the_start_becomes_zero():
    assert stamp(-1) == "00:00:00,000"


def test_a_rounding_that_reaches_a_whole_second_carries():
    assert stamp(1.9999) == "00:00:02,000"


def test_text_is_broken_where_a_reader_can_follow_it():
    pieces = break_text("one two three four five six", limit=12)
    assert all(len(piece) <= 12 for piece in pieces)
    assert " ".join(pieces) == "one two three four five six"


def test_a_word_longer_than_the_limit_is_not_cut():
    assert break_text("supercalifragilistic", limit=5) == ["supercalifragilistic"]


def test_nothing_gives_nothing():
    assert break_text("   ") == []


def test_a_line_of_dialogue_carries_the_name_of_who_says_it():
    # A reader has never seen the cast file and cannot know that BLK is Blook.
    said = line("No.", kind="dialogue", speaker="BLK")
    assert label_for(said, {"BLK": "Blook"}) == "[Blook] "


def test_a_code_with_no_name_falls_back_to_the_code():
    said = line("No.", kind="dialogue", speaker="XYZ")
    assert label_for(said, {}) == "[XYZ] "


def test_two_characters_speaking_together_are_both_named():
    said = line("Stop.", kind="dialogue", speaker="NER/SHN")
    assert label_for(said, {"NER": "Ner", "SHN": "Shn"}) == "[Ner and Shn] "


def test_narration_carries_no_name():
    assert label_for(line("She walked home."), {}) == ""


def test_a_cue_is_made_for_each_utterance():
    timeline = [(line("One."), 0.0, 2.0), (line("Two."), 2.5, 4.0)]
    cues = cues_from_timeline(timeline)
    assert [cue.text for cue in cues] == ["One.", "Two."]
    assert cues[0].start == 0.0 and cues[0].end == 2.0


def test_a_long_utterance_is_divided_and_shares_out_its_time():
    text = "one two three four five six seven eight nine ten eleven twelve"
    cues = cues_from_timeline([(line(text), 0.0, 12.0)], limit=20)
    assert len(cues) > 1
    assert cues[0].start == 0.0
    assert cues[-1].end == 12.0
    # No gap and no overlap between the pieces of one utterance.
    for before, after in itertools.pairwise(cues):
        assert before.end == pytest.approx(after.start)


def test_only_the_first_piece_of_a_line_carries_the_name():
    text = "one two three four five six seven eight nine ten"
    said = Utterance(text=text, voice=VOICE, kind="dialogue", speaker="BLK")
    cues = cues_from_timeline([(said, 0.0, 6.0)], names={"BLK": "Blook"}, limit=20)
    assert cues[0].text.startswith("[Blook] ")
    assert not cues[1].text.startswith("[Blook]")


def test_an_action_is_captioned_as_a_sound_and_not_as_speech():
    # A caption says what a listener hears. Nobody says the word "cough".
    action = Utterance(text="cough", voice=VOICE, kind="action")
    (cue,) = cues_from_timeline([(action, 1.0, 1.5)])
    assert cue.text == "[cough]"


def test_srt_numbers_its_cues_from_one():
    text = to_srt([Cue(0.0, 1.0, "One."), Cue(1.0, 2.0, "Two.")])
    assert text.startswith("1\n00:00:00,000 --> 00:00:01,000\nOne.")
    assert "\n2\n" in text


def test_a_cue_of_no_length_is_given_one():
    # Some players refuse a cue that ends where it starts.
    text = to_srt([Cue(1.0, 1.0, "Blink.")])
    assert "00:00:01,000 --> 00:00:01,001" in text


def test_a_short_caption_stays_on_one_line():
    from openbook.speech.captions import lay_out

    assert "\n" not in lay_out("Short enough.")


def test_a_long_caption_is_put_on_two_lines_of_about_the_same_length():
    # One long line is broken by the player wherever the screen ends. Two lines
    # chosen here look the same on every screen.
    from openbook.speech.captions import lay_out

    text = "Not the kind of something that takes up space or casts shadows"
    laid = lay_out(text)
    first, second = laid.split("\n")
    assert abs(len(first) - len(second)) <= 8
    assert laid.replace("\n", " ") == text


def test_a_caption_never_breaks_inside_a_word():
    from openbook.speech.captions import lay_out

    laid = lay_out("one two three four five six seven eight nine ten eleven")
    for line in laid.split("\n"):
        assert not line.startswith(" ") and not line.endswith(" ")


def test_every_cue_of_a_render_is_at_most_two_lines():
    text = "one two three four five six seven eight nine ten eleven twelve thirteen"
    cues = cues_from_timeline([(line(text), 0.0, 10.0)])
    assert all(cue.text.count("\n") <= 1 for cue in cues)


def test_the_chapter_name_is_not_captioned():
    # The card on the screen already carries it, and a caption of the same
    # words over the top says one thing twice.
    said = Utterance(text="Chapter 0. Point - Null.", voice=VOICE, kind="announcement")
    timeline = [(said, 0.0, 2.0), (line("She walked home."), 2.0, 4.0)]
    assert [cue.text for cue in cues_from_timeline(timeline)] == ["She walked home."]


def test_the_chapter_name_can_be_asked_for():
    # Sound with no picture behind it wants the announcement after all.
    said = Utterance(text="Chapter 0. Point - Null.", voice=VOICE, kind="announcement")
    cues = cues_from_timeline([(said, 0.0, 2.0)], announcements=True)
    assert cues[0].text == "Chapter 0. Point - Null."
