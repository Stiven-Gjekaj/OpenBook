import shutil
from pathlib import Path

import pytest

from openbook.cli import main
from test_epub import make_epub

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "soultale"


@pytest.fixture
def project(tmp_path):
    """A project directory with the example configuration and a small book."""
    shutil.copy(EXAMPLES / "cast.toml", tmp_path / "cast.toml")
    grammar = (EXAMPLES / "grammar.toml").read_text(encoding="utf-8")
    grammar = grammar.replace(
        'files = ["soultale-definitivus-pt-1.epub", "soultale-definitivus-pt-2.epub"]',
        'files = ["book.epub"]',
    )
    (tmp_path / "grammar.toml").write_text(grammar, encoding="utf-8")
    make_epub(
        tmp_path / "book.epub",
        [
            ("a.xhtml", "(Chapter -1 || Archive) The Continuity.", "<p>skip</p>"),
            ("b.xhtml", "(Chapter 0 || Prologue) Point - Null.", "<p>one</p>"),
            ("c.xhtml", "(Chapter 3 || Volume 1) Wandering Spirit.", "<p>two</p>"),
            ("d.xhtml", "(Chapter 23 || Volume 2) Snowflake.", "<p>three</p>"),
        ],
    )
    return tmp_path


def test_chapters_lists_the_book_without_the_archive(project, capsys):
    assert main(["-C", str(project), "chapters"]) == 0
    out = capsys.readouterr().out
    assert "Point - Null." in out
    assert "The Continuity." not in out


def test_the_prologue_is_listed_under_volume_one(project, capsys):
    assert main(["-C", str(project), "chapters"]) == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert lines[0].split()[1:3] == ["Volume", "1"]


def test_chapters_can_show_one_volume(project, capsys):
    assert main(["-C", str(project), "chapters", "--volume", "Volume 1"]) == 0
    out = capsys.readouterr().out
    assert "Wandering Spirit." in out
    assert "Snowflake." not in out


def test_a_volume_that_does_not_exist_is_named(project, capsys):
    assert main(["-C", str(project), "chapters", "--volume", "Volume 4"]) == 2
    assert "no volume is named 'Volume 4'" in capsys.readouterr().err


def test_check_reports_that_the_cast_is_not_finished(project, capsys):
    # The example cast ships with no voices, so check must say so and give back
    # a code that is not zero.
    assert main(["-C", str(project), "check"]) == 1
    out = capsys.readouterr().out
    assert "the narrator has no voice yet" in out
    assert "not ready" in out


def test_check_names_a_book_file_that_is_absent(project, capsys):
    (project / "book.epub").unlink()
    assert main(["-C", str(project), "check"]) == 1
    assert "missing" in capsys.readouterr().err


def test_a_configuration_that_does_not_exist_gives_one_line(tmp_path, capsys):
    assert main(["-C", str(tmp_path), "check"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("openbook: ")
    assert "the file does not exist" in err
