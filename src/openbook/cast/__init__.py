"""Gives each segment a voice."""

from .resolve import chapter_label, last_chapters, resolve_chapter
from .utterance import (
    BlendedVoice,
    Item,
    MixedVoice,
    Silence,
    Utterance,
    Voice,
    VoiceRef,
)

__all__ = [
    "BlendedVoice",
    "Item",
    "MixedVoice",
    "Silence",
    "Utterance",
    "Voice",
    "VoiceRef",
    "chapter_label",
    "last_chapters",
    "resolve_chapter",
]
