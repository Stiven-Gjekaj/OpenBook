"""What to say instead, for a line that came out wrong.

This is the second half of the review loop. The page writes out the lines a
person marked while listening; this reads them back and puts the corrected
words in front of the engine.

A correction is keyed on the whole line, exactly as the page showed it, and
that text is what the engine was given: after the lexicon, and after a long
line was divided. The value is what to say in its place.

Nothing else has to change for a marked line to be made again. The cache keys
each piece of audio on the text, so different words are a different key, the
corrected line is made, and every other line in the volume is taken from the
cache as before.

Two entries are refused rather than ignored. An entry that matches nothing
looks like work that was done and was not, and an entry whose answer repeats
its own question makes the same audio under the same key, which looks exactly
like a correction that did not take.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config.reader import Table, load_toml
from .errors import ConfigError


def settle(text: str) -> str:
    """The form a line is matched in.

    A run of spaces and a line break both become one space. A person typing an
    entry by hand cannot be expected to reproduce the spacing of the book, and
    no two different lines become the same one by this.
    """
    return " ".join(text.split())


@dataclass(frozen=True)
class Corrections:
    """The lines to say differently, and the ones still waiting for an answer."""

    entries: dict[str, str]
    waiting: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "_settled", {settle(line): say for line, say in self.entries.items()}
        )

    def says(self, text: str) -> str | None:
        return self._settled.get(settle(text))

    def apply(self, text: str) -> str:
        return self.says(text) or text

    def __len__(self) -> int:
        return len(self.entries)


EMPTY = Corrections(entries={})


def load_corrections(path: Path) -> Corrections:
    """Read a corrections file. A file that is not there corrects nothing."""
    if not path.exists():
        return EMPTY
    root = Table(load_toml(path), path=str(path))
    found = root.string_map("corrections", optional=True)
    root.done()

    entries: dict[str, str] = {}
    waiting: list[str] = []
    for line, say in found.items():
        if not settle(line):
            raise ConfigError(
                "a correction with no line to match cannot match anything. "
                "The name of an entry is the line as the review page showed it",
                path=str(path),
                key="corrections",
            )
        if not settle(say):
            # The page writes each marked line with its answer left blank. That
            # is a line waiting for words, and not a mistake.
            waiting.append(line)
            continue
        if settle(say) == settle(line):
            raise ConfigError(
                f"the correction for {_short(line)} says the same words again, "
                "so it would make the same audio under the same key and look "
                "like a correction that did not take. Change the words, or "
                "take the entry out",
                path=str(path),
                key="corrections",
            )
        entries[line] = say

    return Corrections(entries=entries, waiting=tuple(waiting))


def used_by(texts, corrections: Corrections) -> tuple[str, ...]:
    """Which corrections have a line here to change, in the order given."""
    if not len(corrections):
        return ()
    settled = {settle(text) for text in texts}
    return tuple(line for line in corrections.entries if settle(line) in settled)


def _short(line: str) -> str:
    line = settle(line)
    return repr(line if len(line) <= 50 else f"{line[:50]}...")
