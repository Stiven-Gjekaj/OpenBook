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
from .corrections import EMPTY as EMPTY_CORRECTIONS
from .corrections import Corrections, load_corrections, used_by
from .errors import OpenBookError
from .lexicon import EMPTY as EMPTY_LEXICON
from .lexicon import Lexicon, load_lexicon
from .parse import Note, ParsedChapter, parse_chapter
from .plan.planner import Plan, plan_chapter, plan_volume
from .source.epub import Chapter, read_book, read_file
from .volumes import Volume, read_volumes


@dataclass
class Project:
    """A directory that holds the configuration and the book."""

    directory: Path
    grammar: Grammar
    cast: Cast
    lexicon: Lexicon
    corrections: Corrections

    # Reading and parsing a book is the same answer every time within one
    # command, and several commands ask for it more than once. A check on a
    # book of 325 chapters asked thirty times and took five seconds where it
    # takes a quarter of one. Nothing on disk changes while a command runs.
    _read: tuple[Chapter, ...] | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _parsed: tuple[ParsedChapter, ...] | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _volumes: dict[str, Volume] | None = field(
        default=None, init=False, repr=False, compare=False
    )

    @classmethod
    def open(cls, directory: Path) -> Project:
        directory = Path(directory)
        return cls(
            directory=directory,
            grammar=load_grammar(directory / "grammar.toml"),
            cast=load_cast(directory / "cast.toml"),
            lexicon=load_lexicon(directory / "lexicon.toml"),
            corrections=load_corrections(directory / "corrections.toml"),
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

    @property
    def work_directory(self) -> Path:
        """Where the half finished things go while a command runs.

        Everything a project makes belongs to the project, so a person who
        wants the whole thing gone can delete one directory and be sure. The
        pieces here are minutes old and are removed as they are finished with,
        but a command that is interrupted leaves them, and a stray file under
        this name says what it belongs to. A stray file in the system temp
        directory says nothing at all.

        It is kept apart from out, which holds only what was asked for.
        """
        return self.directory / ".work"

    def prepare(self) -> Path:
        """Make the working directory, and send anything using temp into it."""
        import tempfile

        self.work_directory.mkdir(parents=True, exist_ok=True)
        # This reaches everything in the process that asks for a temporary
        # file, including the parts of the project that never hear about a
        # project directory, and anything a library does on their behalf.
        tempfile.tempdir = str(self.work_directory)
        return self.work_directory

    def chapters(self) -> tuple[Chapter, ...]:
        # The files are looked for every time, and only the reading is kept.
        # A file that went missing is the caller's situation and has to be
        # reported whenever it is asked about.
        missing = [path for path in self.files if not path.exists()]
        if missing:
            names = ", ".join(str(path) for path in missing)
            raise OpenBookError(f"these book files are missing: {names}")
        if self._read is None:
            self._read = read_book(self.files, self.grammar.source)
        return self._read

    def parsed(self) -> tuple[ParsedChapter, ...]:
        if self._parsed is None:
            self._parsed = tuple(
                parse_chapter(c, self.grammar) for c in self.chapters()
            )
        return self._parsed

    def volume_of(self, chapter: ParsedChapter) -> str:
        return self.grammar.output.group_for(chapter.number, chapter.volume)

    def volumes(self) -> dict[str, Volume]:
        """The name of each volume, out of the archive chapters.

        Each file is read on its own. Both archive chapters are numbered -1, so
        reading the book as a whole keeps the first and drops the second, and
        the second is the one that names the last three volumes.
        """
        if self._volumes is not None:
            return self._volumes
        found: dict[str, Volume] = {}
        for path in self.files:
            found |= read_volumes(read_file(path, self.grammar.source, skipped=True))
        self._volumes = found
        return found


@dataclass
class VolumePlan:
    """A volume, ready to be made into sound."""

    name: str
    chapters: tuple[ParsedChapter, ...]
    plan: Plan
    chapter_plans: tuple[Plan, ...]
    grammar: Grammar
    narrator: str
    every: tuple[ParsedChapter, ...]

    # The voice that speaks to the listener rather than inside the book, and
    # how much feeling it reads with. Empty means the narrator does it.
    host: str = ""
    host_exaggeration: float | None = None
    notes: tuple[Note, ...] = field(default_factory=tuple)

    # The intro and the outro are made when the volume is spoken, and not when
    # it is planned, because their words need the details of the volume filled
    # in. They still get everything the chapters get, so these come along.
    lexicon: Lexicon = EMPTY_LEXICON
    corrections: Corrections = EMPTY_CORRECTIONS

    def as_spoken(self, text: str, named) -> str:
        """One line the narrator reads outside the chapters, ready to say."""
        return self.corrections.apply(self.as_marked(text, named))

    def as_marked(self, text: str, named) -> str:
        """The same line as the review page showed it, before any correction.

        This is what a correction names. Asking whether a correction is used
        against the corrected words would never find one.
        """
        return self.lexicon.apply(fill(text, self, named))

    def announcements(self, named) -> tuple[str, ...]:
        return tuple(
            said
            for said in (
                self.as_marked(self.grammar.render.intro, named),
                self.as_marked(self.grammar.render.outro, named),
            )
            if said
        )

    def corrections_used(self, named=None) -> tuple[str, ...]:
        """Every correction this volume uses, the intro and the outro too."""
        outside = used_by(self.announcements(named), self.corrections)
        return tuple(dict.fromkeys(self.plan.corrected + outside))


def build_volume(
    project: Project,
    name: str,
    *,
    max_characters: int | None = None,
    only: int | None = None,
) -> VolumePlan:
    """Work every stage for one volume, up to but not including the sound.

    One chapter can be asked for, and then nothing else in the volume is
    resolved at all. That matters while a cast is being filled in: a chapter
    whose characters all have voices can be heard without waiting for the
    other twenty two to be cast.

    The chapter keeps its own number and the volume keeps its length, so a
    card still reads Chapter 0 of 2 and not Chapter 1 of 1.
    """
    chapters = [c for c in project.parsed() if project.volume_of(c) == name]
    if not chapters:
        known = sorted({project.volume_of(c) for c in project.parsed()})
        raise OpenBookError(
            f"no volume is named {name!r}. The book has {', '.join(known)}"
        )

    if only is not None:
        held = ", ".join(str(c.number) for c in chapters)
        chapters = [c for c in chapters if c.number == only]
        if not chapters:
            raise OpenBookError(
                f"volume {name!r} has no chapter {only}. It holds {held}"
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
            plan_chapter(
                resolved,
                project.grammar,
                max_characters=max_characters,
                corrections=project.corrections,
            )
        )
        notes.extend(chapter.notes)

    return VolumePlan(
        name=name,
        chapters=tuple(chapters),
        plan=plan_volume(
            items,
            project.grammar,
            max_characters=max_characters,
            corrections=project.corrections,
        ),
        chapter_plans=tuple(chapter_plans),
        grammar=project.grammar,
        narrator=project.cast.narrator,
        host=project.cast.host_voice(),
        host_exaggeration=project.cast.host_exaggeration,
        every=project.parsed(),
        notes=tuple(notes),
        lexicon=project.lexicon,
        corrections=project.corrections,
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


def fill(text: str, volume: VolumePlan, named) -> str:
    """Put the details of a volume into a piece of text the author wrote."""
    numbers = [chapter.number for chapter in volume.chapters]
    for name, value in (
        ("VOLUME", named.name if named else volume.name),
        ("TITLE", named.title if named else ""),
        ("FIRST", str(min(numbers)) if numbers else ""),
        ("LAST", str(max(numbers)) if numbers else ""),
        ("CHAPTERS", str(len(numbers))),
    ):
        text = text.replace(f"{{{name}}}", value)
    return " ".join(text.split())


def render_volume(volume: VolumePlan, engine, cache, *, named=None):
    """Make the sound for a volume, and say where each chapter starts.

    The chapters are made one at a time so that the mark for each one carries
    the length the engine actually produced, and not the length the plan
    guessed. A guess drifts, and a chapter mark that drifts is worse than none.
    """
    from .cast import chapter_label, last_chapters
    from .cast.utterance import ANNOUNCEMENT, HOST, Silence, Utterance, Voice
    from .plan.planner import Plan
    from .speech.audio import Audio, join_all
    from .speech.package import Mark
    from .speech.render import RenderReport, render_plan

    pieces: list[Audio] = []
    marks: list[Mark] = []
    total = RenderReport()
    at = 0.0
    render = volume.grammar.render
    host = Voice(volume.host or volume.narrator)

    def rest() -> None:
        """The gap between the host and the book."""
        nonlocal at
        pieces.append(Audio.silence(seconds=render.between_chapters, rate=engine.rate))
        at += render.between_chapters

    def spoken(text: str, title: str, *, after: bool = False) -> None:
        """Put a piece the host reads before or after the chapters.

        These words go through the lexicon and the corrections like any other,
        which they did not until it was noticed that an intro naming the book
        and its characters was the one place every pronunciation entry was
        ignored.

        The rest falls between the host and the book either way: after the
        intro, and before the outro. A listener needs the same moment to change
        from being spoken to, to being read to, in both directions.
        """
        nonlocal at
        words = volume.as_spoken(text, named)
        if not words:
            return
        if after:
            rest()
        said = Utterance(
            text=words,
            voice=host,
            kind=ANNOUNCEMENT,
            speaker=HOST,
            exaggeration=volume.host_exaggeration,
        )
        audio, report = render_plan(Plan(items=(said,)), engine, cache)
        pieces.append(audio)
        marks.append(Mark(title=title, start=at, end=at + audio.seconds, host=True))
        total.made += report.made
        total.reused += report.reused
        total.keys |= report.keys
        total.timeline += [(u, at + b, at + e) for u, b, e in report.timeline]
        at += audio.seconds
        if not after:
            rest()

    spoken(render.intro, render.intro_title)

    last = last_chapters(volume.every)
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
        marks.append(
            Mark(
                title=chapter.title,
                start=at,
                end=at + audio.seconds,
                label=chapter_label(chapter.number, last[chapter.volume]),
            )
        )
        at += audio.seconds

        total.made += report.made
        total.reused += report.reused
        total.retried += report.retried
        total.keys |= report.keys
        # Each chapter is made on its own and starts at zero, so its places
        # move to where the chapter sits in the volume.
        start = at - audio.seconds
        total.timeline += [
            (utterance, start + begins, start + ends)
            for utterance, begins, ends in report.timeline
        ]

    spoken(render.outro, render.outro_title, after=True)

    joined = join_all(pieces, engine.rate)
    total.seconds = joined.seconds
    return joined, marks, total


def volume_names(project: Project) -> tuple[str, ...]:
    """Every volume of the book, in the order the chapters come in."""
    seen: dict[str, None] = {}
    for chapter in project.parsed():
        seen.setdefault(project.volume_of(chapter), None)
    return tuple(seen)
