"""Runs every stage, from the EPUB files to a finished volume.

This is the only place that knows the order of the stages. Each stage takes
what the one before it made, so nothing here does work of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .cast import resolve_chapter
from .cast.utterance import Item
from .config.cast import Cast, load_cast
from .config.grammar import Grammar, load_grammar
from .errors import OpenBookError
from .lexicon import Lexicon, load_lexicon
from .parse import Note, ParsedChapter, parse_chapter
from .plan.planner import Plan, plan_chapter, plan_volume
from .source.epub import Chapter, read_book


@dataclass
class Project:
    """A directory that holds the configuration and the book."""

    directory: Path
    grammar: Grammar
    cast: Cast
    lexicon: Lexicon

    @classmethod
    def open(cls, directory: Path) -> Project:
        directory = Path(directory)
        return cls(
            directory=directory,
            grammar=load_grammar(directory / "grammar.toml"),
            cast=load_cast(directory / "cast.toml"),
            lexicon=load_lexicon(directory / "lexicon.toml"),
        )

    @property
    def files(self) -> list[Path]:
        return [self.directory / name for name in self.grammar.source.files]

    @property
    def cache_directory(self) -> Path:
        return self.directory / "cache"

    @property
    def output_directory(self) -> Path:
        return self.directory / "out"

    def chapters(self) -> tuple[Chapter, ...]:
        missing = [path for path in self.files if not path.exists()]
        if missing:
            names = ", ".join(str(path) for path in missing)
            raise OpenBookError(f"these book files are missing: {names}")
        return read_book(self.files, self.grammar.source)

    def parsed(self) -> tuple[ParsedChapter, ...]:
        return tuple(parse_chapter(c, self.grammar) for c in self.chapters())

    def volume_of(self, chapter: ParsedChapter) -> str:
        return self.grammar.output.group_of(chapter.volume)


@dataclass
class VolumePlan:
    """A volume, ready to be made into sound."""

    name: str
    chapters: tuple[ParsedChapter, ...]
    plan: Plan
    chapter_plans: tuple[Plan, ...]
    notes: tuple[Note, ...] = field(default_factory=tuple)


def build_volume(
    project: Project, name: str, *, max_characters: int | None = None
) -> VolumePlan:
    """Work every stage for one volume, up to but not including the sound."""
    chapters = [c for c in project.parsed() if project.volume_of(c) == name]
    if not chapters:
        known = sorted({project.volume_of(c) for c in project.parsed()})
        raise OpenBookError(
            f"no volume is named {name!r}. The book has {', '.join(known)}"
        )

    items: list[tuple[Item, ...]] = []
    chapter_plans: list[Plan] = []
    notes: list[Note] = []
    for chapter in chapters:
        resolved = _say_as_written(
            resolve_chapter(chapter, project.grammar, project.cast), project.lexicon
        )
        items.append(resolved)
        chapter_plans.append(
            plan_chapter(resolved, project.grammar, max_characters=max_characters)
        )
        notes.extend(chapter.notes)

    return VolumePlan(
        name=name,
        chapters=tuple(chapters),
        plan=plan_volume(items, project.grammar, max_characters=max_characters),
        chapter_plans=tuple(chapter_plans),
        notes=tuple(notes),
    )


def _say_as_written(items: tuple[Item, ...], lexicon: Lexicon) -> tuple[Item, ...]:
    """Put the lexicon into the words, just before they reach a voice.

    This happens here and not in the parser, so that the manuscript keeps its
    own spelling and only the sound changes.
    """
    if not len(lexicon):
        return items

    from dataclasses import replace

    from .cast.utterance import Utterance

    return tuple(
        replace(item, text=lexicon.apply(item.text))
        if isinstance(item, Utterance)
        else item
        for item in items
    )


def render_volume(volume: VolumePlan, engine, cache):
    """Make the sound for a volume, and say where each chapter starts.

    The chapters are made one at a time so that the mark for each one carries
    the length the engine actually produced, and not the length the plan
    guessed. A guess drifts, and a chapter mark that drifts is worse than none.
    """
    from .cast.utterance import Silence
    from .speech.audio import Audio, join_all
    from .speech.package import Mark
    from .speech.render import RenderReport, render_plan

    pieces: list[Audio] = []
    marks: list[Mark] = []
    total = RenderReport()
    at = 0.0

    for index, (chapter, plan) in enumerate(
        zip(volume.chapters, volume.chapter_plans, strict=True)
    ):
        if index:
            gap = Silence(seconds=0.0, reason="new chapter")
            for item in volume.plan.items:
                if isinstance(item, Silence) and item.reason == "new chapter":
                    gap = item
                    break
            pieces.append(Audio.silence(seconds=gap.seconds, rate=engine.rate))
            at += gap.seconds

        audio, report = render_plan(plan, engine, cache)
        pieces.append(audio)
        marks.append(Mark(title=chapter.title, start=at, end=at + audio.seconds))
        at += audio.seconds

        total.made += report.made
        total.reused += report.reused
        total.retried += report.retried
        total.keys |= report.keys

    joined = join_all(pieces, engine.rate)
    total.seconds = joined.seconds
    return joined, marks, total


def volume_names(project: Project) -> tuple[str, ...]:
    """Every volume of the book, in the order the chapters come in."""
    seen: dict[str, None] = {}
    for chapter in project.parsed():
        seen.setdefault(project.volume_of(chapter), None)
    return tuple(seen)
