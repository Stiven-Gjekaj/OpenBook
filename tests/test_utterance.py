import pytest

from openbook.cast import BlendedVoice, Silence, Utterance, Voice


def test_a_voice_keys_on_its_name():
    assert Voice("af_heart").key() == "af_heart"


def test_a_blended_voice_keys_on_every_part_and_weight():
    # The key reaches the cache. Two blends that differ only in weight must not
    # share a piece of audio.
    one = BlendedVoice(parts=("a", "b"), weights=(0.5, 0.5))
    two = BlendedVoice(parts=("a", "b"), weights=(0.7, 0.3))
    assert one.key() != two.key()


def test_a_blended_voice_needs_a_weight_for_each_part():
    with pytest.raises(ValueError, match="one weight for each part"):
        BlendedVoice(parts=("a", "b"), weights=(1.0,))


def test_a_blended_voice_needs_at_least_one_part():
    with pytest.raises(ValueError, match="at least one part"):
        BlendedVoice(parts=(), weights=())


def test_an_utterance_refuses_a_kind_it_does_not_know():
    # The planner decides where a pause falls from the kind, so a kind it does
    # not know must fail here and not quietly get no pause.
    with pytest.raises(ValueError, match="is not a kind of utterance"):
        Utterance(text="x", voice=Voice("v"), kind="whisper")


def test_an_utterance_carries_no_position_in_the_book():
    # Two lines with the same words in the same voice must reach the same audio
    # and share it, so nothing about where they sit may be part of them.
    one = Utterance(text="Yes.", voice=Voice("v"), kind="dialogue", speaker="IVY")
    two = Utterance(text="Yes.", voice=Voice("v"), kind="dialogue", speaker="IVY")
    assert one == two
    assert hash(one) == hash(two)


def test_a_silence_carries_why_it_is_there():
    assert Silence(seconds=2.0, reason="scene break").reason == "scene break"
