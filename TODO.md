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

### The first chapter through Chatterbox

The engine is built and nothing has read a chapter with it yet. Three numbers
decide whether it stays, and none of them can be guessed:

- [ ] How fast it reads on this machine. Kokoro does about ten times real
      time, so a four hour volume takes twenty three minutes. A model that
      makes a token at a time will be slower, and how much slower decides
      whether a volume is an afternoon or a week.
- [ ] Whether it drops or repeats a word over a whole chapter. This is the one
      risk Kokoro does not carry, and listening is the only thing that finds
      it.
- [ ] Whether the narrator still sounds like one person from the first chapter
      to the last.

Nothing is lost either way. The cache keys on the engine, so a chapter read by
each engine can sit side by side and be compared.

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

- [ ] **A recording for each of the 44 codes in Volume 1.** The book now reads
      in the voice of a recording rather than choosing from a list of twenty
      eight, so this is no longer a naming job. Ten to twenty seconds of clean
      speech for each character, in `voices/`, named in `cast.toml`.
      `openbook check --engine chatterbox` says which ones are not there yet.

      What is in the recording is what comes out, including the room it was
      recorded in and anything behind it. Two of these matter more than the
      rest: the narrator reads 79 percent of the book, and Blook has 160 lines.

      A recording of a real person is that person's voice. Recording them
      yourself, or taking one from the public domain, is the road with no
      complaint at the end of it. See [TERMS.md](TERMS.md).
- [ ] **The 539 pronunciations.** `openbook words --write` has already written
      them into `lexicon.toml` with each sound left blank, most frequent first.
      Vazroth alone is said 273 times. The first twenty entries cover most of
      what a listener would notice.
- [ ] **The licence of the MonsterFriend font.** The Determination font is
      CC BY 3.0, its credit is written into every description, and its licence
      sits beside it in `examples/soultale/fonts/`. The logo face came with no
      licence file and is a fan recreation of a face owned by Toby Fox. Both
      files are in the repository and the open question is written down in
      `examples/soultale/fonts/NOTICE.md`. Settle it, or replace the face,
      before a volume goes up.
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
