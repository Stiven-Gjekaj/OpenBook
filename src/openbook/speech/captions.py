"""Writes the captions for a finished render.

Nothing here listens to the audio. It does not have to. Every piece of speech
was made on its own from text this project already holds, so both the words and
the moment they are said are known exactly.

That gives captions which speech recognition cannot match. A recogniser hears
"Vazroth" and writes something else, every time, for forty seven hours, in the
same way the phonemizer says it wrongly. These captions spell it correctly
because they were never a guess.

They also carry the name of whoever is speaking, which a recogniser cannot know
at all, and mark the sounds that are not speech.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..cast.utterance import ACTION, ANNOUNCEMENT, DIALOGUE, NARRATOR, Utterance

# What a reader can take in. Two lines of about forty characters is the usual
# limit for a caption, and a cue that stays up longer than this feels stuck.
MOST_CHARACTERS = 84
LINE_CHARACTERS = 42
MOST_SECONDS = 7.0
LEAST_SECONDS = 1.0


@dataclass(frozen=True)
class Cue:
    """One caption, and when it is on the screen."""

    start: float
    end: float
    text: str


def stamp(seconds: float) -> str:
    """A time in the form an SRT file uses."""
    seconds = max(0.0, seconds)
    whole = int(seconds)
    hours, rest = divmod(whole, 3600)
    minutes, second = divmod(rest, 60)
    thousandths = round((seconds - whole) * 1000)
    if thousandths == 1000:
        thousandths, second = 0, second + 1
    return f"{hours:02d}:{minutes:02d}:{second:02d},{thousandths:03d}"


def break_text(text: str, limit: int = MOST_CHARACTERS) -> list[str]:
    """Divide one utterance into pieces a reader can take in."""
    words = text.split()
    if not words:
        return []
    pieces: list[str] = []
    line = words[0]
    for word in words[1:]:
        wider = f"{line} {word}"
        if len(wider) <= limit:
            line = wider
        else:
            pieces.append(line)
            line = word
    pieces.append(line)
    return pieces


def lay_out(text: str, width: int = LINE_CHARACTERS) -> str:
    """Put a caption on two lines of about the same length.

    One long line is left to the player to break, and it breaks it wherever the
    width of the screen falls. Two lines chosen here are the same on every
    screen, and the break lands between words rather than inside a phrase.
    """
    if len(text) <= width:
        return text
    words = text.split()
    best, difference = len(words) // 2, None
    for cut in range(1, len(words)):
        first = len(" ".join(words[:cut]))
        second = len(" ".join(words[cut:]))
        apart = abs(first - second)
        if difference is None or apart < difference:
            best, difference = cut, apart
    return " ".join(words[:best]) + "\n" + " ".join(words[best:])


def label_for(utterance: Utterance, names: dict[str, str] | None) -> str:
    """What to put in front of a line, so a reader knows who says it.

    The name of the character and not the code. A reader has never seen the
    cast file and cannot know that BLK is Blook.
    """
    if utterance.kind != DIALOGUE or utterance.speaker == NARRATOR:
        return ""
    parts = [
        (names or {}).get(code, code) or code for code in utterance.speaker.split("/")
    ]
    return f"[{' and '.join(parts)}] "


def cues_from_timeline(
    timeline: list[tuple[Utterance, float, float]],
    *,
    names: dict[str, str] | None = None,
    limit: int = MOST_CHARACTERS,
    announcements: bool = False,
) -> list[Cue]:
    """Turn the places of the utterances into captions.

    An utterance longer than one caption is divided, and the time it takes is
    shared out by how much text each piece holds. The pace of a voice is even
    enough over one sentence for that to hold.

    The name of the chapter is left out. The card on the screen already carries
    it, and a caption of the same words over the top of it says one thing
    twice. Ask for announcements when the captions go with sound that has no
    picture behind it.
    """
    cues: list[Cue] = []
    for utterance, start, end in timeline:
        if utterance.kind == ANNOUNCEMENT and not announcements:
            continue
        if utterance.kind == ACTION:
            # An action is a sound and not speech, and a caption says so.
            cues.append(Cue(start=start, end=end, text=f"[{utterance.text}]"))
            continue

        label = label_for(utterance, names)
        pieces = break_text(utterance.text, limit)
        if not pieces:
            continue

        total = sum(len(piece) for piece in pieces)
        at = start
        for index, piece in enumerate(pieces):
            share = (end - start) * (len(piece) / total) if total else 0.0
            stop = end if index == len(pieces) - 1 else at + share
            text = f"{label}{piece}" if index == 0 else piece
            cues.append(Cue(start=at, end=stop, text=lay_out(text)))
            at = stop
    return cues


def to_srt(cues: list[Cue]) -> str:
    """Write the captions as SRT, which YouTube reads."""
    blocks: list[str] = []
    for number, cue in enumerate(cues, 1):
        # A cue that ends before it starts, or lasts no time, is refused by
        # some players rather than ignored.
        end = max(cue.end, cue.start + 0.001)
        blocks.append(f"{number}\n{stamp(cue.start)} --> {stamp(end)}\n{cue.text}\n")
    return "\n".join(blocks)


def names_from_cast(cast) -> dict[str, str]:
    """The name of each character, for the label in front of their lines."""
    return {
        code: group[0].name
        for code, group in cast.entries.items()
        if group and group[0].name
    }
