<div align="center">
  <a href="../README.md"><img src="../assets/openbook.svg" alt="OpenBook" height="44"></a>
</div>

# Configuration

## What lives where

Everything a project reads and everything it makes is inside the project
directory. Delete that one directory and the whole thing is gone.

```
my-audiobook/
  grammar.toml        what a chapter looks like
  cast.toml           which voice each character takes
  lexicon.toml        how a word is said
  corrections.toml    what to say instead, for one line
  book.epub           your manuscript
  voices/             the recordings a Chatterbox voice is taken from
  cache/              the audio already made, keyed on text and voice
  out/                the finished files, and nothing else
  .work/              half finished pieces, removed as they are used
```

`out` holds only what you asked for. The levelled copy, the mixed copy and the
chapter cards are working files and go to `.work`, which is made when a command
starts and emptied as it runs. Anything in the process that asks for a
temporary file is sent there too, so a command that is interrupted leaves its
pieces under a name that says what they belong to, rather than in the system
temporary directory where they say nothing.

**One thing sits outside**, and it is not the project's to hold: the speech
models, in `~/.cache/huggingface`. Chatterbox is 3 GB of it and Kokoro 0.3 GB.
They are shared by every project on the machine, and `HF_HOME` moves them if
you want them somewhere else.

---

A project is a directory holding the book and up to three files. Only the first
two are needed.

| File | What it says | Needed |
| ---- | ------------ | ------ |
| `grammar.toml` | What a chapter looks like, and what comes out | Yes |
| `cast.toml` | Which voice each character takes | Yes |
| `lexicon.toml` | How a word is said | No |
| `corrections.toml` | What to say instead, for one line that came out wrong | No |

The examples in [examples/soultale](../examples/soultale) carry a comment on
every key and are the fastest way to start.

Two rules hold everywhere. **A key that nothing reads is an error**, and the
message names the key next to it, because a file that ignores a misspelled key
lies about what it does. And **a value in double quotes is a template** that
OpenBook compiles, while **a value in single quotes is a regular expression**
already; use a template unless a template cannot say what you need.

---

## grammar.toml

### [source]

| Key | Means |
| --- | ----- |
| `format` | `"epub"`. Nothing else is read yet |
| `files` | The book files, in order. A chapter in two of them is taken from the first |
| `chapter_title` | A template for the title of a chapter, capturing `{NUMBER}`, `{VOLUME}` and `{TITLE}` |
| `number_pattern` | What a chapter number may look like. `'-?\d+'` allows the negative ones |
| `volume_pattern` | What a volume may look like. It is text, because "Prologue" is a volume |
| `skip_volume_pattern` | A volume matching this is read but not spoken |
| `chapter_announcement` | What the narrator says at the start of a chapter |
| `chapter_announcement_named` | The same, for a volume whose name holds no number |

Give both announcements the same words when you want a prologue chapter
announced by its number. The card under the title says whatever the narrator
says, and a check refuses a video where the two differ.

### [grammar]

| Key | Means |
| --- | ----- |
| `dialogue_elements` | The elements that can hold a speaker code. Some exporters use two |
| `dialogue` | A template for a line of dialogue, capturing `{SPEAKER}` and `{TEXT}` |
| `speaker_pattern` | What a speaker code may look like |
| `split_at_line_break` | Divide a paragraph at every line break before looking for a speaker |
| `action` | A regular expression for an action written inside a line of dialogue |

`split_at_line_break` matters more than it looks. In Soultale nearly two thirds
of the dialogue lines share a paragraph with another one, and a parser that
reads a paragraph as one unit gets most of the dialogue wrong.

### [grammar.unison]

| Key | Means |
| --- | ----- |
| `separator` | What divides two names in one code, such as `" & "` |
| `mode` | `voice_blend`, `mix`, `mix_matched`, or `primary` |

| Mode | What a listener hears |
| ---- | --------------------- |
| `voice_blend` | One voice, made from the average of the two. It belongs to neither character |
| `mix` | Both voices. They start together and the shorter reading stops first |
| `mix_matched` | Both voices, brought to one length, so they speak together throughout |
| `primary` | The voice of the first character named |

