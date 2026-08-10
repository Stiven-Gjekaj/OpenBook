from pathlib import Path

import pytest

from openbook.cast.utterance import Silence, Utterance, Voice
from openbook.config.grammar import load_grammar
from openbook.corrections import Corrections
from openbook.plan.planner import Plan, plan_chapter, plan_volume

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "soultale"
NARRATOR = Voice("af_heart")
IVY = Voice("bf_emma")


@pytest.fixture
def grammar():
    return load_grammar(EXAMPLES / "grammar.toml")


def narration(text="Some prose."):
    return Utterance(text=text, voice=NARRATOR, kind="narration")


def dialogue(text="A line.", speaker="IVY"):
    return Utterance(text=text, voice=IVY, kind="dialogue", speaker=speaker)


def reasons(plan: Plan):
    return [i.reason for i in plan.items if isinstance(i, Silence)]


def test_two_lines_of_dialogue_get_no_pause_between_them(grammar):
    # The rule the author asked for. A conversation must keep its speed.
    plan = plan_chapter((dialogue("One."), dialogue("Two.")), grammar)
    assert reasons(plan) == []
    assert len(plan.utterances) == 2


def test_two_paragraphs_of_narration_get_no_pause_between_them(grammar):
    plan = plan_chapter((narration("One."), narration("Two.")), grammar)
    assert reasons(plan) == []


def test_narration_into_dialogue_gets_a_pause(grammar):
    plan = plan_chapter((narration(), dialogue()), grammar)
    assert reasons(plan) == ["narration to dialogue"]
    assert plan.silences[0].seconds == 0.6


def test_dialogue_into_narration_gets_a_pause(grammar):
    plan = plan_chapter((dialogue(), narration()), grammar)
    assert reasons(plan) == ["dialogue to narration"]
    assert plan.silences[0].seconds == 0.4


def test_a_conversation_inside_prose_gets_a_pause_at_each_end_only(grammar):
    items = (
        narration(),
        dialogue("One."),
        dialogue("Two."),
        dialogue("Three."),
        narration(),
    )
    plan = plan_chapter(items, grammar)
    assert reasons(plan) == ["narration to dialogue", "dialogue to narration"]


def test_the_chapter_name_is_followed_by_its_own_pause(grammar):
    announcement = Utterance(text="Chapter 230.", voice=NARRATOR, kind="announcement")
    plan = plan_chapter((announcement, narration()), grammar)
    assert reasons(plan) == ["after the chapter name"]
    assert plan.silences[0].seconds == 1.0


def test_a_silence_already_there_is_not_doubled(grammar):
    # A scene break comes from the cast stage. One pause in a place is enough.
    items = (narration(), Silence(seconds=2.0, reason="scene break"), dialogue())
    plan = plan_chapter(items, grammar)
    assert reasons(plan) == ["scene break"]


def test_an_action_pause_keeps_the_line_from_gaining_more(grammar):
    items = (
        dialogue("I am fine"),
        Silence(seconds=0.5, reason="action: cough"),
        dialogue("really."),
    )
    plan = plan_chapter(items, grammar)
    assert reasons(plan) == ["action: cough"]


def test_an_action_the_narrator_speaks_gets_a_pause_on_each_side(grammar):
    # The narrator breaking into a line of speech is exactly the change that
    # the rule exists for.
    action = Utterance(text="cough", voice=NARRATOR, kind="action")
    plan = plan_chapter((dialogue("Fine"), action, dialogue("really.")), grammar)
    assert reasons(plan) == ["dialogue to narration", "narration to dialogue"]


def test_the_end_matter_counts_as_narration(grammar):
    end = Utterance(text="End of Chapter 230", voice=NARRATOR, kind="end matter")
    plan = plan_chapter((dialogue(), end), grammar)
    assert reasons(plan) == ["dialogue to narration"]


def test_nothing_is_added_to_an_empty_chapter(grammar):
    assert plan_chapter((), grammar).items == ()


def test_one_utterance_gains_no_pause(grammar):
    assert reasons(plan_chapter((narration(),), grammar)) == []


