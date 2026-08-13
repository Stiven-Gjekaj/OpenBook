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

Six engines use that interface. **Chatterbox** reads the book in the voice of
a recording you supply. **Chatterbox Turbo** is the same idea through a newer
model that reads about twice as fast and holds one loudness by itself.
**IndexTTS** reads those same recordings and is the only one here that can
raise its voice, at about eight times the cost, so it is for the lines that
need it rather than for a volume. **Kokoro** chooses from its own list of
voices and is the one to fall back to.
**espeak-ng** sounds like a machine from the 1990s and needs no model, no
download and no Python package, so a whole volume can be checked against real
speech in seconds. **The silent engine** is a clock: quiet of the length the
words would take, which is what the stages after it were built and tested
against.

One render can use several of them at once. `--engine-for dialogue=indextts`
puts a second engine in front of one kind of line, and what comes back answers
every question a single engine answers, so the planner, the renderer and the
cache carry on unchanged. The care is all in the key: it names the engine that
speaks the line rather than the one holding them, so a volume already made by
Turbo keeps every line of the kinds nobody routed. Routing the dialogue of the
prologue leaves 221 of its 349 lines alone.

The third of those properties is what lets the narrator and the cast use
different engines. The narrator reads 79 percent of Soultale in one voice, and
wants a model that cannot drift over a third of a million words. The cast
speaks in pieces that average thirteen words, where a model that is less steady
is safe and a bad piece costs five seconds to make again.

A voice for either Chatterbox model is a path to a recording, so the recording
is part of the key and the path is not. Two takes under one name are two voices,
and a cache that could not tell them apart would serve the old one for ever. A
file that only changed its name is the same voice and keeps every line it has.

Adding the cache later would mean rebuilding the stages around it, so it comes
first.

## What a token at a time costs

Chatterbox is autoregressive and Kokoro is not, and that one difference decides
where each belongs. A model that makes a token at a time can repeat itself,
drop a word, or trail off. Kokoro cannot: its failure is a wrong sound for a
word, which the lexicon corrects. A wrong number of words is found by nothing
except listening.

Three things hold that down, and none of them removes it:

- The planner already cuts everything into pieces, and a short piece wanders
  far less than a long one.
- Chatterbox takes 300 characters at a time where the others take 480. The cut
  falls at the end of a sentence either way, so a lower limit costs a few more
  pieces and buys back the failure that is hardest to find.
- The reading is seeded from the words and the voice, so the same line always
  comes out the same way. A book is made over days and in pieces, and a line
  remade next week has to match the chapter around it.

What is left is why the review page exists. These engines are the reason a
person has to be able to find six bad lines without listening to forty seven
hours.

### What it costs, measured

Chapter 0 is 112 pieces and seventeen minutes of audio. Chatterbox made it in
thirty eight minutes, which is **0.45 times real time**, so a four hour volume
is about eight and a half hours. Kokoro does about ten times real time.

The audio also came back peaking at **+0.6 dB**, above what a sample holds, so
the chapter was clipping before the levelling stage saw it.

Turbo was added because of those two numbers, and the same chapter through it
answers both. It is 114 pieces rather than 112, the two extra being the end
matter, and it came to 906 seconds of audio in 1068 seconds of compute. That is
**0.85 times real time**, counted from the command to the finished file and so
carrying the 3.8 GB of weights being loaded. Twice Chatterbox, and not the six
times the model claims. It also reads faster than Chatterbox does: the same
chapter runs 906 seconds where the older model took 1020, so a volume is
shorter as well as sooner, and Volume 1 falls from about eight and a half hours
to a little over four.

Nothing clipped. The loudest of the 114 pieces peaks at **-3.11 dBFS** and none
reaches full scale, because Turbo brings each piece to one loudness itself: the
median sits at -26.6 dBFS against the -27 the model aims for, and the spread
from quietest to loudest is 11.2 dB.

The third cost is the one no measurement reaches. Nothing above says whether a
word was dropped or repeated across 114 generations. What can be said is that
no piece is long or short for the words in it: the six furthest from the median
are all single words, where the silence at each end is most of the piece. That
is the absence of the obvious failure rather than proof there was none, which
is once more why the review page exists.

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
