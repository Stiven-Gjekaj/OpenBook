"""Checks that the picture and the sound agree, before anything is encoded.

Three faults reached a finished video before this existed, and no test caught
any of them. Each piece behaved as it was written. They only disagreed with
each other, and only where somebody watches and listens at the same time:

  A card said "Chapter 22 of 23" while the narrator said "Chapter 21".
  A card said "Chapter 0" while the narrator said "Prologue".
  A card changed twenty two seconds before the chapter it named began.

A unit test cannot find any of those, because there is nothing wrong with
either side on its own. What is needed is a check that reads both sides and
compares them, which is what this does.

It runs before the encode, so a fault costs a second instead of two minutes.
"""

from __future__ import annotations

from ..cast.utterance import ANNOUNCEMENT, Utterance
from ..errors import OpenBookError

# How far a card may sit from the chapter it names. One frame at one frame each
# second, with a little room for rounding.
DRIFT_SECONDS = 1.5


def spoken_announcements(volume) -> list[str]:
    """What the narrator says at the start of each chapter of a volume."""
    said: list[str] = []
    for plan in volume.chapter_plans:
        first = next(
            (
                item.text
                for item in plan.items
                if isinstance(item, Utterance) and item.kind == ANNOUNCEMENT
            ),
            "",
        )
        said.append(first)
    return said


def check_marks_against_speech(marks, volume) -> None:
    """Refuse a video whose chapter cards disagree with its narration.

    A mark with no label is an intro or an outro. It has no chapter line on its
    card, so there is nothing for the narration to disagree with.
    """
    said = {}
    for chapter, text in zip(
        volume.chapters, spoken_announcements(volume), strict=True
    ):
        said[chapter.title] = (chapter.number, text)

    for mark in marks:
        if not mark.label or mark.title not in said:
            continue
        number, announcement = said[mark.title]
        if not announcement:
            continue
        head = mark.label.split(" of ")[0].strip()
        if head.lower() not in announcement.lower():
            raise OpenBookError(
                f"chapter {number}: the card says {mark.label!r} and the "
                f"narrator says {announcement!r}. The listener would see one "
                "thing and hear another. Make chapter_announcement and the "
                "card use the same words"
            )


def check_cards_against_speech(volume, labels: list[str]) -> None:
    """Refuse a video whose cards disagree with its narration.

    A label reads "Chapter 3 of 22" and the narrator says "Chapter 3. Wandering
    Spirit." The part of the label in front of "of" has to appear in what the
    narrator says, or the listener sees one number and hears another.
    """
    said = spoken_announcements(volume)
    if len(labels) != len(said):
        raise OpenBookError(
            f"there are {len(labels)} cards and {len(said)} chapters. One card "
            "belongs to each chapter"
        )

    for label, announcement, chapter in zip(labels, said, volume.chapters, strict=True):
        if not announcement:
            # The chapter is not announced at all, so there is nothing that the
            # card can disagree with.
            continue
        head = label.split(" of ")[0].strip()
        if head.lower() not in announcement.lower():
            raise OpenBookError(
                f"chapter {chapter.number}: the card says {label!r} and the "
                f"narrator says {announcement!r}. The listener would see one "
                "thing and hear another. Make chapter_announcement and the "
                "card use the same words"
            )


def check_cards_against_time(cards, marks, total: float) -> None:
    """Refuse a video whose cards do not sit where their chapters do."""
    if len(cards) != len(marks):
        raise OpenBookError(f"there are {len(cards)} cards and {len(marks)} chapters")

    at = 0.0
    for (_, seconds), mark in zip(cards, marks, strict=True):
        if abs(at - mark.start) > DRIFT_SECONDS:
            raise OpenBookError(
                f"the card for {mark.title!r} appears at {at:.1f}s and its "
                f"chapter begins at {mark.start:.1f}s. The picture and the "
                "sound have come apart"
            )
        at += seconds

    if abs(at - total) > DRIFT_SECONDS:
        raise OpenBookError(
            f"the cards run {at:.1f}s and the sound runs {total:.1f}s. The "
            "video would end on a still picture over silence"
        )
