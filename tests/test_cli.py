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


def cast_with_voices(project):
    """Give every code in the example cast a voice, so a render can run."""
    import re

    path = project / "cast.toml"
    text = path.read_text(encoding="utf-8")
    count = [0]

    def fill(_):
        count[0] += 1
        return f'voice = "v{count[0]:03d}"'

    path.write_text(re.sub(r'voice = ""', fill, text), encoding="utf-8")
    return project


def test_check_is_ready_once_every_voice_is_chosen(project, capsys):
    # Being ready includes having ffmpeg, so this cannot pass without it.
    import shutil

    if not shutil.which("ffmpeg"):
        import pytest

        pytest.skip("ffmpeg is not installed")
    assert main(["-C", str(cast_with_voices(project)), "check"]) == 0
    assert "ready" in capsys.readouterr().out


def test_plan_prints_a_line_with_its_voice(project, capsys):
    cast_with_voices(project)
    assert main(["-C", str(project), "plan", "--volume", "Volume 1"]) == 0
    assert "Point - Null." in capsys.readouterr().out


def test_plan_can_show_one_chapter(project, capsys):
    cast_with_voices(project)
    assert (
        main(["-C", str(project), "plan", "--volume", "Volume 1", "--chapter", "3"])
        == 0
    )
    out = capsys.readouterr().out
    assert "chapter 3" in out
    assert "chapter 0" not in out


def test_notes_reports_what_the_parser_noticed(project, capsys):
    assert main(["-C", str(project), "notes"]) == 0
    assert "notes" in capsys.readouterr().err


def test_a_dry_run_makes_nothing(project, capsys):
    cast_with_voices(project)
    assert (
        main(["-C", str(project), "render", "--volume", "Volume 1", "--dry-run"]) == 0
    )
    assert "utterances" in capsys.readouterr().out
    assert not (project / "out").exists()


def test_a_render_writes_a_file_and_reuses_it(project, capsys):
    import shutil

    if not shutil.which("ffmpeg"):
        import pytest

        pytest.skip("ffmpeg is not installed")

    cast_with_voices(project)
    assert main(["-C", str(project), "render", "--volume", "Volume 1"]) == 0
    first = capsys.readouterr().out
    assert "Soultale - Volume 1.m4b" in first
    assert (project / "out" / "Soultale - Volume 1.m4b").exists()

    assert main(["-C", str(project), "render", "--volume", "Volume 1"]) == 0
    assert "0 made" in capsys.readouterr().out


def test_a_render_of_a_volume_that_does_not_exist_is_named(project, capsys):
    cast_with_voices(project)
    assert main(["-C", str(project), "render", "--volume", "Volume 9"]) == 2
    assert "no volume is named 'Volume 9'" in capsys.readouterr().err


def test_a_render_stops_when_a_code_has_no_voice(project, capsys):
    # The example ships uncast. A render must refuse rather than narrate.
    assert main(["-C", str(project), "render", "--volume", "Volume 1"]) == 2
    assert "no voice" in capsys.readouterr().err


def test_the_cache_reports_what_it_holds(project, capsys):
    assert main(["-C", str(project), "cache"]) == 0
    assert "pieces" in capsys.readouterr().out


def test_words_lists_what_needs_a_pronunciation(project, capsys):
    import openbook.cli as cli

    # A small word list, so the test does not depend on the machine having one.
    monkey = {"the", "light", "arrives"}
    import openbook.lexicon as lexicon_module

    real = lexicon_module.known_words
    lexicon_module.known_words = lambda: monkey
    try:
        assert cli.main(["-C", str(project), "words"]) == 0
    finally:
        lexicon_module.known_words = real
    assert "words have no entry" in capsys.readouterr().err


def test_a_lexicon_entry_reaches_the_render(project, capsys):
    cast_with_voices(project)
    (project / "lexicon.toml").write_text(
        '[words]\nPoint = "Poynt"\n', encoding="utf-8"
    )
    assert main(["-C", str(project), "plan", "--volume", "Volume 1"]) == 0
    assert "Poynt" in capsys.readouterr().out


def test_the_plan_totals_describe_what_was_printed(project, capsys):
    # A person who asks for one chapter must not be given the number that
    # belongs to the whole volume.
    cast_with_voices(project)
    main(["-C", str(project), "plan", "--volume", "Volume 1", "--chapter", "0"])
    one = capsys.readouterr().err
    main(["-C", str(project), "plan", "--volume", "Volume 1"])
    whole = capsys.readouterr().err
    assert "1 chapters" in one
    assert "1 chapters" not in whole


def test_a_chapter_that_is_not_in_the_volume_is_named(project, capsys):
    cast_with_voices(project)
    assert (
        main(["-C", str(project), "plan", "--volume", "Volume 1", "--chapter", "99"])
        == 2
    )
    assert "has no chapter 99" in capsys.readouterr().err


def test_a_render_writes_captions_beside_the_audiobook(project, capsys):
    import shutil

    if not shutil.which("ffmpeg"):
        import pytest

        pytest.skip("ffmpeg is not installed")

    cast_with_voices(project)
    assert main(["-C", str(project), "render", "--volume", "Volume 1"]) == 0
    captions = project / "out" / "Soultale - Volume 1.srt"
    assert captions.exists()
    # Sound with no picture has nothing else marking where a chapter begins,
    # so the announcements belong in these captions.
    assert "Chapter 0." in captions.read_text(encoding="utf-8")


def test_a_render_can_write_a_review_page(project, capsys):
    import shutil

    if not shutil.which("ffmpeg"):
        import pytest

        pytest.skip("ffmpeg is not installed")

    cast_with_voices(project)
    assert main(["-C", str(project), "render", "--volume", "Volume 1", "--review"]) == 0
    page = project / "out" / "review - Volume 1.html"
    assert page.exists()
    assert "Point - Null." in page.read_text(encoding="utf-8")


def test_the_lexicon_it_writes_is_one_it_can_read(project, capsys):
    # A tool that writes a file it cannot read back is worse than one that
    # writes nothing. Many of these words hold an apostrophe, which TOML does
    # not accept in a name unless the name is quoted.
    import openbook.lexicon as lexicon_module

    real = lexicon_module.known_words
    lexicon_module.known_words = lambda: {"the", "light", "arrives"}
    try:
        assert main(["-C", str(project), "words", "--write"]) == 0
    finally:
        lexicon_module.known_words = real

    written = project / "lexicon.toml"
    assert written.exists()
    from openbook.lexicon import load_lexicon

    assert len(load_lexicon(written)) >= 0


def test_a_lexicon_that_exists_is_not_written_over(project, capsys):
    # Whatever is in there was written by hand and must not be lost.
    (project / "lexicon.toml").write_text(
        '[words]\nNilah = "Nee-lah"\n', encoding="utf-8"
    )
    assert main(["-C", str(project), "words", "--write"]) == 2
    assert "exists already" in capsys.readouterr().err
    assert "Nee-lah" in (project / "lexicon.toml").read_text(encoding="utf-8")
