"""The errors that OpenBook shows to the person who runs it.

Every error here is one that a person can correct. Each message names the thing
to change and where to find it. An error that a person cannot correct is a bug,
and it stays an ordinary Python exception so that it keeps its traceback.
"""

from __future__ import annotations


class OpenBookError(Exception):
    """The parent of every error that a person can correct."""


class ConfigError(OpenBookError):
    """A configuration file is missing something, or says something wrong."""

    def __init__(
        self, message: str, *, path: str | None = None, key: str | None = None
    ):
        self.path = path
        self.key = key
        where = ""
        if path and key:
            where = f"{path}, in {key}: "
        elif path:
            where = f"{path}: "
        elif key:
            where = f"{key}: "
        super().__init__(where + message)


class SourceError(OpenBookError):
    """A source file is missing, or is not the kind of file it must be."""


class CastError(OpenBookError):
    """A chapter uses a speaker code that the cast file does not give a voice.

    The build stops here. A code without a voice becomes narration, and a
    finished audiobook with a wrong voice in it is worse than no audiobook.
    """

    def __init__(self, code: str, chapter: int, *, detail: str | None = None):
        self.code = code
        self.chapter = chapter
        message = (
            f"chapter {chapter} uses the speaker code {code!r}, "
            f"which the cast file does not have"
        )
        if detail:
            message = f"{message}. {detail}"
        super().__init__(message)
