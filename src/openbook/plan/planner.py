"""Puts the silences in, and divides anything too long for an engine.

The rule for a pause is the one the author asked for: a silence falls only
where the kind of the text changes. Two lines of dialogue that follow each
other get nothing between them, so a conversation keeps its speed. Two
paragraphs of narration get nothing either.

The speech engine still stops at the end of a sentence on its own. Everything
here is silence added on top of that stop.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..cast.utterance import ANNOUNCEMENT, DIALOGUE, Item, Silence, Utterance
from ..config.grammar import Grammar
from ..corrections import EMPTY, Corrections, used_by
from .sentences import split_clauses, split_sentences

NARRATION_TO_DIALOGUE = "narration to dialogue"
DIALOGUE_TO_NARRATION = "dialogue to narration"
AFTER_CHAPTER_NAME = "after the chapter name"


@dataclass(frozen=True)
class Plan:
    """Everything a render does, in order."""

    items: tuple[Item, ...]

    # Which corrections had a line here to change. The plan says what was done
    # to make it, so a person can be told the file is being read at all.
    corrected: tuple[str, ...] = ()

    @property
    def utterances(self) -> tuple[Utterance, ...]:
        return tuple(i for i in self.items if isinstance(i, Utterance))

    @property
    def silences(self) -> tuple[Silence, ...]:
        return tuple(i for i in self.items if isinstance(i, Silence))

    @property
    def silent_seconds(self) -> float:
        return sum(s.seconds for s in self.silences)

    def words(self) -> int:
        return sum(len(u.text.split()) for u in self.utterances)


def plan_chapter(
    items: tuple[Item, ...],
    grammar: Grammar,
    *,
    max_characters: int | None = None,
    corrections: Corrections = EMPTY,
) -> Plan:
    """Add the silences to the utterances of one chapter."""
    divided = _divide_long(items, max_characters)
    divided, used = _correct(divided, corrections, max_characters)
    return Plan(items=tuple(_add_pauses(divided, grammar)), corrected=used)


def plan_volume(
    chapters: list[tuple[Item, ...]],
    grammar: Grammar,
    *,
    max_characters: int | None = None,
    corrections: Corrections = EMPTY,
) -> Plan:
    """Join the chapters of one volume into a single plan.

    A pause between two chapters is the pause after a chapter name, because the
    next thing a listener hears is the name of the chapter that follows.
    """
    items: list[Item] = []
    used: list[str] = []
    for index, chapter in enumerate(chapters):
        if index:
            items.append(
                # The gap that closes a chapter. It follows the end matter,
                # which is the last thing said, so it is the rest a listener
                # gets before the next chapter is announced. It used to borrow
                # the pause that follows a chapter name, which is a different
                # thing that happens to be a length.
                Silence(seconds=grammar.render.between_chapters, reason="new chapter")
            )
        plan = plan_chapter(
            chapter, grammar, max_characters=max_characters, corrections=corrections
        )
        items.extend(plan.items)
        used.extend(line for line in plan.corrected if line not in used)
    return Plan(items=tuple(items), corrected=tuple(used))


def _correct(
    items: list[Item], corrections: Corrections, max_characters: int | None
) -> tuple[list[Item], tuple[str, ...]]:
    """Put the corrected words in place of the ones that came out wrong.

    This happens after a long line is divided, because the review page shows
    the divided pieces and an entry names a line as the page showed it.

    The corrected words are divided again. A correction is usually about the
    same length as what it replaces, but nothing makes it so, and a piece that
    grew past the limit of the engine would be cut by the engine instead.
    """
    used = used_by(
        (item.text for item in items if isinstance(item, Utterance)), corrections
    )
    if not used:
        return items, ()

    changed: list[Item] = [
        replace(item, text=corrections.apply(item.text))
        if isinstance(item, Utterance)
        else item
        for item in items
    ]
    return _divide_long(tuple(changed), max_characters), used


def _side(utterance: Utterance) -> str:
    """Which side of the pause rule an utterance sits on.

    Only dialogue is dialogue. An action that the narrator speaks belongs with
    narration, which is right: the narrator breaking into a line of speech is
    exactly the change that wants a pause on each side of it.
    """
    return "dialogue" if utterance.kind == DIALOGUE else "narration"


def _add_pauses(items: list[Item], grammar: Grammar):
    render = grammar.render
    previous: Utterance | None = None
    silence_since = False

    for item in items:
        if isinstance(item, Silence):
            # A silence the cast stage already put in, for a scene break or an
            # action. One pause in a place is enough.
            silence_since = True
            previous = None if item.reason == "new chapter" else previous
            yield item
            continue

        if previous is not None and not silence_since:
            pause = _pause_between(previous, item, render)
            if pause is not None:
                yield pause

        yield item
        previous = item
        silence_since = False


def _pause_between(before: Utterance, after: Utterance, render) -> Silence | None:
    if before.kind == ANNOUNCEMENT:
        return Silence(seconds=render.after_chapter_name, reason=AFTER_CHAPTER_NAME)

    one, two = _side(before), _side(after)
    if one == two:
        return None
    if two == "dialogue":
        return Silence(
            seconds=render.narration_to_dialogue, reason=NARRATION_TO_DIALOGUE
        )
    return Silence(seconds=render.dialogue_to_narration, reason=DIALOGUE_TO_NARRATION)


def _divide_long(items: tuple[Item, ...], max_characters: int | None) -> list[Item]:
    """Divide an utterance that is longer than the engine accepts.

    The cut falls at the end of a sentence. A cut inside a sentence takes the
    fall of the voice with it, and the two halves sound like separate thoughts.
    """
    if max_characters is None:
        return list(items)

    divided: list[Item] = []
    for item in items:
        if isinstance(item, Silence) or len(item.text) <= max_characters:
            divided.append(item)
            continue
        for piece in _pieces(item.text, max_characters):
            divided.append(
                Utterance(
                    text=piece, voice=item.voice, kind=item.kind, speaker=item.speaker
                )
            )
    return divided


def _pieces(text: str, limit: int) -> list[str]:
    """Group sentences into pieces no longer than the limit.

    A sentence that is longer than the limit on its own divides again, at the
    places a reader would take a breath. Soultale has 34 of those, and the
    longest holds 1059 characters. Handing one to an engine whole means the
    engine cuts it where its own limit falls, and nothing chooses where that
    lands.
    """
    return _group(_units(text, limit), limit)


def _units(text: str, limit: int) -> list[str]:
    """The smallest pieces to build from: sentences, divided again if long."""
    units: list[str] = []
    for sentence in split_sentences(text):
        if len(sentence) <= limit:
            units.append(sentence)
            continue
        for clause in split_clauses(sentence):
            units.extend(_words(clause, limit) if len(clause) > limit else [clause])
    return units


def _words(text: str, limit: int) -> list[str]:
    """The last choice. A clause with no mark in it, longer than the limit.

    Cutting between two words is bad. Letting the engine cut inside a word is
    worse, and that is the only other option left here.
    """
    pieces: list[str] = []
    current = ""
    for word in text.split():
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= limit:
            current = f"{current} {word}"
        else:
            pieces.append(current)
            current = word
    if current:
        pieces.append(current)
    return pieces


def _group(units: list[str], limit: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for unit in units:
        if not current:
            current = unit
        elif len(current) + 1 + len(unit) <= limit:
            current = f"{current} {unit}"
        else:
            pieces.append(current)
            current = unit
    if current:
        pieces.append(current)
    return pieces
