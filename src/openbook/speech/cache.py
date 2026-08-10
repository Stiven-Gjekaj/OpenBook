"""Keeps the audio that has already been made.

This is the centre of the project rather than a saving of time. Each piece of
audio is kept under a key made from the text, the voice, the engine, and the
version of the engine, and from nothing else. Everything useful follows:

  A correction to one line makes one line again, and not a chapter.
  A change of voice for one character touches nobody else.
  A character can move to another engine and the rest keeps its audio.

Nothing about where a line sits in the book is part of the key. Two lines with
the same words in the same voice are the same sound, and they share it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..cast.utterance import Utterance, VoiceRef
from .audio import Audio


def key_for(
    text: str, voice: VoiceRef | str, engine_name: str, engine_version: str
) -> str:
    """The name under which one piece of audio is kept.

    Every part is written with its length in front of it, so that no two
    different sets of parts can join into the same line of text. Without that,
    a voice called "a" with text "bc" and a voice called "ab" with text "c"
    would share one piece of audio.

    The voice arrives either as itself or as the name an engine gives it. See
    key_of for why an engine gets a say in that.
    """
    named = voice if isinstance(voice, str) else voice.key()
    parts = (engine_name, engine_version, named, text)
    joined = "\x1f".join(f"{len(part)}:{part}" for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def key_of(utterance: Utterance, engine) -> str:
    """The key for one utterance, spoken by one engine.

    The engine names the voice rather than the voice naming itself, because for
    an engine that reads a voice out of a recording the name is a file path and
    the sound is the file. Two different recordings under one path are two
    different voices, and a cache that could not tell them apart would hand
    back the old voice for ever without saying anything.
    """
    return key_for(
        utterance.text,
        engine.voice_key(
            utterance.voice, kind=utterance.kind, exaggeration=utterance.exaggeration
        ),
        engine.name,
        engine.version,
    )


@dataclass
class Cache:
    """A directory of audio, named by key."""

    directory: Path

    def __post_init__(self) -> None:
        self.directory = Path(self.directory)

    def path_for(self, key: str) -> Path:
        # Two letters of the key make the name of a directory, so that no one
        # directory holds every file. A book of this size makes tens of
        # thousands, and some file systems slow down badly past that.
        return self.directory / key[:2] / f"{key}.wav"

    def holds(self, key: str) -> bool:
        return self.path_for(key).exists()

    def get(self, key: str) -> Audio | None:
        path = self.path_for(key)
        return Audio.read(path) if path.exists() else None

    def put(self, key: str, audio: Audio) -> None:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        audio.write(path)

    def keys(self) -> set[str]:
        return {path.stem for path in self.directory.glob("*/*.wav")}

    def size(self) -> int:
        return sum(path.stat().st_size for path in self.directory.glob("*/*.wav"))

    def prune(self, live: set[str]) -> int:
        """Remove the audio that nothing points at, and say how much went."""
        removed = 0
        for path in self.directory.glob("*/*.wav"):
            if path.stem not in live:
                path.unlink()
                removed += 1
        for child in self.directory.glob("*"):
            if child.is_dir() and not any(child.iterdir()):
                child.rmdir()
        return removed
