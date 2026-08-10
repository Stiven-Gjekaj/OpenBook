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

Done. The finder reports 539 words over the whole book.

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

Done. Kokoro speaks, and a silent engine gives the right timing without a model.

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

Mostly done. The M4B is written with its chapter marks. Loudness levelling and the per-chapter Opus are not.

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

A site where a person reads Soultale and listens to it. This is not a page
about the tool. It is the book itself, with the audio beside the text.

The site is made by the same pipeline that makes the audio. One parse gives
both, so the words on the page and the words in the audio cannot disagree.

- [ ] Write the chapters out as HTML from the parsed segments.
- [ ] A player beside the text, with one file for each chapter.
- [ ] Remember where a person stopped, in their own browser.
- [ ] Move the text with the audio, at least by paragraph, because the parse
      already knows where each piece of speech starts.
- [ ] A page for each volume, and a way to reach any chapter.
- [ ] A link to download the M4B of a volume, for a person who wants it in an
      audiobook application.
- [ ] Build with no framework. The pages are made from data that this project
      already holds.

### The two audio formats

The volume M4B is for downloading, and it is wrong for the web. Volume 9 is
about nine hours in one file, and a browser must fetch a large part of it to
start in the middle.

- [ ] Write one Opus file for each chapter, beside the M4B of each volume.
      Opus at about 32 kbit for one channel is good for speech, and the whole
      book is then near 680 MB. The player fetches one chapter, seeks in it
      quickly, and loads nothing else.

### Where to host it

The text is small. The audio is not, and the audio decides this.

**The pages: Cloudflare Pages.** Free, no charge for bandwidth on a static
site, a custom name at no cost, and it builds from this repository on a push.

**The audio: Cloudflare R2.** It charges nothing to send data out, ever. The
whole book costs about one cent each month to store, and a thousand listeners
cost the same as one. Every other object store charges for each gigabyte that
leaves it, and that bill grows exactly when the book does well.

**Not GitHub Pages, for the audio.** A published site should stay under a
gigabyte and a hundred gigabytes each month, and GitHub asks that Pages is not
used to serve media. 47 hours of audio reaches the first limit and passes the
second with few listeners. Git also keeps every version of a binary file
forever, so each new render makes the repository permanently larger.

GitHub Pages is still fine for the text alone, if the audio lives elsewhere.
Backblaze B2 behind Cloudflare gives the same free egress as R2 with more
setup. Bunny is cheap and good for media, but not free. The Internet Archive
costs nothing and keeps things for a long time, and is worth a copy as a
second home, but it gives no control over the player.

- [ ] Put the audio in R2 and the pages in Cloudflare Pages.
- [ ] A workflow that publishes the pages on a push to the default branch.
- [ ] A command that uploads only the audio that changed.
- [ ] Keep the site out of the test and lint runs, or give it its own.

## Documents

- [ ] `docs/architecture.md`: the stages, and what each one hands to the next.
- [ ] `docs/configuration.md`: every key of both files, and what it does.
- [ ] `CHANGELOG.md`, once there is a release to write in it.
- [ ] A note in the readme about which speech models work, once one does.

## Repository

- [ ] Move the test count in the readme when the number changes. A test should
      check it, so that the badge cannot go stale on its own.
- [ ] Decide whether the project goes to PyPI. If it does, a release workflow.
