import pytest

from openbook.corrections import EMPTY, Corrections, load_corrections, settle, used_by
from openbook.errors import ConfigError


def test_a_correction_replaces_the_whole_line():
    corrections = Corrections(entries={"He said Vazroth.": "He said Vaz-roth."})
    assert corrections.apply("He said Vazroth.") == "He said Vaz-roth."


def test_a_line_with_no_correction_is_left_alone():
    corrections = Corrections(entries={"One line.": "Another."})
    assert corrections.apply("A different line.") == "A different line."


def test_the_spacing_of_a_line_does_not_have_to_match():
    # A person typing an entry by hand cannot reproduce the spacing of the
    # book, and no two different lines become the same one by this.
    corrections = Corrections(entries={"He  said\n  Vazroth.": "Said."})
    assert corrections.apply("He said Vazroth.") == "Said."


def test_the_case_of_a_line_does_have_to_match():
    # Capitals reach the engine and change what it says, so two lines that
    # differ only in case are two different lines.
    corrections = Corrections(entries={"HELP": "Help."})
    assert corrections.apply("help") == "help"


def test_no_corrections_change_nothing():
    assert EMPTY.apply("Nothing changes.") == "Nothing changes."
    assert len(EMPTY) == 0


def test_a_file_that_is_not_there_corrects_nothing(tmp_path):
    assert len(load_corrections(tmp_path / "absent.toml")) == 0


def test_a_file_is_read(tmp_path):
    path = tmp_path / "corrections.toml"
    path.write_text('[corrections]\n"He said." = "He whispered."\n', encoding="utf-8")
    assert load_corrections(path).says("He said.") == "He whispered."


def test_a_blank_answer_is_a_line_still_waiting(tmp_path):
    # The page writes each marked line with its answer left blank.
    path = tmp_path / "corrections.toml"
    path.write_text('[corrections]\n"He said." = ""\n', encoding="utf-8")
    corrections = load_corrections(path)
    assert len(corrections) == 0
    assert corrections.waiting == ("He said.",)
    assert corrections.apply("He said.") == "He said."


def test_an_answer_that_repeats_the_question_is_refused(tmp_path):
    # It would make the same audio under the same key, so nothing would be
    # remade and it would look like a correction that did not take.
    path = tmp_path / "corrections.toml"
    path.write_text('[corrections]\n"He said." = "He said."\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="same words again"):
        load_corrections(path)


def test_an_entry_with_no_line_is_refused(tmp_path):
    path = tmp_path / "corrections.toml"
    path.write_text('[corrections]\n"  " = "Words."\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="no line to match"):
        load_corrections(path)


def test_a_key_that_nothing_reads_is_refused(tmp_path):
    path = tmp_path / "corrections.toml"
    path.write_text('[correction]\n"He said." = "x"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="nothing reads this key"):
        load_corrections(path)


def test_used_by_names_the_corrections_that_have_a_line_here():
    corrections = Corrections(entries={"One.": "1.", "Two.": "2."})
    assert used_by(["One.", "Three."], corrections) == ("One.",)


def test_used_by_with_no_corrections_is_empty():
    assert used_by(["One."], EMPTY) == ()


def test_settle_collapses_every_run_of_space():
    assert settle("  a \n b\tc ") == "a b c"
