"""Turns the segments of a chapter into utterances and silences.

This stage decides who speaks. It does not decide how long anything waits,
because a pause depends on what comes after it, and that is the planner's
question.
"""

from __future__ import annotations

from ..config.cast import Cast
from ..config.grammar import Grammar
from ..errors import CastError, OpenBookError
from ..parse import Dialogue, EndMatter, Narration, ParsedChapter, SceneBreak
from ..parse.segments import Action, Speech
from .utterance import (
    ACTION,
    ANNOUNCEMENT,
    DIALOGUE,
    END_MATTER,
    NARRATION,
    NARRATOR,
    BlendedVoice,
    Item,
    MixedVoice,
    Silence,
    Utterance,
    Voice,
    VoiceRef,
)

# A scene break carries no words. It reaches the planner as a silence with this
# reason, so the planner can give it the length the configuration asks for.
SCENE_BREAK = "scene break"


def resolve_chapter(
    chapter: ParsedChapter, grammar: Grammar, cast: Cast
) -> tuple[Item, ...]:
    """Give every segment of a chapter a voice."""
    narrator, told = _narrator(cast, chapter.number)
    items: list[Item] = []

    if grammar.render.read_chapter_names:
        items.append(
            Utterance(
                text=_announcement(chapter, grammar),
                voice=narrator,
                kind=ANNOUNCEMENT,
                exaggeration=told,
            )
        )

    for segment in chapter.segments:
        items.extend(_resolve(segment, chapter, grammar, cast, narrator, told))

    return tuple(items)


def _resolve(
    segment,
    chapter: ParsedChapter,
    grammar: Grammar,
    cast: Cast,
    narrator: VoiceRef,
    told: float | None = None,
) -> list[Item]:
    if isinstance(segment, Narration):
        return [
            Utterance(
                text=segment.text, voice=narrator, kind=NARRATION, exaggeration=told
            )
        ]

    if isinstance(segment, SceneBreak):
        return [Silence(seconds=grammar.render.at_scene_break, reason=SCENE_BREAK)]

    if isinstance(segment, EndMatter):
        if not grammar.render.read_end_matter:
            return []
        return [
            Utterance(
                text=segment.text, voice=narrator, kind=END_MATTER, exaggeration=told
            )
        ]

    if isinstance(segment, Dialogue):
        return _resolve_dialogue(segment, chapter, grammar, cast, narrator, told)

    raise OpenBookError(f"the cast stage does not know the segment {segment!r}")


def _resolve_dialogue(
    segment: Dialogue,
    chapter: ParsedChapter,
    grammar: Grammar,
    cast: Cast,
    narrator: VoiceRef,
    told: float | None = None,
) -> list[Item]:
    voice = _dialogue_voice(segment, chapter.number, grammar, cast)
    speaker = "/".join(segment.speakers)
    # A line two characters share takes the number of the first of them, the
    # same way the primary mode takes the voice of the first of them.
    said = cast.resolve(segment.speakers[0], chapter.number).exaggeration
    items: list[Item] = []

    for piece in segment.pieces:
        if isinstance(piece, Speech):
            items.append(
                Utterance(
                    text=piece.text,
                    voice=voice,
                    kind=DIALOGUE,
                    speaker=speaker,
                    exaggeration=said,
                )
            )
        elif isinstance(piece, Action):
            items.extend(_resolve_action(piece, grammar, narrator, told))

    return items


def _resolve_action(
    action: Action, grammar: Grammar, narrator: VoiceRef, told: float | None = None
) -> list[Item]:
    """Give an action the treatment the configuration asks for.

    The words of an action are never spoken by the character. The author wrote
    *cough* to say how the line sounds, not to have somebody say "cough".
    """
    mode = grammar.render.action
    if mode == "drop":
        return []
    if mode == "narrator":
        return [
            Utterance(text=action.text, voice=narrator, kind=ACTION, exaggeration=told)
        ]
    return [Silence(seconds=grammar.render.at_action, reason=f"action: {action.text}")]


def _dialogue_voice(
    segment: Dialogue, chapter: int, grammar: Grammar, cast: Cast
) -> VoiceRef:
    entries = [cast.resolve(code, chapter) for code in segment.speakers]
    for entry, code in zip(entries, segment.speakers, strict=True):
        if not entry.is_cast:
            raise CastError(
                code,
                chapter,
                detail=(
                    "The cast file has this code but gives it no voice. "
                    "Fill in the voice, or the line becomes narration and "
                    "nobody hears that it went wrong"
                ),
            )

    if len(entries) == 1:
        return Voice(name=entries[0].voice)

    mode = grammar.dialogue.unison.mode
    if mode == "primary":
        return Voice(name=entries[0].voice)
    if mode == "voice_blend":
        share = 1.0 / len(entries)
        return BlendedVoice(
            parts=tuple(entry.voice for entry in entries),
            weights=tuple(share for _ in entries),
        )
    if mode in ("mix", "mix_matched"):
        return MixedVoice(
            parts=tuple(entry.voice for entry in entries),
            matched=mode == "mix_matched",
        )

    raise OpenBookError(
        f"the unison mode {mode!r} is not one this cast stage knows. Use "
        "voice_blend, mix, mix_matched, or primary"
    )


def _narrator(cast: Cast, chapter: int) -> tuple[VoiceRef, float | None]:
    """Who tells this chapter, and how they read it.

    A book does not have to keep one narrator. Soultale tells the prologue
    from outside and then gives the telling to the character whose story it
    is, so the chapter number chooses.
    """
    voice, told = cast.narrator_for(chapter)
    if not voice:
        raise CastError(
            NARRATOR,
            chapter,
            detail=(
                "The narrator has no voice. The narrator speaks most of this "
                "book, so choose this one first"
            ),
        )
    return Voice(name=voice), told


def _announcement(chapter: ParsedChapter, grammar: Grammar) -> str:
    """Say the name of a chapter the way the configuration asks.

    A volume that is a word takes the second form, so a prologue chapter opens
    with "Prologue." and not with "Chapter 0."
    """
    source = grammar.source
    template = (
        source.announcement
        if volume_is_numbered(chapter.volume)
        else source.announcement_named
    )
    text = template.source
    for name, value in (
        ("NUMBER", str(chapter.number)),
        ("VOLUME", chapter.volume),
        ("TITLE", chapter.title),
    ):
        text = text.replace(f"{{{name}}}", value)
    return text


def volume_is_numbered(volume: str) -> bool:
    """True when the name of a volume holds a number.

    "Volume 7" does. "Prologue" does not, and a chapter in it is announced by
    the name of the volume rather than by its number. The card asks this same
    question, so the picture and the voice cannot say different things.
    """
    return any(part.isdigit() for part in volume.split())


def chapter_label(number: int, last_in_volume: int) -> str:
    """What a card calls a chapter.

    The number is the one the book gives, and the second number is the last
    chapter of the volume this one belongs to, so a listener sees how far
    through that volume they are. The prologue runs 0 to 2 and volume 1 runs
    3 to 22, so the two do not share a count.

    The narrator says the same number, because the announcement uses it too.
    """
    return f"Chapter {number} of {last_in_volume}"


def last_chapters(chapters) -> dict[str, int]:
    """The last chapter number of each volume of the book.

    This looks at the volume a chapter was written in, and not the file it ends
    up in. The prologue is put into the first file, and still counts to 2.
    """
    last: dict[str, int] = {}
    for chapter in chapters:
        last[chapter.volume] = max(
            last.get(chapter.volume, chapter.number), chapter.number
        )
    return last
