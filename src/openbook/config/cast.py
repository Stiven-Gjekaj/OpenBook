"""Reads the cast file, which gives a voice to each speaker code.

Most codes name one character and take one entry. The code for an unknown
character does not. It names a different character in each part of the book, so
it takes one entry for each group of chapters, and the chapter number chooses
between them.

A code with no entry stops the build. A code with an entry but no voice also
stops the build, but only when the renderer reaches it, so that a person can
look at a cast that is not finished yet.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from ..errors import CastError, ConfigError
from .reader import Table, load_toml

# One chapter, or a run of chapters, or several of either divided by commas.
_RANGE = re.compile(r"\A(-?\d+)\s*(?:-\s*(-?\d+))?\Z")


@dataclass(frozen=True)
class Chapters:
    """The chapters that one entry covers."""

    spans: tuple[tuple[int, int], ...]

    def contains(self, chapter: int) -> bool:
        return any(low <= chapter <= high for low, high in self.spans)

    def __str__(self) -> str:
        return ", ".join(
            str(low) if low == high else f"{low}-{high}" for low, high in self.spans
        )


ALL_CHAPTERS = Chapters(spans=())


@dataclass(frozen=True)
class Entry:
    """One character, and the voice that speaks for them."""

    code: str
    name: str
    voice: str
    chapters: Chapters | None = None

    # How much feeling this character is read with, when somebody wrote a
    # number down for them. Nothing here without one: an engine that reads
    # with feeling then picks its own from the kind of the line.
    exaggeration: float | None = None

    @property
    def is_cast(self) -> bool:
        return bool(self.voice)

    def covers(self, chapter: int) -> bool:
        return self.chapters is None or self.chapters.contains(chapter)


@dataclass(frozen=True)
class Cast:
    """Every entry in the cast file."""

    narrator: str
    narrator_exaggeration: float | None
    entries: dict[str, tuple[Entry, ...]]
    aliases: dict[str, str]

    def codes(self) -> tuple[str, ...]:
        return tuple(sorted(self.entries))

    def canonical(self, code: str) -> str:
        return self.aliases.get(code, code)

    def resolve(self, code: str, chapter: int) -> Entry:
        """Find the entry for a code in a chapter, or stop the build."""
        wanted = self.canonical(code)
        found = self.entries.get(wanted)
        if not found:
            near = difflib.get_close_matches(code, self.codes(), n=1)
            detail = f"The code near to it is {near[0]!r}" if near else None
            raise CastError(code, chapter, detail=detail)

        for entry in found:
            if entry.covers(chapter):
                return entry

        covered = "; ".join(str(entry.chapters) for entry in found)
        raise CastError(
            code,
            chapter,
            detail=(
                "The cast file has this code, but no entry of it covers this "
                f"chapter. The entries cover {covered}. Add an entry for the "
                "chapters that are missing"
            ),
        )

    def uncast(self) -> tuple[Entry, ...]:
        """Every entry that has no voice yet."""
        return tuple(
            entry
            for group in self.entries.values()
            for entry in group
            if not entry.is_cast
        )

    def voices(self) -> tuple[str, ...]:
        """Every voice this cast asks for, the narrator first, said once each.

        What a voice is depends on the engine. It is a name to Kokoro and a
        path to a recording to Chatterbox, and this does not know or care
        which. It answers what was written down.
        """
        found = [self.narrator] if self.narrator else []
        for group in self.entries.values():
            for entry in group:
                if entry.is_cast and entry.voice not in found:
                    found.append(entry.voice)
        return tuple(found)


def parse_chapters(text: str, *, key: str, path: str) -> Chapters:
    """Turn 38, or 115-120, or 38, 115-120 into the chapters it names."""
    spans: list[tuple[int, int]] = []
    for piece in text.split(","):
        found = _RANGE.match(piece.strip())
        if found is None:
            raise ConfigError(
                f"{piece.strip()!r} does not name a chapter or a run of "
                "chapters. Write 38, or 115-120",
                path=path,
                key=key,
            )
        low = int(found.group(1))
        high = int(found.group(2)) if found.group(2) else low
        if high < low:
            raise ConfigError(
                f"the run {piece.strip()!r} ends before it starts",
                path=path,
                key=key,
            )
        spans.append((low, high))
    return Chapters(spans=tuple(spans))


def load_cast(path: Path) -> Cast:
    """Read a cast file, or say which entry in it is wrong."""
    name = str(path)
    root = Table(load_toml(path), path=name)

    narrator_table = root.table("narrator")
    narrator = narrator_table.string("voice", "")
    narrator_exaggeration = narrator_table.number("exaggeration", None)
    narrator_table.done()

    entries: dict[str, list[Entry]] = {}
    aliases: dict[str, str] = {}

    for code, body in root.raw_table("cast").items():
        table = Table(body, path=name, prefix=f"cast.{code}")
        entries.setdefault(code, []).append(
            Entry(
                code=code,
                name=table.string("name", ""),
                voice=table.string("voice", ""),
                exaggeration=table.number("exaggeration", None),
            )
        )
        _add_aliases(aliases, table.strings("aliases", ()), code, path=name)
        table.done()

    for code, bodies in root.raw_table("cast_range").items():
        if not isinstance(bodies, list):
            raise ConfigError(
                "this must be a list of tables. Write [[cast_range.CODE]] with "
                "two brackets, one table for each group of chapters",
                path=name,
                key=f"cast_range.{code}",
            )
        for index, body in enumerate(bodies):
            key = f"cast_range.{code}[{index}]"
            table = Table(body, path=name, prefix=key)
            entries.setdefault(code, []).append(
                Entry(
                    code=code,
                    name=table.string("name", ""),
                    voice=table.string("voice", ""),
                    exaggeration=table.number("exaggeration", None),
                    chapters=parse_chapters(
                        table.string("chapters"), key=f"{key}.chapters", path=name
                    ),
                )
            )
            table.done()

    root.done()
    _refuse_overlap(entries, path=name)

    return Cast(
        narrator=narrator,
        narrator_exaggeration=narrator_exaggeration,
        entries={code: tuple(group) for code, group in entries.items()},
        aliases=aliases,
    )


def _add_aliases(
    aliases: dict[str, str], names: tuple[str, ...], code: str, *, path: str
) -> None:
    for alias in names:
        if alias in aliases and aliases[alias] != code:
            raise ConfigError(
                f"the alias {alias!r} belongs to {aliases[alias]!r} already",
                path=path,
                key=f"cast.{code}.aliases",
            )
        aliases[alias] = code


def _refuse_overlap(entries: dict[str, list[Entry]], *, path: str) -> None:
    """Refuse a code whose entries could both answer for one chapter."""
    for code, group in entries.items():
        if len(group) == 1:
            continue
        without_chapters = [entry for entry in group if entry.chapters is None]
        if without_chapters:
            raise ConfigError(
                f"the code {code!r} has an entry for every chapter and an entry "
                "for some chapters. Give each entry its own chapters",
                path=path,
                key=f"cast.{code}",
            )
        for first in range(len(group)):
            for second in range(first + 1, len(group)):
                one, two = group[first], group[second]
                if any(
                    two.chapters.contains(low) or two.chapters.contains(high)
                    for low, high in one.chapters.spans
                ):
                    raise ConfigError(
                        f"two entries for the code {code!r} cover the same "
                        f"chapter: {one.chapters} and {two.chapters}",
                        path=path,
                        key=f"cast_range.{code}",
                    )
