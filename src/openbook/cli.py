"""The command line.

Every command reads the same two configuration files and the same book. A
command that finds a problem in either writes one line to the error stream and
gives back the code 2. Nothing here writes audio yet.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .config.cast import load_cast
from .config.grammar import load_grammar
from .errors import OpenBookError
from .source.epub import read_book


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openbook",
        description="Turns a book in EPUB form into an audiobook.",
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

    chapters = commands.add_parser(
        "chapters", help="list the chapters that the audiobook will contain"
    )
    chapters.add_argument(
        "--volume", help="list one volume only, such as 'Volume 1'", default=None
    )

    commands.add_parser(
        "check", help="read the configuration and report what is not finished"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    options = parser.parse_args(argv)
    try:
        if options.command == "chapters":
            return _chapters(options)
        return _check(options)
    except OpenBookError as error:
        print(f"openbook: {error}", file=sys.stderr)
        return 2


def _load(options: argparse.Namespace):
    project: Path = options.project
    grammar = load_grammar(project / "grammar.toml")
    cast = load_cast(project / "cast.toml")
    files = [project / name for name in grammar.source.files]
    return grammar, cast, files


def _chapters(options: argparse.Namespace) -> int:
    grammar, _, files = _load(options)
    chapters = read_book(files, grammar.source)
    wanted = options.volume

    shown = 0
    for chapter in chapters:
        group = grammar.output.group_of(chapter.volume)
        if wanted and wanted not in (chapter.volume, group):
            continue
        print(f"{chapter.number:>4}  {group:<10}  {chapter.title}")
        shown += 1

    if wanted and shown == 0:
        volumes = sorted({grammar.output.group_of(c.volume) for c in chapters})
        print(
            f"openbook: no volume is named {wanted!r}. The book has "
            f"{', '.join(volumes)}",
            file=sys.stderr,
        )
        return 2
    print(f"\n{shown} chapters", file=sys.stderr)
    return 0


def _check(options: argparse.Namespace) -> int:
    grammar, cast, files = _load(options)
    print(f"grammar  reads {len(grammar.source.files)} book file(s)")

    missing = [path for path in files if not path.exists()]
    for path in missing:
        print(f"missing  {path}", file=sys.stderr)

    if not missing:
        chapters = read_book(files, grammar.source)
        volumes = sorted({grammar.output.group_of(c.volume) for c in chapters})
        print(f"book     {len(chapters)} chapters in {len(volumes)} volumes")

    uncast = cast.uncast()
    print(f"cast     {len(cast.codes())} speaker codes")
    if not cast.narrator:
        print("         the narrator has no voice yet")
    if uncast:
        print(f"         {len(uncast)} of them have no voice yet")
        for entry in uncast[:10]:
            print(f"           {entry.code}")
        if len(uncast) > 10:
            print(f"           and {len(uncast) - 10} more")

    ready = not missing and not uncast and bool(cast.narrator)
    print("ready" if ready else "not ready")
    return 0 if ready else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
