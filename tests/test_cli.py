import shutil
from pathlib import Path

import pytest

from openbook.cli import main
from test_epub import make_epub

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "soultale"

# Writing an M4B needs ffmpeg, and CI installs it on one runner of the six.
needs_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg"), reason="ffmpeg is not installed"
)


def point_at_one_book(grammar: str) -> str:
    """Aim the example grammar at the small book a test builds.

    The names of the real files are matched by shape and not written out here,
    so that renaming the manuscript, or moving it into a directory, does not
    break every test that reads a book.
    """
    import re

    made = re.sub(r"files = \[[^\]]*\]", 'files = ["book.epub"]', grammar, count=1)
    assert made != grammar, "the example grammar no longer names its book files"
    return made


@pytest.fixture
def project(tmp_path):
    """A project directory with the example configuration and a small book."""
    shutil.copy(EXAMPLES / "cast.toml", tmp_path / "cast.toml")
    grammar = point_at_one_book((EXAMPLES / "grammar.toml").read_text("utf-8"))
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
    cast_with_no_voices(project)
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


def cast_with_no_voices(project):
    """Blank every voice in the cast.

    The example is a working project now and some of it is cast. A test that
    needs an unfinished cast makes one rather than trusting a shipped file to
    stay blank for ever.
    """
    import re

    path = project / "cast.toml"
    path.write_text(
        re.sub(r'voice = "[^"]*"', 'voice = ""', path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    return project


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


@needs_ffmpeg
def test_check_is_ready_once_every_voice_is_chosen(project, capsys):
    # Being ready includes having ffmpeg, so this cannot pass without it.
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


@needs_ffmpeg
def test_a_render_writes_a_file_and_reuses_it(project, capsys):
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
    cast_with_no_voices(project)
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


@needs_ffmpeg
def test_a_render_writes_captions_beside_the_audiobook(project, capsys):
    cast_with_voices(project)
    assert main(["-C", str(project), "render", "--volume", "Volume 1"]) == 0
    captions = project / "out" / "Soultale - Volume 1.srt"
    assert captions.exists()
    # Sound with no picture has nothing else marking where a chapter begins,
    # so the announcements belong in these captions.
    assert "Chapter 0." in captions.read_text(encoding="utf-8")


@needs_ffmpeg
def test_a_render_can_write_a_review_page(project, capsys):
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
    # Whatever is in there was written by hand and must not be lost. This is
    # checked before anything about the machine, so a person whose real problem
    # is a file they wrote is not told about a missing word list.
    (project / "lexicon.toml").write_text(
        '[words]\nNilah = "Nee-lah"\n', encoding="utf-8"
    )
    assert main(["-C", str(project), "words", "--write"]) == 2
    assert "exists already" in capsys.readouterr().err
    assert "Nee-lah" in (project / "lexicon.toml").read_text(encoding="utf-8")


def corrections(project, text):
    (project / "corrections.toml").write_text(text, encoding="utf-8")
    return project


@needs_ffmpeg
def test_a_render_says_how_many_corrections_it_used(project, capsys):
    cast_with_voices(project)
    corrections(project, '[corrections]\n"two" = "too"\n"absent" = "gone"\n')
    assert main(["-C", str(project), "render", "--volume", "Volume 1"]) == 0
    out = capsys.readouterr().out
    assert "corrections 1 used, 1 for no line in this volume" in out


def test_a_render_with_a_correction_speaks_the_corrected_words(project, capsys):
    cast_with_voices(project)
    corrections(project, '[corrections]\n"two" = "too"\n')
    assert main(["-C", str(project), "plan", "--volume", "Volume 1"]) == 0
    out = capsys.readouterr().out
    assert "]  too" in out
    assert "]  two" not in out


def test_a_dry_run_says_how_many_corrections_it_would_use(project, capsys):
    cast_with_voices(project)
    corrections(project, '[corrections]\n"two" = "too"\n')
    assert (
        main(["-C", str(project), "render", "--volume", "Volume 1", "--dry-run"]) == 0
    )
    assert "corrections 1 used" in capsys.readouterr().out


@needs_ffmpeg
def test_a_render_says_nothing_when_there_is_no_corrections_file(project, capsys):
    cast_with_voices(project)
    assert main(["-C", str(project), "render", "--volume", "Volume 1"]) == 0
    assert "corrections" not in capsys.readouterr().out


@needs_ffmpeg
def test_a_line_still_waiting_for_words_is_counted(project, capsys):
    cast_with_voices(project)
    corrections(project, '[corrections]\n"two" = ""\n')
    assert main(["-C", str(project), "render", "--volume", "Volume 1"]) == 0
    assert "corrections 0 used, 1 still waiting for words" in capsys.readouterr().out


def test_check_refuses_a_correction_that_matches_no_line_in_the_book(project, capsys):
    # The mistake this file is most likely to hold. Nothing else finds it: the
    # render says nothing, the audio does not change, and the only way left is
    # to listen to the line again.
    cast_with_voices(project)
    corrections(project, '[corrections]\n"nobody says this" = "x"\n')
    assert main(["-C", str(project), "check"]) == 1
    out = capsys.readouterr().out
    assert "1 match no line in the book" in out
    assert "nobody says this" in out


def test_check_accepts_a_correction_for_another_volume(project, capsys):
    # The book is read whole, so a correction for volume 2 is not a mistake
    # while volume 1 is being made.
    cast_with_voices(project)
    corrections(project, '[corrections]\n"three" = "iii"\n')
    assert main(["-C", str(project), "check"]) in (0, 1)
    out = capsys.readouterr().out
    assert "match no line in the book" not in out


def test_check_does_not_blame_the_corrections_for_an_unfinished_cast(project, capsys):
    cast_with_no_voices(project)
    corrections(project, '[corrections]\n"nobody says this" = "x"\n')
    assert main(["-C", str(project), "check"]) == 1
    out = capsys.readouterr().out
    assert "not checked against the book" in out
    assert "match no line in the book" not in out


def with_intro(project, words):
    """Give the example grammar an intro for the narrator to read.

    The key goes inside the [render] table the example already has. A second
    table of the same name is not valid TOML.
    """
    path = project / "grammar.toml"
    text = path.read_text(encoding="utf-8")
    assert "\n[render]\n" in text
    path.write_text(
        text.replace("\n[render]\n", f'\n[render]\nintro = "{words}"\n', 1),
        encoding="utf-8",
    )
    return project


@needs_ffmpeg
def test_the_lexicon_reaches_the_intro(project, capsys):
    # The intro names the book and its characters, so it was the one place a
    # pronunciation entry was worth having and the one place it was ignored.
    cast_with_voices(project)
    with_intro(project, "Welcome to Vazroth.")
    (project / "lexicon.toml").write_text(
        '[words]\nVazroth = "Vaz-roth"\n', encoding="utf-8"
    )
    assert main(["-C", str(project), "render", "--volume", "Volume 1", "--review"]) == 0
    page = (project / "out" / "review - Volume 1.html").read_text(encoding="utf-8")
    assert "Vaz-roth" in page
    assert "Welcome to Vazroth." not in page


@needs_ffmpeg
def test_a_correction_reaches_the_intro(project, capsys):
    cast_with_voices(project)
    with_intro(project, "Welcome along.")
    corrections(project, '[corrections]\n"Welcome along." = "Welcome, along."\n')
    assert main(["-C", str(project), "render", "--volume", "Volume 1"]) == 0
    assert "corrections 1 used" in capsys.readouterr().out


def test_check_accepts_a_correction_for_the_intro(project, capsys):
    # The intro is made when the volume is spoken and not when it is planned,
    # so a check that only looked at the plan called this a mistake.
    cast_with_voices(project)
    with_intro(project, "Welcome along.")
    corrections(project, '[corrections]\n"Welcome along." = "Welcome, along."\n')
    main(["-C", str(project), "check"])
    assert "match no line in the book" not in capsys.readouterr().out


def test_a_book_is_read_and_parsed_once_for_one_command(project):
    # A check on 325 chapters asked thirty times and took five seconds where
    # it takes a quarter of one.
    from openbook.build import Project

    opened = Project.open(project)
    assert opened.chapters() is opened.chapters()
    assert opened.parsed() is opened.parsed()
    assert opened.volumes() is opened.volumes()


def test_a_book_file_that_goes_missing_is_still_reported(project):
    # Only the reading is kept. Whether the file is there is the caller's
    # situation and has to be answered whenever it is asked.
    from openbook.build import Project
    from openbook.errors import OpenBookError

    opened = Project.open(project)
    assert opened.chapters()
    (project / "book.epub").unlink()
    with pytest.raises(OpenBookError, match="missing"):
        opened.chapters()


def small_dictionary(words):
    """Stand in for the word list of the machine, so a test is not tied to it."""
    import openbook.lexicon as lexicon_module

    real = lexicon_module.known_words
    lexicon_module.known_words = lambda: set(words)
    return real, lexicon_module


def a_book_saying(project, text):
    make_epub(
        project / "book.epub",
        [
            ("a.xhtml", "(Chapter -1 || Archive) The Continuity.", "<p>skip</p>"),
            ("b.xhtml", "(Chapter 0 || Prologue) Point - Null.", f"<p>{text}</p>"),
        ],
    )
    return project


def words_with(project, argv, known=("the", "and")):
    real, module = small_dictionary(known)
    try:
        return main(["-C", str(project), "words", *argv])
    finally:
        module.known_words = real


def test_merge_adds_only_the_words_that_are_not_there_yet(project, capsys):
    a_book_saying(project, "Vazroth and Nilah and Astra")
    (project / "lexicon.toml").write_text(
        '[words]\n"vazroth" = "Vaz-roth"\n"nilah" = ""\n', encoding="utf-8"
    )
    assert words_with(project, ["--merge"]) == 0

    text = (project / "lexicon.toml").read_text(encoding="utf-8")
    assert text.count('"astra"') == 1
    # Answered or not, a word already written down is left where it is.
    assert text.count('"vazroth"') == 1
    assert text.count('"nilah"') == 1
    assert '"vazroth" = "Vaz-roth"' in text


def test_merge_keeps_every_answer_and_comment_already_written(project, capsys):
    # The file holds work somebody sat down and did. None of it survives a
    # tool that reads a file and writes it back out again.
    a_book_saying(project, "Vazroth and Astra")
    written = project / "lexicon.toml"
    written.write_text(
        "# My own note at the top.\n"
        "[words]\n"
        '"vazroth" = "Vaz-roth"  # I checked this one by ear\n',
        encoding="utf-8",
    )
    assert words_with(project, ["--merge"]) == 0

    text = written.read_text(encoding="utf-8")
    assert "# My own note at the top." in text
    assert '"vazroth" = "Vaz-roth"  # I checked this one by ear' in text
    assert '"astra" = ""' in text


def test_a_merged_file_reads_back(project, capsys):
    # The rule this project keeps: a tool must read what it writes.
    from openbook.lexicon import load_lexicon

    a_book_saying(project, "Vazroth and Nilah's and Astra")
    (project / "lexicon.toml").write_text(
        '[words]\n"vazroth" = "Vaz-roth"\n', encoding="utf-8"
    )
    assert words_with(project, ["--merge"]) == 0

    lexicon = load_lexicon(project / "lexicon.toml")
    assert lexicon.says("vazroth") == "Vaz-roth"
    assert lexicon.has("nilah's"), "a word holding an apostrophe survived"
    assert lexicon.has("astra")


def test_merge_says_so_when_there_is_nothing_to_add(project, capsys):
    a_book_saying(project, "Vazroth and Vazroth")
    written = project / "lexicon.toml"
    before = '[words]\n"vazroth" = "Vaz-roth"\n'
    written.write_text(before, encoding="utf-8")
    assert words_with(project, ["--merge"]) == 0
    assert "nothing to add" in capsys.readouterr().out
    assert written.read_text(encoding="utf-8") == before, "the file was not touched"


def test_merge_makes_the_table_when_the_file_has_none(project, capsys):
    from openbook.lexicon import load_lexicon

    a_book_saying(project, "Vazroth and Astra")
    (project / "lexicon.toml").write_text(
        "# Only a comment so far.\n", encoding="utf-8"
    )
    assert words_with(project, ["--merge"]) == 0
    assert load_lexicon(project / "lexicon.toml").has("astra")


def test_merge_with_no_file_names_the_flag_that_makes_one(project, capsys):
    a_book_saying(project, "Vazroth")
    assert words_with(project, ["--merge"]) == 2
    err = capsys.readouterr().err
    assert "no" in err and "--write" in err


def test_write_over_a_file_that_exists_names_merge(project, capsys):
    a_book_saying(project, "Vazroth")
    (project / "lexicon.toml").write_text("[words]\n", encoding="utf-8")
    assert words_with(project, ["--write"]) == 2
    assert "--merge" in capsys.readouterr().err


def test_write_and_merge_cannot_be_asked_for_together(project):
    with pytest.raises(SystemExit):
        main(["-C", str(project), "words", "--write", "--merge"])


def test_a_merge_that_would_not_read_back_leaves_the_file_alone(tmp_path):
    # Defensive. A lexicon holds one table, so the normal path cannot make an
    # unreadable file, and the check is here because the file it adds to holds
    # work that must not be lost to a mistake this one cannot foresee.
    from openbook.cli import _readable
    from openbook.errors import OpenBookError

    with pytest.raises(OpenBookError, match="does not read back"):
        _readable('[words]\n"a" = \n', tmp_path / "lexicon.toml", 1)


def test_a_merge_that_loses_an_entry_leaves_the_file_alone(tmp_path):
    from openbook.cli import _readable
    from openbook.errors import OpenBookError

    with pytest.raises(OpenBookError, match="where 3 were meant"):
        _readable('[words]\n"a" = ""\n', tmp_path / "lexicon.toml", 3)


def test_check_finds_a_voice_recording_that_was_never_made(project, capsys):
    # Chatterbox takes a voice from a recording. Forty of them are named in a
    # cast, and finding out after twenty minutes of rendering is too late.
    import re

    path = project / "cast.toml"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        re.sub(r'voice = ""', 'voice = "voices/nobody.wav"', text, count=3),
        encoding="utf-8",
    )
    assert main(["-C", str(project), "check", "--engine", "chatterbox"]) == 1
    out = capsys.readouterr().out
    assert "cannot find" in out
    assert "voices/nobody.wav" in out


def test_check_says_nothing_about_voices_an_engine_reads_by_name(project, capsys):
    # Kokoro takes a name and never touches the disk, so there is nothing to
    # report and the check must not invent something.
    cast_with_voices(project)
    main(["-C", str(project), "check"])
    assert "cannot find" not in capsys.readouterr().out


def test_a_card_names_a_volume_the_archive_does_not_list(project):
    """The archive names the numbered volumes and says nothing about the
    prologue. A card that showed nothing above the work would leave a listener
    with no idea where in the book they are, so the name the chapter was
    written under is used instead."""
    from openbook.build import Project, build_volume
    from openbook.cli import _volume_labels
    from openbook.speech.package import Mark

    cast_with_voices(project)
    opened = Project.open(project)
    volume = build_volume(opened, "Volume 1", max_characters=480)

    written = {c.title: c.volume for c in volume.chapters}
    assert written["Point - Null."] == "Prologue"
    assert "Prologue" not in opened.volumes(), "the archive never names it"

    marks = [Mark(title=c.title, start=0.0, end=10.0) for c in volume.chapters]
    labels = dict(
        zip(
            [m.title for m in marks],
            _volume_labels(opened, volume, marks),
            strict=True,
        )
    )

    # The prologue keeps the name it was written under, with no title beneath.
    assert labels["Point - Null."] == ("Prologue", "")
    # A volume the archive does name keeps both.
    assert labels["Wandering Spirit."][0] == "Volume 1"


def test_one_chapter_can_be_rendered_while_the_rest_is_uncast(project, capsys):
    """The reason the narrowing happens before the cast is resolved.

    A person filling in forty four voices wants to hear the chapter they have
    finished, not to wait for the other twenty two.
    """
    import re

    path = project / "cast.toml"
    text = path.read_text(encoding="utf-8")
    # Only the narrator has a voice. Every character is still waiting.
    path.write_text(
        re.sub(r'^voice = ""', 'voice = "af_heart"', text, count=1, flags=re.M),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "-C",
                str(project),
                "render",
                "--volume",
                "Volume 1",
                "--chapter",
                "0",
                "--dry-run",
            ]
        )
        == 0
    )
    assert "1 chapters" in capsys.readouterr().out


def test_a_chapter_that_is_not_in_the_volume_is_named_by_render(project, capsys):
    cast_with_voices(project)
    assert (
        main(
            [
                "-C",
                str(project),
                "render",
                "--volume",
                "Volume 1",
                "--chapter",
                "99",
                "--dry-run",
            ]
        )
        == 2
    )
    assert "has no chapter 99" in capsys.readouterr().err


def test_one_chapter_keeps_the_number_its_volume_gives_it(project):
    """A card must read Chapter 0 of 2, not Chapter 1 of 1. The volume is
    narrowed but the book is not, so the count comes from the whole book."""
    from openbook.build import Project, build_volume
    from openbook.cast import last_chapters

    cast_with_voices(project)
    opened = Project.open(project)
    volume = build_volume(opened, "Volume 1", max_characters=480, only=0)
    assert len(volume.chapters) == 1
    assert len(volume.every) > 1, "the whole book is still there to count with"
    last = last_chapters(volume.every)
    assert last[volume.chapters[0].volume] >= volume.chapters[0].number
