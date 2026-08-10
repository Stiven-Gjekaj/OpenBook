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

Done. Over the whole book it finds 7163 lines of dialogue, 186 speaker codes,
48 actions, 3 lines that two characters say together, and 665 pieces of end
matter.

- Turns the body of a chapter into typed segments: narration, dialogue,
  action, scene break, end matter.
- Divides a paragraph at every line break before it looks for a speaker.
- Removes the elements that carry only style, and keeps the text in them.
- Decodes the entities, so that the unison separator is found.
- Takes an action out of a line of dialogue and keeps it as a piece of that
  line, because the words on both sides belong to one breath.
- Reports an asterisk with no pair, in narration as well as dialogue. The book
  has one, in chapter 314.

## Stage: cast and plan

Done.

- Give every segment a voice, through the cast file.
- Stop the build on a speaker code with no entry, and on an entry with no
  voice, and name the chapter.
- Speak a unison line with one voice made from the two style vectors.
- Put a pause only where the kind of the text changes. Two dialogue lines
  together get none, and two narration paragraphs together get none.
- Divide a long segment at a sentence end, so that no single piece is
  longer than the engine accepts. Use a real sentence splitter and not a
  full stop.
- Write the plan out as a manifest that the cache can key on.
- A command that prints the plan for a chapter, so a person can read every
  line and its voice before any audio exists.

## Stage: lexicon

Done. The finder reports 539 words over the whole book.

- Read `lexicon.toml`.
- Find the words that need an entry: compare every word of the book against
  the dictionary of the phonemizer, and report what is missing, most
  frequent first, with a chapter that holds it.
- Put the entries into the text at plan time, so that the manuscript stays
  clean.
- A command that prints the report.

This is the largest quality problem in the whole project. A fixed voice says an
invented name the same wrong way for 47 hours, and no casting decision repairs
that.

## Stage: speech

Done. Kokoro speaks, and a silent engine gives the right timing without a model.

- An engine interface, so that a character can use a different engine from
  the narrator.
- The Kokoro engine.
- Voice blending, both for a unison line and to widen the set of voices
  past the ones the model ships.
- A cache that keys on the text, the voice, the engine, its settings, and
  the version of the model. A correction to one line then re-makes one line.
- A retry for an engine that can fail, with a limit, because a model that
  generates one word at a time sometimes repeats itself or stops early.

## Stage: audio and packaging

Mostly done. The M4B is written with its chapter marks. Loudness levelling and the per-chapter Opus are not.

- Join the pieces with the silences that the plan asks for.
- [ ] Level the loudness to the audiobook standard.
- Write one M4B file for each volume, with a chapter mark for each chapter.
- [ ] Take the cover and the author out of the EPUB metadata for the file tags.
- Name the file from the pattern in the configuration.

## Review

The largest piece still missing.

- [ ] A page, written after a render, that lists every piece of speech with its
  chapter, speaker, voice, text, and a button to hear it.
- [ ] A list of the pieces worth looking at first: the long ones, a speaker
  code seen for the first time, a line with digits or capitals, and a word
  that the lexicon does not have.
- [ ] A file of corrections that the render reads, so that a marked line is
  made again and nothing else is.

## Release on YouTube

Built. One video for each volume, with a card for each chapter, a description
carrying a time for each chapter, and captions.

- Writes an MP4 of a still card per chapter, with the volume named above the
  work and the chapter below it.
- Puts music under the speech and compresses it against the voice, so the bed
  drops where somebody talks.
- Writes the description with a time for each chapter, the words of the author,
  an optional sneak peek from the opening, and the credits a licence asks for.
- Writes captions from the render itself. Nothing listens to the audio, so the
  invented names are spelled correctly and every line carries the name of who
  says it.
- The narrator reads an intro and an outro, in the words of the author, each
  taking a chapter mark of its own.
- Refuses before encoding when a card and the narration disagree, when the
  cards drift from the chapters, or when a volume is longer than YouTube takes.

Measured on volume 1: 3 hours 49 minutes, 214 MB, two minutes to encode.

### Still to do here

- [ ] Level the loudness to the audiobook standard. Nothing does this yet, and
      a volume that is quieter than the one before it is the first thing a
      listener notices.
- [ ] Put the cover and the author from the EPUB metadata into the M4B tags.
- [ ] Give the MP4 its own chapter marks. YouTube reads the description
      instead, so this is only for a player that is not YouTube.
- [ ] Write captions beside the M4B as well, not only beside the video.
- [ ] Divide a volume into parts of about two hours. The grouping already
      lives in configuration, so this extends merge_volumes to named spans of
      chapters rather than adding anything new. Arc boundaries beat the two
      hours whenever the two disagree.

## Documents

- [ ] `docs/architecture.md`: the stages, and what each one hands to the next.
- [ ] `docs/configuration.md`: every key of both files, and what it does.
- [ ] `CHANGELOG.md`, once there is a release to write in it.
- [ ] A starter lexicon written by the tool, holding the words it found and
      leaving the sound of each one blank, the way the cast file was made.
- [ ] A note in the readme about which speech models work, once one does.

## Repository

- [ ] Move the test count in the readme when the number changes. A test should
  check it, so that the badge cannot go stale on its own.
- [ ] Decide whether the project goes to PyPI. If it does, a release workflow.
