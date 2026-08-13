"""Reads values out of a parsed TOML table, and refuses what it does not know.

Every value comes out of a Table, which remembers which keys it gave. When the
caller has taken everything it wants, it calls done, and any key that stayed
untouched becomes an error. A key that nothing reads is nearly always a
spelling mistake, and a configuration file that quietly ignores one is a
configuration file that lies about what it does.

An error names the file, the full path of the key, and, when the key looks
like one that exists, the key it probably meant.
"""

from __future__ import annotations

import difflib
import re
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..errors import ConfigError

_MISSING = object()

# A length of time, written with its unit. A bare number is refused, because
# 400 could be seconds or milliseconds and the difference is large.
_DURATION = re.compile(r"\A\s*(\d+(?:\.\d+)?)\s*(ms|s)\s*\Z")


def parse_duration(text: str, *, key: str, path: str) -> float:
    """Turn a length of time such as 400ms or 1.5s into seconds."""
    found = _DURATION.match(text)
    if found is None:
        raise ConfigError(
            f"{text!r} is not a length of time. Write a number and a unit, "
            "such as 400ms or 1s",
            path=path,
            key=key,
        )
    value = float(found.group(1))
    return value / 1000 if found.group(2) == "ms" else value


def load_toml(path: Path) -> Mapping[str, Any]:
    """Read a TOML file, or say which file could not be read."""
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError as error:
        raise ConfigError("the file does not exist", path=str(path)) from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(
            f"the file is not valid TOML: {error}", path=str(path)
        ) from error


class Table:
    """One table of a configuration file, which checks what it is asked for."""

    def __init__(self, data: Mapping[str, Any], *, path: str, prefix: str = ""):
        if not isinstance(data, Mapping):
            raise ConfigError("this must be a table", path=path, key=prefix or None)
        self._data = data
        self._path = path
        self._prefix = prefix
        self._seen: set[str] = set()

    @property
    def path(self) -> str:
        return self._path

    def _key_name(self, key: str) -> str:
        return f"{self._prefix}.{key}" if self._prefix else key

    def _raw(self, key: str, default: Any) -> Any:
        self._seen.add(key)
        if key in self._data:
            return self._data[key]
        if default is _MISSING:
            raise ConfigError(
                "this key is required but the file does not have it",
                path=self._path,
                key=self._key_name(key),
            )
        return default

    def _typed(self, key: str, default: Any, kind: type, name: str) -> Any:
        value = self._raw(key, default)
        if value is default and default is not _MISSING:
            return value
        # bool is a subclass of int in Python, so an integer check must refuse
        # a boolean before it accepts it.
        if kind is int and isinstance(value, bool):
            value = None
        if not isinstance(value, kind):
            raise ConfigError(
                f"this must be {name}, and it is {type(value).__name__}",
                path=self._path,
                key=self._key_name(key),
            )
        return value

    def string(self, key: str, default: Any = _MISSING) -> str:
        return self._typed(key, default, str, "text")

    def boolean(self, key: str, default: Any = _MISSING) -> bool:
        return self._typed(key, default, bool, "true or false")

    def integer(self, key: str, default: Any = _MISSING) -> int:
        return self._typed(key, default, int, "a whole number")

    def number(self, key: str, default: Any = _MISSING) -> float:
        """A number that need not be whole. TOML gives 1 and 0.7 as two types."""
        value = self._raw(key, default)
        if value is default and default is not _MISSING:
            return value
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ConfigError(
                f"this must be a number, and it is {type(value).__name__}",
                path=self._path,
                key=self._key_name(key),
            )
        return float(value)

    def duration(self, key: str, default: Any = _MISSING) -> float:
        value = self.string(key, default)
        if isinstance(value, float):
            return value
        return parse_duration(value, key=self._key_name(key), path=self._path)

    def strings(self, key: str, default: Any = _MISSING) -> tuple[str, ...]:
        value = self._raw(key, default)
        if value is default and default is not _MISSING:
            return tuple(value)
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise ConfigError(
                "this must be a list of text values",
                path=self._path,
                key=self._key_name(key),
            )
        return tuple(value)

    def table(self, key: str, *, optional: bool = False) -> Table | None:
        value = self._raw(key, {} if optional else _MISSING)
        if optional and not value:
            return None
        return Table(value, path=self._path, prefix=self._key_name(key))

    def string_map(self, key: str, *, optional: bool = False) -> dict[str, str]:
        value = self._raw(key, {} if optional else _MISSING)
        if not isinstance(value, Mapping) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in value.items()
        ):
            raise ConfigError(
                "this must be a table of text values",
                path=self._path,
                key=self._key_name(key),
            )
        return dict(value)

    def keys(self) -> tuple[str, ...]:
        return tuple(self._data)

    def raw_table(self, key: str) -> Mapping[str, Any]:
        """Take a table without checking it, for a caller that walks it itself."""
        value = self._raw(key, {})
        if not isinstance(value, Mapping):
            raise ConfigError(
                "this must be a table", path=self._path, key=self._key_name(key)
            )
        return value

    def raw_list(self, key: str) -> list[Any]:
        """Take a list of tables without checking them, for a caller that walks
        it itself. This is what [[key]] gives, written twice over."""
        value = self._raw(key, [])
        if not isinstance(value, list):
            raise ConfigError(
                "this must be a list of tables. Write [[key]] with two "
                "brackets, one table for each group of chapters",
                path=self._path,
                key=self._key_name(key),
            )
        return value

    def one_of(
        self, key: str, allowed: tuple[str, ...], default: Any = _MISSING
    ) -> str:
        value = self.string(key, default)
        if value not in allowed:
            choices = ", ".join(allowed)
            raise ConfigError(
                f"{value!r} is not one of the values this key accepts: {choices}",
                path=self._path,
                key=self._key_name(key),
            )
        return value

    def done(self) -> None:
        """Refuse any key that nothing read."""
        extra = [key for key in self._data if key not in self._seen]
        if not extra:
            return
        key = extra[0]
        near = difflib.get_close_matches(key, sorted(self._seen), n=1)
        message = "nothing reads this key"
        if near:
            message = f"{message}. The name near to it is {near[0]!r}"
        raise ConfigError(message, path=self._path, key=self._key_name(key))
