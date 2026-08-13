from pathlib import Path

import pytest

from openbook.config.cast import load_cast, parse_chapters
from openbook.errors import CastError, ConfigError

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "soultale" / "cast.toml"

BASE = """
[narrator]
voice = "af_heart"

[cast.BLK]
name = "Blook"
voice = "am_michael"

[cast.INK]
name = "Ink"
voice = "bf_emma"
aliases = ["INKK"]

[[cast_range."???"]]
chapters = "38"
name = "Unknown in volume 2"
voice = "am_onyx"

[[cast_range."???"]]
chapters = "115-120"
name = "Unknown in volume 4"
voice = "bm_george"
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "cast.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_example_that_ships_with_the_project_loads():
    cast = load_cast(EXAMPLE)
    assert "BLK" in cast.entries
    assert "///" in cast.entries


def test_the_example_lists_every_code_that_volume_one_uses():
    cast = load_cast(EXAMPLE)
    assert len(cast.codes()) == 44


def test_an_entry_without_a_voice_is_reported_and_not_refused():
    # A person must be able to read a cast before they fill it in, so loading
    # works and the report names the entries that are still waiting. The
    # example is a working project and some of it is cast, so this counts what
    # is left rather than expecting the whole file to be blank.
    cast = load_cast(EXAMPLE)
    assert cast.uncast(), "the example still has entries waiting for a voice"
    assert all(not entry.voice for entry in cast.uncast())
    assert len(cast.uncast()) + len(cast.voices()) - 1 <= len(cast.codes())


def test_reads_a_chapter_and_a_run_of_chapters():
    assert parse_chapters("38", key="k", path="p").spans == ((38, 38),)
    assert parse_chapters("115-120", key="k", path="p").spans == ((115, 120),)
    assert parse_chapters("38, 115-120", key="k", path="p").spans == (
        (38, 38),
        (115, 120),
    )


def test_a_run_that_ends_before_it_starts_is_refused():
    with pytest.raises(ConfigError, match="ends before it starts"):
        parse_chapters("120-115", key="k", path="p")


def test_text_that_is_not_a_chapter_is_refused():
    with pytest.raises(ConfigError, match="does not name a chapter"):
        parse_chapters("volume 4", key="k", path="p")


def test_resolves_an_ordinary_code_in_any_chapter(tmp_path):
    cast = load_cast(write(tmp_path, BASE))
    assert cast.resolve("BLK", 4).voice == "am_michael"
    assert cast.resolve("BLK", 300).voice == "am_michael"


def test_an_alias_reaches_the_entry_it_belongs_to(tmp_path):
    cast = load_cast(write(tmp_path, BASE))
    assert cast.resolve("INKK", 1).name == "Ink"


def test_the_unknown_code_takes_a_different_voice_in_each_group(tmp_path):
    cast = load_cast(write(tmp_path, BASE))
    assert cast.resolve("???", 38).voice == "am_onyx"
    assert cast.resolve("???", 117).voice == "bm_george"


def test_the_unknown_code_in_a_chapter_no_entry_covers_stops_the_build(tmp_path):
    # This is the case that matters. A new mystery character needs a new voice,
    # and the build must ask for one instead of choosing.
    cast = load_cast(write(tmp_path, BASE))
    with pytest.raises(CastError, match="no entry of it covers this chapter"):
        cast.resolve("???", 175)


def test_a_code_the_cast_does_not_have_names_the_chapter(tmp_path):
    cast = load_cast(write(tmp_path, BASE))
    with pytest.raises(CastError, match="chapter 325 uses the speaker code 'KRN'"):
        cast.resolve("KRN", 325)


def test_an_unknown_code_suggests_the_code_near_to_it(tmp_path):
    cast = load_cast(write(tmp_path, BASE))
    with pytest.raises(CastError, match="near to it is 'BLK'"):
        cast.resolve("BLL", 4)


def test_two_groups_that_cover_the_same_chapter_are_refused(tmp_path):
    text = BASE.replace('chapters = "115-120"', 'chapters = "30-40"')
    with pytest.raises(ConfigError, match="cover the same chapter"):
        load_cast(write(tmp_path, text))


def test_a_code_with_a_plain_entry_and_a_group_entry_is_refused(tmp_path):
    text = BASE + '\n[cast."???"]\nname = "Unknown"\nvoice = "am_echo"\n'
    with pytest.raises(ConfigError, match="entry for every chapter"):
        load_cast(write(tmp_path, text))


def test_an_alias_that_belongs_to_two_codes_is_refused(tmp_path):
    text = BASE.replace(
        '[cast.BLK]\nname = "Blook"', '[cast.BLK]\naliases = ["INKK"]\nname = "Blook"'
    )
    with pytest.raises(ConfigError, match="belongs to"):
        load_cast(write(tmp_path, text))


def test_a_group_written_with_one_bracket_is_refused(tmp_path):
    # Two groups written with one bracket each is a duplicate that TOML itself
    # refuses. One group written with one bracket parses, and reaches here as a
    # table where a list of tables belongs.
    text = """
[narrator]
voice = "af_heart"