`mix` and `mix_matched` speak the line once in each voice and lay the readings
over each other, so each character keeps their own voice. Two readings of the
same words are two different lengths, which is what the two modes disagree
about. Measured on Kokoro with `af_heart` and `am_michael`:

| The line | `mix` ends apart by | `mix_matched` moves each voice by |
| -------- | ------------------- | --------------------------------- |
| One word | 0.07s | 4.4% |
| Six words | 0.35s | 8.7% |
| Fifteen words | 0.60s | 6.4% |

A short line under `mix` sounds like two people. A long one starts to sound
like a round.

`mix_matched` changes how fast a character talks, which is why it is asked for
and never assumed. It brings both readings to their average length rather than
stretching one to meet the other, so neither carries the whole change: a tempo
moved 7 percent is near the point where nobody hears it, and 14 percent is not.
A reading that would have to move more than 25 percent stops at 25, because
past that it is no longer the same performance.

It needs ffmpeg, which holds the pitch while it moves the tempo. Playing a
piece slower is one line of arithmetic and it drops the voice with it, which
turns a character into somebody else. Nothing is stretched when the readings
already agree on length, so a check with the silent engine still needs
nothing installed.

### [grammar.structure]

| Key | Means |
| --- | ----- |
| `end_matter_element` | The element that holds the words at the end of a chapter |
| `end_matter_tail` | A closing line that does not wear that element, by its shape |
| `scene_break` | A line matching this becomes a silence and is not spoken |
| `strip_elements` | Elements removed while their text is kept |

`end_matter_tail` is for a book whose closing is not all marked the same way.
Soultale underlines `End of Chapter 4` and the name of the chapter, then leaves
a line in brackets under them in bold alone, so `end_matter_element = "u"`
finds two lines of three. The pattern matches only where a closing has already
begun, because the same shape in the middle of a chapter is something else
entirely. Leave it out and nothing changes.

The lines of a closing are then read as one, with a full stop put where the
line break was and none added where the line already ends in one. A book
writes them separately because that is how they sit on a page; a reader still
says them as a single sentence falling to its end, and an engine given three
pieces returns three endings in a row. In chapter 0 the three came to 6.6
seconds and the one comes to 4.5, the difference being the silence each
separate reading carried at its ends.

### [render]

| Key | Means |
| --- | ----- |
| `read_chapter_names` | Announce each chapter |
| `read_end_matter` | Speak the end matter of a chapter |
| `pause_dialogue_to_narration` | Silence where speech turns into prose |
| `pause_narration_to_dialogue` | Silence where prose turns into speech |
| `pause_at_scene_break` | Silence at a scene break |
| `pause_after_chapter_name` | Silence after a chapter is announced |
| `pause_between_chapters` | The rest at the end of a chapter, before the next is announced |
| `pause_at_host` | The gap between the host and the book, at each end |
| `action` | `pause`, `narrator`, or `drop` |
| `pause_at_action` | How long an action lasts when it becomes a pause |
| `intro` | What the narrator reads before the chapters |
| `outro` | What the narrator reads after them |
| `intro_title` | The name of the intro in the chapter list |
| `outro_title` | The name of the outro |

`intro` and `outro` are spoken to the listener rather than to the book. They
take `{VOLUME}`, `{TITLE}`, `{FIRST}`, `{LAST}` and `{CHAPTERS}`. Name a voice
for them under `[host]` in `cast.toml`, or leave that out and the narrator
reads them.

Neither takes a chapter mark. They hold a place on the timeline, so the video
draws a card for each, and that card carries the name of the work and nothing
else. Nothing that lists chapters lists them: not the chapter marks of the
M4B, and not the times in the YouTube description. The time is not lost,
because the first chapter listed reads 0:00 and an intro in front of it
belongs to that chapter as far as a viewer clicking the list is concerned.

A rest of `pause_at_host` falls between the host and the book, after the intro
and before the outro. It has a length of its own rather than borrowing the
rest between two chapters: that one is long because a listener has just
finished a chapter and is owed a moment with it, and the same length after
somebody talks to the camera sounds like the file has stopped.

`read_end_matter` decides whether the words that close a chapter are spoken.
In Soultale every chapter ends with three lines:

```
End of Chapter 0
"Point - Null"
[ The 1 named 0. ]
```

