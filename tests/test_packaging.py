"""Checks the things a release would get wrong.

Both of these are one line of a file each, and both are the kind of line that
is changed in one place and forgotten in the other. A release workflow reads
them and cannot know which of the two was meant.
"""

import tomllib
from pathlib import Path

import openbook

ROOT = Path(__file__).resolve().parent.parent


def project() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]


def test_the_package_and_the_code_agree_on_the_version():
    assert openbook.__version__ == project()["version"], (
        "pyproject.toml and src/openbook/__init__.py give different versions. "
        "A release is named after one of them and reports the other"
    )


def test_every_command_the_package_offers_can_be_reached():
    """A named entry point that imports nothing is found by the first user."""
    for name, target in project()["scripts"].items():
        module, _, function = target.partition(":")
        __import__(module)
        import sys

        assert callable(getattr(sys.modules[module], function)), (
            f"the command {name!r} points at {target!r}, which is not something "
            "that can be run"
        )
