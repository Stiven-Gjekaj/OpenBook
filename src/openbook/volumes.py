"""Reads the name of each volume out of the archive chapters.

The archive chapters are not read aloud. They hold a table of the volumes, and
that table is the only place the name of a volume is written:

    [Volume 1] The Ascension (3 - 22)

The names are wanted on the cards and in the description, so they are taken
from there rather than typed into the configuration a second time. Typing them
twice is how the two come to disagree.

The exporter breaks a long line wherever it pleases, so "The Apostle Of Love"
arrives across three lines. Everything is joined into one run of text before
anything is matched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Where the table starts inside an archive chapter.
HEADING = "|| Volumes ||"

_ENTRY = re.compile(
    r"\[(Prologue|Volume\s+\d+)\]\s*"  # the marker
    r"(.+?)\s*"  # the name
    r"(?:\(\s*(-?\d+)\s*-\s*([\dX]+)\s*\))?"  # the chapters, when given
    r"(?=\s*\[|\s*$)",
    re.S,
)


@dataclass(frozen=True)
class Volume:
    """One volume of the book, as the archive describes it."""

    name: str
    title: str
    first: int | None = None
    last: int | None = None

    @property
    def full(self) -> str:
        """The name and the title, as a card shows them."""
        return f"{self.name} {self.title}".strip()

    @property
    def written(self) -> str:
        """The name and the title, as a sentence writes them."""
        return f"{self.name}: {self.title}" if self.title else self.name


def read_volumes(chapters) -> dict[str, Volume]:
    """Find the table of volumes in whichever chapter holds it.

    A book with no such table gives nothing back, and everything that uses this
    carries on without the names.
    """
    found: dict[str, Volume] = {}
    for chapter in chapters:
        text = _plain(chapter.body)
        if HEADING not in text:
            continue
        for name, title, first, last in _ENTRY.findall(text.split(HEADING, 1)[-1]):
            volume = Volume(
                name=" ".join(name.split()),
                title=" ".join(title.split()),
                first=int(first) if first else None,
                # The last volume of a book still being written has no last
                # chapter, and says so with letters rather than a number.
                last=int(last) if last and last.isdigit() else None,
            )
            found.setdefault(volume.name, volume)
    return found


def _plain(body: str) -> str:
    import html

    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", body)).split())
