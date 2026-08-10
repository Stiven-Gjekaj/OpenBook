"""What comes out of the cast stage.

An utterance is a piece of text and the voice that speaks it. A silence is a
length of time with a reason. A render is a list of these two things and
nothing else, which is why the stages after this one do not need to know what
a chapter is.

Every field is part of what makes the audio, so the cache can key on the whole
utterance. Nothing here carries a position in the book, because two lines with
the same words in the same voice must reach the same audio and share it.
"""

from __future__ import annotations

from dataclasses import dataclass

NARRATOR = "narrator"

# What an utterance is for. The planner uses this to decide where a pause
# falls, so a value that the planner does not know is a mistake it can find.
NARRATION = "narration"
DIALOGUE = "dialogue"
ACTION = "action"
ANNOUNCEMENT = "announcement"
END_MATTER = "end matter"

KINDS = (NARRATION, DIALOGUE, ACTION, ANNOUNCEMENT, END_MATTER)


@dataclass(frozen=True)
class Voice:
    """One voice, named as the engine names it."""

    name: str

    def key(self) -> str:
        return self.name


@dataclass(frozen=True)
class BlendedVoice:
    """One voice made from several, for a line that two characters say.

    The engine averages the style of each part, with the weights given. The
    result is one piece of audio, so the two characters cannot drift apart.
    """

    parts: tuple[str, ...]
    weights: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.parts) != len(self.weights):
            raise ValueError("a blended voice needs one weight for each part")
        if not self.parts:
            raise ValueError("a blended voice needs at least one part")

    def key(self) -> str:
        return "+".join(
            f"{part}:{weight:.3f}"
            for part, weight in zip(self.parts, self.weights, strict=True)
        )


@dataclass(frozen=True)
class MixedVoice:
    """Several voices, each saying the whole line, laid over each other.

    Unlike a blended voice this keeps the characters apart, because each one is
    a separate piece of audio in its own voice. What it does not keep on its
    own is their timing: two readings of the same words are two different
    lengths, so the longer one is still going when the shorter has stopped.

    matched brings the readings to one length first, so the two speak together
    from the first word to the last. That is a change to how fast a character
    talks, which is why it is asked for and not assumed.
    """

    parts: tuple[str, ...]
    matched: bool = False

    def __post_init__(self) -> None:
        if len(self.parts) < 2:
            raise ValueError("a mixed voice needs at least two parts")

    def key(self) -> str:
        # A different separator, because the two make different audio out of
        # the same voices and must not share a piece of it in the cache.
        return ("=" if self.matched else "&").join(self.parts)


VoiceRef = Voice | BlendedVoice | MixedVoice


@dataclass(frozen=True)
class Utterance:
    """Words, and the voice that says them."""

    text: str
    voice: VoiceRef
    kind: str
    speaker: str = NARRATOR

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"{self.kind!r} is not a kind of utterance")


@dataclass(frozen=True)
class Silence:
    """A length of time with nothing in it, and why it is there."""

    seconds: float
    reason: str


Item = Utterance | Silence