def test_a_long_utterance_is_divided_at_a_sentence_end(grammar):
    text = "One two three. Four five six. Seven eight nine."
    plan = plan_chapter((narration(text),), grammar, max_characters=20)
    assert [u.text for u in plan.utterances] == [
        "One two three.",
        "Four five six.",
        "Seven eight nine.",
    ]


def test_a_division_keeps_the_voice_and_the_speaker(grammar):
    text = "One two three. Four five six."
    plan = plan_chapter((dialogue(text, speaker="IVY"),), grammar, max_characters=16)
    assert all(u.voice == IVY and u.speaker == "IVY" for u in plan.utterances)
    assert all(u.kind == "dialogue" for u in plan.utterances)


def test_sentences_are_grouped_up_to_the_limit(grammar):
    # Two sentences fit in twenty characters and the third does not, so the
    # piece holds the two and the next piece starts.
    text = "One two. Three four. Five six."
    plan = plan_chapter((narration(text),), grammar, max_characters=20)
    assert [u.text for u in plan.utterances] == ["One two. Three four.", "Five six."]


def test_single_letters_are_initials_and_not_sentences(grammar):
    # "A. B. C." is a name. The divider must not make three pieces of it and
    # then speak each letter as though it ended a thought.
    plan = plan_chapter((narration("A. B. C. D."),), grammar, max_characters=40)
    assert [u.text for u in plan.utterances] == ["A. B. C. D."]


def test_no_piece_is_ever_longer_than_the_limit(grammar):
    # The engine cuts anything over its limit wherever that limit lands, which
    # can be inside a word. Every path here must get under it first.
    text = (
        "The drill left his arm with a sound like tearing metal, crossing the "
        "open ground between the rogue and the boy with a speed that compressed "
        "the distance into something far too small, and nobody moved."
    )
    for limit in (20, 40, 80, 200):
        plan = plan_chapter((narration(text),), grammar, max_characters=limit)
        assert all(len(u.text) <= limit for u in plan.utterances), limit
        assert " ".join(u.text for u in plan.utterances) == text


def test_nothing_is_divided_without_a_limit(grammar):
    text = "One two three. Four five six."
    plan = plan_chapter((narration(text),), grammar)
    assert len(plan.utterances) == 1


def test_a_volume_puts_a_pause_between_its_chapters(grammar):
    one = (narration("One."),)
    two = (narration("Two."),)
    plan = plan_volume([one, two], grammar)
    assert reasons(plan) == ["new chapter"]
    assert [u.text for u in plan.utterances] == ["One.", "Two."]


def test_a_volume_of_one_chapter_gains_nothing(grammar):
    assert reasons(plan_volume([(narration(),)], grammar)) == []


def test_a_chapter_boundary_does_not_also_get_a_kind_pause(grammar):
    # The pause between chapters replaces the one the change of kind would ask
    # for. Two silences in a row would be heard as a fault.
    plan = plan_volume([(dialogue(),), (narration(),)], grammar)
    assert reasons(plan) == ["new chapter"]


def test_the_plan_counts_its_words_and_its_silence(grammar):
    plan = plan_chapter((narration("One two three."), dialogue("Four five.")), grammar)
    assert plan.words() == 5
    assert plan.silent_seconds == 0.6


def test_a_sentence_longer_than_the_limit_divides_at_a_comma(grammar):
    # 34 sentences in the book are longer on their own than an engine accepts.
    # Handing one over whole means the engine cuts it wherever its own limit
    # lands, and nothing chooses that place.
    text = "He ran fast, she followed him, and the heavy door closed behind them."
    plan = plan_chapter((narration(text),), grammar, max_characters=30)
    assert all(len(u.text) <= 30 for u in plan.utterances)
    assert " ".join(u.text for u in plan.utterances) == text


def test_a_clause_with_no_mark_divides_between_words_as_a_last_resort(grammar):
    text = "one two three four five six seven eight nine ten eleven twelve"
    plan = plan_chapter((narration(text),), grammar, max_characters=20)
    assert all(len(u.text) <= 20 for u in plan.utterances)
    assert " ".join(u.text for u in plan.utterances) == text


