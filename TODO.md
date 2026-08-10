<div align="center">
  <a href="README.md"><img src="assets/openbook.svg" alt="OpenBook" height="44"></a>
</div>

# What is left to build

A task with a box is not built. A task without one is done.

## Where things are

The chain runs from end to end. One command reads the EPUB files and writes a
levelled M4B with chapter marks and a cover, a video for YouTube with a card
for each chapter, a description carrying the time of each chapter, captions,
and a page for checking the result by ear.

Measured on Volume 1 of Soultale, which is 23 chapters and 3 hours 49 minutes:

| | |
| --- | --- |
| Reading and parsing the whole book | under a second, 325 chapters |
| Speaking it with Kokoro | 23 minutes, about ten times faster than real time |
| Speaking it again after a change | seconds, from the cache |
| Speaking one corrected line again | one piece made, the rest from the cache |
| Levelling | -25.2 LUFS raw, -19.1 after |
| Encoding the video | 2 minutes, 214 MB |

Built: the EPUB reader, the parser, the cast, the planner, the lexicon and its
word finder, three engines, the cache, loudness, the M4B, the video with its
cards and description and captions, the review page and the corrections it
writes, and the checks that refuse a video whose picture and sound disagree.

## Still to build

The list of code is short now. Everything below is small, and none of it stops
a volume being made.

### Speaking

- [ ] A way to add the words a new chapter brought to a `lexicon.toml` that
      already exists. `openbook words --write` refuses to write over a file, so
      that nothing you wrote is lost, and there is no way yet to put only the
      new blanks in.

### Repository

- [ ] Publish to PyPI. **Not yet, and here is the condition.** Publishing is a
      promise that the command line and the shape of the configuration files
      will not move under somebody, and neither has yet been through a real
      release of a real book. A tag builds the package and attaches it to a
      release on GitHub, and `uv add` installs from a git tag in one line, so
      nothing is blocked by waiting. Publish once the first volume is out and
      the configuration has survived it.

## Dropped

- **A website.** The audiobooks go to YouTube instead.
- **One Opus file for each chapter.** It existed so a browser could start in
  the middle of a volume without fetching all of it, and there is no browser.
- **Cloudflare Pages and R2.** They went with the website.

## Waiting on the author

None of this is work the tool can do. All of it blocks a real release.

- [ ] **A voice for each of the 44 codes in Volume 1**, with the gender and the
      accent of each. The current audio uses placeholders handed out in order,
      so it proves the pipeline and nothing else.
- [ ] **The 539 pronunciations.** `openbook words --write` has already written
      them into `lexicon.toml` with each sound left blank, most frequent first.
      Vazroth alone is said 273 times. The first twenty entries cover most of
      what a listener would notice.
- [ ] **The licence of the MonsterFriend font.** The Determination font is
      CC BY 3.0 and its credit is already written into every description. The
      logo face came with no licence file.
- [ ] **Music, and clearing it.** A bed is mixed and ducked when one is named.
      Whatever is chosen has to survive Content ID, because a claim against the
      music affects the whole video.
- [ ] **Uploading.**

## Rules this project holds to

Written down because each one was learned from something that went wrong.

- **Check the thing that was made, not only the test.** Every fault in the
  video path was found by probing the finished file. None of them raised
  anything.
- **Check the caller's situation before the machine's.** A missing picture was
  twice reported as a missing tool. The caller can see their own problem.
- **A tool must read what it writes.** The first lexicon it wrote would not
  parse, because a word holding an apostrophe is not a name TOML accepts.
- **A rule about the book lives in configuration, never in the code.**
- **A refusal is better than a guess** wherever a wrong answer would only be
  found by listening.
- **A test that needs a program says so, and skips without it.** ffmpeg and
  espeak-ng are installed on one runner of the six, so a test that takes them
  for granted passes here and fails on five machines. Run the suite with both
  off the path before pushing.
- **A number written on the page is a claim, and a claim gets a test.** The
  badge said 336 tests for a long time while there were 426.
