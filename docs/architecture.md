<div align="center">
  <a href="../README.md"><img src="../assets/openbook.svg" alt="OpenBook" height="44"></a>
</div>

# Architecture

OpenBook is a pipeline. Each stage takes what the stage before it made, and
adds one thing. This document says what each stage does and why the divisions
fall where they do.

## The stages

```
EPUB files
   |
   |  source     (src/openbook/source/epub.py)
   v
 chapters                       number, volume, title, body
   |
   |  parse      (src/openbook/parse/)
   v
 segments                       narration, dialogue, action, scene break
   |
   |  cast       (src/openbook/cast/)
   v
 utterances                     each with a voice and an engine
   |
   |  plan       (src/openbook/plan/)
   v
 a manifest                     utterances and the silences between them
   |
   |  speech     (src/openbook/speech/)
   v
 audio for each utterance       through a cache
   |
   |  loudness   (src/openbook/speech/loudness.py)
   v
 one level for the whole volume
   |
   +--> package  an M4B with chapter marks, a cover, and captions
   |
   +--> video    a card for each chapter, a description, captions
   |
   +--> review   a page listing every line, to check it by ear
```

The first four stages need the standard library only. They hold nearly every
rule that the book brings with it, they run in under a second, and they are
fully testable. A person can read the whole parse of a book, and the voice of
every line in it, before any audio exists. This is the point of the division.

The stages after `plan` are the slow ones and the ones with dependencies. They
are also the ones a person changes least.

## Where the rules live

The parser holds no rule about Soultale. Every rule comes out of `grammar.toml`
and reaches the code as a compiled template or a compiled regular expression. A
fork that reads a different book writes a different grammar file.

This is a rule about the code and not only a preference. A rule that moves into
the parser cannot be seen, cannot be changed without a release, and cannot be
tested against a second book. When a change needs a new rule, the change adds a
key.

## The cache is the centre

The `speech` stage keys each piece of audio on the text, the voice, the engine,
the settings of the engine, and the version of the model. Nothing else.

Everything useful follows from that:

- A correction to one line makes one line again, and not a chapter.
- A change of voice for one character makes that character again, and touches
  nobody else.
- A character can move to a different engine, and the rest of the book keeps
  the audio it already has.

Three engines use that interface. **Kokoro** is the one a book ships in.
**espeak-ng** sounds like a machine from the 1990s and needs no model, no
download and no Python package, so it says real words at real lengths on any
machine and a whole volume can be checked against real speech in seconds.
**The silent engine** is a clock: quiet of the length the words would take,
which is what the stages after it were built and tested against.

The last of these is what lets the narrator and the cast use different engines.
The narrator reads 79 percent of Soultale in one voice, and wants a model that
cannot drift over a third of a million words. The cast speaks in pieces that
average thirteen words, where a model that is less steady is safe and a bad
piece costs five seconds to make again.

Adding the cache later would mean rebuilding the stages around it, so it comes
first.

## Checking the thing that was made

Every fault found in the video path was found by looking at the finished file,
and none of them raised anything:

  A video seven minutes longer than its audio, because the reader of the card
  list needs the last card written twice and that repeat carries its duration.
  A card changing twenty two seconds before the chapter it names, because the
  silence between two chapters belongs to the card in front of it.
  A card saying "Chapter 22 of 23" where the narrator says "Chapter 21".
  A card saying "Chapter 0" where the narrator says "Prologue".

Each piece behaved as written. They disagreed only with each other, and only
where somebody watches and listens at once. A test of one side cannot find
that, so `speech/verify.py` reads both sides and compares them, and it runs
before the encode rather than after it.

The same reasoning gives the review page. A test says a line was made; only a
person can say it sounds right, and the page exists so that finding the six
lines that went wrong does not mean listening to forty seven hours.

## The review loop

The page is one half. It writes out the lines a person marked, and
`corrections.toml` reads them back:

```
render --review  ->  a page  ->  mark and copy  ->  corrections.toml  ->  render
```

A correction lands at plan time, after the lexicon and after a long line is
divided, because that is the text the page showed and the text the engine was
given. Nothing after that stage is told about corrections at all. The cache
keys on the text, a correction changes the text, and so the marked line is
made again and the rest of the volume is not.

This is the third thing the cache gives away, after a change of voice and a
change of engine, and it is the reason the loop costs seconds rather than the
twenty three minutes a volume takes to make.

## Errors

An error that a person can correct is an `OpenBookError`. It names the file,
the key, or the chapter that the person must change, and the command prints one
line and gives back the code 2. Anything else stays an ordinary exception and
keeps its traceback, because it is a fault in this project and a traceback is
what a fault needs.

Two refusals matter more than the others:

- **A configuration key that nothing reads.** A file that ignores a misspelled
  key lies about what it does. The person then looks for the reason in the
  audio, which is the most expensive place to look.
- **A speaker code with no voice.** A finished audiobook with a wrong voice in
  it is worse than no audiobook, and a code that quietly became narration is
  found only by listening.

## What the source is

The book arrives as EPUB. The chapters were written on Wattpad, and the editor
there stores four things: bold, italic, underline, and alignment. No export can
carry a distinction that the editor never held.

This decides several rules. Bold marks a speaker code at the start of a segment
and emphasis anywhere else, and nothing else can tell them apart. Italic is
emphasis, so the parser removes it. Alignment carries no meaning, because three
quarters of the paragraphs in the book are centred. An action inside dialogue
is marked with asterisks that the author typed, and not with an element.

A Markdown export of the same chapters exists and is not usable: it loses the
speaker element in 55 of 192 chapters, which turns 985 lines of dialogue into
narration without saying so.