[cast_range."???"]
chapters = "38"
voice = "am_onyx"
"""
    with pytest.raises(ConfigError, match="two brackets"):
        load_cast(write(tmp_path, text))


def test_a_cast_says_every_voice_it_asks_for(tmp_path):
    # What a voice is depends on the engine. This answers what was written.
    path = tmp_path / "cast.toml"
    path.write_text(
        '[narrator]\nvoice = "voices/narrator.wav"\n\n'
        '[cast.BLK]\nname = "Blook"\nvoice = "voices/blook.wav"\n\n'
        '[cast.IVY]\nname = "Ivy"\nvoice = "voices/blook.wav"\n\n'
        '[cast.NEW]\nname = "New"\nvoice = ""\n',
        encoding="utf-8",
    )
    voices = load_cast(path).voices()
    assert voices[0] == "voices/narrator.wav", "the narrator comes first"
    assert voices.count("voices/blook.wav") == 1, "a shared voice is said once"
    assert "" not in voices, "an entry with no voice yet asks for nothing"


def test_a_host_speaks_the_words_outside_the_book(tmp_path):
    # The intro and the outro speak to the listener. Nobody in the book hears
    # them, so the voice that reads them is not in the cast.
    path = tmp_path / "cast.toml"
    path.write_text(
        '[narrator]\nvoice = "voices/narrator.wav"\n\n'
        '[host]\nvoice = "voices/host.wav"\nexaggeration = 0.7\n\n'
        '[cast.BLK]\nname = "Blook"\nvoice = "voices/blook.wav"\n',
        encoding="utf-8",
    )
    cast = load_cast(path)
    assert cast.host == "voices/host.wav"
    assert cast.host_exaggeration == 0.7
    assert cast.host_voice() == "voices/host.wav"
    assert "BLK" in cast.entries and "host" not in cast.entries


def test_with_no_host_the_narrator_speaks_them(tmp_path):
    # What happened before a host could be named, and what still happens for a
    # book that names none.
    path = tmp_path / "cast.toml"
    path.write_text(
        '[narrator]\nvoice = "voices/narrator.wav"\n\n'
        '[cast.BLK]\nname = "Blook"\nvoice = "voices/blook.wav"\n',
        encoding="utf-8",
    )
    cast = load_cast(path)
    assert cast.host == ""
    assert cast.host_voice() == "voices/narrator.wav"


def test_the_example_names_a_host():
    assert load_cast(EXAMPLE).host == "voices/host.wav"


def test_a_narrator_can_change_with_the_chapter(tmp_path):
    # A book does not have to keep one narrator. Soultale tells the prologue
    # from outside and then gives the telling to the character whose story it
    # is, and later chapters change again.
    path = tmp_path / "cast.toml"
    path.write_text(
        '[narrator]\nvoice = "voices/outside.wav"\n\n'
        '[[narrator_range]]\nchapters = "3-22"\n'
        'name = "Blook"\nvoice = "voices/blook.wav"\nexaggeration = 0.4\n\n'
        '[[narrator_range]]\nchapters = "23-40"\nvoice = "voices/other.wav"\n\n'
        '[cast.BLK]\nname = "Blook"\nvoice = "voices/blook.wav"\n',
        encoding="utf-8",
    )
    cast = load_cast(path)
    assert cast.narrator_for(0) == ("voices/outside.wav", None)
    assert cast.narrator_for(2) == ("voices/outside.wav", None)
    assert cast.narrator_for(3) == ("voices/blook.wav", 0.4)
    assert cast.narrator_for(22) == ("voices/blook.wav", 0.4)
    assert cast.narrator_for(30) == ("voices/other.wav", None)
    # A chapter no range covers falls back, so a book with none behaves as
    # every book did before ranges existed.
    assert cast.narrator_for(99) == ("voices/outside.wav", None)


def test_every_narrator_recording_is_asked_for(tmp_path):
    # check names a recording that is not there. A narrator of one volume must
    # be named too, or the one that is missing is found by a render instead.
    path = tmp_path / "cast.toml"
    path.write_text(
        '[narrator]\nvoice = "voices/outside.wav"\n\n'
        '[[narrator_range]]\nchapters = "3-22"\nvoice = "voices/blook.wav"\n\n'
        '[cast.BLK]\nname = "Blook"\nvoice = "voices/blook.wav"\n',
        encoding="utf-8",
    )
    voices = load_cast(path).voices()
    assert voices[0] == "voices/outside.wav", "the narrator comes first"
    assert "voices/blook.wav" in voices
    assert voices.count("voices/blook.wav") == 1, "a shared voice is said once"


def test_two_narrator_ranges_over_one_chapter_are_refused(tmp_path):
    path = tmp_path / "cast.toml"
    path.write_text(
        '[narrator]\nvoice = "voices/outside.wav"\n\n'
        '[[narrator_range]]\nchapters = "3-22"\nvoice = "voices/one.wav"\n\n'
        '[[narrator_range]]\nchapters = "20-30"\nvoice = "voices/two.wav"\n\n'
        '[cast.BLK]\nname = "Blook"\nvoice = "voices/blook.wav"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="cover"):
        load_cast(path)
