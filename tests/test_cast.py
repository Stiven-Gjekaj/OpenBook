from pathlib import Path

import pytest

from openbook.config.cast import load_cast, parse_chapters
from openbook.errors import CastError, ConfigError

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "soultale" / "cast.toml"

BASE = """
[narrator]
voice = "af_heart"

[cast.BLK]
name = "Black"
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
    assert len(cast.codes()) == 46


def test_an_entry_without_a_voice_is_reported_and_not_refused():
    # The example ships with no voice chosen. A person must be able to read the
    # cast before they fill it in, so loading works and the report names them.
    cast = load_cast(EXAMPLE)
    assert len(cast.uncast()) == 46


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
        '[cast.BLK]\nname = "Black"', '[cast.BLK]\naliases = ["INKK"]\nname = "Black"'
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
