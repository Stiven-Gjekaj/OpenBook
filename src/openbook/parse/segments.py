"""The pieces that a chapter divides into.

A segment is one thing that the renderer treats as a unit. A pause can fall
between two segments, and never inside one.

A line of dialogue is one segment even when an action interrupts it, because
the words on both sides of the action belong to the same person and the same
breath. The action is a piece inside that segment, not a segment of its own.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Speech:
    """Words that a character says."""

    text: str


@dataclass(frozen=True)
class Action:
    """What a character does, written between asterisks inside their words.

    The renderer never speaks this text. The author wrote *cough* to say how the
    line sounds, and *to his assistant* to say where the character looks, and a
    voice that says either one out loud is wrong.
    """

    text: str


Piece = Speech | Action


@dataclass(frozen=True)
class Narration:
    """A paragraph that nobody in the story says."""

    text: str


@dataclass(frozen=True)
class Dialogue:
    """One line that one or more characters say."""

    speakers: tuple[str, ...]
    pieces: tuple[Piece, ...]

    @property
    def is_unison(self) -> bool:
        return len(self.speakers) > 1

    @property
    def text(self) -> str:
        """Every spoken word of the line, with the actions taken out."""
        return " ".join(
            piece.text for piece in self.pieces if isinstance(piece, Speech)
        ).strip()

    @property
    def actions(self) -> tuple[Action, ...]:
        return tuple(piece for piece in self.pieces if isinstance(piece, Action))


@dataclass(frozen=True)
class SceneBreak:
    """A division inside a chapter. The renderer makes a silence here."""


@dataclass(frozen=True)
class EndMatter:
    """The words at the end of a chapter that repeat its name and number."""

    text: str


Segment = Narration | Dialogue | SceneBreak | EndMatter


@dataclass(frozen=True)
class Note:
    """Something the parser wants a person to look at.

    A note is not an error. The chapter still parses. It marks a place where
    the source is not what the rules expect, and where the audio is therefore
    worth hearing before it ships.
    """

    kind: str
    detail: str

    def __str__(self) -> str:
        return f"{self.kind}: {self.detail}"
