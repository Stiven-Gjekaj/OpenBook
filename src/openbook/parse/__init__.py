"""Turns the body of a chapter into typed segments."""

from .chapter import ParsedChapter, parse_chapter
from .segments import (
    Action,
    Dialogue,
    EndMatter,
    Narration,
    Note,
    SceneBreak,
    Segment,
    Speech,
)

__all__ = [
    "Action",
    "Dialogue",
    "EndMatter",
    "Narration",
    "Note",
    "ParsedChapter",
    "SceneBreak",
    "Segment",
    "Speech",
    "parse_chapter",
]
