<div align="center">

<img src="assets/openbook.svg" alt="OpenBook" width="180">

### Turns a book into an audiobook on your own machine, with a different voice for each character

_Reads EPUB, separates narration from dialogue, writes one file for each volume_

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12 or newer"/>
  <img src="https://img.shields.io/badge/tests-542_passing-427819?style=for-the-badge" alt="542 tests passing"/>
</p>

<p align="center">
  <a href="https://www.youtube.com/@SoultaleLibrary"><img src="https://img.shields.io/badge/Listen_on_YouTube-Soultale_Library-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="The Soultale Library channel on YouTube"/></a>
</p>

<p align="center">
  <a href="https://github.com/Stiven-Gjekaj/OpenBook/actions/workflows/ci.yml"><img src="https://github.com/Stiven-Gjekaj/OpenBook/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT License"/>
</p>

<p align="center">
  <a href="#quick-start"><b>Quick Start</b></a> |
  <a href="#how-it-works"><b>How it works</b></a> |
  <a href="#configuration"><b>Configuration</b></a> |
  <a href="#documentation"><b>Documentation</b></a> |
  <a href="TODO.md"><b>Roadmap</b></a>
</p>

</div>

---

## Overview

**OpenBook** reads the chapters of a book out of an EPUB file, divides the text
into narration and dialogue, gives each character the voice you chose for them,
and joins the result into one audio file for each volume. It runs on your own
machine with open source speech models. Nothing is uploaded, there is no
account, and there is no cost for each hour of audio.

It reads one book format, the format of Soultale, in which a line of dialogue
starts with a short code for the character speaking it:

```
The light arrives like violence. Not gentle. Not gradual.

JHN: Did you feel that?
JHN: Everyone felt that. Question is what it means.

I stop. Which means nothing. But the hesitation feels real.
```

Every rule of that format lives in a configuration file rather than in the
code, so a fork describes a different book by writing a different grammar file.

The pipeline runs end to end. One command reads the EPUB files and writes a
levelled M4B with chapter marks and a cover, a video for YouTube with a card
for each chapter, a description carrying the time of each chapter, captions,
and a page for checking the result by ear.

What is left is the author's own work: the voices, the pronunciations, and the
music. [TODO.md](TODO.md) holds every task, with the reason for each.

## Features

<table>
<tr>
<td width="50%" valign="top">

### Reading a book

- Reads one or more EPUB files as one book
- Follows the spine, so the order is the reading order and not the order of the
  file names
- Joins parts that overlap, and keeps one copy of a repeated chapter
- Passes over the volumes you tell it to skip
- Groups the finished audio by volume, and can fold a short volume into another
  or split a long one into named parts
- Passes over a cover and a table of contents without being told to

</td>
<td width="50%" valign="top">

### Configuring it

- Templates rather than regular expressions: `(Chapter {NUMBER} || {VOLUME})`
- A regular expression is there for a rule a template cannot say
- A key that nothing reads is an error, and the message names the key you meant
- A speaker code with no voice stops the build and names the chapter
- One speaker code can be several characters, chosen by chapter, for a
  character whose name the story has not given yet
- Two characters can share a line, in one blended voice or as two readings laid
  over each other and held in step

</td>
</tr>
</table>

## Quick Start

