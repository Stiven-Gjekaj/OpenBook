"""How a word is said, and which words nobody has told the engine about.

This is the largest quality problem in the whole project. A fixed voice says an
invented name the same wrong way every time it appears, for forty seven hours,
and no casting decision repairs that. Nilah, Vazroth, Astra: each is either
right everywhere or wrong everywhere.

The lexicon changes the text at plan time and never touches the manuscript. A
name is replaced by a spelling that the engine says correctly, or by phonemes
inside the marks that the engine reads as phonemes.

The finder is the other half. It compares every word the book speaks against
the words the phonemizer knows, and gives back what is left, most frequent
first. That turns a job with no end into a list with one.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .config.reader import Table, load_toml
from .errors import ConfigError

# A word of the text. An apostrophe stays inside a word, so "don't" is one word
# and not two, and a hyphen divides, so "Thread-Weaver" gives both halves and
# each one can have its own entry.
WORD = re.compile(r"[A-Za-z][A-Za-z']*")


@dataclass(frozen=True)
class Lexicon:
    """What each word becomes before it reaches a voice."""

    entries: dict[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "_lowered", {word.lower(): say for word, say in self.entries.items()}
        )

    def says(self, word: str) -> str | None:
        return self._lowered.get(word.lower())

    def has(self, word: str) -> bool:
        """Whether the file holds this word at all, answered or not.

        This is not the same question as says. A word written down with its
        sound left blank is still waiting for an answer, so the report goes on
        naming it, and it is already in the file, so a merge must not put it
        there twice.
        """
        return word.lower() in self._lowered

    def apply(self, text: str) -> str:
        """Put the entries into a piece of text.

        Whole words only. A rule for "Ivy" must not reach inside "Ivory".
        """
        if not self.entries:
            return text
        return WORD.sub(lambda m: self.says(m.group(0)) or m.group(0), text)

    def __len__(self) -> int:
        return len(self.entries)


EMPTY = Lexicon(entries={})


def load_lexicon(path: Path) -> Lexicon:
    """Read a lexicon file. A file that is not there is an empty lexicon."""
    if not path.exists():
        return EMPTY
    root = Table(load_toml(path), path=str(path))
    entries = root.string_map("words", optional=True)
    root.done()
    for word in entries:
        if not WORD.fullmatch(word):
            raise ConfigError(
                f"{word!r} is not one word. An entry names one word, with "
                "letters and apostrophes only",
                path=str(path),
                key="words",
            )
    return Lexicon(entries=entries)


@dataclass(frozen=True)
class Unknown:
    """A word that the phonemizer does not have."""

    word: str
    count: int
    chapter: int
    line: str


def words_of(text: str) -> list[str]:
    return WORD.findall(text)


def find_unknown(
    spoken: list[tuple[int, str]], lexicon: Lexicon, *, known: set[str] | None = None
) -> list[Unknown]:
    """Find the words that need an entry, most frequent first.

    spoken is every piece of text the book says, with the chapter it came from.
    A word that the lexicon already has does not come back, because it is
    answered.
    """
    known = known if known is not None else known_words()
    counts: Counter[str] = Counter()
    first: dict[str, tuple[int, str]] = {}

    for chapter, text in spoken:
        for word in words_of(text):
            lowered = word.lower()
            if lexicon.says(word) or is_known(lowered, known):
                continue
            counts[lowered] += 1
            first.setdefault(lowered, (chapter, text))

    return [
        Unknown(word=word, count=count, chapter=first[word][0], line=first[word][1])
        for word, count in counts.most_common()
    ]


def is_known(word: str, known: set[str]) -> bool:
    """True when a word, or the word it is built from, is in the list.

    The word list of a system holds base forms. "walk" is in it and "walked" is
    not, so a check on the word alone calls every past tense in the book an
    invented name and buries the real ones. Each ending is taken off in turn
    and the base looked for.
    """
    if word in known or word in IRREGULAR:
        return True

    # A word with an apostrophe is known when the part in front of it is.
    # "you're" gives "you", and "don't" gives "don". The second is not a word,
    # so the part after the apostrophe is checked as well. "Vazroth's" gives
    # "vazroth", which is not known, and that is right: the name still needs an
    # entry and the possessive is the same name.
    if "'" in word:
        head, _, tail = word.partition("'")
        if head in known and (not tail or tail in CONTRACTION_TAILS):
            return True
        if head in IRREGULAR:
            return True

    for ending, bases in _ENDINGS:
        if not word.endswith(ending):
            continue
        stem = word[: -len(ending)]
        for base in bases(stem):
            if base and base in known:
                return True
    return False


# An ending, and the ways a word could look before it was added. "running"
# doubles its last letter, "tried" turns a y into an i, and "moved" loses an e.
_ENDINGS: tuple[tuple[str, object], ...] = (
    ("s", lambda s: (s, s + "e")),
    ("es", lambda s: (s, s + "e")),
    ("ed", lambda s: (s, s + "e", s[:-1], s[:-1] + "y")),
    ("d", lambda s: (s, s + "e")),
    ("ing", lambda s: (s, s + "e", s[:-1])),
    ("ly", lambda s: (s, s + "e", s[:-1] + "y")),
    ("er", lambda s: (s, s + "e", s[:-1])),
    ("est", lambda s: (s, s + "e", s[:-1])),
    ("ness", lambda s: (s, s[:-1] + "y")),
    ("less", lambda s: (s,)),
    ("ish", lambda s: (s, s + "e")),
    ("ies", lambda s: (s + "y",)),
    ("ied", lambda s: (s + "y",)),
    ("ier", lambda s: (s + "y",)),
    ("iest", lambda s: (s + "y",)),
)

# What can follow an apostrophe in English. Anything else after one is part of
# a name and not a contraction.
CONTRACTION_TAILS = frozenset(
    {"s", "t", "d", "m", "re", "ve", "ll", "n", "em", "cause", "til"}
)

# Words that a word list of base forms does not hold, and that a voice says
# correctly anyway. Without these the top of the report is filled with ordinary
# English and the invented names sit below it.
IRREGULAR = frozenset(
    [
        "am",
        "are",
        "is",
        "was",
        "were",
        "been",
        "being",
        "had",
        "has",
        "have",
        "does",
        "did",
        "done",
        "goes",
        "gone",
        "went",
        "began",
        "begun",
        "became",
        "become",
        "came",
        "come",
        "saw",
        "seen",
        "said",
        "made",
        "known",
        "knew",
        "grown",
        "grew",
        "thrown",
        "threw",
        "drawn",
        "drew",
        "fell",
        "fallen",
        "felt",
        "kept",
        "left",
        "lost",
        "meant",
        "met",
        "paid",
        "put",
        "read",
        "run",
        "ran",
        "sat",
        "set",
        "shot",
        "shown",
        "showed",
        "slept",
        "sold",
        "sent",
        "spent",
        "stood",
        "stuck",
        "taken",
        "took",
        "taught",
        "told",
        "thought",
        "understood",
        "woke",
        "worn",
        "wore",
        "won",
        "wrote",
        "written",
        "spoke",
        "spoken",
        "broke",
        "broken",
        "chose",
        "chosen",
        "drove",
        "driven",
        "ate",
        "eaten",
        "forgot",
        "forgotten",
        "froze",
        "frozen",
        "gave",
        "given",
        "held",
        "heard",
        "hid",
        "hidden",
        "let",
        "lay",
        "lain",
        "led",
        "lit",
        "rode",
        "ridden",
        "rose",
        "risen",
        "sang",
        "sung",
        "sank",
        "sunk",
        "swore",
        "sworn",
        "swam",
        "swum",
        "tore",
        "torn",
        "wound",
        "bent",
        "built",
        "burnt",
        "bought",
        "caught",
        "children",
        "feet",
        "teeth",
        "men",
        "women",
        "people",
        "mice",
        "geese",
        "lives",
        "wives",
        "knives",
        "i",
        "i'm",
        "i'd",
        "i'll",
        "i've",
        "you're",
        "you'd",
        "you'll",
        "you've",
        "he'd",
        "he'll",
        "he's",
        "she'd",
        "she'll",
        "she's",
        "it's",
        "we're",
        "we'd",
        "we'll",
        "we've",
        "they're",
        "they'd",
        "they'll",
        "they've",
        "don't",
        "doesn't",
        "didn't",
        "isn't",
        "aren't",
        "wasn't",
        "weren't",
        "hasn't",
        "haven't",
        "hadn't",
        "can't",
        "couldn't",
        "won't",
        "wouldn't",
        "shouldn't",
        "shan't",
        "mustn't",
        "needn't",
        "that's",
        "there's",
        "here's",
        "what's",
        "who's",
        "let's",
        "who'd",
        "who'll",
        "ok",
        "okay",
        "yeah",
        "hey",
        "huh",
        "hmm",
        "oh",
        "ah",
        "eh",
        "um",
        "uh",
        "mm",
    ]
)


def known_words() -> set[str]:
    """The words that the phonemizer can already say.

    espeak-ng answers this when it is installed. It is the same program that
    Kokoro falls back to, so its answer is the one that matters. Without it
    every word looks unknown, which is useless, so this says so instead.
    """
    return _espeak_words()


def _espeak_words() -> set[str]:
    """Ask espeak-ng which words it holds in its dictionary."""
    try:
        result = subprocess.run(
            ["espeak-ng", "--version"], capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        return set()
    if result.returncode != 0:
        return set()
    return _dictionary_words()


def _dictionary_words() -> set[str]:
    """Read the word list of the system, which every unix has.

    This is not the dictionary of espeak-ng, which is compiled and not text. It
    is a list of ordinary English words, and a word that is in it is one that a
    phonemizer says correctly by rule. What is left over is what this project
    cares about: the invented names.
    """
    for path in (Path("/usr/share/dict/words"), Path("/usr/dict/words")):
        if path.exists():
            return {
                line.strip().lower() for line in path.read_text(errors="ignore").split()
            }
    return set()


def have_dictionary() -> bool:
    return bool(known_words())
