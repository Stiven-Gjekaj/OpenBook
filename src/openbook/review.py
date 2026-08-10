"""Writes the page that makes 47 hours of audio checkable.

Listening to a whole volume to find the six lines that went wrong is not a
plan. This writes one file listing every piece of speech with the voice it
took, the words it said, and a button that plays it, so a person can skim and
stop only where something looks wrong.

Nothing is guessed. The page is built from the same plan that made the audio,
and each row points at the piece in the cache that the render produced.

The order is the point. The pieces most likely to be wrong come first, so a
person who has ten minutes spends them where the faults are rather than at the
beginning of chapter one.

The file is written whole, with the page and its behaviour inside it. There is
no server to start and nothing to fetch, because a review that needs setting up
is a review that does not happen.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from pathlib import Path

from .cast.utterance import DIALOGUE, Utterance
from .lexicon import Lexicon, is_known, words_of

# A line longer than this is worth hearing, because a long one is where an
# engine wanders and where a division fell in an awkward place.
LONG_CHARACTERS = 320


@dataclass
class Row:
    """One piece of speech, as the page shows it."""

    order: int
    chapter: int
    chapter_title: str
    speaker: str
    voice: str
    kind: str
    text: str
    start: float
    audio: str
    reasons: list[str] = field(default_factory=list)

    @property
    def suspect(self) -> bool:
        return bool(self.reasons)


def reasons_to_hear(
    utterance: Utterance,
    *,
    first_time: bool,
    lexicon: Lexicon,
    known: set[str],
) -> list[str]:
    """Why this line is worth hearing before the others."""
    found: list[str] = []
    text = utterance.text

    if len(text) > LONG_CHARACTERS:
        found.append("long")
    if first_time and utterance.kind == DIALOGUE:
        found.append("first line by this character")
    if any(character.isdigit() for character in text):
        found.append("holds a number")
    if any(word.isupper() and len(word) > 2 for word in text.split()):
        found.append("holds capitals")
    if "*" in text:
        found.append("holds an asterisk")

    missing = [
        word
        for word in words_of(text)
        if not lexicon.says(word) and not is_known(word.lower(), known)
    ]
    if missing:
        found.append(f"words with no entry: {', '.join(sorted(set(missing))[:3])}")
    return found


def rows_from(
    timeline: list[tuple[Utterance, float, float]],
    marks,
    *,
    names: dict[str, str],
    lexicon: Lexicon,
    known: set[str],
    keys: dict[int, str],
) -> list[Row]:
    """Turn a finished render into the rows of the page."""
    seen: set[str] = set()
    rows: list[Row] = []

    for order, (utterance, start, _) in enumerate(timeline):
        chapter, title = _chapter_at(marks, start)
        first_time = utterance.speaker not in seen
        seen.add(utterance.speaker)
        rows.append(
            Row(
                order=order,
                chapter=chapter,
                chapter_title=title,
                speaker=names.get(utterance.speaker, utterance.speaker),
                voice=utterance.voice.key(),
                kind=utterance.kind,
                text=utterance.text,
                start=start,
                audio=keys.get(order, ""),
                reasons=reasons_to_hear(
                    utterance, first_time=first_time, lexicon=lexicon, known=known
                ),
            )
        )
    return rows


def _chapter_at(marks, start: float) -> tuple[int, str]:
    found = ("", "")
    for index, mark in enumerate(marks):
        if mark.start <= start:
            found = (index, mark.title)
    return found


def write_page(rows: list[Row], out: Path, *, title: str, cache: Path) -> Path:
    """Write the page, with everything it needs inside it."""
    out.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "n": row.order,
            "ch": row.chapter,
            "ct": row.chapter_title,
            "sp": row.speaker,
            "v": row.voice,
            "k": row.kind,
            "t": row.text,
            "at": round(row.start, 2),
            "a": row.audio,
            "r": row.reasons,
        }
        for row in rows
    ]
    page = _TEMPLATE.replace("__TITLE__", html.escape(title))
    page = page.replace("__CACHE__", html.escape(cache.resolve().as_uri()))
    page = page.replace("__ROWS__", json.dumps(data))
    out.write_text(page, encoding="utf-8")
    return out


_TEMPLATE = """<!doctype html>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
 :root { color-scheme: dark; --bg:#12101f; --fg:#ddd8f0; --dim:#7e779e;
         --edge:#2a2540; --warn:#d8b45a; }
 body { margin:0; background:var(--bg); color:var(--fg);
        font:15px/1.5 ui-monospace, Menlo, Consolas, monospace; }
 header { position:sticky; top:0; background:var(--bg); padding:14px 18px;
          border-bottom:1px solid var(--edge); }
 h1 { margin:0 0 10px; font-size:17px; font-weight:600; }
 input, select, button { background:#1b1830; color:var(--fg);
        border:1px solid var(--edge); border-radius:5px; padding:5px 8px;
        font:inherit; }
 button { cursor:pointer; }
 /* One width for play and for pause, so a row does not move under the
    pointer when the word changes. */
 .hear { width:64px; }
 .bar { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
 .count { color:var(--dim); margin-left:auto; }
 table { width:100%; border-collapse:collapse; }
 td { padding:7px 10px; border-bottom:1px solid var(--edge);
      vertical-align:top; }
 tr.suspect { background:#1d1830; }
 .who { color:#b9a8f0; white-space:nowrap; }
 .meta { color:var(--dim); white-space:nowrap; font-size:13px; }
 .why { color:var(--warn); font-size:13px; }
 .flagged { outline:2px solid var(--warn); }
 td.text { width:100%; }
</style>
<header>
  <h1>__TITLE__</h1>
  <div class="bar">
    <input id="q" placeholder="search the words" size="26">
    <select id="who"><option value="">every voice</option></select>
    <select id="ch"><option value="">every chapter</option></select>
    <label><input type="checkbox" id="only"> only the ones worth hearing</label>
    <button id="copy">copy what I marked</button>
    <span class="count" id="count"></span>
  </div>
</header>
<table><tbody id="body"></tbody></table>
<script>
const ROWS = __ROWS__, CACHE = "__CACHE__";
const marked = new Set(JSON.parse(localStorage.getItem("openbook-marked") || "[]"));

// One line sounds at a time. Reviewing means starting a line, hearing enough,
// and stopping, and two lines at once tells you nothing about either. The row
// is held by its number and not by its button, so filtering the table while a
// line plays leaves the sound alone and the button comes back in the right
// state.
let sound = null, sounding = null;

function silence() {
  if (sound) { sound.pause(); sound.currentTime = 0; }
  sound = null; sounding = null;
}

function hear(row) {
  if (sounding === row.n && sound) {
    if (sound.paused) sound.play(); else sound.pause();
    draw();
    return;
  }
  silence();
  sound = new Audio(`${CACHE}/${row.a.slice(0,2)}/${row.a}.wav`);
  sounding = row.n;
  sound.onended = () => { silence(); draw(); };
  sound.onpause = draw;
  sound.onplay = draw;
  sound.play();
  draw();
}
const body = document.getElementById("body");
const pad = n => String(Math.floor(n)).padStart(2, "0");
const at = s => `${pad(s/3600)}:${pad((s/60)%60)}:${pad(s%60)}`;

for (const key of ["who","ch"]) {
  const values = [...new Set(ROWS.map(r => key === "who" ? r.sp : r.ch))];
  for (const v of values) {
    const o = document.createElement("option");
    o.value = v; o.textContent = key === "who" ? v : `chapter ${v}`;
    document.getElementById(key).append(o);
  }
}

function draw() {
  const q = document.getElementById("q").value.toLowerCase();
  const who = document.getElementById("who").value;
  const ch = document.getElementById("ch").value;
  const only = document.getElementById("only").checked;
  // The ones worth hearing first, then everything else in the order it is said.
  const shown = ROWS.filter(r =>
      (!q || r.t.toLowerCase().includes(q)) &&
      (!who || r.sp === who) && (!ch || String(r.ch) === ch) &&
      (!only || r.r.length))
    .sort((a,b) => (b.r.length>0) - (a.r.length>0) || a.n - b.n);

  body.replaceChildren(...shown.slice(0, 3000).map(r => {
    const tr = document.createElement("tr");
    if (r.r.length) tr.className = "suspect";
    if (marked.has(r.n)) tr.classList.add("flagged");
    const play = document.createElement("button");
    play.className = "hear";
    play.textContent = (sounding === r.n && sound && !sound.paused) ? "pause" : "play";
    play.disabled = !r.a;
    play.onclick = () => hear(r);
    const mark = document.createElement("button");
    mark.textContent = marked.has(r.n) ? "marked" : "mark";
    mark.onclick = () => { marked.has(r.n) ? marked.delete(r.n) : marked.add(r.n);
      localStorage.setItem("openbook-marked", JSON.stringify([...marked])); draw(); };
    const cells = [play, `${at(r.at)}`, r.sp, r.v, r.t, mark];
    cells.forEach((c, i) => {
      const td = document.createElement("td");
      if (i === 4) {
        td.className = "text"; td.textContent = c;
        if (r.r.length) { const w = document.createElement("div");
          w.className = "why"; w.textContent = r.r.join(" | "); td.append(w); }
      } else if (i === 1 || i === 3) { td.className = "meta"; td.textContent = c; }
      else if (i === 2) { td.className = "who"; td.textContent = c; }
      else td.append(c);
      tr.append(td);
    });
    return tr;
  }));
  document.getElementById("count").textContent =
    `${shown.length} of ${ROWS.length} lines, ${marked.size} marked`;
}

const button = document.getElementById("copy");
button.onclick = async () => {
  const lines = ROWS.filter(r => marked.has(r.n)).map(r => {
    const said = r.t.replace(/"/g, '\\\\"');
    return `# chapter ${r.ch}, ${r.sp}, ${at(r.at)}\\n"${said}" = ""`;
  });
  const text = "[corrections]\\n" + lines.join("\\n") + "\\n";
  await navigator.clipboard.writeText(text);
  button.textContent = "copied";
  setTimeout(() => button.textContent = "copy what I marked", 1500);
};

for (const id of ["q","who","ch","only"])
  document.getElementById(id).addEventListener("input", draw);
draw();
</script>
"""
