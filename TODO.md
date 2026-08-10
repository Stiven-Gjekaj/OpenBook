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

- [ ] A page, written after a render, that lists every piece of speech with its
  chapter, speaker, voice, text, and a button to hear it.
- [ ] A list of the pieces worth looking at first: the long ones, a speaker
  code seen for the first time, a line with digits or capitals, and a word
  that the lexicon does not have.
- [ ] A file of corrections that the render reads, so that a marked line is
  made again and nothing else is.

## Release on YouTube

One video for each volume. The website is not being built.

YouTube takes video and not audio, so a volume becomes a still picture with the
sound behind it. The cover of the book is inside each EPUB file already, so
nothing new has to be drawn.

- [ ] A command that writes one video for each volume: the cover held still,
      with the audio of the volume behind it.
- [ ] Encode as H.264 in MP4, with the picture at one frame each second and the
      encoder told it is a still. A nine hour video of one picture is then
      small and quick to make.
- [ ] Give the sound at 48000 samples a second, in two channels. Kokoro makes
      24000 in one channel, and YouTube changes whatever it is given. Doing the
      change here means it happens once and well, rather than twice.
- [ ] Write the description of the video beside it, with a time for each
      chapter. YouTube reads those times and makes its own chapter list from
      them. The first one has to be 0:00, there have to be at least three, and
      each has to last at least ten seconds. The render already knows where
      every chapter starts, so this is only a change of form.
- [ ] Check the length of each volume against the twelve hour limit of a
      video. Volume 9 is the longest at about nine hours, so all of them fit,
      but the check should exist before one of them does not.

The M4B stays. It is what a person downloads for an audiobook application, and
it is where the video takes its sound from.

The per-chapter Opus files are no longer needed. They existed so a browser
could start in the middle of a volume without fetching all of it, and there is
no browser now.

## Documents

- [ ] `docs/architecture.md`: the stages, and what each one hands to the next.
- [ ] `docs/configuration.md`: every key of both files, and what it does.
- [ ] `CHANGELOG.md`, once there is a release to write in it.
- [ ] A note in the readme about which speech models work, once one does.

## Repository

- [ ] Move the test count in the readme when the number changes. A test should
  check it, so that the badge cannot go stale on its own.
- [ ] Decide whether the project goes to PyPI. If it does, a release workflow.