You need [uv](https://docs.astral.sh/uv/).

```
git clone https://github.com/Stiven-Gjekaj/OpenBook
cd OpenBook
uv sync
```

Make a project directory. It holds your EPUB files and two configuration files.
Copy the ones for Soultale to start:

```
mkdir -p ~/audiobook && cp examples/soultale/*.toml ~/audiobook/
```

Put your EPUB files beside them, and name them in `grammar.toml` under
`source.files`. Then read the configuration and the book:

```
uv run openbook -C ~/audiobook check
```

```
grammar      reads 2 book file(s)
book         325 chapters in 9 volumes
cast         46 speaker codes
             the narrator has no voice yet
             46 of them have no voice yet
ffmpeg       found
not ready
```

List what the audiobook will contain:

```
uv run openbook -C ~/audiobook chapters --volume "Prologue"
```

```
   0  Prologue    Point - Null.
   1  Prologue    What I Hold Dear.
   2  Prologue    On The 7th Day.
```

## How it works

```
EPUB files -> chapters -> segments -> utterances -> a manifest -> audio -> one file per volume
```

The first stages need the standard library only. They hold nearly every rule
the book brings with them, they run in under a second, and you can read the
whole parse of a book, and the voice of every line in it, before any audio
exists.

Each piece of audio is stored under a key made from its text, its voice, its
engine, and the version of the model. Correcting one line makes one line again.
Changing a voice makes one character again. This is what lets the narrator and
the cast use different speech models, and it is why the cache comes first
rather than last.

On an Apple M5, Kokoro makes about **10.6 seconds of speech for each second it
runs**. A four hour volume takes about twenty minutes, and the whole of
Soultale, at 47 hours, takes about four and a half. The second render of
anything takes seconds, because only what changed is made again.

Five engines use one interface, chosen with `--engine`. **chatterbox** reads
the book in the voice of a recording you supply, and **chatterbox-turbo** is
the same through a newer model that reads about twice as fast and holds one
loudness by itself. **kokoro** chooses from its own list of voices and is the
one to fall back to. **espeak-ng** sounds like a machine from the 1990s and needs no model, no
download and no Python package, so a whole volume can be checked against real
speech in seconds. **silent** is the default and is a clock: quiet of the
length the words would take, for checking the pauses and the chapter marks
with nothing installed at all.

Chatterbox makes a token at a time, so it can drop a word where Kokoro cannot,
and a dropped word is found by nothing except listening. It takes less text at
once for that reason, and its reading is seeded from the words and the voice so
a line remade next week matches the chapter around it. The rest is what the
review page is for.

See [docs/architecture.md](docs/architecture.md) for the whole picture.

## Configuration

Two files are needed, and both are commented line by line.

**[grammar.toml](examples/soultale/grammar.toml)** says what a chapter looks
like: how a heading reads, how a line of dialogue is marked, which volumes to
skip, how long each silence is, and how the finished audio is divided.

```toml
chapter_title = "(Chapter {NUMBER} || {VOLUME}) {TITLE}"
skip_volume_pattern = '^Archive'

[render]
pause_dialogue_to_narration = "400ms"
pause_narration_to_dialogue = "600ms"
```

A pause falls only where the kind of the text changes. Two lines of dialogue
together get none, so a conversation stays quick.

**[cast.toml](examples/soultale/cast.toml)** gives a voice to each speaker
code.

```toml
[narrator]
voice = "af_heart"

[cast.BLK]
name  = "Blook"
voice = "am_michael"

[[cast_range."???"]]
chapters = "115-120"
name     = "Unknown, volume 4"
voice    = "bm_george"
```

The last one is for a character the story has not named. That code is a
different character in each part of the book, so it takes one entry for each
group of chapters, and the chapter number chooses. A `???` line in a chapter
that no group covers stops the build, because a new mystery character needs a
new voice and the tool must ask rather than choose.

Two more files are optional. **`lexicon.toml`** says how an invented name is
said, everywhere in the book. **`corrections.toml`** says what one line should
say instead. See [docs/configuration.md](docs/configuration.md) for every key
of every file.

## Checking it by ear

A test can say a line was made. Only a person can say it sounds right, and
nobody listens to forty seven hours to find the six lines that went wrong.

```
uv run openbook -C ~/audiobook render --volume "Volume 1" --review
```

That writes a page beside the audiobook listing every line with the voice it
took and a button that plays it. The lines most likely to be wrong come first:
the long ones, the first line each character speaks, the ones holding a number
or a run of capitals, and the ones using a word with no pronunciation entry.

Mark what sounds wrong, press **copy what I marked**, and paste the result into
`corrections.toml`:

```toml
[corrections]
"He turned to face the Vazroth." = "He turned to face the Vaz-roth."
```

Render again. The cache keys each piece of audio on its text, so a correction
makes that one line again and takes every other line from the cache. A four
hour volume comes back in seconds. `openbook check` refuses a correction that
matches no line in the book, because a correction that quietly matches nothing
is found only by listening to the same fault twice.

## Project structure

A project directory holds your book, your configuration, and everything the
tool makes from them. `out/` holds the finished files, `cache/` the audio
already made, `voices/` your recordings, and `.work/` the half finished pieces.
Nothing is written outside it except the speech models, which live in
`~/.cache/huggingface` and are shared with every other project on the machine.

```
src/openbook/       the pipeline
  config/           reads and checks the configuration files
  source/           reads chapters out of EPUB files
  parse/            turns a chapter into typed segments
  cast/             gives each segment a voice
  plan/             puts the silences in and divides long lines
  speech/           engines, the cache, and the audio
  lexicon.py        how a word is said
  corrections.py    what to say instead, for a line that came out wrong
  review.py         the page for checking a render by ear
  build.py          runs the stages in order
  cli.py            the command line
tests/              the tests
examples/soultale/  the working project: configuration, book, and fonts
docs/               how the parts fit together
assets/             the logo
```

## Documentation

<table>
<tr>
<td align="center" width="16%" valign="top">
<h3>Build</h3>
<p>How the stages<br/>fit together</p>
<a href="docs/architecture.md"><b>Architecture</b></a>
</td>
<td align="center" width="16%" valign="top">
<h3>Configure</h3>
<p>Every key of<br/>every file</p>
<a href="docs/configuration.md"><b>Configuration</b></a>
</td>
<td align="center" width="16%" valign="top">
<h3>Plan</h3>
<p>Every task<br/>that is left</p>
<a href="TODO.md"><b>Roadmap</b></a>
</td>
<td align="center" width="16%" valign="top">
<h3>Help</h3>
<p>When it refuses<br/>to run</p>
<a href="SUPPORT.md"><b>Support</b></a>
</td>
<td align="center" width="16%" valign="top">
<h3>Join in</h3>
<p>How to work<br/>on this</p>
<a href="CONTRIBUTING.md"><b>Contributing</b></a>
</td>
<td align="center" width="16%" valign="top">
<h3>Follow</h3>
<p>What changed,<br/>and when</p>
<a href="CHANGELOG.md"><b>Changelog</b></a>
</td>
</tr>
</table>

## Testing

```
uv run pytest
```

The tests read the example configuration rather than writing their own, because
the example is the only configuration the project has, and a change that breaks
it breaks the tool.

The test that reads an EPUB builds its archive backwards, so a reader that
trusts the order of the files inside the zip instead of the spine gets the book
in reverse and the test says so.

One test counts the tests and compares the answer with the badge at the top of
this page. A badge is a claim, and a claim that nothing checks goes stale the
first time somebody adds a test.

The same checks run in the workflow, on Linux, Windows, and macOS, against
Python 3.12 and 3.13, together with `ruff format --check` and `ruff check`.

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md),
follow the [Code of Conduct](CODE_OF_CONDUCT.md), and see
[SUPPORT.md](SUPPORT.md) if you need help.

## A note on rights

OpenBook makes a recording of a text that you supply, and gives you no right to
that text. The speech models carry their own licences, and some permit less
than this project does. A voice copied from a recording can belong to the person
who owns it. See [TERMS.md](TERMS.md).

## License

MIT. See [LICENSE](LICENSE) for the text, and [TERMS.md](TERMS.md) for the terms
of the project.

<div align="center">
<sub>Built to make one book listenable. Start at the <a href="TODO.md">roadmap</a>.</sub>
</div>

