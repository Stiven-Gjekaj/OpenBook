"""The command line.

Every command reads the same configuration and the same book. A problem that a
person can correct writes one line to the error stream and gives back the code
2. A command that finds work still to do gives back 1. Nothing else gives back
anything but 0.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .build import Project, build_volume, render_volume, volume_names
from .errors import OpenBookError
from .source.epub import BookDetails, read_details
from .speech import Cache, SilentEngine
from .speech.package import have_ffmpeg, write_m4b

ENGINES = ("silent", "espeak", "kokoro")


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

    check = commands.add_parser(
        "check", help="read the configuration and say what is missing"
    )
    # A correction names a piece of a divided line, and where a line divides
    # depends on how much the engine takes at once, so the check has to be told
    # which engine the render will use.
    check.add_argument("--engine", choices=ENGINES, default="silent")

    plan = commands.add_parser("plan", help="print every line and the voice it takes")
    plan.add_argument("--volume", required=True)
    plan.add_argument("--chapter", type=int, default=None, help="one chapter only")

    commands.add_parser("notes", help="print what the parser noticed in the book")

    words = commands.add_parser(
        "words", help="list the words that need a pronunciation entry"
    )
    words.add_argument("--limit", type=int, default=60, help="how many to show")
    # One makes the file and one adds to it. Each refuses the other's job and
    # names it, so neither can write over what you have already answered.
    writing = words.add_mutually_exclusive_group()
    writing.add_argument(
        "--write",
        action="store_true",
        help="write lexicon.toml with the words found and their sound left blank",
    )
    writing.add_argument(
        "--merge",
        action="store_true",
        help="add the words that are not in lexicon.toml yet to the end of it",
    )

    render = commands.add_parser("render", help="make the audio for a volume")
    render.add_argument("--volume", required=True)
    render.add_argument("--engine", choices=ENGINES, default="silent")
    render.add_argument(
        "--speed", type=float, default=1.0, help="how fast a real voice reads"
    )
    render.add_argument(
        "--review",
        action="store_true",
        help="write a page listing every line, to check the render by ear",
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
        group = project.grammar.output.group_for(chapter.number, chapter.volume)
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
    print(f"grammar      reads {len(project.grammar.source.files)} book file(s)")

    ready = True
    try:
        chapters = project.chapters()
        print(
            f"book         {len(chapters)} chapters in "
            f"{len(volume_names(project))} volumes"
        )
    except OpenBookError as error:
        print(f"book         {error}", file=sys.stderr)
        ready = False

    uncast = project.cast.uncast()
    print(f"cast         {len(project.cast.codes())} speaker codes")
    if not project.cast.narrator:
        print("             the narrator has no voice yet")
        ready = False
    if uncast:
        print(f"             {len(uncast)} of them have no voice yet")
        for entry in uncast[:10]:
            print(f"               {entry.code}")
        if len(uncast) > 10:
            print(f"               and {len(uncast) - 10} more")
        ready = False

    if not _corrections_match(project, _engine_for(options)):
        ready = False

    print(
        f"ffmpeg       {'found' if have_ffmpeg() else 'not found, needed for an M4B'}"
    )
    if not have_ffmpeg():
        ready = False

    print("ready" if ready else "not ready")
    return 0 if ready else 1


def _corrections_match(project, engine) -> bool:
    """Say whether every correction has a line in the book to change.

    A correction that matches nothing is the worst kind of mistake this file
    can hold, because the render says nothing, the audio does not change, and
    the only way left to find it is to listen to the line again.

    The lines are compared against the whole book and not one volume, so a
    correction for volume 4 is not called a mistake while volume 1 is checked.
    """
    corrections = project.corrections
    if not len(corrections) and not corrections.waiting:
        return True

    print(f"corrections  {len(corrections) + len(corrections.waiting)} in the file")
    if corrections.waiting:
        print(f"             {len(corrections.waiting)} still waiting for words")

    try:
        used: set[str] = set()
        for name in volume_names(project):
            volume = build_volume(project, name, max_characters=engine.max_characters)
            used |= set(volume.corrections_used(project.volumes().get(name)))
    except OpenBookError as error:
        # The cast is unfinished, or the book cannot be read. Both are already
        # reported above, and neither is a fault of this file.
        print(f"             not checked against the book: {error}")
        return True

    missing = [line for line in corrections.entries if line not in used]
    if not missing:
        return True

    print(f"             {len(missing)} match no line in the book")
    for line in missing[:5]:
        print(f"               {_short(line)}")
    if len(missing) > 5:
        print(f"               and {len(missing) - 5} more")
    return False


def _short(line: str) -> str:
    line = " ".join(line.split())
    return line if len(line) <= 60 else f"{line[:60]}..."


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

    espeak-ng is the one in between. It sounds like a machine from the 1990s
    and it says real words at real lengths, which is enough to check the
    captions and the cards of a whole volume in seconds.
    """
    asked = getattr(options, "engine", "silent")
    if asked == "espeak":
        from .speech.espeak import EspeakEngine

        return EspeakEngine(speed=getattr(options, "speed", 1.0))
    if asked == "kokoro":
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

    # Whether a file is already there is the caller's situation and is checked
    # before anything about the machine. Reporting a missing word list to
    # somebody whose real problem is a file they wrote is the wrong answer.
    written = project.directory / "lexicon.toml"
    if options.write and written.exists():
        raise OpenBookError(
            f"{written} exists already. Use --merge to add the words that are "
            "not in it yet, so that nothing you have written is lost"
        )
    if options.merge and not written.exists():
        raise OpenBookError(f"there is no {written} to add to. Use --write to make one")

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
    if options.merge:
        return _merge_lexicon(written, unknown, lexicon)
    if options.write:
        written.write_text(_starter_lexicon(unknown), encoding="utf-8")
        print(f"{written}")
        print(f"  {len(unknown)} words, each with its sound left blank")
        return 0

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
        print(f"volume      {volume.name}, {len(volume.chapters)} chapters")
        print(f"utterances  {total}, of which {held} are already made")
        print(f"words       {volume.plan.words():,}")
        print(f"silence     {volume.plan.silent_seconds:.0f}s")
        _report_corrections(
            project, volume, project.volumes().get(volume.name), lead=""
        )
        return 0

    named = project.volumes().get(volume.name)
    audio, marks, report = render_volume(volume, engine, cache, named=named)
    name = project.grammar.output.file_name.replace("{VOLUME}", volume.name)
    path = project.output_directory / name

    if options.review:
        print(f"{_review_page(project, volume, marks, report, engine)}")
    print(f"{_write_captions(project, path, report, announcements=True)}")
    audio = _levelled(audio, project, path.stem)
    output = project.grammar.output
    details = read_details(project.files[0]) if project.files else BookDetails()
    write_m4b(
        audio,
        marks,
        path,
        title=f"{details.title or 'Soultale'}, {volume.name}",
        author=details.author,
        cover=details.cover,
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
    _report_corrections(project, volume, named)
    return 0


def _video(options) -> int:
    from .speech.cards import Style, make_chapter_cards, write_concat_list
    from .speech.verify import (
        check_cards_against_time,
        check_marks_against_speech,
    )
    from .speech.video import (
        Music,
        mix_music,
        opening_words,
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
    named = project.volumes().get(volume.name)
    audio, marks, report = render_volume(volume, engine, cache, named=named)

    name = (settings.file_name if settings else "{VOLUME}.mp4").replace(
        "{VOLUME}", volume.name
    )
    out = project.output_directory / name
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"{_write_captions(project, out, report)}")

    # The name of the volume comes from the archive chapters, so it is written
    # in one place and read from there rather than typed again here.
    heading = f"Soultale, {named.written}" if named else f"Soultale, {volume.name}"

    before = settings.description.strip() if settings else ""
    if settings and settings.peek_words and volume.chapters:
        peek = opening_words(volume.chapters[0], settings.peek_words)
        if peek:
            before = f"{before}\n\n{peek}".strip()

    description = out.with_suffix(".txt")
    description.write_text(
        youtube_description(
            marks,
            title=heading,
            before=before,
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
        audio = _levelled(audio, project, out.stem)
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
            # Each card names the volume of the chapter on it. The prologue
            # and volume 1 share a file and are still two volumes.
            volumes = project.volumes()
            by_title = {c.title: c.volume for c in volume.chapters}
            names = []
            for mark in marks:
                found = volumes.get(by_title.get(mark.title, ""))
                names.append((found.name, found.title) if found else ("", ""))
            cards = make_chapter_cards(
                marks,
                style,
                project.output_directory / ".cards",
                total=audio.seconds,
                volumes=names,
            )
            check_marks_against_speech(marks, volume)
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
    _report_corrections(project, volume, named)
    return 0


def _report_corrections(project, volume, named=None, *, lead: str = "  ") -> None:
    """Say what the corrections file did to this render.

    A file that is read and changes nothing looks exactly like a file that is
    not read at all, so this is printed whenever the file exists, including
    when the count is zero.
    """
    said = _corrections_said(project.corrections, len(volume.corrections_used(named)))
    if said:
        print(f"{lead}corrections {said}")


def _corrections_said(corrections, used: int) -> str:
    if not len(corrections) and not corrections.waiting:
        return ""
    said = [f"{used} used"]
    elsewhere = len(corrections) - used
    if elsewhere:
        said.append(f"{elsewhere} for no line in this volume")
    if corrections.waiting:
        said.append(f"{len(corrections.waiting)} still waiting for words")
    return ", ".join(said)


def _starter_lexicon(unknown) -> str:
    """A lexicon file holding the words found, with each sound left blank.

    The same shape as the cast sheet: the work of finding what needs an answer
    is done here, and the answers are yours.
    """
    lines = [
        "# How a word is said.",
        "#",
        "# Each entry replaces a word before it reaches a voice. Write the",
        "# spelling that the engine says correctly, and leave the manuscript",
        "# alone. A blank one does nothing.",
        "#",
        f"# {len(unknown)} words in this book have no entry. They are in the",
        "# order they appear in, most often first, because the one said most",
        "# is the one worth getting right.",
        "",
        "[words]",
    ]
    lines.extend(_entry_line(entry) for entry in unknown)
    return "\n".join(lines) + "\n"


def _entry_line(entry) -> str:
    """One word, with its sound left blank and its count beside it.

    Every key is quoted. A word holding an apostrophe, and there are many of
    those, is not a name TOML accepts on its own, and the file would not read
    back.
    """
    name = entry.word.replace("\\", "\\\\").replace('"', '\\"')
    times = "time" if entry.count == 1 else "times"
    return f'"{name}" = ""  # {entry.count} {times}, first in chapter {entry.chapter}'


def _merge_lexicon(path: Path, unknown, lexicon) -> int:
    """Add the words that are not in the lexicon yet to the end of it.

    The file is added to and never rewritten. It holds answers somebody sat
    down and worked out, in whatever order and with whatever comments they
    chose, and none of that survives a tool that reads a file and writes it
    back out again.

    A word already written down is left alone whether it has an answer or not.
    A blank entry is a word waiting for one, and putting it in the file a
    second time helps nobody.
    """
    fresh = [entry for entry in unknown if not lexicon.has(entry.word)]
    if not fresh:
        print(f"{path}")
        print(f"  nothing to add. All {len(lexicon)} words the book says are in it")
        return 0

    text = path.read_text(encoding="utf-8")
    added = [
        "",
        f"# Added by 'openbook words --merge'. {len(fresh)} words the book says",
        "# that had no entry, most often first.",
    ]
    # A lexicon holds one table and it is [words], so new keys at the end of
    # the file land in it. A file that never declared it needs the header, and
    # a file that did must not get it twice: TOML refuses a table named twice.
    if "words" not in tomllib.loads(text):
        added.append("[words]")
    added.extend(_entry_line(entry) for entry in fresh)
    made = text.rstrip("\n") + "\n" + "\n".join(added) + "\n"

    # Read what is about to be written before anything is written. A lexicon
    # that will not parse is worse than one that is out of date, and the file
    # this is adding to is not one to leave broken.
    _readable(made, path, len(lexicon) + len(fresh))

    path.write_text(made, encoding="utf-8")
    print(f"{path}")
    print(f"  {len(fresh)} words added, each with its sound left blank")
    for entry in fresh[:5]:
        print(f"    {entry.word}")
    if len(fresh) > 5:
        print(f"    and {len(fresh) - 5} more")
    return 0


def _readable(text: str, path: Path, expected: int) -> None:
    try:
        found = tomllib.loads(text).get("words", {})
    except tomllib.TOMLDecodeError as error:
        raise OpenBookError(
            f"{path} was left alone, because adding the words to it would have "
            f"made a file that does not read back: {error}"
        ) from error
    if len(found) != expected:
        raise OpenBookError(
            f"{path} was left alone. Adding the words to it would have given "
            f"{len(found)} entries where {expected} were meant, so something "
            "in the file is not what this expected"
        )


def _write_captions(project, beside, report, *, announcements: bool = False):
    """Write the captions next to a finished file.

    The video asks for no announcements, because its card already carries the
    name of the chapter. Sound with no picture asks for them, because nothing
    else marks where a chapter begins.
    """
    from .speech.captions import cues_from_timeline, names_from_cast, to_srt

    path = beside.with_suffix(".srt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        to_srt(
            cues_from_timeline(
                report.timeline,
                names=names_from_cast(project.cast),
                announcements=announcements,
            )
        ),
        encoding="utf-8",
    )
    return path


def _review_page(project, volume, marks, report, engine):
    """Write the page that makes a render checkable by ear."""
    from .lexicon import known_words, load_lexicon
    from .review import rows_from, write_page
    from .speech.cache import key_of
    from .speech.captions import names_from_cast

    keys = {order: key_of(u, engine) for order, (u, _, _) in enumerate(report.timeline)}
    rows = rows_from(
        report.timeline,
        marks,
        names=names_from_cast(project.cast),
        lexicon=load_lexicon(project.directory / "lexicon.toml"),
        known=known_words(),
        keys=keys,
    )
    out = project.output_directory / f"review - {volume.name}.html"
    return write_page(
        rows, out, title=f"Soultale, {volume.name}", cache=project.cache_directory
    )


def _levelled(audio, project, stem: str):
    """Bring the speech to the loudness an audiobook is expected to have.

    A volume quieter than the one before it means reaching for the dial at the
    start of every part, and an uploaded file cannot be corrected.
    """
    from .speech.audio import Audio
    from .speech.loudness import LEAST_SECONDS, level, measure
    from .speech.package import have_ffmpeg

    if not project.grammar.output.level or not have_ffmpeg():
        return audio
    if audio.seconds < LEAST_SECONDS:
        # Loudness is measured over a whole recording, and there is not enough
        # of one here to measure. A piece this short is an excerpt or a test.
        print(f"  loudness   not measured, only {audio.seconds:.1f}s of audio")
        return audio

    project.output_directory.mkdir(parents=True, exist_ok=True)
    before = project.output_directory / f".{stem}.raw.wav"
    after = project.output_directory / f".{stem}.level.wav"
    try:
        audio.write(before)
        measured = measure(before)
        if measured.silent:
            # A render made with the silent engine. There is nothing to raise.
            print("  loudness   not measured, this audio is silent")
            return audio
        level(before, after, measured)
        levelled = Audio.read(after)
        print(f"  loudness   {measured} -> {measure(after)}")
        return levelled
    finally:
        before.unlink(missing_ok=True)
        after.unlink(missing_ok=True)


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
