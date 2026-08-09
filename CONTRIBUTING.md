<div align="center">
  <a href="README.md"><img src="assets/openbook.svg" alt="OpenBook" height="44"></a>
</div>

# Contributing to OpenBook

Thank you for your interest. OpenBook turns a book in EPUB form into an
audiobook on the machine that runs it. Reports of a fault, corrections to the
documents, and new code are all welcome.

## What this project is, and what it is not

OpenBook reads one book format: the format of Soultale, in which a line of
dialogue starts with a short code for the character who speaks it. This is on
purpose. The project has one book to test against, and code for a format that
nobody can test rots.

The rules of that format live in a configuration file and not in the code. A
fork that reads a different book writes a different grammar file. A change that
moves a rule out of the configuration and into the parser goes the wrong way,
and a pull request that does it needs a reason.

## Ways to help

- Report a fault or ask for a feature. Open an issue.
- Correct the documents in `docs/` or the readme.
- Take a task from [TODO.md](TODO.md).

Open an issue before you start a large piece of work, so that we agree on the
way to do it before you write it.

## Development setup

You need `uv`. Then:

    git clone https://github.com/Stiven-Gjekaj/OpenBook
    cd OpenBook
    uv sync

Run the tests:

    uv run pytest

Run the tool against a book:

    uv run openbook -C path/to/project check

A project directory holds `grammar.toml`, `cast.toml`, and the EPUB files that
the grammar names. `examples/soultale/` holds the configuration for Soultale.

## Where a change lives

| Change | Files |
| ------ | ----- |
| A rule about the shape of a chapter | `examples/soultale/grammar.toml`, and `src/openbook/config/grammar.py` only when the rule needs a new key |
| A new kind of segment | `src/openbook/parse/`, then the planner and the renderer |
| A voice for a character | `examples/soultale/cast.toml` |
| How a word is spoken | the lexicon file, not the source text |
| A new command | `src/openbook/cli.py` and `tests/test_cli.py` |
| A speech engine | `src/openbook/speech/`, behind the engine interface |

## Rules that this project holds to

- **Code and its tests go in one commit. Documents go in their own.**
- **A commit carries no version prefix and changes no version.** The version in
  `pyproject.toml` moves only when something is released.
- **An error that a person can correct is an `OpenBookError`.** It names the
  file, the key, or the chapter that the person must change. An error that a
  person cannot correct stays an ordinary exception and keeps its traceback.
- **A configuration key that nothing reads is an error.** A file that ignores a
  misspelled key lies about what it does, and the person then looks for the
  reason in the audio.
- **A speaker code with no voice stops the build.** A finished audiobook with a
  wrong voice in it is worse than no audiobook.
- **Run it. Do not conclude that it works.** Say so plainly when a measurement
  does not support the conclusion.

## Before you open a pull request

Run these, exactly as the workflow does:

    uv run ruff format --check .
    uv run ruff check .
    uv run pytest

Add tests for what you change. A test that reads the example configuration is
better than a test that writes its own, because the example is the only
configuration the project has, and a change that breaks it breaks the tool.

## Style

- Match the code around you. Small functions and clear names.
- Add a dependency only with a reason. The core of OpenBook declares none, and
  reads EPUB files, configuration, and text with the standard library. A speech
  engine needs more, and it belongs in the optional group.
- Write documents and comments in plain sentences. Use no em-dash and no emoji
  in source, documents, commit messages, or examples.

## Commit messages and pull requests

- Write a present-tense subject that describes the change.
- Keep one logical change in one commit.
- In the pull request, say what changed, why, and how you tested it.

## Reporting a security problem

Do not open a public issue. See [SECURITY.md](SECURITY.md).

## Code of conduct

By taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
