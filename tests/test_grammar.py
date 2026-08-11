from pathlib import Path

import pytest

from openbook.config.grammar import load_grammar
from openbook.errors import ConfigError

EXAMPLE = (
    Path(__file__).resolve().parent.parent / "examples" / "soultale" / "grammar.toml"
)

MINIMAL = """
[source]
format = "epub"
files = ["book.epub"]
chapter_title = "(Chapter {NUMBER} || {VOLUME}) {TITLE}"
number_pattern = '-?\\d+'
volume_pattern = '[^)]+'
skip_volume_pattern = '^Archive'
chapter_announcement = "Chapter {NUMBER}. {TITLE}"
chapter_announcement_named = "{VOLUME}. {TITLE}"

[grammar]
dialogue_elements = ["b", "strong"]
dialogue = "{SPEAKER}: {TEXT}"
speaker_pattern = '[A-Z0-9?/#&][A-Z0-9?/#& ]{1,13}'
split_at_line_break = true
action = '\\*(?P<TEXT>[^*\\n]{1,80})\\*'

[grammar.unison]
separator = " & "
mode = "voice_blend"

[grammar.structure]
end_matter_element = "u"
scene_break = '^\\s*-{3,}\\s*$'
strip_elements = ["i", "em", "b", "strong"]

[render]
read_chapter_names = true
read_end_matter = false
pause_dialogue_to_narration = "400ms"
pause_narration_to_dialogue = "600ms"
pause_at_scene_break = "2s"
pause_after_chapter_name = "1s"
action = "pause"
pause_at_action = "500ms"

[output]
group_by = "volume"
file_name = "Soultale - {VOLUME}.m4b"

[output.merge_volumes]
"Prologue" = "Volume 1"
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "grammar.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_example_that_ships_with_the_project_loads():
    # The example is the only grammar the project has. A change that breaks it
    # breaks the whole tool, so the test suite reads the real file.
    grammar = load_grammar(EXAMPLE)
    assert grammar.source.format == "epub"
    assert grammar.output.group_by == "volume"


def test_the_chapter_title_template_reads_a_real_title():
    grammar = load_grammar(EXAMPLE)
    found = grammar.source.chapter_title.match(
        "(Chapter 230 || Volume 7) The Poison Chooses."
    )
    assert found is not None
    assert found["NUMBER"] == "230"
    assert found["VOLUME"] == "Volume 7"


def test_the_archive_volumes_are_skipped_and_the_prologue_is_not():
    grammar = load_grammar(EXAMPLE)
    assert grammar.source.is_skipped("Archive")
    assert grammar.source.is_skipped("Archive Pt.2")
    assert not grammar.source.is_skipped("Prologue")
    assert not grammar.source.is_skipped("Volume 1")


def test_the_prologue_stands_on_its_own():
    # The book gives chapters 0 to 2 a volume of their own, and the example
    # merges nothing, so the prologue becomes its own file and its own video.
    grammar = load_grammar(EXAMPLE)
    assert grammar.output.merge_volumes == {}
    assert grammar.output.group_of("Prologue") == "Prologue"
    assert grammar.output.group_of("Volume 3") == "Volume 3"


def test_a_volume_can_be_put_into_the_file_of_another(tmp_path):
    # The example does not use this. A volume too short to stand alone does.
    # MINIMAL carries the mapping, because this is where it is tested now.
    grammar = load_grammar(write(tmp_path, MINIMAL))
    assert grammar.output.group_of("Prologue") == "Volume 1"
    assert grammar.output.group_for(0, "Prologue") == "Volume 1"
    assert grammar.output.group_of("Volume 3") == "Volume 3"


def test_the_pauses_become_seconds():
    grammar = load_grammar(EXAMPLE)
    assert grammar.render.dialogue_to_narration == 0.4
    assert grammar.render.narration_to_dialogue == 0.6
    assert grammar.render.at_scene_break == 2.0


def test_both_bold_elements_are_accepted(tmp_path):
    grammar = load_grammar(write(tmp_path, MINIMAL))
    assert grammar.dialogue.elements == frozenset({"b", "strong"})


def test_the_action_pattern_finds_a_stage_direction(tmp_path):
    grammar = load_grammar(write(tmp_path, MINIMAL))
    found = grammar.dialogue.action.search(
        "You want to try that again? *circling warily*"
    )
    assert found is not None
    assert found.group("TEXT") == "circling warily"


def test_a_missing_key_names_the_file_and_the_key(tmp_path):
    text = MINIMAL.replace('end_matter_element = "u"\n', "")
    with pytest.raises(ConfigError, match=r"end_matter_element: this key is required"):
        load_grammar(write(tmp_path, text))


def test_a_key_that_nothing_reads_is_refused(tmp_path):
    text = MINIMAL.replace("[output]\n", '[output]\nfile_nme = "x"\n')
    with pytest.raises(ConfigError, match="nothing reads this key"):
        load_grammar(write(tmp_path, text))


def test_a_file_name_without_the_volume_is_refused(tmp_path):
    # Without the name of the volume every volume writes over the one before.
    text = MINIMAL.replace('"Soultale - {VOLUME}.m4b"', '"Soultale.m4b"')
    with pytest.raises(ConfigError, match=r"must contain \{VOLUME\}"):
        load_grammar(write(tmp_path, text))


def test_an_unknown_unison_mode_is_refused(tmp_path):
    text = MINIMAL.replace('mode = "voice_blend"', 'mode = "average"')
    with pytest.raises(ConfigError, match="not one of the values"):
        load_grammar(write(tmp_path, text))


def test_a_dialogue_template_without_the_text_is_refused(tmp_path):
    text = MINIMAL.replace('dialogue = "{SPEAKER}: {TEXT}"', 'dialogue = "{SPEAKER}:"')
    with pytest.raises(ConfigError, match=r"must capture \{TEXT\}"):
        load_grammar(write(tmp_path, text))


def test_a_book_with_no_files_is_refused(tmp_path):
    text = MINIMAL.replace('files = ["book.epub"]', "files = []")
    with pytest.raises(ConfigError, match="name at least one book file"):
        load_grammar(write(tmp_path, text))


def test_the_export_keeps_the_form_of_the_engine_by_default(tmp_path):
    grammar = load_grammar(write(tmp_path, MINIMAL))
    assert grammar.output.sample_rate is None
    assert grammar.output.channels is None
    assert grammar.output.bitrate == "64k"


def test_the_export_can_be_asked_for_another_rate_and_channels(tmp_path):
    # The keys go before [output.merge_volumes]. A bare key written after a
    # sub-table header belongs to that sub-table, which is the easiest mistake
    # to make in a TOML file and gives a puzzling error far from its cause.
    text = MINIMAL.replace(
        'file_name = "Soultale - {VOLUME}.m4b"',
        'file_name = "Soultale - {VOLUME}.m4b"\n'
        'bitrate = "128k"\nsample_rate = 48000\nchannels = 2',
    )
    grammar = load_grammar(write(tmp_path, text))
    assert grammar.output.sample_rate == 48000
    assert grammar.output.channels == 2
    assert grammar.output.bitrate == "128k"


def test_the_intro_and_outro_are_empty_unless_asked_for(tmp_path):
    grammar = load_grammar(write(tmp_path, MINIMAL))
    assert grammar.render.intro == ""
    assert grammar.render.outro == ""
    assert grammar.render.intro_title == "Introduction"


def test_the_intro_and_outro_are_the_words_the_author_wrote(tmp_path):
    added = (
        'action = "pause"\nintro = "Welcome to {VOLUME}."\noutro = "That was {VOLUME}."'
    )
    text = MINIMAL.replace('action = "pause"', added)
    grammar = load_grammar(write(tmp_path, text))
    assert grammar.render.intro == "Welcome to {VOLUME}."
    assert grammar.render.outro == "That was {VOLUME}."


VIDEO = """
[video]
file_name = "Soultale - {VOLUME}.mp4"
visual = "cover.png"
description = "A book about a world that begins again."
"""


def test_a_release_can_carry_a_description_of_its_own(tmp_path):
    # A prologue and a volume go out as separate videos, and what is worth
    # saying about one is not what is worth saying about the other.
    text = MINIMAL + VIDEO + '\n[video.descriptions]\nPrologue = "Where it starts."\n'
    grammar = load_grammar(write(tmp_path, text))
    assert grammar.video.description_for("Prologue") == "Where it starts."


def test_a_release_nobody_wrote_one_for_takes_the_general_words(tmp_path):
    # An empty description is worse than a general one.
    text = MINIMAL + VIDEO + '\n[video.descriptions]\nPrologue = "Where it starts."\n'
    grammar = load_grammar(write(tmp_path, text))
    assert grammar.video.description_for("Volume 2") == (
        "A book about a world that begins again."
    )


def test_a_book_with_one_description_uses_it_everywhere(tmp_path):
    grammar = load_grammar(write(tmp_path, MINIMAL + VIDEO))
    assert grammar.video.descriptions == {}
    assert grammar.video.description_for("Prologue") == (
        "A book about a world that begins again."
    )


def test_a_book_with_no_parts_groups_by_volume(tmp_path):
    grammar = load_grammar(write(tmp_path, MINIMAL))
    assert grammar.output.parts == {}
    assert grammar.output.group_for(5, "Volume 1") == "Volume 1"


def test_a_named_span_of_chapters_becomes_its_own_file(tmp_path):
    # A volume of four hours is a long listen and a long upload. Where a part
    # ends is a decision about the story, so it is written down.
    text = MINIMAL.replace(
        'file_name = "Soultale - {VOLUME}.m4b"',
        'file_name = "Soultale - {VOLUME}.m4b"\n\n[output.parts]\n'
        '"Volume 1, Part 1" = "0-12"\n"Volume 1, Part 2" = "13-22"',
    )
    grammar = load_grammar(write(tmp_path, text))
    assert grammar.output.group_for(0, "Prologue") == "Volume 1, Part 1"
    assert grammar.output.group_for(12, "Volume 1") == "Volume 1, Part 1"
    assert grammar.output.group_for(13, "Volume 1") == "Volume 1, Part 2"


def test_a_chapter_outside_every_span_keeps_its_volume(tmp_path):
    text = MINIMAL.replace(
        'file_name = "Soultale - {VOLUME}.m4b"',
        'file_name = "Soultale - {VOLUME}.m4b"\n\n[output.parts]\n"Early" = "0-12"',
    )
    grammar = load_grammar(write(tmp_path, text))
    assert grammar.output.group_for(40, "Volume 2") == "Volume 2"


def test_a_span_that_is_not_chapters_is_refused(tmp_path):
    text = MINIMAL.replace(
        'file_name = "Soultale - {VOLUME}.m4b"',
        'file_name = "Soultale - {VOLUME}.m4b"\n\n[output.parts]\n"Bad" = "the middle"',
    )
    with pytest.raises(ConfigError, match="does not name a chapter"):
        load_grammar(write(tmp_path, text))
