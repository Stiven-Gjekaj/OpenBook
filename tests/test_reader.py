import pytest

from openbook.config.reader import Table, load_toml, parse_duration
from openbook.errors import ConfigError


def table(data, prefix=""):
    return Table(data, path="grammar.toml", prefix=prefix)


def test_reads_a_duration_in_milliseconds_and_seconds():
    assert parse_duration("400ms", key="k", path="p") == 0.4
    assert parse_duration("1s", key="k", path="p") == 1.0
    assert parse_duration("1.5s", key="k", path="p") == 1.5


def test_a_bare_number_is_not_a_duration():
    # 400 could be seconds or milliseconds, and the difference is large enough
    # that guessing is worse than refusing.
    with pytest.raises(ConfigError, match="not a length of time"):
        parse_duration("400", key="pause", path="grammar.toml")


def test_reads_the_ordinary_kinds():
    t = table({"name": "Ivy", "read": True, "wait": "600ms", "tags": ["a", "b"]})
    assert t.string("name") == "Ivy"
    assert t.boolean("read") is True
    assert t.duration("wait") == 0.6
    assert t.strings("tags") == ("a", "b")
    t.done()


def test_a_missing_required_key_is_named():
    t = table({})
    with pytest.raises(
        ConfigError, match=r"grammar\.toml, in voice: this key is required"
    ):
        t.string("voice")


def test_a_default_is_used_when_the_key_is_absent():
    t = table({})
    assert t.string("voice", "af_heart") == "af_heart"
    assert t.boolean("read", False) is False
    assert t.duration("wait", 0.4) == 0.4
    t.done()


def test_a_wrong_type_names_the_key_and_what_it_found():
    t = table({"read": "yes"})
    with pytest.raises(ConfigError, match="in read: this must be true or false"):
        t.boolean("read")


def test_a_key_that_nothing_reads_is_refused():
    t = table({"voice": "af_heart", "vioce": "am_michael"})
    t.string("voice")
    with pytest.raises(ConfigError, match="nothing reads this key"):
        t.done()


def test_an_unread_key_suggests_the_name_near_to_it():
    t = table({"voice": "af_heart", "vioce": "am_michael"})
    t.string("voice")
    with pytest.raises(ConfigError, match="near to it is 'voice'"):
        t.done()


def test_the_key_path_includes_the_table_it_is_in():
    t = table({"pause": "nope"}, prefix="render")
    with pytest.raises(ConfigError, match=r"in render\.pause"):
        t.duration("pause")


def test_one_of_refuses_a_value_outside_the_list():
    t = table({"mode": "blend"})
    with pytest.raises(ConfigError, match="not one of the values"):
        t.one_of("mode", ("voice_blend", "mix", "primary"))


def test_one_of_accepts_a_value_in_the_list():
    t = table({"mode": "mix"})
    assert t.one_of("mode", ("voice_blend", "mix", "primary")) == "mix"


def test_a_nested_table_carries_the_path():
    t = table({"unison": {"mode": 4}})
    inner = t.table("unison")
    with pytest.raises(ConfigError, match=r"in unison\.mode"):
        inner.string("mode")


def test_an_optional_table_that_is_absent_is_none():
    t = table({})
    assert t.table("unison", optional=True) is None
    t.done()


def test_a_number_is_not_accepted_where_text_is_required():
    t = table({"voice": 7})
    with pytest.raises(ConfigError, match="this must be text, and it is int"):
        t.string("voice")


def test_a_boolean_is_not_a_string():
    t = table({"voice": True})
    with pytest.raises(ConfigError, match="this must be text"):
        t.string("voice")


def test_load_toml_names_a_file_that_does_not_exist(tmp_path):
    with pytest.raises(ConfigError, match="the file does not exist"):
        load_toml(tmp_path / "absent.toml")


def test_load_toml_names_a_file_that_does_not_parse(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text("this is not = = toml\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid TOML"):
        load_toml(bad)


def test_load_toml_reads_a_file(tmp_path):
    good = tmp_path / "good.toml"
    good.write_text('voice = "af_heart"\n', encoding="utf-8")
    assert load_toml(good) == {"voice": "af_heart"}
