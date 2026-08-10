import pytest

from openbook.cast.utterance import Utterance, Voice
from openbook.errors import OpenBookError
from openbook.plan.planner import Plan
from openbook.speech.package import Mark
from openbook.speech.verify import check_cards_against_speech, check_cards_against_time

NARRATOR = Voice("af_heart")


class FakeVolume:
    """Enough of a volume for the checks to read."""

    def __init__(self, announcements, numbers=None):
        self.chapter_plans = [
            Plan(
                items=(
                    Utterance(text=text, voice=NARRATOR, kind="announcement"),
                    Utterance(text="Some prose.", voice=NARRATOR, kind="narration"),
                )
                if text
                else (Utterance(text="Some prose.", voice=NARRATOR, kind="narration"),)
            )
            for text in announcements
        ]
        self.chapters = [
            type("C", (), {"number": n, "title": f"T{n}."})()
            for n in (numbers or range(len(announcements)))
        ]


def test_a_card_that_matches_the_narration_passes():
    volume = FakeVolume(
        ["Chapter 3. Wandering Spirit.", "Chapter 4. Will of The Weak."]
    )
    check_cards_against_speech(volume, ["Chapter 3 of 22", "Chapter 4 of 22"])


def test_a_card_that_names_another_chapter_is_refused():
    # The fault that reached a finished video: the card counted its place in
    # the volume and the narrator read the number of the book.
    volume = FakeVolume(["Chapter 21. Whose Names Aren't Called."], numbers=[21])
    with pytest.raises(OpenBookError, match="see one thing and hear another"):
        check_cards_against_speech(volume, ["Chapter 22 of 23"])


def test_a_prologue_card_that_disagrees_with_the_narration_is_refused():
    volume = FakeVolume(["Prologue. Point - Null."], numbers=[0])
    with pytest.raises(OpenBookError, match="Chapter 0 of 2"):
        check_cards_against_speech(volume, ["Chapter 0 of 2"])


def test_a_prologue_card_passes_when_the_narrator_says_the_number():
    volume = FakeVolume(["Chapter 0. Point - Null."], numbers=[0])
    check_cards_against_speech(volume, ["Chapter 0 of 2"])


def test_a_chapter_that_is_not_announced_has_nothing_to_disagree_with():
    volume = FakeVolume([""], numbers=[3])
    check_cards_against_speech(volume, ["Chapter 3 of 22"])


def test_one_card_for_each_chapter():
    volume = FakeVolume(["Chapter 1. A.", "Chapter 2. B."])
    with pytest.raises(OpenBookError, match="One card belongs to each chapter"):
        check_cards_against_speech(volume, ["Chapter 1 of 2"])


def test_cards_that_sit_where_their_chapters_do_pass():
    marks = [Mark("One.", 0.0, 100.0), Mark("Two.", 101.0, 200.0)]
    cards = [("a.png", 101.0), ("b.png", 99.0)]
    check_cards_against_time(cards, marks, 200.0)


def test_drift_that_builds_up_over_chapters_is_refused():
    # Each card a second short, which is how the pictures came apart from the
    # sound. One second alone is inside the tolerance, as it should be; the
    # fault is that it never stops growing.
    marks = [Mark(f"C{i}.", i * 101.0, i * 101.0 + 100.0) for i in range(5)]
    cards = [(f"{i}.png", 100.0) for i in range(5)]
    with pytest.raises(OpenBookError, match="come apart"):
        check_cards_against_time(cards, marks, 505.0)


def test_one_second_on_one_chapter_is_inside_the_tolerance():
    marks = [Mark("One.", 0.0, 100.0), Mark("Two.", 101.0, 200.0)]
    check_cards_against_time([("a.png", 100.4), ("b.png", 99.6)], marks, 200.0)


def test_cards_that_outlast_the_sound_are_refused():
    # The concat reader repeats the last card, which added its whole duration
    # to the end and left a still picture over silence.
    marks = [Mark("One.", 0.0, 100.0)]
    cards = [("a.png", 200.0)]
    with pytest.raises(OpenBookError, match="still picture over silence"):
        check_cards_against_time(cards, marks, 100.0)


def test_a_small_rounding_difference_is_allowed():
    marks = [Mark("One.", 0.0, 100.0)]
    check_cards_against_time([("a.png", 100.4)], marks, 100.0)
