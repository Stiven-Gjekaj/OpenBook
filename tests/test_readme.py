"""Checks the claims the readme makes about the project.

A badge is a claim, and one that nothing checks goes stale the first time
somebody adds a test. It is worse than no badge then, because a reader who
finds one number wrong stops believing the rest of the page.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

BADGE = re.compile(r"tests-(\d+)_passing")
COUNTED = re.compile(r"(\d+) tests? collected")


def collected() -> int:
    """How many tests this project has, counted by pytest itself.

    A separate run rather than the one in progress, because this test must
    give the same answer whether the whole suite was asked for or only this
    file. Nothing is run: the tests are only counted.

    The settings of the project are cleared for the run, because they carry
    the quiet flag and the quiet output does not hold a total.
    """
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "--collect-only",
            "-q",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    found = COUNTED.search(done.stdout)
    if found is None:
        pytest.skip(f"pytest did not say how many tests it found: {done.stdout[-200:]}")
    return int(found.group(1))


def test_the_readme_says_how_many_tests_there_are():
    claimed = BADGE.search(README.read_text(encoding="utf-8"))
    assert claimed is not None, (
        "the readme has no test badge. It reads tests-<number>_passing"
    )

    counted = collected()
    assert int(claimed.group(1)) == counted, (
        f"the readme badge claims {claimed.group(1)} tests and there are "
        f"{counted}. Write tests-{counted}_passing in README.md"
    )


def test_every_file_the_readme_points_at_is_there():
    """A link to a file that was moved is the other claim that rots quietly."""
    text = README.read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)#:]+\.md|[^)#:]+\.toml|[^)#:]+\.svg)\)", text)
    missing = [link for link in links if not (ROOT / link).exists()]
    assert not missing, f"the readme points at files that are not there: {missing}"