Read together they close the chapter: it is named, then titled, then answered.
Read alone the last line arrives from nowhere, which is why `end_matter_tail`
exists and why this key governs all three rather than the two that share an
element. They reach the engine as one line, and `pause_between_chapters`
follows them.

**A pause falls only where the kind of the text changes.** Two lines of
dialogue get nothing between them, so a conversation keeps its speed, and two
paragraphs of prose get nothing either.

### [output]

| Key | Means |
| --- | ----- |
| `group_by` | `"volume"` |
| `file_name` | The name of each file. It must hold `{VOLUME}` |
| `bitrate` | The bitrate of the audio |
| `sample_rate` | `0` keeps what the engine made. `48000` for YouTube |
| `channels` | `0` keeps one channel. `2` for YouTube |
| `level` | Bring the speech to the loudness an audiobook is expected to have |

Both of the tables below change the grouping of the output only. A chapter
keeps the number and the volume the book gives it, in the chapter list, on the
card, and in the words the narrator speaks.

`[output.merge_volumes]` puts one volume into the file of another. Use it for a
volume too short to stand alone. Soultale merges nothing: the book gives
chapters 0 to 2 a volume named Prologue, and they go out first and on their
own, so the grouping the book already carries is the right one.

```toml
[output.merge_volumes]
"Prologue" = "Volume 1"
```

`[output.parts]` names a run of chapters that becomes a file of its own. A part
wins over both the volume and any merge. Use it where the division you want
does not follow a volume, most often to divide a long one:

```toml
[output.parts]
"Volume 1, Part 1" = "3-12"
"Volume 1, Part 2" = "13-22"
```

### [video]

Only needed to make a video.

| Key | Means |
| --- | ----- |
| `file_name` | The name of each video. It must hold `{VOLUME}` |
| `title` | The name of the work, drawn large on every card |
| `title_font`, `title_back_font` | The face for that name. Two files draw an outline behind a fill |
| `body_font` | The face for everything else |
| `background` | The colour behind it all |
| `visual` | A picture to use instead of drawing cards |
| `music` | A bed to put under the speech |
| `music_level` | How loud the bed is before it is ducked |
| `fade` | How long the picture and the music take to arrive and to leave |
| `framerate` | Frames each second. `1` is right for a still |
| `bitrate`, `sample_rate`, `channels` | The audio of the video |
| `description` | Your own words, above the chapter times |
| `peek_words` | How many words of the opening to quote. `0` for none |
| `credits` | Lines naming what a licence asks you to name |

`[video.descriptions]` gives one release its own words, keyed by the name of
the file being made. A release with no entry takes `description`, so write
nothing about one volume there:

```toml
[video.descriptions]
Prologue = """
Before there was anyone to name it, there was one consciousness alone.
"""
```

Put this table at the end of the file. A bare key written after a table header
belongs to that table, so every other key of `[video]` has to come first.

Name the fonts and a card is drawn for each chapter. Name a `visual` instead
and that picture is used. Give neither and the file refuses to load.

Music is compressed against the speech rather than laid under it, so it drops
where somebody talks. A bed at one level fights the narration and is tiring
long before the end of a volume. One track is looped to the length of the
volume, so a six minute piece goes round seven times under a prologue.

`fade` brings the picture out of black and takes it back into black, and the
music arrives and leaves with it. **The speech never fades.** The first word
of an intro would be swallowed by it, and the picture is not what carries the
story. Leave the key out and nothing fades.

There is no music under the M4B, and no key for one. An audiobook with a bed
under it is not one any distributor accepts: ACX asks for -19 LUFS and -3
dBTP, which this project already hits, and forbids background music outright.

---

## cast.toml

```toml
[narrator]
voice = "af_heart"

[host]
voice = "voices/host.wav"

[cast.BLK]
name  = "Blook"
voice = "am_michael"
aliases = ["BLCK"]
```

`[[narrator_range]]` gives a run of chapters its own narrator, for a book
where the telling changes hands:

```toml
[narrator]
voice = "voices/outside.wav"

[[narrator_range]]
chapters = "3-22"
name     = "Blook"
voice    = "voices/blook.wav"
```

