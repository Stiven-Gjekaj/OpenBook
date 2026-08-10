import pytest

from openbook.plan import split_sentences


def test_divides_at_a_full_stop():
    assert split_sentences("She walked home. It was late.") == (
        "She walked home.",
        "It was late.",
    )


def test_divides_at_a_question_and_at_an_exclamation():
    assert split_sentences("Is he dead? No. Run!") == ("Is he dead?", "No.", "Run!")


def test_keeps_every_word():
    # The text comes back when the sentences are joined. A divider that loses a
    # character loses it from the audio, where nobody sees it go.
    text = "One. Two! Three? Four."
    assert " ".join(split_sentences(text)) == text


def test_empty_text_gives_nothing():
    assert split_sentences("") == ()
    assert split_sentences("   ") == ()


def test_runs_of_space_become_one_space():
    assert split_sentences("One.   Two.") == ("One.", "Two.")


def test_a_title_is_not_the_end_of_a_sentence():
    assert split_sentences("Mr. Hendricks was late.") == ("Mr. Hendricks was late.",)


def test_a_short_form_in_dialogue_is_not_the_end_of_a_sentence():
    assert split_sentences("No. 7 was empty.") == ("No. 7 was empty.",)


def test_a_number_with_a_full_stop_stays_whole():
    assert split_sentences("It cost 3.5 marks.") == ("It cost 3.5 marks.",)


def test_initials_stay_with_the_name():
    assert split_sentences("J. R. Hendricks arrived.") == ("J. R. Hendricks arrived.",)


def test_an_ellipsis_inside_a_sentence_does_not_divide_it():
    # This is the common case in the book. A pause, not an end.
    assert split_sentences("Johann... I'm sorry.") == ("Johann... I'm sorry.",)


def test_an_ellipsis_that_ends_a_sentence_does_divide_it():
    assert split_sentences("I don't know... She left.") == (
        "I don't know...",
        "She left.",
    )


def test_a_closing_quotation_mark_stays_with_its_sentence():
    # A voice that begins a sentence with a quotation mark pauses in the wrong
    # place, so the mark must belong to the sentence that ends.
    assert split_sentences('"I won\'t." He turned away.') == (
        '"I won\'t."',
        "He turned away.",
    )


def test_a_closing_bracket_stays_with_its_sentence():
    assert split_sentences("(He knew.) She did not.") == ("(He knew.)", "She did not.")


def test_several_stops_together_end_a_sentence():
    assert split_sentences("What?! Run.") == ("What?!", "Run.")


def test_a_sentence_without_a_final_stop_is_kept():
    assert split_sentences("She walked home. It was late") == (
        "She walked home.",
        "It was late",
    )


def test_one_sentence_stays_one():
    assert split_sentences("A disturbance.") == ("A disturbance.",)


@pytest.mark.parametrize(
    "text,count",
    [
        (
            "She walked Leah home. It was not something she had decided with any "
            "deliberation. It simply happened.",
            3,
        ),
        (
            "The man collapsed, but he did not stop breathing. He folded to the "
            "ground in the particular boneless way of someone whose nervous system "
            "had been disabled.",
            2,
        ),
        ("This was not the calibration she had used three weeks ago.", 1),
    ],
)
def test_real_sentences_from_the_book(text, count):
    assert len(split_sentences(text)) == count
