"""Puts the silences in, and divides anything too long for an engine.

The rule for a pause is the one the author asked for: a silence falls only
where the kind of the text changes. Two lines of dialogue that follow each
other get nothing between them, so a conversation keeps its speed. Two
paragraphs of narration get nothing either.

The speech engine still stops at the end of a sentence on its own. Everything
here is silence added on top of that stop.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..cast.utterance import ANNOUNCEMENT, DIALOGUE, Item, Silence, Utterance
from ..config.grammar import Grammar
from .sentences import split_sentences

NARRATION_TO_DIALOGUE = "narration to dialogue"
DIALOGUE_TO_NARRATION = "dialogue to narration"
AFTER_CHAPTER_NAME = "after the chapter name"


@dataclass(frozen=True)
class Plan:
    """Everything a render does, in order."""

    items: tuple[Item, ...]

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
    items: tuple[Item, ...], grammar: Grammar, *, max_characters: int | None = None
) -> Plan:
    """Add the silences to the utterances of one chapter."""
    divided = _divide_long(items, max_characters)
    return Plan(items=tuple(_add_pauses(divided, grammar)))


def plan_volume(
    chapters: list[tuple[Item, ...]],
    grammar: Grammar,
    *,
    max_characters: int | None = None,
) -> Plan:
    """Join the chapters of one volume into a single plan.

    A pause between two chapters is the pause after a chapter name, because the
    next thing a listener hears is the name of the chapter that follows.
    """
    items: list[Item] = []
    for index, chapter in enumerate(chapters):
        if index:
            items.append(
                Silence(seconds=grammar.render.after_chapter_name, reason="new chapter")
            )
        items.extend(
            plan_chapter(chapter, grammar, max_characters=max_characters).items
        )
    return Plan(items=tuple(items))


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

    A single sentence longer than the limit stays whole. Cutting it would do
    more harm than giving the engine more than it asked for, and an engine that
    truly cannot take it should say so itself.
    """
    pieces: list[str] = []
    current = ""
    for sentence in split_sentences(text):
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= limit:
            current = f"{current} {sentence}"
        else:
            pieces.append(current)
            current = sentence
    if current:
        pieces.append(current)
    return pieces or [text]
