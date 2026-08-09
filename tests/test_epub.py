import zipfile
from pathlib import Path

import pytest

from openbook.config.grammar import load_grammar
from openbook.errors import SourceError
from openbook.source.epub import read_book, read_file

EXAMPLE = (
    Path(__file__).resolve().parent.parent / "examples" / "soultale" / "grammar.toml"
)

CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="EPUB/content.opf"
      media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

DOCUMENT = """<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{title}</title></head>
<body><h1 class="chapter-title">{title}</h1>
<section class="chapter-body">{body}</section></body></html>
"""


def make_epub(path: Path, parts: list[tuple[str, str, str]]) -> Path:
    """Build an EPUB whose spine order is the order of parts.

    Each part is a file name, a title, and a body. The files are written to the
    archive in reverse, so a reader that trusts the order of the archive rather
    than the spine gets the book backwards and the test catches it.
    """
    manifest = "\n".join(
        f'<item id="i{n}" href="{name}" media-type="application/xhtml+xml"/>'
        for n, (name, _, _) in enumerate(parts)
    )
    spine = "\n".join(f'<itemref idref="i{n}"/>' for n in range(len(parts)))
    opf = f"""<?xml version='1.0' encoding='UTF-8'?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="p">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Book</dc:title></metadata>
  <manifest>{manifest}</manifest>
  <spine>{spine}</spine>
</package>
"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("META-INF/container.xml", CONTAINER)
        archive.writestr("EPUB/content.opf", opf)
        for name, title, body in reversed(parts):
            archive.writestr(f"EPUB/{name}", DOCUMENT.format(title=title, body=body))
    return path


@pytest.fixture
def source():
    return load_grammar(EXAMPLE).source


def test_reads_chapters_in_spine_order_and_not_archive_order(tmp_path, source):
    book = make_epub(
        tmp_path / "a.epub",
        [
            ("one.xhtml", "(Chapter 1 || Volume 1) First.", "<p>one</p>"),
            ("two.xhtml", "(Chapter 2 || Volume 1) Second.", "<p>two</p>"),
        ],
    )
    chapters = read_file(book, source)
    assert [c.number for c in chapters] == [1, 2]
    assert [c.title for c in chapters] == ["First.", "Second."]


def test_takes_the_body_and_leaves_the_heading_out(tmp_path, source):
    book = make_epub(
        tmp_path / "a.epub",
        [("one.xhtml", "(Chapter 1 || Volume 1) First.", "<p>hello</p>")],
    )
    (chapter,) = read_file(book, source)
    assert chapter.body == "<p>hello</p>"
    assert "chapter-title" not in chapter.body


def test_a_document_that_is_not_a_chapter_is_passed_over(tmp_path, source):
    book = make_epub(
        tmp_path / "a.epub",
        [
            ("cover.xhtml", "Cover", "<p>cover</p>"),
            ("one.xhtml", "(Chapter 1 || Volume 1) First.", "<p>one</p>"),
        ],
    )
    assert [c.number for c in read_file(book, source)] == [1]


def test_an_archive_volume_is_not_read(tmp_path, source):
    book = make_epub(
        tmp_path / "a.epub",
        [
            ("arch.xhtml", "(Chapter -1 || Archive) The Continuity.", "<p>a</p>"),
            ("one.xhtml", "(Chapter 0 || Prologue) Point - Null.", "<p>b</p>"),
        ],
    )
    chapters = read_file(book, source)
    assert [c.number for c in chapters] == [0]
    assert chapters[0].volume == "Prologue"


def test_a_negative_chapter_number_is_read(tmp_path, source):
    book = make_epub(
        tmp_path / "a.epub",
        [("x.xhtml", "(Chapter -1 || Volume 1) Before.", "<p>x</p>")],
    )
    assert read_file(book, source)[0].number == -1


def test_two_files_join_and_a_repeated_chapter_is_taken_one_time(tmp_path, source):
    one = make_epub(
        tmp_path / "one.epub",
        [
            ("a.xhtml", "(Chapter 1 || Volume 1) First.", "<p>from one</p>"),
            ("b.xhtml", "(Chapter 2 || Volume 1) Second.", "<p>b</p>"),
        ],
    )
    two = make_epub(
        tmp_path / "two.epub",
        [
            ("a.xhtml", "(Chapter 1 || Volume 1) First.", "<p>from two</p>"),
            ("c.xhtml", "(Chapter 3 || Volume 2) Third.", "<p>c</p>"),
        ],
    )
    chapters = read_book([one, two], source)
    assert [c.number for c in chapters] == [1, 2, 3]
    assert chapters[0].body == "<p>from one</p>"


def test_the_chapters_come_back_in_order_of_number(tmp_path, source):
    two = make_epub(
        tmp_path / "two.epub",
        [("c.xhtml", "(Chapter 9 || Volume 2) Later.", "<p>c</p>")],
    )
    one = make_epub(
        tmp_path / "one.epub",
        [("a.xhtml", "(Chapter 2 || Volume 1) Early.", "<p>a</p>")],
    )
    assert [c.number for c in read_book([two, one], source)] == [2, 9]


def test_a_file_that_does_not_exist_is_named(tmp_path, source):
    with pytest.raises(SourceError, match="the file does not exist"):
        read_file(tmp_path / "absent.epub", source)


def test_a_file_that_is_not_a_zip_is_named(tmp_path, source):
    bad = tmp_path / "bad.epub"
    bad.write_text("not an epub", encoding="utf-8")
    with pytest.raises(SourceError, match="this is not an EPUB file"):
        read_file(bad, source)


def test_a_zip_without_a_container_is_named(tmp_path, source):
    bad = tmp_path / "bad.epub"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("hello.txt", "hello")
    with pytest.raises(SourceError, match=r"has no META-INF/container\.xml"):
        read_file(bad, source)


def test_an_empty_spine_is_named(tmp_path, source):
    bad = tmp_path / "bad.epub"
    make_epub(bad, [])
    with pytest.raises(SourceError, match="empty spine"):
        read_file(bad, source)
