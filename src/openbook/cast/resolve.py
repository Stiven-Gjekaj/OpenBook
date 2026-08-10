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
    narrator = _narrator(cast, chapter.number)
    items: list[Item] = []

    if grammar.render.read_chapter_names:
        items.append(
            Utterance(
                text=_announcement(chapter, grammar),
                voice=narrator,
                kind=ANNOUNCEMENT,
            )
        )

    for segment in chapter.segments:
        items.extend(_resolve(segment, chapter, grammar, cast, narrator))

    return tuple(items)


def _resolve(
    segment, chapter: ParsedChapter, grammar: Grammar, cast: Cast, narrator: VoiceRef
) -> list[Item]:
    if isinstance(segment, Narration):
        return [Utterance(text=segment.text, voice=narrator, kind=NARRATION)]

    if isinstance(segment, SceneBreak):
        return [Silence(seconds=grammar.render.at_scene_break, reason=SCENE_BREAK)]

    if isinstance(segment, EndMatter):
        if not grammar.render.read_end_matter:
            return []
        return [Utterance(text=segment.text, voice=narrator, kind=END_MATTER)]

    if isinstance(segment, Dialogue):
        return _resolve_dialogue(segment, chapter, grammar, cast, narrator)

    raise OpenBookError(f"the cast stage does not know the segment {segment!r}")


def _resolve_dialogue(
    segment: Dialogue,
    chapter: ParsedChapter,
    grammar: Grammar,
    cast: Cast,
    narrator: VoiceRef,
) -> list[Item]:
    voice = _dialogue_voice(segment, chapter.number, grammar, cast)
    speaker = "/".join(segment.speakers)
    items: list[Item] = []

    for piece in segment.pieces:
        if isinstance(piece, Speech):
            items.append(
                Utterance(text=piece.text, voice=voice, kind=DIALOGUE, speaker=speaker)
            )
        elif isinstance(piece, Action):
            items.extend(_resolve_action(piece, grammar, narrator))

    return items


def _resolve_action(action: Action, grammar: Grammar, narrator: VoiceRef) -> list[Item]:
    """Give an action the treatment the configuration asks for.

    The words of an action are never spoken by the character. The author wrote
    *cough* to say how the line sounds, not to have somebody say "cough".
    """
    mode = grammar.render.action
    if mode == "drop":
        return []
    if mode == "narrator":
        return [Utterance(text=action.text, voice=narrator, kind=ACTION)]
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

    raise OpenBookError(
        f"the unison mode {mode!r} is not built yet. Use voice_blend, which "
        "makes one piece of audio and cannot drift, or primary, which uses the "
        "voice of the first character"
    )


def _narrator(cast: Cast, chapter: int) -> VoiceRef:
    if not cast.narrator:
        raise CastError(
            NARRATOR,
            chapter,
            detail=(
                "The narrator has no voice. The narrator speaks most of this "
                "book, so choose this one first"
            ),
        )
    return Voice(name=cast.narrator)


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


def chapter_label(number: int, volume: str) -> str:
    """What to call a chapter, in the words the narrator uses for it."""
    return f"Chapter {number}" if volume_is_numbered(volume) else volume
