"""Divides the HTML of a chapter into the lines that the parser reads.

A line here is not a line of the file. It is the text between two paragraph
ends, or between two line breaks inside a paragraph. The difference matters:
the exporter puts several turns of one conversation inside one paragraph and
divides them with a line break, and a reader that treats a paragraph as one
unit gets most of the dialogue of this book wrong.

Each line arrives as a list of runs. A run is a piece of text together with the
elements that surround it, so that a caller can ask whether the text at the
front of a line was inside a bold element without looking at the HTML again.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

# Elements that end a block of text on their own. A missing closing tag for one
# of these is common in exported HTML, so the reader closes a block when it
# sees the next one start.
_BLOCK_ELEMENTS = frozenset(
    {"p", "div", "section", "li", "blockquote", "h1", "h2", "h3"}
)

_SPACES = re.compile(r"\s+")


@dataclass(frozen=True)
class Run:
    """A piece of text, and the elements that hold it."""

    text: str
    elements: frozenset[str]

    def inside(self, elements: frozenset[str]) -> bool:
        return bool(self.elements & elements)


@dataclass(frozen=True)
class Line:
    """One line of a chapter, as a list of runs."""

    runs: tuple[Run, ...]

    @property
    def text(self) -> str:
        """The words of the line, with the elements taken away."""
        return _SPACES.sub(" ", "".join(run.text for run in self.runs)).strip()

    def first_run(self) -> Run | None:
        """The first run that holds anything but space."""
        for run in self.runs:
            if run.text.strip():
                return run
        return None

    def wholly_inside(self, elements: frozenset[str]) -> bool:
        """True when every run that holds text is inside one of the elements."""
        runs = [run for run in self.runs if run.text.strip()]
        return bool(runs) and all(run.inside(elements) for run in runs)


class _Reader(HTMLParser):
    def __init__(self) -> None:
        # convert_charrefs turns &amp; into & before the text arrives. The
        # unison separator is written with an entity in the source, and the
        # rule that divides two speakers finds nothing without this.
        super().__init__(convert_charrefs=True)
        self.lines: list[Line] = []
        self._runs: list[Run] = []
        self._open: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "br":
            self._end_line()
            return
        if tag in _BLOCK_ELEMENTS:
            self._end_line()
        self._open.append(tag)

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag == "br":
            self._end_line()

    def handle_endtag(self, tag: str) -> None:
        if tag == "br":
            return
        if tag in _BLOCK_ELEMENTS:
            self._end_line()
        # An element that closes without opening, and an element that closes
        # out of order, both appear in exported HTML. Remove the nearest match
        # and leave the rest of the stack alone.
        for index in range(len(self._open) - 1, -1, -1):
            if self._open[index] == tag:
                del self._open[index]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self._runs.append(Run(text=data, elements=frozenset(self._open)))

    def _end_line(self) -> None:
        if any(run.text.strip() for run in self._runs):
            self.lines.append(Line(runs=tuple(self._runs)))
        self._runs = []

    def close(self) -> None:
        super().close()
        self._end_line()


def read_lines(body: str) -> tuple[Line, ...]:
    """Divide the HTML of a chapter into lines."""
    reader = _Reader()
    reader.feed(body)
    reader.close()
    return tuple(reader.lines)
