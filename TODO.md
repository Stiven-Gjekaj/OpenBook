<div align="center">
  <a href="README.md"><img src="assets/openbook.svg" alt="OpenBook" height="44"></a>
</div>

# What is left to build

This file holds every task that OpenBook still needs. The first goal is one
volume of Soultale, made into an audiobook from end to end, with nothing wrong
in it. Volume 1 is that volume: 23 chapters, about four hours, and 46 speaker
codes.

A task with a box is not built. A task without one is done.

## Built already

- The project, the pinned interpreter, and the tools.
- A workflow that tests on three systems and two versions of Python.
- The errors, and the template compiler that turns a template into a regular
  expression.
- The configuration reader, which refuses a key that nothing reads.
- The grammar file and the cast file, with chapter groups for an unknown
  speaker.
- The EPUB reader. It follows the spine, joins more than one file, drops a
  chapter it already has, and passes over the volumes that the configuration
  skips. It reads all 325 chapters of Soultale.
- The commands `chapters` and `check`.

## Stage: parse

The next piece. Everything after it waits for this.

- [ ] Turn the body of a chapter into typed segments: heading, narration,
      dialogue, action, scene break, end matter.
- [ ] Divide a paragraph at every line break before looking for a speaker.
      Nearly two thirds of the dialogue lines share a paragraph with another
      one, so a parser that reads a paragraph as one unit gets most of the
      dialogue wrong.
- [ ] Remove the elements that carry only style, and keep the text inside them.
- [ ] Decode the XML entities. The unison separator arrives as `&amp;`, and the
      rule finds nothing without this step.
- [ ] Find an action inside a line of dialogue, and give it its own segment.
- [ ] Report a line of dialogue that holds an odd number of asterisks. About 21
      of these exist, where the editor made half of a pair into italic text and
      left the other half behind. A balanced pattern cannot see them, and a
      stray asterisk must not reach a voice.
- [ ] Tests that use the real shapes: a packed paragraph, a unison line, an
      action, a scene break, and a chapter with no dialogue at all.

## Stage: cast and plan

- [ ] Give every segment a voice, through the cast file.
- [ ] Stop the build on a speaker code with no entry, and on an entry with no
      voice, and name the chapter.
- [ ] Speak a unison line with one voice made from the two style vectors.
- [ ] Put a pause only where the kind of the text changes. Two dialogue lines
      together get none, and two narration paragraphs together get none.
- [ ] Divide a long segment at a sentence end, so that no single piece is
      longer than the engine accepts. Use a real sentence splitter and not a
      full stop.
- [ ] Write the plan out as a manifest that the cache can key on.
- [ ] A command that prints the plan for a chapter, so a person can read every
      line and its voice before any audio exists.

## Stage: lexicon

- [ ] Read `lexicon.toml`.
- [ ] Find the words that need an entry: compare every word of the book against
      the dictionary of the phonemizer, and report what is missing, most
      frequent first, with a chapter that holds it.
- [ ] Put the entries into the text at plan time, so that the manuscript stays
      clean.
- [ ] A command that prints the report.

This is the largest quality problem in the whole project. A fixed voice says an
invented name the same wrong way for 47 hours, and no casting decision repairs
that.

## Stage: speech

- [ ] An engine interface, so that a character can use a different engine from
      the narrator.
- [ ] The Kokoro engine.
- [ ] Voice blending, both for a unison line and to widen the set of voices
      past the ones the model ships.
- [ ] A cache that keys on the text, the voice, the engine, its settings, and
      the version of the model. A correction to one line then re-makes one line.
- [ ] A retry for an engine that can fail, with a limit, because a model that
      generates one word at a time sometimes repeats itself or stops early.

## Stage: audio and packaging

- [ ] Join the pieces with the silences that the plan asks for.
- [ ] Level the loudness to the audiobook standard.
- [ ] Write one M4B file for each volume, with a chapter mark for each chapter.
- [ ] Take the cover and the author out of the EPUB metadata for the file tags.
- [ ] Name the file from the pattern in the configuration.

## Review

- [ ] A page, written after a render, that lists every piece of speech with its
      chapter, speaker, voice, text, and a button to hear it.
- [ ] A list of the pieces worth looking at first: the long ones, a speaker
      code seen for the first time, a line with digits or capitals, and a word
      that the lexicon does not have.
- [ ] A file of corrections that the render reads, so that a marked line is
      made again and nothing else is.

## The website

A site for the project, in this repository, built from the same documents.

- [ ] Write the pages: what OpenBook is, how to install it, how to write the two
      configuration files, and what each stage does.
- [ ] Put a few short pieces of audio on the page. A person deciding whether to
      use this wants to hear it, and no description of a voice is worth ten
      seconds of one.
- [ ] Build the site with no framework. The content is a handful of pages, and a
      build tool would be larger than the thing it builds.
- [ ] A workflow that publishes on a push to the default branch.
- [ ] Keep the site out of the test and lint runs, or give it its own.

**Where to host it: GitHub Pages.** The repository is already here, so there is
no second account and no third party that has to stay working. Publishing is a
workflow in this repository, which means the site cannot fall behind the code
without the same commit that moved the code. A custom name costs nothing, and
the same pattern already runs on MiruScriptX.

Cloudflare Pages is the one to change to later, and only for a reason: it
serves from more places, and it can run code at the edge. A page that describes
a command line tool needs neither. Netlify and Vercel are the same answer with
another account attached.

## Documents

- [ ] `docs/architecture.md`: the stages, and what each one hands to the next.
- [ ] `docs/configuration.md`: every key of both files, and what it does.
- [ ] `CHANGELOG.md`, once there is a release to write in it.
- [ ] A note in the readme about which speech models work, once one does.

## Repository

- [ ] Move the test count in the readme when the number changes. A test should
      check it, so that the badge cannot go stale on its own.
- [ ] Decide whether the project goes to PyPI. If it does, a release workflow.
