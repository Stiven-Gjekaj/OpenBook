"""Turns the lines of a chapter into segments.

Each line becomes exactly one segment, or none. The order of the checks is the
order of certainty: end matter is known by its element, a scene break by its
shape, dialogue by a bold code at the front, and everything left is narration.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config.grammar import Grammar
from ..source.epub import Chapter
from .blocks import Line, read_lines
from .segments import (
    Action,
    Dialogue,
    EndMatter,
    Narration,
    Note,
    Piece,
    SceneBreak,
    Segment,
    Speech,
)


@dataclass(frozen=True)
class ParsedChapter:
    """One chapter, divided into the pieces the renderer works on."""

    number: int
    volume: str
    title: str
    segments: tuple[Segment, ...]
    notes: tuple[Note, ...]

    def speakers(self) -> tuple[str, ...]:
        """Every speaker code the chapter uses, in the order it first uses one."""
        seen: dict[str, None] = {}
        for segment in self.segments:
            if isinstance(segment, Dialogue):
                for code in segment.speakers:
                    seen.setdefault(code, None)
        return tuple(seen)


def parse_chapter(chapter: Chapter, grammar: Grammar) -> ParsedChapter:
    """Divide one chapter into segments."""
    segments: list[Segment] = []
    notes: list[Note] = []
    end_matter = frozenset({grammar.structure.end_matter_element})

    for line in read_lines(chapter.body):
        closing = bool(segments) and isinstance(segments[-1], EndMatter)
        segment = _read_line(
            line, grammar, end_matter, chapter.number, notes, closing=closing
        )
        if segment is not None:
            segments.append(segment)

    return ParsedChapter(
        number=chapter.number,
        volume=chapter.volume,
        title=chapter.title,
        segments=tuple(_one_closing(segments)),
        notes=tuple(notes),
    )


def _one_closing(segments: list[Segment]) -> list[Segment]:
    """Join the lines that close a chapter into one.

    A closing is one thing: the words 'End of Chapter 4', the name of the
    chapter, and the line the author leaves under it. The book writes them on
    separate lines because that is how they look on a page, and a reader would
    still say them as a single sentence falling to its end.

    Read as three, they come back as three endings in a row, each with its own
    fall. Read as one, the engine is given the whole shape at once.
    """
    joined: list[Segment] = []
    for segment in segments:
        if isinstance(segment, EndMatter) and isinstance(
            joined[-1] if joined else None, EndMatter
        ):
            joined[-1] = EndMatter(text=_and_then(joined[-1].text, segment.text))
        else:
            joined.append(segment)
    return joined


# What a reader would hear as the end of a sentence, once the marks that can
# close one from the outside are set aside.
STOPS = ".!?…:;"
CLOSERS = "\"'”’)]}"


def _and_then(before: str, after: str) -> str:
    """Join two closing lines, with a stop where the line break used to be.

    Without one the engine reads 'End of Chapter 0 "Point - Null"' as a single
    clause and hurries through the name.
    """
    ends = before.rstrip().rstrip(CLOSERS)
    return (
        f"{before} {after}" if ends and ends[-1] in STOPS else f"{before}. {after}"
    )


def _read_line(
    line: Line,
    grammar: Grammar,
    end_matter: frozenset[str],
    chapter: int,
    notes: list[Note],
    *,
    closing: bool = False,
) -> Segment | None:
    text = line.text
    if not text:
        return None

    if line.wholly_inside(end_matter):
        return EndMatter(text=text)

    # A line that closes a chapter without wearing the element the others wear.
    # Soultale underlines 'End of Chapter 4' and the name of the chapter, and
    # leaves the line beneath them in bold alone, so the element alone would
    # hand the last line of a closing to the narration. It is only a closing
    # where a closing has already begun, because the same shape means nothing
    # in the middle of a chapter.
    tail = grammar.structure.end_matter_tail
    if closing and tail is not None and tail.match(text):
        return EndMatter(text=text)

    if grammar.structure.scene_break.match(text):
        return SceneBreak()

    dialogue = _read_dialogue(line, text, grammar)
    if dialogue is not None:
        _note_lone_asterisk(dialogue.text, "/".join(dialogue.speakers), chapter, notes)
        return dialogue

    _note_lone_asterisk(text, "narration", chapter, notes)
    return Narration(text=text)


def _read_dialogue(line: Line, text: str, grammar: Grammar) -> Dialogue | None:
    """Read a line as dialogue, or give back None.

    Two things must agree. The text at the front of the line must sit inside a
    bold element, and the whole line must match the dialogue template. Bold
    alone is not enough, because bold also marks emphasis inside a sentence.
    The template alone is not enough either, because a narration line can start
    with capitals and a colon.
    """
    first = line.first_run()
    if first is None or not first.inside(grammar.dialogue.elements):
        return None

    found = grammar.dialogue.template.match(text)
    if found is None:
        return None

    speakers = _read_speakers(found["SPEAKER"], grammar)
    pieces = _read_pieces(found["TEXT"], grammar)
    if not pieces:
        return None
    return Dialogue(speakers=speakers, pieces=pieces)


def _read_speakers(code: str, grammar: Grammar) -> tuple[str, ...]:
    separator = grammar.dialogue.unison.separator
    if separator and separator in code:
        return tuple(part.strip() for part in code.split(separator) if part.strip())
    return (code.strip(),)


def _read_pieces(text: str, grammar: Grammar) -> tuple[Piece, ...]:
    """Divide the words of a line into speech and the actions inside it."""
    pattern = grammar.dialogue.action
    pieces: list[Piece] = []

    if pattern is None:
        speech = text.strip()
        return (Speech(text=speech),) if speech else ()

    position = 0
    for found in pattern.finditer(text):
        _add_speech(pieces, text[position : found.start()])
        action = (found.groupdict().get("TEXT") or found.group(0)).strip()
        if action:
            pieces.append(Action(text=action))
        position = found.end()
    _add_speech(pieces, text[position:])
    return tuple(pieces)


def _add_speech(pieces: list[Piece], text: str) -> None:
    speech = text.strip()
    if speech:
        pieces.append(Speech(text=speech))


def _note_lone_asterisk(text: str, where: str, chapter: int, notes: list[Note]) -> None:
    """Report an asterisk that no pair of asterisks used.

    The editor that made this book turned half of some pairs into italic text
    and left the other half as a character. A rule that looks for two asterisks
    cannot see one that stayed behind, and it would otherwise reach a voice.

    This checks narration as well as dialogue. The one place in Soultale where
    it happens is a paragraph of narration, so a check on dialogue alone would
    have found nothing and said the book was clean.
    """
    if "*" not in text:
        return
    notes.append(
        Note(
            kind="lone asterisk",
            detail=(
                f"chapter {chapter}, {where}: an asterisk with no pair, "
                f"in {text[:60]!r}"
            ),
        )
    )
