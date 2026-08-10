"""Gives each segment a voice."""

from .resolve import resolve_chapter
from .utterance import BlendedVoice, Item, Silence, Utterance, Voice, VoiceRef

__all__ = [
    "BlendedVoice",
    "Item",
    "Silence",
    "Utterance",
    "Voice",
    "VoiceRef",
    "resolve_chapter",
]
