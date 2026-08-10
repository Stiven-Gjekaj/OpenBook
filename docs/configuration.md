<div align="center">
  <a href="../README.md"><img src="../assets/openbook.svg" alt="OpenBook" height="44"></a>
</div>

# Configuration

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
| `mode` | `voice_blend`, `primary`, or `mix` |

`voice_blend` averages the style of both voices and speaks the line once, so
the two cannot drift apart. `primary` uses the voice of the first character
named. `mix` speaks the line once in each voice and lays the readings over each
other, which keeps the characters apart and lets their timing separate: two
readings of the same words are two different lengths, so the longer one is
still going when the shorter has stopped. Whether that sounds like a crowd or
like an echo depends on the line, which is why the blend is the usual choice
and this is the one you ask for.

### [grammar.structure]

| Key | Means |
| --- | ----- |
| `end_matter_element` | The element that holds the words at the end of a chapter |
| `scene_break` | A line matching this becomes a silence and is not spoken |
| `strip_elements` | Elements removed while their text is kept |

### [render]

| Key | Means |
| --- | ----- |
| `read_chapter_names` | Announce each chapter |
| `read_end_matter` | Speak the end matter of a chapter |
| `pause_dialogue_to_narration` | Silence where speech turns into prose |
| `pause_narration_to_dialogue` | Silence where prose turns into speech |
| `pause_at_scene_break` | Silence at a scene break |
| `pause_after_chapter_name` | Silence after a chapter is announced |
| `action` | `pause`, `narrator`, or `drop` |
| `pause_at_action` | How long an action lasts when it becomes a pause |
| `intro` | What the narrator reads before the chapters |
| `outro` | What the narrator reads after them |
| `intro_title` | The name of the intro in the chapter list |
| `outro_title` | The name of the outro |

**A pause falls only where the kind of the text changes.** Two lines of
dialogue get nothing between them, so a conversation keeps its speed, and two
paragraphs of prose get nothing either.

The intro and the outro accept `{VOLUME}`, `{TITLE}`, `{FIRST}`, `{LAST}` and
`{CHAPTERS}`. Each takes a chapter mark of its own, so the first time in a
YouTube description still points at 0:00.

### [output]

| Key | Means |
| --- | ----- |
| `group_by` | `"volume"` |
| `file_name` | The name of each file. It must hold `{VOLUME}` |
| `bitrate` | The bitrate of the audio |
| `sample_rate` | `0` keeps what the engine made. `48000` for YouTube |
| `channels` | `0` keeps one channel. `2` for YouTube |
| `level` | Bring the speech to the loudness an audiobook is expected to have |

`[output.merge_volumes]` puts one volume into another file, which is how the
prologue ships inside volume 1.

`[output.parts]` names a run of chapters that becomes a file of its own, and it
wins over the volume grouping:

```toml
[output.parts]
"Volume 1, Part 1" = "0-12"
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
| `framerate` | Frames each second. `1` is right for a still |
| `bitrate`, `sample_rate`, `channels` | The audio of the video |
| `description` | Your own words, above the chapter times |
| `peek_words` | How many words of the opening to quote. `0` for none |
| `credits` | Lines naming what a licence asks you to name |

Name the fonts and a card is drawn for each chapter. Name a `visual` instead
and that picture is used. Give neither and the file refuses to load.

Music is compressed against the speech rather than laid under it, so it drops
where somebody talks. A bed at one level fights the narration and is tiring
long before the end of a volume.

---

## cast.toml

```toml
[narrator]
voice = "af_heart"

[cast.BLK]
name  = "Black"
voice = "am_michael"
aliases = ["BLCK"]
```

The narrator speaks most of a book, so choose that voice first and listen to it
for several minutes before accepting it.

`name` is for you, for the reports, and for the speaker labels in the captions.
A reader of the captions has never seen this file and cannot know that BLK is
Black.

A code with no entry stops the build and names the chapter. A code with an
entry but no voice stops the build when the renderer reaches it, so a cast can
be read before it is finished.

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