A range wins over `[narrator]`, which answers for every chapter no range
covers, so a book with one narrator writes none of these. Two ranges over one
chapter are refused, the same as two entries of one speaker code are. Each
range can carry its own `exaggeration`.

Soultale needs this because the prologue is told from outside, with no first
person in all 5,306 words of its narration, and chapter 3 opens in the first
person and stays there. Where a character tells their own chapters, the
narrator and that character's code take the same recording: it is one person
thinking and then speaking.

`[host]` is the voice that speaks to the listener rather than inside the book.
It reads the `intro` and the `outro` from `[render]`, where a video says hello
and asks for a subscription. It is not a character and it is not in the cast,
because nobody in the book ever hears it. Leave it out and the narrator reads
those words.

**What a voice is depends on the engine.**

| Engine | A voice is | Example |
| ------ | ---------- | ------- |
| `chatterbox` | A path to a recording of the character, read from the project directory | `"voices/blook.wav"` |
| `chatterbox-turbo` | The same, through a model that reads about twice as fast | `"voices/blook.wav"` |
| `indextts` | The same recordings again, through the one model here that can raise its voice | `"voices/zero.wav"` |
| `kokoro` | One of its own voice names. The first letter is the accent | `"af_heart"` |
| `espeak` | A language, and a variant after a plus | `"en-gb+Alicia"` |

For Chatterbox, ten to twenty seconds of clean speech is enough, and what is in
the recording is what comes out: the accent, the pace, the room it was recorded
in, and anything behind it. `openbook check --engine chatterbox` names every
recording that is not there, so a missing one is found before a render rather
than twenty minutes into one.

A recording is part of what the cache keys on, not only its path. Writing a
better take over `voices/blook.wav` makes every line Blook has again. Without
that the path would not have changed, nothing would have been remade, and the
old voice would have stayed in the book for ever with nothing said about it.

**Two models read from a recording.** `chatterbox` is the older: 0.45 times
real time, and audio that peaked above what a sample holds, so a whole chapter
was clipping before the levelling stage saw it. `chatterbox-turbo` made the
same chapter at 0.85 times real time, with nothing clipping and every piece
brought to one loudness by the model.

**A third reads from a recording, and it is the only one with a range.**
`indextts` keeps the feeling apart from the voice: the recording says who is
speaking and eight numbers say how. It is the answer to a thing the others
cannot do at all. Zero murmurs "These connections..." and then shouts "I am
the true strongest!" at the end of chapter 2, and Turbo reads that pair 0.3 dB
apart with its loudness normaliser off, the shout being the quieter of the
two. Through IndexTTS the same pair, from the same `voices/zero.wav`, measured
15.5 dB apart.

It costs about eight times what Turbo costs, so it is not for reading a book.
The cache holds the name of the engine, so a line made here sits beside its
neighbours made by Turbo and neither disturbs the other. Render a volume with
Turbo, then render the lines that need a raised voice with this.

It needs a Python of its own, because `indextts` asks for a version below 3.12
and torch 2.8 while this project asks for 3.12 and holds torch 2.6 for
Chatterbox. Both pins are exact and no version of Python satisfies both, so
the model runs beside the project and talks to it over a pipe:

```
uv venv --python 3.11 ~/.openbook/indextts
VIRTUAL_ENV=~/.openbook/indextts uv pip install \
    "indextts @ git+https://github.com/index-tts/index-tts.git"
hf download IndexTeam/IndexTTS-2
```

That is where the engine looks first. `OPENBOOK_INDEXTTS_PYTHON` names another
interpreter and `OPENBOOK_INDEXTTS_MODEL` names another directory of weights,
which is also how the worker is pointed at a machine with a graphics card.

**A render can use more than one engine.** `--engine` says which reads the
book, and `--engine-for` puts another in front of one kind of line. Repeat it
for each kind:

```
openbook render --volume "Prologue" --engine chatterbox-turbo \
    --engine-for dialogue=indextts --engine-for host=indextts
```

The kinds are `narration`, `dialogue`, `action`, `announcement`, `end matter`
and `host`. A misspelled one is refused by name rather than ignored, because
a route that silently did nothing would give back the render you were trying
not to make.

