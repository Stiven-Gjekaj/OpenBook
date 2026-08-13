"""Several engines behind one, chosen by what a line is for.

A book does not want one engine everywhere. Narration is most of the words and
wants the fastest model that holds steady over hundreds of thousands of them.
Dialogue is where a character shouts, and only IndexTTS can shout. The host
speaks to the listener rather than inside the book and is a few lines either
side of the whole volume, so what it costs hardly matters.

Nothing else has to know. This holds one engine for each kind of line and
answers the same questions any single engine answers, so the planner, the
renderer and the cache carry on as they were.

The one thing it must get right is the cache. A key is made from the name and
the version of the engine that speaks the line, so this hands out the engine
that will really speak rather than answering for it. A volume already rendered
by Turbo therefore keeps every line of narration it has, and routing dialogue
elsewhere makes only the dialogue again.
"""

from __future__ import annotations

from ..cast.utterance import KINDS, NARRATION
from ..errors import OpenBookError
from .audio import Audio


class ByKind:
    """One engine for each kind of line, and one for the kinds left over."""

    def __init__(self, default, *, by_kind: dict[str, object] | None = None) -> None:
        chosen = dict(by_kind or {})
        for kind in chosen:
            if kind not in KINDS:
                known = ", ".join(sorted(KINDS))
                raise OpenBookError(
                    f"there is no kind of line called {kind!r}. The kinds are: {known}"
                )
        self._default = default
        self._by_kind = chosen

        # Every engine has to give back audio at one rate. Pieces are laid end
        # to end and over each other, and two rates meeting there is refused,
        # which would happen partway through a volume rather than at the start.
        rates = {engine.rate for engine in self.engines}
        if len(rates) > 1:
            named = ", ".join(
                f"{engine.name} at {engine.rate}" for engine in self.engines
            )
            raise OpenBookError(
                "engines that give back different rates cannot read one book, "
                f"because their pieces cannot be joined: {named}"
            )

    @property
    def engines(self) -> tuple:
        """Every engine this can hand out, the default first and once each."""
        found = [self._default]
        for engine in self._by_kind.values():
            if engine not in found:
                found.append(engine)
        return tuple(found)

    @property
    def name(self) -> str:
        """What to call this in a message to a person.

        Never in a cache key. A key names the engine that speaks the line, and
        that is what for_kind hands out.
        """
        parts = [
            f"{kind}={engine.name}" for kind, engine in sorted(self._by_kind.items())
        ]
        return (
            f"{self._default.name}[{', '.join(parts)}]" if parts else self._default.name
        )

    @property
    def version(self) -> str:
        return self._default.version

    @property
    def rate(self) -> int:
        return self._default.rate

    @property
    def max_characters(self) -> int | None:
        """The least any of them takes.

        The planner divides a line once, before anything is spoken, so the cut
        has to suit whichever engine ends up saying it.
        """
        limits = [
            engine.max_characters
            for engine in self.engines
            if engine.max_characters is not None
        ]
        return min(limits) if limits else None

    def for_kind(self, kind: str):
        """The engine that speaks this kind of line."""
        return self._by_kind.get(kind, self._default)

    def voice_key(self, voice, *, kind: str = NARRATION, exaggeration=None) -> str:
        return self.for_kind(kind).voice_key(
            voice, kind=kind, exaggeration=exaggeration
        )

    def speak(
        self, text: str, voice, *, kind: str = NARRATION, exaggeration=None
    ) -> Audio:
        return self.for_kind(kind).speak(
            text, voice, kind=kind, exaggeration=exaggeration
        )

    def close(self) -> None:
        """Let go of any engine that holds something, such as a subprocess."""
        for engine in self.engines:
            closing = getattr(engine, "close", None)
            if closing is not None:
                closing()
