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
| Levelling | -25.2 LUFS raw, -19.1 after |
| Encoding the video | 2 minutes, 214 MB |

Built: the EPUB reader, the parser, the cast, the planner, the lexicon and its
word finder, the Kokoro and silent engines, the cache, loudness, the M4B, the
video with its cards and description and captions, the review page, and the
checks that refuse a video whose picture and sound disagree.

## Still to build

### The other half of the review loop

The page marks a line and copies out a block of corrections. Nothing reads that
block back, so a marked line is not yet remade.

- [ ] Read `corrections.toml` when planning, and use the corrected words in
      place of the original.
- [ ] Put the correction into the cache key, so a marked line is made again and
      nothing else is.
- [ ] Report how many corrections were used, so a person can see that the file
      is being read at all.

### Speaking

- [ ] The `mix` mode for a line two characters say together. It refuses with a
      reason today. `voice_blend` covers the three lines in this book, so this
      only matters for a book that needs the two voices kept apart.
- [ ] A second engine, so a character can be spoken by something other than
      Kokoro. The interface is there and nothing else uses it yet.

### Repository

- [ ] A test that checks the number in the readme badge against the number of
      tests, so the badge cannot go stale on its own.
- [ ] `CHANGELOG.md`, once there is a release to write in it.
- [ ] Decide whether this goes to PyPI, and add a release workflow if it does.

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