**A kind nobody routed keeps the audio it already has.** A key names the
engine that speaks the line, so putting IndexTTS in front of dialogue leaves
every line of narration where it is. On the prologue that is 221 of 349 lines
untouched and 128 to make.

Two engines have to give back audio at the same rate, or their pieces cannot
be joined, and a disagreement is refused before anything is spoken rather than
partway through a volume. Every engine here gives back 24000. `espeak-ng`
writes 22050 and has no setting for it, so that one is resampled on the way
out, which roughly doubles what it costs a line and still leaves it the
fastest way to hear a volume in real words.

**Do not write an `exaggeration` for a new character while Turbo is the
engine.** It cannot do the thing its name promises, and it still changes the
key of every line that character says, so writing one makes that character
again and gives a different reading. Give the character a recording and stop
there.

**The exaggeration does nothing on Turbo.** One line read at 0.0, 0.5 and 1.0
from one seed comes back bit for bit the same, and the library warns on every
line that it ignores the number. It stays in the key of a line, so changing it
still gives a different reading, and each model keeps its own numbers. To ask
Turbo for a feeling, put a tag in the words: see corrections.toml below.

Both hold their audio apart, because the name of the engine is part of a key.
The same chapter can be read by each and the two compared, and neither throws
the other away.

The narrator speaks most of a book, so choose that voice first and listen to it
for several minutes before accepting it. It is also where the choice of engine
costs most: see [architecture.md](architecture.md) on why an engine that makes
a token at a time is a different risk over a third of a million words.

`name` is for you, for the reports, and for the speaker labels in the captions.
A reader of the captions has never seen this file and cannot know that BLK is
Blook.

A code with no entry stops the build and names the chapter. A code with an
entry but no voice stops the build when the renderer reaches it, so a cast can
be read before it is finished.

### How much feeling a line is read with

An engine that reads with feeling, which today means Chatterbox, takes an
**exaggeration**. It comes from the kind of the line unless an entry says
otherwise:

| The line | Read with |
| -------- | --------- |
| Dialogue | 0.7 |
| Narration, actions, chapter announcements, end matter | 0.3 |

A narrator states what happened and holds one level for hours. A character in
a fantasy is frightened, or lying, or giving an order. One value for both
gives either a theatrical narrator or a flat cast, and a book is 79 percent
the first and all of the second.

Write `exaggeration` on an entry to say something else about one character,
and on `[narrator]` to say it about the narration:

```toml
[narrator]
voice        = "voices/narrator.wav"
exaggeration = 0.25

[cast.BLK]
name         = "Blook"
voice        = "voices/blook.wav"
exaggeration = 0.85
```

The number is part of the key of each line, not of the whole render. Changing
it for one character remakes that character and touches nobody else, and
changing what dialogue is read with leaves three hundred thousand words of
narration exactly where they are.

A line two characters share takes the number of the first of them, the same
way `primary` takes the voice of the first of them.

### A code that is not one character

`???` is a different character in each part of a book, so it takes one entry
for each run of chapters:

```toml
[[cast_range."???"]]
chapters = "115-120"
name     = "Unknown, volume 4"
voice    = "bm_george"
```

A line in a chapter that no entry covers stops the build. That is correct: a
new unknown character needs a new voice, and the tool should ask rather than
choose.

---

## lexicon.toml

```toml
[words]
"vazroth" = "Vaz-roth"
```

Each entry replaces a word before it reaches a voice, and never touches the
book. Whole words only, so a rule for "Ivy" does not reach inside "Ivory".
It reaches the `intro` and the `outro` as well, which are the lines most
likely to name the book and the people in it.

**Every name is quoted.** A great many of these words hold an apostrophe, and
TOML does not accept one in a bare name.

This is the largest quality problem in any audiobook made this way. A fixed
voice says an invented name the same wrong way every time it appears, for the
whole book, and no casting decision repairs it.

`openbook words` finds the words that need an entry, most frequent first.

| Command | What it does |
| ------- | ------------ |
| `openbook words` | List the words that need an entry |
| `openbook words --write` | Make the file, every sound left blank |
| `openbook words --merge` | Add the words that are not in the file yet |

`--write` refuses to write over a file that is already there, and `--merge`
refuses when there is none. Each names the other.

