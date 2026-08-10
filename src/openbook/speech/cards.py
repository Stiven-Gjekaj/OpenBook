"""Draws the pictures that a video shows.

The pictures are drawn here and not by ffmpeg. ffmpeg can draw text, but only
when it was built with freetype, and a great many builds were not, including
the one this project was written against. Drawing here also allows a face made
of two layers, where one file holds the outline and another holds the fill,
which ffmpeg cannot do in a single pass.

One picture is made for each chapter. The video then holds the name of the
chapter that is playing, and the whole volume still encodes at nearly the cost
of one still picture, because 23 pictures across four hours is 23 frames that
differ and many thousands that do not.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..errors import OpenBookError


@dataclass(frozen=True)
class _Pillow:
    """The three parts of Pillow that this module uses."""

    image: object
    draw: object
    font: object


def _pillow() -> _Pillow:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as error:
        raise OpenBookError(
            "drawing a card needs Pillow, which is not installed. Add it with "
            "'uv sync --extra video'"
        ) from error
    return _Pillow(image=Image, draw=ImageDraw, font=ImageFont)


@dataclass(frozen=True)
class Style:
    """How a card looks."""

    title_font: Path
    body_font: Path
    title: str = "SOULTALE"
    title_back_font: Path | None = None
    width: int = 1920
    height: int = 1080
    background: str = "#12101F"
    title_colour: str = "#F3EFFF"
    title_back_colour: str = "#5B4B9E"
    body_colour: str = "#C9C2E8"
    faint_colour: str = "#6E6795"
    title_size: int = 190
    body_size: int = 64
    faint_size: int = 40

    def __post_init__(self) -> None:
        for path in (self.title_font, self.body_font, self.title_back_font):
            if path is not None and not Path(path).exists():
                raise OpenBookError(f"{path}: the font file does not exist")
        if self.width % 2 or self.height % 2:
            raise OpenBookError(
                "a card must have an even width and height, because video is "
                "encoded in blocks of two pixels"
            )


def wrap(draw, text: str, font, limit: int) -> list[str]:
    """Break a line so that no part of it is wider than the limit."""
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    line = words[0]
    for word in words[1:]:
        wider = f"{line} {word}"
        if draw.textbbox((0, 0), wider, font=font)[2] <= limit:
            line = wider
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def make_card(
    style: Style, out: Path, *, chapter: str = "", subtitle: str = ""
) -> Path:
    """Draw one card: the name of the work, and what is playing under it."""
    pillow = _pillow()

    canvas = pillow.image.new("RGB", (style.width, style.height), style.background)
    draw = pillow.draw.Draw(canvas)
    margin = int(style.width * 0.08)
    limit = style.width - margin * 2

    title_font = pillow.font.truetype(str(style.title_font), style.title_size)
    body_font = pillow.font.truetype(str(style.body_font), style.body_size)
    faint_font = pillow.font.truetype(str(style.body_font), style.faint_size)

    # Everything is measured before anything is drawn, so that the whole group
    # sits in the middle of the frame. Placing the title at a fixed height
    # leaves the lower third of a card empty and the group looking high.
    title_box = draw.textbbox((0, 0), style.title, font=title_font)
    title_height = title_box[3] - title_box[1]
    lines = [line for line in wrap(draw, subtitle, body_font, limit) if line]

    gap = style.body_size * 0.9
    block = title_height + gap
    if chapter:
        block += style.faint_size * 1.9
    block += len(lines) * style.body_size * 1.35

    top = (style.height - block) / 2

    box = draw.textbbox((0, 0), style.title, font=title_font)
    x = (style.width - (box[2] - box[0])) / 2 - box[0]
    y = top - title_box[1]
    if style.title_back_font is not None:
        back = pillow.font.truetype(str(style.title_back_font), style.title_size)
        draw.text((x, y), style.title, font=back, fill=style.title_back_colour)
    draw.text((x, y), style.title, font=title_font, fill=style.title_colour)

    below = top + title_height + gap
    if chapter:
        width = draw.textbbox((0, 0), chapter, font=faint_font)[2]
        draw.text(
            ((style.width - width) / 2, below),
            chapter,
            font=faint_font,
            fill=style.faint_colour,
        )
        below += style.faint_size * 1.9

    for line in lines:
        width = draw.textbbox((0, 0), line, font=body_font)[2]
        draw.text(
            ((style.width - width) / 2, below),
            line,
            font=body_font,
            fill=style.body_colour,
        )
        below += style.body_size * 1.35

    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


def make_chapter_cards(
    marks,
    style: Style,
    directory: Path,
    *,
    total: float | None = None,
    labels: list[str] | None = None,
) -> list[tuple[Path, float]]:
    """Draw one card for each chapter, and say how long each is shown.

    A card is held from the moment its chapter starts until the next one
    starts, and not for the length of its own audio. The two are not the same:
    a silence sits between two chapters, and it belongs to the card in front of
    it. Using the length of the audio instead loses that silence from every
    card, and by the last chapter the picture changes some seconds early.
    """
    directory.mkdir(parents=True, exist_ok=True)
    ends = [mark.start for mark in marks[1:]] + [total if total else marks[-1].end]

    cards: list[tuple[Path, float]] = []
    for index, (mark, until) in enumerate(zip(marks, ends, strict=True)):
        path = directory / f"card-{index:03d}.png"
        # The words the narrator uses for this chapter. A prologue chapter is
        # announced as "Prologue" and not as "Chapter 0", and a card that
        # disagrees with the voice is worse than a card with no label at all.
        label = (
            labels[index]
            if labels is not None
            else f"Chapter {index + 1} of {len(marks)}"
        )
        make_card(style, path, chapter=label, subtitle=mark.title)
        cards.append((path, max(0.04, until - mark.start)))
    return cards


def write_concat_list(cards: list[tuple[Path, float]], path: Path) -> Path:
    """Write the list that tells ffmpeg which card to show and for how long.

    The last file is written a second time with no duration. The concat reader
    of ffmpeg needs that, or it drops the final card.
    """
    if not cards:
        raise OpenBookError("there are no cards to show")
    lines: list[str] = []
    for card, seconds in cards:
        lines.append(f"file '{card.resolve().as_posix()}'")
        lines.append(f"duration {seconds:.3f}")
    lines.append(f"file '{cards[-1][0].resolve().as_posix()}'")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
