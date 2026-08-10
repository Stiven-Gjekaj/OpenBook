"""Divides text into sentences.

A speech engine has a limit on how much text it takes at one time, and a long
paragraph must be divided before it reaches one. The division has to fall at
the end of a sentence. A cut in the middle of a sentence takes the fall of the
voice with it, and the two halves then sound like two separate thoughts.

A split on every full stop is wrong in ways that are easy to miss and hard to
hear the reason for. "Mr." is not a sentence. Neither is "St." or "No." or the
full stop inside 3.5. An ellipsis is three full stops and one pause. A closing
quotation mark comes after the full stop that ends the sentence, not before it.

This module is small on purpose and tested against real sentences from the
book. It is the most likely place in the project for a fault that nobody
notices until they hear it.
"""

from __future__ import annotations

import re

# A word that ends in a full stop and does not end a sentence. The list holds
# what this book uses. A title, a saint, a street, and the short forms that
# appear in dialogue.
ABBREVIATIONS = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "dr",
        "prof",
        "st",
        "mt",
        "sr",
        "jr",
        "vs",
        "etc",
        "inc",
        "ltd",
        "approx",
        "a.m",
        "p.m",
    }
)

# A word that ends in a full stop and does not end a sentence, but only when a
# number comes after it. "No." is a whole sentence far more often than it is
# the front of "No. 7", and putting it in the list above turns every refusal in
# the book into part of the sentence after it.
NUMBER_ABBREVIATIONS = frozenset({"no", "nos", "vol", "ch", "pt", "fig", "min", "max"})

# Words that carry a capital letter wherever they sit. After an ellipsis a
# capital usually means a new sentence, and these are the exception that proves
# nothing: "Johann... I'm sorry" is one sentence with a pause in it.
ALWAYS_CAPITAL = frozenset({"i", "i'm", "i'll", "i've", "i'd"})

# The end of a sentence: one or more of . ! ?, then any closing quotation marks
# or brackets, then space. The closing marks belong to the sentence that ends,
# because a voice that starts a sentence with a quotation mark pauses wrongly.
_BOUNDARY = re.compile(r'([.!?]+)([")\'\u201d\u2019\]]*)(\s+)')

# A single letter standing alone before the full stop, as in an initial. Two of
# them in a row are a name and not two sentences.
_INITIAL = re.compile(r"(?:\A|\s)[A-Za-z]\Z")

# A number with a full stop inside it.
_DECIMAL = re.compile(r"\d\Z")

# Where a reader takes a breath inside a sentence. The mark is captured so that
# it can stay with the words before it.
_CLAUSE = re.compile(r"([;:,])\s+")


def split_sentences(text: str) -> tuple[str, ...]:
    """Divide text into sentences, keeping every character.

    Joining the result with a single space gives back the text, with runs of
    space made into one space.
    """
    text = " ".join(text.split())
    if not text:
        return ()

    sentences: list[str] = []
    start = 0

    for found in _BOUNDARY.finditer(text):
        end = found.end(2)
        if _is_end_of_sentence(text, start, found):
            sentences.append(text[start:end].strip())
            start = found.end()

    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return tuple(sentences)


def split_clauses(text: str) -> tuple[str, ...]:
    """Divide one sentence at the places a reader would take a breath.

    This is the second choice, for a sentence that is longer on its own than an
    engine accepts. 34 sentences in Soultale are, and the longest holds 1059
    characters and 17 commas. Handing one of those to an engine whole means it
    cuts the sentence where its own limit falls, which is worse than cutting it
    at a comma, because nothing chooses where that cut lands.

    The mark stays with the piece before it, the way it is written.
    """
    text = " ".join(text.split())
    if not text:
        return ()
    pieces = [piece.strip() for piece in _CLAUSE.split(text)]
    joined: list[str] = []
    for index in range(0, len(pieces), 2):
        body = pieces[index]
        mark = pieces[index + 1] if index + 1 < len(pieces) else ""
        if body:
            joined.append(f"{body}{mark}")
    return tuple(joined) or (text,)


def _is_end_of_sentence(text: str, start: int, found: re.Match[str]) -> bool:
    stops = found.group(1)
    before = text[start : found.start(1)]
    after = text[found.end() :]

    # An ellipsis is a pause inside a sentence far more often than the end of
    # one. When it does end a sentence, the next word carries a capital. The
    # exception is a word that carries one wherever it sits, which in practice
    # means "I" and what it joins to.
    if stops in {"...", "…"}:
        word = after.split(" ", 1)[0] if after else ""
        return bool(word[:1].isupper()) and word.lower().strip(".,!?") not in (
            ALWAYS_CAPITAL
        )

    if len(stops) > 1:
        return True

    # A number with a full stop in it, as in 3.5.
    if _DECIMAL.search(before) and after[:1].isdigit():
        return False

    last = before.rsplit(" ", 1)[-1].lower().rstrip(".") if before else ""
    if last in ABBREVIATIONS:
        return False

    # A short form that only holds when a number follows it.
    if last in NUMBER_ABBREVIATIONS and after[:1].isdigit():
        return False

    # An initial, as in J. R. Hendricks. The piece after it starts with a
    # capital, which otherwise looks exactly like a new sentence.
    return not _INITIAL.search(before)