**`--merge` adds to the end of the file and never rewrites it**, so every
answer, comment and ordering you chose stays exactly where you put it. Use it
when new chapters bring new names. A word already written down is left alone
whether it has an answer or not, so a blank entry is never added twice.

That gives you a way to say a word is fine as it is: leave its entry in the
file with a blank sound. It changes no audio and it keeps the word out of
every later merge. `openbook words` goes on listing it, because a blank entry
is a question nobody has answered.

---

## corrections.toml

A lexicon entry answers a word everywhere in the book. This answers one line.

```toml
[corrections]
"He turned to face the Vazroth." = "He turned to face the Vaz-roth."
"She read it out: 1874." = "She read it out: eighteen seventy four."
```

You do not write this file by hand. `openbook render --review` writes a page
listing every line of the render with a button that plays it. Mark the ones
that came out wrong, press **copy what I marked**, and paste the result here.
Then fill in what each line should say and render again.

**Write the line exactly as the page shows it.** That text is what the engine
was given: after `lexicon.toml`, and after a line too long for the engine was
divided, which is why the page sometimes shows a paragraph in two pieces. Runs
of spaces and line breaks do not have to match, and capitals do.

Because the lexicon comes first, **a new lexicon entry can leave a correction
with nothing to match**, if the entry changes a word in the corrected line.
That is not quiet: `openbook check` names the line, and the answer is to copy
it again from a new review page.

Two entries are refused rather than ignored:

- **One whose answer repeats its own question.** It would make the same audio
  under the same key, so nothing would change and it would look like a
  correction that did not take.
- **One that matches no line anywhere in the book.** `openbook check` finds
  this, because nothing else can: the render says nothing, the audio does not
  change, and the only way left is to listen to the line again.

An entry with a blank answer, which is what the page writes, is a line waiting
for words. It changes nothing and is counted apart.

### Asking for a feeling

The text of an entry reaches the engine untouched, so a tag in it is read as
an instruction. This is how one line is given a feeling that the words alone
do not carry:

```toml
"Zero, no!" = "[fear] Zero, no!"
"Finally, someone newer than me!" = "[happy] Finally, someone newer than me!"
```

The captions take the tag out again, so a viewer sees the words alone. Text
the book itself writes in brackets is kept, because the rule matches a list of
known tags and never the shape of the brackets.

The tags belong to the engine and the two Chatterbox models do not agree on
them. `chatterbox-turbo` reads `[angry]`, `[fear]`, `[surprised]`,
`[whispering]`, `[happy]`, `[crying]`, `[sarcastic]` and `[dramatic]`, and the
sounds `[laugh]`, `[chuckle]`, `[sigh]`, `[gasp]`, `[cough]`, `[groan]`,
`[sniff]`, `[shush]` and `[clear throat]`. The older `chatterbox` has no
feelings at all and spells several of the sounds differently, so a file of
Turbo tags read by it says the letters out loud.

`indextts` reads the same tags and is the only engine where they change how
hard a line is said. It has eight feelings and the tags map onto them:

| Tag | Feeling |
| --- | ------- |
| `[angry]`, `[dramatic]` | angry |
| `[happy]` | happy |
| `[crying]`, `[cry]` | sad |
| `[fear]` | afraid |
| `[surprised]` | surprised |
| `[whispering]`, `[whisper]`, `[narration]` | calm |

A tag naming a sound rather than a delivery, `[cough]` or `[laugh]`, has no
feeling to map to. It is taken out of the words like any other and the line is
read flat. `[sarcastic]` is the same: this model has no such feeling, and
guessing one for it would be inventing a reading the author did not ask for.

What the tags mean is part of the version of the engine, so changing this
table remakes the lines carrying those tags and leaves every other line in the
book where it is.

Use one only where the words leave no doubt. A tag on a line that could be
read two ways replaces the author's ambiguity with a guess.

A render says what the file did:

```
  corrections 4 used, 1 for no line in this volume, 2 still waiting for words
```

Nothing puts a correction into the cache key. The key is made from the text
and a correction changes the text, so only the marked line is made again and
every other line in the volume still comes from the cache. The old audio stays
in the cache, so taking a correction back out costs nothing either.

Two lines with the same words in the same voice share one piece of audio, and
a correction reaches both. That is the same rule the cache runs on.
