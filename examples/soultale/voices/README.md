# Where each voice comes from

The recordings in this directory are not in the repository. This file is, so
that the record of who is who survives a directory that gets cleared.

Read this before you add a voice. One source must speak for one character
only. A listener who hears the same voice twice hears one person, and the
book then has two characters that a reader cannot tell apart.

## The cast now

| Code | Character | Voice | From | Pitch |
| ---- | --------- | ----- | ---- | ----- |
| END | The end | My Liege, Dramatic Old Male | a voice library, not a character | 79 Hz |
| EDG | Edge | Denji | Chainsaw Man | 113 Hz |
| ZER | zero | Ayanokoji | Classroom of the Elite | 130 Hz |
| INK | Ink | Childe | Genshin Impact | 178 Hz |
| | narrator | Frieren, soft | Frieren: Beyond Journey's End | 211 Hz |
| DRM | dream | Abridged Kirito | Sword Art Online Abridged | 274 Hz |
| BLB | Blueberry | Luffy | One Piece | 341 Hz |

Ordered by pitch, because that is the order in which two of them collide.

The closest pair is Ink and the host, 11 Hz apart, and they never meet: the
host speaks only before and after the book. Among characters who share a
scene, the closest are Edge and zero at 17 Hz, and Edge has four lines.

This took three attempts. dream and Ink were 3 Hz apart with Sunday and
Subaru, then 7 Hz apart with Xiao and Childe. They are 96 Hz apart now, so if
a listener still confuses them the reason is not pitch.

`///` is the nameless voice of the prologue. It is zero, so it uses
`zero.wav`. Change it whenever ZER changes, or the two come apart.

The pitch is the median of the reference recording. It is here because two
voices close in pitch are the two a listener confuses. The cast above spans
79 to 341 Hz, which is over two octaves.

## Held, not used

| Voice | From | Pitch | File | Was |
| ----- | ---- | ----- | ---- | --- |
| Xiao | Genshin Impact | 171 Hz | `xiao.wav` | dream, never heard |
| Venti | Genshin Impact | 274 Hz | `venti.wav` | dream |
| Yanqing | Honkai: Star Rail | 288 Hz | `yanqing.wav` | Ink, then Blueberry |

Kept rather than deleted. Each is a converted reference that a rename would
put straight back to work, and 38 codes in [cast.toml](../cast.toml) still
have no voice.

Xiao was built and never rendered: he landed 7 Hz from Childe, which is the
collision this file exists to catch, so he was replaced before any audio was
made from him.

## The host

| Voice | From | Pitch |
| ----- | ---- | ----- |
| Makima | Chainsaw Man | 189 Hz |

This voice speaks to the viewer and not to the book. It reads the words
before the chapters start and the words after they end, where the video says
hello and asks for a subscription.

It is not in the cast, because it is not a character. `host.wav` holds it, and
`[host]` in [cast.toml](../cast.toml) names it. The words are the `intro` and
the `outro` in [grammar.toml](../grammar.toml).

Neither takes a chapter mark. The video draws a card for each, and that card
carries the name of the work and nothing else.

38 codes in [cast.toml](../cast.toml) still have no voice, and Volume 1 needs
them. None of them can have this voice.

## Tried and dropped

These are gone from the disk. They are written down so that nobody spends an
evening finding out the same thing again.

| Voice | From | Was | Why it went |
| ----- | ---- | --- | ----------- |
| Kafka | Honkai: Star Rail | narrator | The author chose Frieren instead |
| Sunday | Honkai: Star Rail | zero, then dream | 3 Hz from Ink as dream |
| Subaru | Re:Zero | Ink | Replaced by Childe |
| Rudeus Greyrat | Mushoku Tensei | dream, then Blueberry | Replaced by Luffy |
| jin_woo | Solo Leveling | Edge | Replaced by Denji |
| AniSpeech 116 | AniSpeech, voice 116 | Ink | Its clips held more than one speaker |
| AniSpeech 142 | AniSpeech, voice 142 | zero | The author preferred Ayanokoji |
| AniSpeech 123 | AniSpeech, voice 123 | dream | Replaced in the overhaul |
| AniSpeech 136 | AniSpeech, voice 136 | The end | Replaced in the overhaul |
| AniSpeech 114 | AniSpeech, voice 114 | Edge | Replaced in the overhaul |

## What a recording must be

Every reference here is 48 kHz, one channel, 16 bits, and 13 to 18 seconds
long. Turbo accepts five seconds. More gives the model more to hold on to.

Four things are measured before a recording is used:

- **The quiet passages must reach silence.** A music bed or an effect never
  lets a recording go quiet, and the model learns whatever is under the
  speech. A clean dataset clip reaches -99 dB. A generated voice reaches
  about -60 dB, and the two worst used here are Venti at -42.8 and Abridged
  Kirito at -45.4. If dream sounds hissier than the rest of the cast, that
  is where it comes from.
- **No sample sits at full scale.** That is a recording already damaged, and
  the damage is copied.
- **The level is brought to about -3 dBFS.** The gain is applied after the
  measurement, so a quiet recording is not refused for being quiet.
- **The pitch is taken**, to keep this table honest and to keep two
  characters apart.

## What the cache does with these

A key is made from the content of the recording and not from its name. So a
better take of one character remakes that character and nobody else. A file
that only changed its name keeps every line it has.

This is why a voice can be put back. Rename a file to what `cast.toml` asks
for, render, and every line that voice already read comes back from the
cache.
