<div align="center">
  <a href="README.md"><img src="assets/openbook.svg" alt="OpenBook" height="44"></a>
</div>

# Changelog

Every release is written here, newest first. A version is `MAJOR.MINOR.PATCH`.
A change to the shape of a configuration file, or to what a command prints,
raises the minor number while the major number is 0.

A tag such as `v0.2.0` builds the package and attaches it to a release on
GitHub. Nothing goes to PyPI yet, and [TODO.md](TODO.md) says why.

## Unreleased

Nothing is released. The whole list below is what is in the repository, and it
waits on the first volume of Soultale: a tool that has not finished the one
book it was written for has not been tested, whatever its tests say.

### It reads a book

- Reads one or more EPUB files as one book, in the order of the spine rather
  than the order of the file names.
- Keeps one copy of a chapter that two files both hold.
- Passes over the volumes named in `skip_volume_pattern`, and over a cover and
  a table of contents without being told to.
- Reads the name of each volume out of the archive chapters, so a volume is
  named in one place.

### It parses a chapter

- Divides narration from dialogue with the rules in `grammar.toml`, and holds
  no rule about any one book in the code.
- Divides a paragraph at every line break before looking for a speaker,
  because two thirds of the dialogue in Soultale shares a paragraph.
- Reads an action written in asterisks inside a line of dialogue, and makes it
  a pause, gives it to the narrator, or drops it.
- Says what it noticed and could not answer, rather than guessing.

### It casts and plans

- Gives each speaker code a voice, and stops the build when a code has none.
- One code can be several characters, chosen by the chapter, for a character
  the story has not named.
- A line two characters say together takes one blended voice, both voices laid
  over each other, both voices held in step with each other, or the voice of
  the first of them.
- Puts a silence only where the kind of the text changes, so a conversation
  keeps its speed.
- Divides a line too long for the engine at the end of a sentence, then at a
  clause, then between two words, in that order.

### It speaks

- Chatterbox, which reads the book in the voice of a recording you supply, its
  Turbo model, which reads about twice as fast and holds one loudness by
  itself, Kokoro, espeak-ng, and a silent engine that gives quiet of the right
  length.
- IndexTTS 2, the only engine here that can raise its voice. It reads the same
  recordings and keeps the feeling apart from the speaker, so a character can
  murmur and shout in one voice. Turbo reads such a pair 0.3 dB apart and this
  reads it 15.5 dB apart. It costs about eight times what Turbo costs, so it
  is for the lines that need it rather than for a volume, and the cache keeps
  the two apart. It runs in a Python of its own because its version and torch
  pins cannot be met alongside Chatterbox's.
- The tags in `corrections.toml` choose the feeling on that engine, so the
  corrections already written keep working and nothing new has to be learned.
- A recording is part of the cache key and not only its path, so a better
  take of a character remakes that character and nothing else.
- Every piece of audio is kept under a key made from the text, the voice, the
  engine, and the version of the engine. A correction makes one line again.
- `lexicon.toml` says how an invented name is said, everywhere in the book,
  the intro and the outro included. `openbook words` finds the words that need
  an entry, most frequent first. `--write` makes the file and `--merge` adds
  the words new chapters brought, without rewriting a line of what you wrote.

### It writes files

- An M4B with chapter marks, a cover, and the loudness an audiobook is
  expected to have.
- A video for each volume, with a card for each chapter, music ducked under
  the speech, a description carrying the time of every chapter, and captions.
- Refuses to encode a video whose cards and narration disagree.

### It can be checked by ear

- `--review` writes a page listing every line with a button that plays it, the
  ones most likely to be wrong first.
- Marked lines go into `corrections.toml`, and a render says how many were
  used. `openbook check` refuses one that matches no line in the book.
