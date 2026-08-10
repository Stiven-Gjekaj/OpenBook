"""The command line.

Every command reads the same configuration and the same book. A problem that a
person can correct writes one line to the error stream and gives back the code
2. A command that finds work still to do gives back 1. Nothing else gives back
anything but 0.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .build import Project, build_volume, render_volume, volume_names
from .cast import chapter_label, last_chapters
from .errors import OpenBookError
from .speech import Cache, SilentEngine
from .speech.package import have_ffmpeg, write_m4b

ENGINES = ("silent", "kokoro")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openbook", description="Turns a book in EPUB form into an audiobook."
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "-C",
        "--project",
        type=Path,
        default=Path("."),
        metavar="DIR",
        help="the directory that holds grammar.toml and cast.toml",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    chapters = commands.add_parser("chapters", help="list the chapters of the book")
    chapters.add_argument("--volume", default=None, help="one volume only")

    commands.add_parser("check", help="read the configuration and say what is missing")

    plan = commands.add_parser("plan", help="print every line and the voice it takes")
    plan.add_argument("--volume", required=True)
    plan.add_argument("--chapter", type=int, default=None, help="one chapter only")

    commands.add_parser("notes", help="print what the parser noticed in the book")

    words = commands.add_parser(
        "words", help="list the words that need a pronunciation entry"
    )
    words.add_argument("--limit", type=int, default=60, help="how many to show")

    render = commands.add_parser("render", help="make the audio for a volume")
    render.add_argument("--volume", required=True)
    render.add_argument("--engine", choices=ENGINES, default="silent")
    render.add_argument(
        "--speed", type=float, default=1.0, help="how fast a real voice reads"
    )
    render.add_argument(
        "--dry-run",
        action="store_true",
        help="say what a render would do, and make nothing",
    )

    video = commands.add_parser("video", help="make the file that goes to YouTube")
    video.add_argument("--volume", required=True)
    video.add_argument("--engine", choices=ENGINES, default="silent")
    video.add_argument("--speed", type=float, default=1.0)
    video.add_argument("--visual", type=Path, default=None, help="a picture or a loop")
    video.add_argument("--music", type=Path, default=None)
    video.add_argument(
        "--description-only",
        action="store_true",
        help="write the times for YouTube and encode nothing",
    )

    cache = commands.add_parser("cache", help="report or clean the audio already made")
    cache.add_argument("--prune", action="store_true", help="remove what nothing uses")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    options = build_parser().parse_args(argv)
    try:
        return _COMMANDS[options.command](options)
    except OpenBookError as error:
        print(f"openbook: {error}", file=sys.stderr)
        return 2


def _chapters(options) -> int:
    project = Project.open(options.project)
    wanted = options.volume
    shown = 0
    for chapter in project.chapters():
        group = project.grammar.output.group_of(chapter.volume)
        if wanted and wanted not in (chapter.volume, group):
            continue
        print(f"{chapter.number:>4}  {group:<10}  {chapter.title}")
        shown += 1

    if wanted and shown == 0:
        raise OpenBookError(
            f"no volume is named {wanted!r}. The book has "
            f"{', '.join(volume_names(project))}"
        )
    print(f"\n{shown} chapters", file=sys.stderr)
    return 0


def _check(options) -> int:
    project = Project.open(options.project)
    print(f"grammar  reads {len(project.grammar.source.files)} book file(s)")

    ready = True
    try:
        chapters = project.chapters()
        print(
            f"book     {len(chapters)} chapters in {len(volume_names(project))} volumes"
        )
    except OpenBookError as error:
        print(f"book     {error}", file=sys.stderr)
        ready = False

    uncast = project.cast.uncast()
    print(f"cast     {len(project.cast.codes())} speaker codes")
    if not project.cast.narrator:
        print("         the narrator has no voice yet")
        ready = False
    if uncast:
        print(f"         {len(uncast)} of them have no voice yet")
        for entry in uncast[:10]:
            print(f"           {entry.code}")
        if len(uncast) > 10:
            print(f"           and {len(uncast) - 10} more")
        ready = False

    print(
        f"ffmpeg   {'found' if have_ffmpeg() else 'not found, needed to write an M4B'}"
    )
    if not have_ffmpeg():
        ready = False

    print("ready" if ready else "not ready")
    return 0 if ready else 1


def _plan(options) -> int:
    project = Project.open(options.project)
    engine = SilentEngine()
    volume = build_volume(project, options.volume, max_characters=engine.max_characters)

    shown = [
        (chapter, plan)
        for chapter, plan in zip(volume.chapters, volume.chapter_plans, strict=True)
        if options.chapter is None or chapter.number == options.chapter
    ]
    if not shown:
        raise OpenBookError(
            f"volume {volume.name!r} has no chapter {options.chapter}. It holds "
            f"{volume.chapters[0].number} to {volume.chapters[-1].number}"
        )

    for chapter, plan in shown:
        print(f"\n=== chapter {chapter.number}: {chapter.title}")
        for item in plan.items:
            if hasattr(item, "seconds"):
                print(f"     ~ {item.seconds:.2f}s  {item.reason}")
            else:
                print(f"  {item.speaker:>10} [{item.voice.key()}]  {item.text[:70]}")

    # The totals describe what was printed, and not the whole volume, or a
    # person reading one chapter is given a number that belongs to 23.
    utterances = sum(len(plan.utterances) for _, plan in shown)
    silence = sum(plan.silent_seconds for _, plan in shown)
    sys.stdout.flush()
    print(
        f"\n{len(shown)} chapters, {utterances} utterances, {silence:.0f}s of silence",
        file=sys.stderr,
    )
    return 0


def _notes(options) -> int:
    project = Project.open(options.project)
    found = [(c.number, note) for c in project.parsed() for note in c.notes]
    for number, note in found:
        print(f"{number:>4}  {note}")
    print(f"\n{len(found)} notes", file=sys.stderr)
    return 0


def _engine_for(options):
    """Build the engine the person asked for.

    The silent engine is the default. It gives quiet of the right length, so a
    person can hear where the pauses fall and check the chapter marks without
    waiting for a real render.
    """
    if getattr(options, "engine", "silent") == "kokoro":
        try:
            from .speech.kokoro import KokoroEngine
        except ImportError as error:
            raise OpenBookError(
                "the kokoro engine is not installed. Add it with "
                "'uv sync --extra speech'"
            ) from error
        return KokoroEngine(speed=getattr(options, "speed", 1.0))
    return SilentEngine()


def _words(options) -> int:
    from .lexicon import find_unknown, have_dictionary, load_lexicon
    from .parse import Dialogue, Narration

    project = Project.open(options.project)
    if not have_dictionary():
        raise OpenBookError(
            "there is no word list on this machine to compare against, so every "
            "word would look unknown. Install espeak-ng, or put a word list at "
            "/usr/share/dict/words"
        )

    lexicon = load_lexicon(project.directory / "lexicon.toml")
    spoken = [
        (chapter.number, segment.text)
        for chapter in project.parsed()
        for segment in chapter.segments
        if isinstance(segment, Narration | Dialogue)
    ]
    unknown = find_unknown(spoken, lexicon)
    for entry in unknown[: options.limit]:
        print(f"{entry.count:>6}  {entry.word:<24} first in chapter {entry.chapter}")
    print(
        f"\n{len(unknown)} words have no entry. {len(lexicon)} are answered already.",
        file=sys.stderr,
    )
    return 0


def _render(options) -> int:
    project = Project.open(options.project)
    engine = _engine_for(options)
    cache = Cache(project.cache_directory)
    volume = build_volume(project, options.volume, max_characters=engine.max_characters)

    if options.dry_run:
        held = sum(1 for u in volume.plan.utterances if cache.holds(_key(u, engine)))
        total = len(volume.plan.utterances)
        print(f"volume     {volume.name}, {len(volume.chapters)} chapters")
        print(f"utterances {total}, of which {held} are already made")
        print(f"words      {volume.plan.words():,}")
        print(f"silence    {volume.plan.silent_seconds:.0f}s")
        return 0

    audio, marks, report = render_volume(volume, engine, cache)
    name = project.grammar.output.file_name.replace("{VOLUME}", volume.name)
    path = project.output_directory / name
    output = project.grammar.output
    write_m4b(
        audio,
        marks,
        path,
        title=volume.name,
        author="",
        bitrate=output.bitrate,
        sample_rate=output.sample_rate,
        channels=output.channels,
    )

    print(f"{path}")
    print(
        f"  {report.utterances} utterances, {report.made} made, "
        f"{report.reused} from the cache"
    )
    print(f"  {len(marks)} chapters, {audio.seconds / 3600:.2f} hours")
    return 0


def _video(options) -> int:
    from .speech.captions import cues_from_timeline, names_from_cast, to_srt
    from .speech.cards import Style, make_chapter_cards, write_concat_list
    from .speech.verify import (
        check_cards_against_speech,
        check_cards_against_time,
    )
    from .speech.video import (
        Music,
        mix_music,
        write_video,
        write_video_from_cards,
        youtube_description,
    )

    project = Project.open(options.project)
    settings = project.grammar.video
    if settings is None and options.visual is None:
        raise OpenBookError(
            "this project has no [video] table and no --visual was given, so "
            "there is no picture to put the sound behind"
        )

    engine = _engine_for(options)
    cache = Cache(project.cache_directory)
    volume = build_volume(project, options.volume, max_characters=engine.max_characters)
    audio, marks, report = render_volume(volume, engine, cache)

    name = (settings.file_name if settings else "{VOLUME}.mp4").replace(
        "{VOLUME}", volume.name
    )
    out = project.output_directory / name
    out.parent.mkdir(parents=True, exist_ok=True)

    captions = out.with_suffix(".srt")
    captions.write_text(
        to_srt(
            cues_from_timeline(report.timeline, names=names_from_cast(project.cast))
        ),
        encoding="utf-8",
    )
    print(f"{captions}")

    description = out.with_suffix(".txt")
    description.write_text(
        youtube_description(
            marks,
            title=f"Soultale, {volume.name}",
            credits=list(settings.credits) if settings else None,
        ),
        encoding="utf-8",
    )
    print(f"{description}")
    if options.description_only:
        return 0

    music_path = options.music or (
        project.directory / settings.music if settings and settings.music else None
    )

    work = project.output_directory / f".{out.stem}.wav"
    try:
        audio.write(work)
        if music_path is not None:
            mixed = project.output_directory / f".{out.stem}.mixed.wav"
            level = settings.music_level if settings else 0.15
            mix_music(work, Music(path=music_path, level=level), mixed)
            work.unlink(missing_ok=True)
            work = mixed
        shape = {
            "marks": marks,
            "framerate": settings.framerate if settings else 1,
            "bitrate": settings.bitrate if settings else "128k",
            "sample_rate": settings.sample_rate if settings else 48000,
            "channels": settings.channels if settings else 2,
        }
        if options.visual is None and settings is not None and settings.draws_cards:
            last = last_chapters(project.parsed())
            labels = [
                chapter_label(chapter.number, last[chapter.volume])
                for chapter in volume.chapters
            ]
            check_cards_against_speech(volume, labels)
            here = project.directory
            style = Style(
                title=settings.title,
                title_font=here / settings.title_font,
                title_back_font=(
                    here / settings.title_back_font
                    if settings.title_back_font
                    else None
                ),
                body_font=here / settings.body_font,
                background=settings.background,
            )
            cards = make_chapter_cards(
                marks, style, project.output_directory / ".cards"
            )
            check_cards_against_time(cards, marks, audio.seconds)
            listing = write_concat_list(cards, project.output_directory / ".cards.txt")
            print(f"  {len(cards)} cards drawn")
            write_video_from_cards(listing, work, out, **shape)
        else:
            visual = options.visual or (project.directory / settings.visual)
            write_video(work, visual, out, **shape)
    finally:
        work.unlink(missing_ok=True)

    print(f"{out}")
    print(
        f"  {len(marks)} chapters, {audio.seconds / 3600:.2f} hours, "
        f"{report.made} made, {report.reused} from the cache"
    )
    return 0


def _cache(options) -> int:
    project = Project.open(options.project)
    cache = Cache(project.cache_directory)
    if options.prune:
        engine = SilentEngine()
        live: set[str] = set()
        for name in volume_names(project):
            volume = build_volume(project, name, max_characters=engine.max_characters)
            live |= {_key(u, engine) for u in volume.plan.utterances}
        removed = cache.prune(live)
        print(f"removed {removed} pieces of audio that nothing uses")
    print(f"{len(cache.keys())} pieces, {cache.size() / 1_000_000:.1f} MB")
    return 0


def _key(utterance, engine) -> str:
    from .speech.cache import key_of

    return key_of(utterance, engine)


_COMMANDS = {
    "chapters": _chapters,
    "check": _check,
    "plan": _plan,
    "notes": _notes,
    "words": _words,
    "render": _render,
    "video": _video,
    "cache": _cache,
}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
