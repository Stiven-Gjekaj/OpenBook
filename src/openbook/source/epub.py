"""Reads chapters out of one or more EPUB files.

An EPUB file is a zip archive. Inside it, a container names a package document,
and the package document holds a spine, which is the order to read the parts
in. This module follows that path, because the order of the names of the files
inside the archive is not the order of the book.

A book can arrive in more than one file, and each file can hold the same
chapter. The chapter number decides, and the first file that has a chapter
keeps it.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ElementTree
import zipfile
from dataclasses import dataclass
from pathlib import Path

from ..config.grammar import Source
from ..errors import SourceError

_CONTAINER = "META-INF/container.xml"
_OPF_NS = "{http://www.idpf.org/2007/opf}"
_CONTAINER_NS = "{urn:oasis:names:tc:opendocument:xmlns:container}"

# The title of a part, out of the head of the document. Every chapter of the
# book carries the same string here, in its <h1>, and in the navigation.
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

# The body of a chapter. The exporter wraps it in a section, which keeps the
# heading and any front matter out of the text that gets spoken.
_BODY = re.compile(
    r"<section[^>]*class=\"chapter-body\"[^>]*>(.*?)</section>",
    re.IGNORECASE | re.DOTALL,
)
_FALLBACK_BODY = re.compile(r"<body[^>]*>(.*?)</body>", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class Chapter:
    """One chapter, before anything looks at the words in it."""

    number: int
    volume: str
    title: str
    body: str
    source: str

    @property
    def full_title(self) -> str:
        return f"(Chapter {self.number} || {self.volume}) {self.title}"


def read_book(
    paths: list[Path], source: Source, *, skipped: bool = False
) -> tuple[Chapter, ...]:
    """Read every chapter of a book, in the order it is read in.

    A chapter whose volume the configuration skips does not come back, unless
    skipped is asked for. The archive chapters are skipped for audio and still
    hold the names of the volumes, so something has to be able to read them.
    """
    chapters: dict[int, Chapter] = {}
    for path in paths:
        for chapter in read_file(path, source, skipped=skipped):
            chapters.setdefault(chapter.number, chapter)
    return tuple(chapters[number] for number in sorted(chapters))


def read_file(
    path: Path, source: Source, *, skipped: bool = False
) -> tuple[Chapter, ...]:
    """Read every chapter of one EPUB file, in spine order."""
    if not path.exists():
        raise SourceError(f"{path}: the file does not exist")
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise SourceError(f"{path}: this is not an EPUB file") from error

    with archive:
        package = _package_path(archive, path)
        documents = _spine_documents(archive, package, path)
        found: list[Chapter] = []
        for name in documents:
            chapter = _read_chapter(archive, name, source, path)
            if chapter is not None and (
                skipped or not source.is_skipped(chapter.volume)
            ):
                found.append(chapter)
    return tuple(found)


def _package_path(archive: zipfile.ZipFile, path: Path) -> str:
    try:
        container = archive.read(_CONTAINER)
    except KeyError as error:
        raise SourceError(
            f"{path}: the file has no {_CONTAINER}, so it is not an EPUB file"
        ) from error
    root = ElementTree.fromstring(container)
    element = root.find(f".//{_CONTAINER_NS}rootfile")
    if element is None or not element.get("full-path"):
        raise SourceError(f"{path}: {_CONTAINER} names no package document")
    return element.get("full-path", "")


def _spine_documents(
    archive: zipfile.ZipFile, package: str, path: Path
) -> tuple[str, ...]:
    root = ElementTree.fromstring(archive.read(package))
    base = package.rpartition("/")[0]

    manifest = {
        item.get("id", ""): item.get("href", "")
        for item in root.iterfind(f".//{_OPF_NS}manifest/{_OPF_NS}item")
    }
    spine = [
        manifest.get(ref.get("idref", ""), "")
        for ref in root.iterfind(f".//{_OPF_NS}spine/{_OPF_NS}itemref")
    ]
    if not spine:
        raise SourceError(f"{path}: the package document has an empty spine")
    return tuple(f"{base}/{href}" if base else href for href in spine if href)


def _read_chapter(
    archive: zipfile.ZipFile, name: str, source: Source, path: Path
) -> Chapter | None:
    try:
        raw = archive.read(name).decode("utf-8")
    except KeyError:
        # The spine names a document the archive does not hold. The rest of the
        # book is still readable, so this is not a reason to stop.
        return None

    title = _TITLE.search(raw)
    if title is None:
        return None
    found = source.chapter_title.match(_text(title.group(1)))
    if found is None:
        # A cover, a table of contents, or anything else that is not a chapter.
        return None

    body = _BODY.search(raw) or _FALLBACK_BODY.search(raw)
    return Chapter(
        number=int(found["NUMBER"]),
        volume=found["VOLUME"],
        title=found["TITLE"],
        body=body.group(1) if body else "",
        source=path.name,
    )


def _text(raw: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", raw)).strip()
