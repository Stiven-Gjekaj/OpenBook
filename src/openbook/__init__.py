"""OpenBook turns a book in EPUB form into an audiobook.

The package is a pipeline. Each stage takes the result of the stage before it
and adds one thing:

    epub      reads chapters out of one or more EPUB files
    parse     turns the text of a chapter into typed segments
    cast      gives each segment a voice
    plan      puts pauses between the segments
    speech    makes audio for each segment
    package   joins the audio into one file for each volume

The first four stages need the standard library only, and they hold most of
the rules that a book brings with it. A person can look at the whole parse of
a book, and at the voice of every line in it, before any audio exists.
"""

__version__ = "0.1.0"
