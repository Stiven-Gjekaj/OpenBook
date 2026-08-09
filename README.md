# OpenBook

Turns a book in EPUB form into an audiobook, on your own machine, with a
different voice for each character.

OpenBook reads the chapters out of an EPUB file, divides the text into
narration and dialogue, gives each character the voice you chose for them, and
joins the result into one audio file for each volume. Nothing leaves the
machine it runs on.

The project reads one book format, the format of Soultale, in which a line of
dialogue starts with a short code for the character who speaks it. The format
is described by a configuration file, so a fork can describe a different one.

## Status

Early. The pipeline is being built from the text end.

## Install

    uv sync

## Test

    uv run pytest

## License

MIT. See [LICENSE](LICENSE).
