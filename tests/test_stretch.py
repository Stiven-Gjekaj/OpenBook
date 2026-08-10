import shutil
from array import array

import pytest

from openbook.speech.audio import Audio
from openbook.speech.stretch import MOST_CHANGE, stretch, to_one_length

needs_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg"), reason="ffmpeg is not installed"
)

RATE = 22050


def tone(seconds: float, rate: int = RATE) -> Audio:
    """A piece of audio with something in it, so a stretch has work to do."""
    import math

    count = round(seconds * rate)
    values = [
        round(12000 * math.sin(i * 2 * math.pi * 220 / rate)) for i in range(count)
    ]
    return Audio(samples=array("h", values).tobytes(), rate=rate)


def test_one_piece_is_left_alone():
    only = [tone(1.0)]
    assert to_one_length(only) == only


def test_pieces_already_of_one_length_are_left_alone():
    # Below the point where a stretch can be heard and the loss of quality can.
    same = [tone(1.0), tone(1.005)]
    assert to_one_length(same) == same


@needs_ffmpeg
def test_two_pieces_come_back_the_same_length():
    made = to_one_length([tone(1.0), tone(1.6)])
    assert abs(made[0].seconds - made[1].seconds) < 0.05


@needs_ffmpeg
def test_the_change_is_shared_between_the_two():
    # The target is the average, so neither reading carries the whole change.
    # One moved the whole way would move twice as far, and a tempo moved 7
    # percent is near the point where nobody hears it while 14 percent is not.
    short, long = to_one_length([tone(1.0), tone(1.6)])
    assert 1.2 < short.seconds < 1.4
    assert 1.2 < long.seconds < 1.4


@needs_ffmpeg
def test_a_stretched_piece_keeps_its_rate_and_its_sound():
    made = stretch(tone(1.0), 1.3)
    assert made.rate == RATE
    assert abs(made.seconds - 1.3) < 0.05
    assert any(made.samples), "the audio is not silent"


@needs_ffmpeg
def test_a_piece_is_never_moved_further_than_the_limit():
    # A reading that has to move this far to meet another is not the same
    # performance afterwards, so it stops at the limit rather than obeying.
    made = stretch(tone(1.0), 10.0)
    assert made.seconds < 1.0 / (1 - MOST_CHANGE) + 0.1


def test_nothing_is_asked_of_a_piece_with_no_length():
    empty = Audio(samples=b"", rate=RATE)
    assert stretch(empty, 1.0) is empty
    assert to_one_length([empty, tone(1.0)]) == [empty, tone(1.0)]
