"""Reads the grammar file, which says what the shape of a chapter is.

The parser holds no rule about the book it reads. Every rule comes from here,
so a fork that reads a different book changes this file and not the code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..errors import ConfigError
from .reader import Table, load_toml
from .template import Template, compile_regex, compile_template

UNISON_MODES = ("voice_blend", "mix", "primary")
ACTION_MODES = ("pause", "narrator", "drop")


@dataclass(frozen=True)
class Source:
    """Where the chapters come from, and which of them are read."""

    format: str
    files: tuple[str, ...]
    chapter_title: Template
    skip_volume: re.Pattern[str] | None
    announcement: Template
    announcement_named: Template

    def is_skipped(self, volume: str) -> bool:
        return (
            self.skip_volume is not None and self.skip_volume.search(volume) is not None
        )


@dataclass(frozen=True)
class Unison:
    """How to speak a line that two characters say together."""

    separator: str
    mode: str


@dataclass(frozen=True)
class Dialogue:
    """How to find a line of dialogue and the code of the character saying it."""

    elements: frozenset[str]
    template: Template
    split_at_line_break: bool
    action: re.Pattern[str] | None
    unison: Unison


@dataclass(frozen=True)
class Structure:
    """The parts of a chapter that are not narration and not dialogue."""

    end_matter_element: str
    scene_break: re.Pattern[str]
    strip_elements: frozenset[str]


@dataclass(frozen=True)
class Render:
    """How long the silences are, and what gets spoken at all."""

    read_chapter_names: bool
    read_end_matter: bool
    dialogue_to_narration: float
    narration_to_dialogue: float
    at_scene_break: float
    after_chapter_name: float
    action: str
    at_action: float


@dataclass(frozen=True)
class Output:
    """How the finished audio is divided into files."""

    group_by: str
    file_name: str
    merge_volumes: dict[str, str]
    bitrate: str
    sample_rate: int | None
    channels: int | None

    def group_of(self, volume: str) -> str:
        return self.merge_volumes.get(volume, volume)


@dataclass(frozen=True)
class Grammar:
    source: Source
    dialogue: Dialogue
    structure: Structure
    render: Render
    output: Output


def load_grammar(path: Path) -> Grammar:
    """Read a grammar file, or say which key in it is wrong."""
    name = str(path)
    root = Table(load_toml(path), path=name)

    source = _read_source(root.table("source"))
    grammar_table = root.table("grammar")
    dialogue = _read_dialogue(grammar_table)
    structure = _read_structure(grammar_table.table("structure"))
    grammar_table.done()
    render = _read_render(root.table("render"))
    output = _read_output(root.table("output"))
    root.done()

    return Grammar(
        source=source,
        dialogue=dialogue,
        structure=structure,
        render=render,
        output=output,
    )


def _read_source(table: Table) -> Source:
    fmt = table.one_of("format", ("epub",))
    files = table.strings("files")
    if not files:
        raise ConfigError(
            "name at least one book file", path=table.path, key="source.files"
        )

    patterns = {
        "NUMBER": table.string("number_pattern", r"-?\d+"),
        "VOLUME": table.string("volume_pattern", r"[^)]+"),
    }
    title = compile_template(
        table.string("chapter_title"),
        patterns,
        key="source.chapter_title",
        path=table.path,
    )
    _require_names(
        title,
        ("NUMBER", "VOLUME", "TITLE"),
        key="source.chapter_title",
        path=table.path,
    )

    skip = table.string("skip_volume_pattern", "")
    announcement = compile_template(
        table.string("chapter_announcement"),
        key="source.chapter_announcement",
        path=table.path,
    )
    announcement_named = compile_template(
        table.string("chapter_announcement_named"),
        key="source.chapter_announcement_named",
        path=table.path,
    )
    table.done()

    return Source(
        format=fmt,
        files=files,
        chapter_title=title,
        skip_volume=(
            compile_regex(skip, key="source.skip_volume_pattern", path=table.path)
            if skip
            else None
        ),
        announcement=announcement,
        announcement_named=announcement_named,
    )


def _read_dialogue(table: Table) -> Dialogue:
    elements = table.strings("dialogue_elements")
    if not elements:
        raise ConfigError(
            "name at least one element that holds a speaker code",
            path=table.path,
            key="grammar.dialogue_elements",
        )

    template = compile_template(
        table.string("dialogue"),
        {"SPEAKER": table.string("speaker_pattern")},
        key="grammar.dialogue",
        path=table.path,
    )
    _require_names(
        template, ("SPEAKER", "TEXT"), key="grammar.dialogue", path=table.path
    )

    action = table.string("action", "")
    unison_table = table.table("unison")
    unison = Unison(
        separator=unison_table.string("separator"),
        mode=unison_table.one_of("mode", UNISON_MODES),
    )
    unison_table.done()

    return Dialogue(
        elements=frozenset(e.lower() for e in elements),
        template=template,
        split_at_line_break=table.boolean("split_at_line_break", True),
        action=(
            compile_regex(action, key="grammar.action", path=table.path)
            if action
            else None
        ),
        unison=unison,
    )


def _read_structure(table: Table) -> Structure:
    structure = Structure(
        end_matter_element=table.string("end_matter_element").lower(),
        scene_break=compile_regex(
            table.string("scene_break"),
            key="grammar.structure.scene_break",
            path=table.path,
        ),
        strip_elements=frozenset(
            e.lower() for e in table.strings("strip_elements", ())
        ),
    )
    table.done()
    return structure


def _read_render(table: Table) -> Render:
    render = Render(
        read_chapter_names=table.boolean("read_chapter_names", True),
        read_end_matter=table.boolean("read_end_matter", False),
        dialogue_to_narration=table.duration("pause_dialogue_to_narration"),
        narration_to_dialogue=table.duration("pause_narration_to_dialogue"),
        at_scene_break=table.duration("pause_at_scene_break"),
        after_chapter_name=table.duration("pause_after_chapter_name"),
        action=table.one_of("action", ACTION_MODES, "pause"),
        at_action=table.duration("pause_at_action", 0.5),
    )
    table.done()
    return render


def _read_output(table: Table) -> Output:
    output = Output(
        group_by=table.one_of("group_by", ("volume",)),
        file_name=table.string("file_name"),
        merge_volumes=table.string_map("merge_volumes", optional=True),
        bitrate=table.string("bitrate", "64k"),
        sample_rate=table.integer("sample_rate", 0) or None,
        channels=table.integer("channels", 0) or None,
    )
    if "{VOLUME}" not in output.file_name:
        raise ConfigError(
            "the name of a file must contain {VOLUME}, or every volume writes "
            "over the one before it",
            path=table.path,
            key="output.file_name",
        )
    table.done()
    return output


def _require_names(
    template: Template, names: tuple[str, ...], *, key: str, path: str
) -> None:
    missing = [name for name in names if name not in template.names]
    if missing:
        wanted = ", ".join(f"{{{name}}}" for name in missing)
        raise ConfigError(f"the template must capture {wanted}", path=path, key=key)
