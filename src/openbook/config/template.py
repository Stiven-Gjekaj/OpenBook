"""Turns a template into a regular expression.

A template says what a line looks like with a name in braces where the useful
text is:

    "# (Chapter {NUMBER} || {VOLUME}) {TITLE}"

Everything outside the braces is literal. The compiler escapes it, so a
bracket, a vertical bar, or a full stop in a template means that character and
nothing more. This is the point of a template: a person who writes one does
not need to know which characters a regular expression treats as special.

Each name becomes a capture group. A name can have its own pattern, which
constrains what it accepts:

    number_pattern = '-?\\d+'

A name without a pattern accepts anything, and stops as soon as the literal
text after it can start. The whole template must match the whole line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..errors import ConfigError

# A name in braces. The name is upper case, which keeps it apart from the
# ordinary text around it.
_PLACEHOLDER = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")

# A brace that no placeholder uses. It is nearly always a spelling mistake in
# the template, so the compiler refuses it instead of matching it as a literal.
_LONE_BRACE = re.compile(r"[{}]")

# What a name accepts when the configuration gives it no pattern. It is not
# greedy, so the literal text after the name ends the match at the first place
# it can, and not at the last.
DEFAULT_PATTERN = r".+?"


@dataclass(frozen=True)
class Template:
    """A compiled template and the names it captures."""

    source: str
    regex: re.Pattern[str]
    names: tuple[str, ...]

    def match(self, line: str) -> dict[str, str] | None:
        """Return the captured text, or None when the line does not match."""
        found = self.regex.match(line)
        if found is None:
            return None
        return {name: found.group(name.lower()) for name in self.names}


def compile_template(
    template: str,
    patterns: dict[str, str] | None = None,
    *,
    key: str | None = None,
    path: str | None = None,
) -> Template:
    """Compile a template into a Template.

    patterns maps a name to the regular expression that the name accepts. A
    name that patterns does not have accepts DEFAULT_PATTERN.

    key and path name the configuration that the template came from, so that an
    error tells the person which line to correct.
    """
    patterns = patterns or {}
    names: list[str] = []
    parts: list[str] = []
    position = 0

    for found in _PLACEHOLDER.finditer(template):
        literal = template[position : found.start()]
        _refuse_lone_brace(literal, template, key=key, path=path)
        parts.append(re.escape(literal))

        name = found.group(1)
        if name in names:
            raise ConfigError(
                f"the template uses the name {{{name}}} more than one time",
                path=path,
                key=key,
            )
        names.append(name)
        parts.append(f"(?P<{name.lower()}>{patterns.get(name, DEFAULT_PATTERN)})")
        position = found.end()

    tail = template[position:]
    _refuse_lone_brace(tail, template, key=key, path=path)
    parts.append(re.escape(tail))

    if not names:
        raise ConfigError(
            f"the template {template!r} captures nothing. "
            "Put a name in braces where the useful text is",
            path=path,
            key=key,
        )

    pattern = "".join(parts)
    try:
        regex = re.compile(rf"\A{pattern}\Z")
    except re.error as error:
        # The literal text is escaped, so a bad pattern here came from one of
        # the patterns that the configuration supplied.
        raise ConfigError(
            f"a pattern for the template {template!r} is not a valid regular "
            f"expression: {error}",
            path=path,
            key=key,
        ) from error

    return Template(source=template, regex=regex, names=tuple(names))


def compile_regex(
    pattern: str, *, key: str | None = None, path: str | None = None
) -> re.Pattern[str]:
    """Compile a regular expression that the configuration gives directly.

    This is the way out for a rule that a template cannot express.
    """
    try:
        return re.compile(pattern)
    except re.error as error:
        raise ConfigError(
            f"{pattern!r} is not a valid regular expression: {error}",
            path=path,
            key=key,
        ) from error


def _refuse_lone_brace(
    literal: str, template: str, *, key: str | None, path: str | None
) -> None:
    if _LONE_BRACE.search(literal):
        raise ConfigError(
            f"the template {template!r} has a brace that no name uses. "
            "A name must look like {NAME}, in capital letters",
            path=path,
            key=key,
        )