def test_a_correction_changes_the_line_the_engine_is_given(grammar):
    corrections = Corrections(entries={"He said Vazroth.": "He said Vaz-roth."})
    plan = plan_chapter(
        (narration("He said Vazroth."),), grammar, corrections=corrections
    )
    assert plan.utterances[0].text == "He said Vaz-roth."
    assert plan.corrected == ("He said Vazroth.",)


def test_a_correction_leaves_every_other_line_alone(grammar):
    corrections = Corrections(entries={"One.": "Won."})
    plan = plan_chapter(
        (narration("One."), narration("Two.")), grammar, corrections=corrections
    )
    assert [u.text for u in plan.utterances] == ["Won.", "Two."]


def test_a_correction_names_a_line_as_the_review_page_showed_it(grammar):
    # The page shows the pieces of a long line, not the line, so an entry
    # names a piece. This one is divided in two and the second half corrected.
    long = narration("Alpha beta gamma. Delta epsilon zeta.")
    corrections = Corrections(entries={"Delta epsilon zeta.": "Delta epsilon Zeta."})
    plan = plan_chapter((long,), grammar, max_characters=20, corrections=corrections)
    assert [u.text for u in plan.utterances] == [
        "Alpha beta gamma.",
        "Delta epsilon Zeta.",
    ]


def test_a_correction_that_grows_past_the_limit_is_divided_again(grammar):
    # Nothing makes a correction the length of what it replaces, and a piece
    # over the limit would be cut by the engine instead of here.
    corrections = Corrections(entries={"Short.": "One two three. Four five six."})
    plan = plan_chapter(
        (narration("Short."),), grammar, max_characters=20, corrections=corrections
    )
    assert [u.text for u in plan.utterances] == ["One two three.", "Four five six."]


def test_a_correction_for_no_line_here_is_not_reported_as_used(grammar):
    corrections = Corrections(entries={"Absent.": "Present."})
    plan = plan_chapter(
        (narration("Something else."),), grammar, corrections=corrections
    )
    assert plan.corrected == ()


def test_a_volume_reports_every_correction_its_chapters_used(grammar):
    corrections = Corrections(entries={"One.": "Won.", "Two.": "Too."})
    plan = plan_volume(
        [(narration("One."),), (narration("Two."),)], grammar, corrections=corrections
    )
    assert sorted(plan.corrected) == ["One.", "Two."]


def test_the_rest_between_chapters_is_its_own_length(grammar):
    """It used to borrow the pause that follows a chapter name.

    They are different things. One is a beat after the narrator says the name
    of a chapter. The other is the rest a listener gets to take in what
    happened, and it falls after the last line of the chapter.
    """
    plan = plan_volume([(narration("Last."),), (narration("First."),)], grammar)
    gaps = [s for s in plan.items if isinstance(s, Silence)]
    assert [s.reason for s in gaps] == ["new chapter"]
    assert gaps[0].seconds == grammar.render.between_chapters
    assert gaps[0].seconds != grammar.render.after_chapter_name


def test_the_end_of_a_chapter_is_the_last_thing_before_the_rest(grammar):
    # End of Chapter 0, then the title, then the line that comments on it,
    # then the silence. Nothing falls between the three, because a pause only
    # lands where the kind of the text changes and all three are narration.
    ending = (
        Utterance(text="End of Chapter 0", voice=NARRATOR, kind="end matter"),
        Utterance(text='"Point - Null"', voice=NARRATOR, kind="end matter"),
        narration("[ The 1 named 0. ]"),
    )
    plan = plan_volume([ending, (narration("Next."),)], grammar)
    said = [
        i.text if isinstance(i, Utterance) else f"~{i.seconds:g}s" for i in plan.items
    ]
    assert said == [
        "End of Chapter 0",
        '"Point - Null"',
        "[ The 1 named 0. ]",
        "~3s",
        "Next.",
    ]
