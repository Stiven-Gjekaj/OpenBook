import pytest

from openbook.errors import ConfigError
from openbook.lexicon import EMPTY, Lexicon, find_unknown, is_known, load_lexicon


def test_a_lexicon_replaces_a_whole_word():
    lexicon = Lexicon(entries={"Nilah": "Nee-lah"})
    assert lexicon.apply("Nilah rises.") == "Nee-lah rises."


def test_a_lexicon_does_not_reach_inside_another_word():
    # A rule for "Ivy" must not change "Ivory".
    lexicon = Lexicon(entries={"Ivy": "Eye-vee"})
    assert lexicon.apply("The ivory was hers.") == "The ivory was hers."


def test_a_lexicon_ignores_the_case_of_a_word():
    lexicon = Lexicon(entries={"nilah": "Nee-lah"})
    assert lexicon.apply("NILAH and Nilah") == "Nee-lah and Nee-lah"


def test_an_empty_lexicon_changes_nothing():
    assert EMPTY.apply("Nothing changes.") == "Nothing changes."


def test_a_lexicon_file_that_is_not_there_is_empty(tmp_path):
    assert len(load_lexicon(tmp_path / "absent.toml")) == 0


def test_a_lexicon_file_is_read(tmp_path):
    path = tmp_path / "lexicon.toml"
    path.write_text('[words]\nNilah = "Nee-lah"\n', encoding="utf-8")
    assert load_lexicon(path).says("nilah") == "Nee-lah"


def test_an_entry_that_is_not_one_word_is_refused(tmp_path):
    path = tmp_path / "lexicon.toml"
    path.write_text('[words]\n"two words" = "x"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="is not one word"):
        load_lexicon(path)


KNOWN = {"walk", "move", "try", "story", "run", "you", "vote", "happy"}


@pytest.mark.parametrize(
    "word",
    [
        "walk",
        "walks",
        "walked",
        "walking",
        "moved",
        "moving",
        "tried",
        "stories",
        "happier",
        "happiest",
        "happily",
        "you're",
        "you've",
        "you'd",
    ],
)
def test_a_word_built_from_a_known_one_is_known(word):
    # A word list holds base forms. Without this every past tense in the book
    # looks like an invented name and buries the real ones.
    assert is_known(word, KNOWN)


@pytest.mark.parametrize("word", ["vazroth", "nilah", "vazroth's", "yseult"])
def test_an_invented_name_is_not_known(word):
    assert not is_known(word, KNOWN)


def test_an_irregular_form_is_known_without_being_in_the_list():
    assert is_known("began", set())
    assert is_known("children", set())
    assert is_known("i'm", set())


def test_the_finder_counts_and_orders_by_how_often_a_word_appears():
    spoken = [(1, "Vazroth spoke."), (2, "Vazroth again."), (3, "Nilah once.")]
    found = find_unknown(spoken, EMPTY, known={"spoke", "again", "once"})
    assert [(f.word, f.count) for f in found] == [("vazroth", 2), ("nilah", 1)]


def test_the_finder_names_the_first_chapter_a_word_appears_in():
    spoken = [(5, "Nothing here."), (9, "Vazroth arrives."), (12, "Vazroth again.")]
    found = find_unknown(spoken, EMPTY, known={"nothing", "here", "arrives", "again"})
    assert found[0].chapter == 9


def test_a_word_the_lexicon_answers_does_not_come_back():
    spoken = [(1, "Vazroth spoke.")]
    lexicon = Lexicon(entries={"Vazroth": "Vaz-roth"})
    assert find_unknown(spoken, lexicon, known={"spoke"}) == []


def test_a_word_may_begin_with_an_apostrophe():
    """The book elides at both ends, "ya'" and "'bout".

    Before the leading one was allowed, a word began at the first letter and
    the mark was left outside it, so there was no way to write an entry for
    "'bout" at all.
    """
    lexicon = Lexicon(entries={"'bout": "bout", "ya'": "ya"})
    assert lexicon.apply("How 'bout it?") == "How bout it?"
    assert lexicon.apply("I'll call ya' Zero!") == "I'll call ya Zero!"


def test_a_quotation_mark_is_not_part_of_the_word():
    # "'But" opens a quotation. An entry for "but" answers the letters and the
    # mark stays where the author put it.
    lexicon = Lexicon(entries={"but": "BUT"})
    assert lexicon.apply("say 'But someone has to'") == "say 'BUT someone has to'"


def test_a_word_with_no_entry_keeps_its_apostrophe():
    lexicon = Lexicon(entries={"woah": "whoa"})
    assert lexicon.apply("How 'bout it?") == "How 'bout it?"
    assert lexicon.apply("say 'But someone'") == "say 'But someone'"


def test_an_entry_beginning_with_an_apostrophe_is_accepted(tmp_path):
    path = tmp_path / "lexicon.toml"
    path.write_text('[words]\n"\'bout" = "bout"\n', encoding="utf-8")
    assert load_lexicon(path).says("'bout") == "bout"


def test_the_elision_wins_over_the_letters_when_both_are_written():
    # An entry for the whole word is the more exact answer of the two.
    lexicon = Lexicon(entries={"'bout": "bout", "bout": "round"})
    assert lexicon.apply("'bout") == "bout"


def test_a_word_opening_with_a_quotation_mark_is_not_an_invented_name():
    # Widening a word to hold a leading apostrophe let every opening quotation
    # mark into the report. "'But" is known when "but" is.
    known = {"but", "bout"}
    assert is_known("'but", known)
    assert is_known("'bout", known)
    assert not is_known("'vazroth", known)


def test_an_apostrophe_on_its_own_is_not_a_word():
    assert not is_known("'", {"but"})
