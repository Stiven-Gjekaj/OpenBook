"""The IndexTTS 2 engine, which is the only one here that can raise its voice.

Every other engine in this project reads a murmur and a shout at one intensity.
That is measured rather than assumed. Zero says "These connections..." and then
"I am the true strongest!" at the end of chapter 2, and Turbo reads the pair
0.3 dB apart with its loudness normaliser off and 0.5 dB apart with it on, the
shout being the quieter of the two. A reference recording carries one delivery
and nothing on that model changes it. The delivery tags do not help: [dramatic]
made that line 3.0 dB quieter than leaving it alone.

IndexTTS 2 separates the feeling from the voice. The recording still says who
is speaking, and a vector of eight numbers says how. The same pair through this
engine measured 15.5 dB apart, from the same zero.wav.

It costs. Turbo renders at 0.85 times real time on this machine and this runs
at about 0.1, so a book read entirely here takes eight times as long. It is not
meant to read the book. The cache is content addressed and holds the name of
the engine, so a line can be made here and its neighbours made by Turbo, and
the few hundred lines the book marks as shouting are what this is for.

WHY IT RUNS IN ANOTHER PROCESS

indextts asks for Python below 3.12 and torch 2.8. This project asks for 3.12
and holds torch 2.6, which is what Chatterbox pins exactly. Both pins are hard
and no Python version reconciles them, so the model runs beside the project
rather than inside it, in an interpreter of its own. See indextts_worker.py.

That boundary earns its keep twice: the machine that runs the worker does not
have to be the machine that runs OpenBook.

SETTING IT UP

    uv venv --python 3.11 ~/.openbook/indextts
    VIRTUAL_ENV=~/.openbook/indextts uv pip install \
        "indextts @ git+https://github.com/index-tts/index-tts.git"

Then name that interpreter, if it is not in the place this looks first:

    export OPENBOOK_INDEXTTS_PYTHON=~/.openbook/indextts/bin/python
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import wave
from pathlib import Path

from ..cast.utterance import NARRATION, BlendedVoice, Voice, VoiceRef
from ..errors import OpenBookError
from .audio import Audio
from .captions import TAG, without_tags

# What every engine here gives back. The model itself works at 22050 and the
# worker resamples before handing a line over, because a render that routes
# some kinds of line to one engine and some to another lays their pieces end
# to end, and two rates meeting there is refused outright.
RATE = 24000

# The same limit Chatterbox takes, and for the same reason: this model is
# autoregressive too. It matters more that the two agree, because the limit
# decides where a long line is divided and a correction names a piece of a
# divided line. Two engines that disagreed would disagree about what a
# correction means.
MAX_CHARACTERS = 300

# The order the model reads the vector in, and it does not check. Getting this
# wrong makes a frightened character sound pleased and nothing reports it.
FEELINGS = (
    "happy",
    "angry",
    "sad",
    "afraid",
    "disgusted",
    "melancholic",
    "surprised",
    "calm",
)

# How hard to push, when a line carries a tag. Measured at 0.8: the angry
# shout came back 9.3 dB above the same words read flat, which is the range
# this engine is here for. Higher clips, and that reading already peaked at
# 0.0 dBFS.
STRENGTH = 0.8

# Which tag means which feeling. The tags are the ones this project already
# writes in corrections.toml, so nothing new has to be learned to use this and
# the eleven corrections that exist keep working.
#
# A tag that names a sound rather than a delivery, [cough] or [laugh], is not
# here. It says what to do, not how to feel, and this model has no way to be
# told it. Those tags are stripped from the words like any other and the line
# is read flat.
MEANINGS = {
    "angry": "angry",
    "happy": "happy",
    "crying": "sad",
    "cry": "sad",
    "fear": "afraid",
    "surprised": "surprised",
    "whispering": "calm",
    "whisper": "calm",
    "narration": "calm",
    # Not a feeling anybody names, but the one tag this book already uses for
    # force. It sits below the rest because a line said with weight is not a
    # line said in anger.
    "dramatic": "angry",
}


def _mapping_key() -> str:
    """What the tags mean, short enough to sit in a version.

    This is part of how a line sounds, so it belongs there. Change a meaning
    and the lines carrying that tag are made again, while every untagged line
    in the book stays where it is, which is most of the book.
    """
    written = json.dumps(MEANINGS, sort_keys=True) + f"|{STRENGTH:g}"
    return hashlib.sha256(written.encode()).hexdigest()[:8]


def feeling_for(text: str) -> tuple[str, list[float] | None]:
    """The words to say, and how to say them.

    A tag in the line chooses the feeling. The tag is taken out either way,
    because it is an instruction and not something anybody says aloud, and a
    model handed the brackets reads them.
    """
    wanted = None
    for found in TAG.finditer(text):
        name = found.group(1).strip().lower()
        if name in MEANINGS:
            wanted = MEANINGS[name]
            break
    said = without_tags(text)
    if wanted is None:
        return (said, None)
    return (said, [STRENGTH if f == wanted else 0.0 for f in FEELINGS])


class IndexTtsEngine:
    """Speaks in the voice of a recording, with a feeling of its own."""

    name = "indextts"

    def __init__(
        self,
        *,
        directory: Path | None = None,
        python: str | None = None,
        model_dir: str | None = None,
        device: str | None = None,
        max_characters: int | None = MAX_CHARACTERS,
    ) -> None:
        self._directory = Path(directory) if directory else Path()
        self._python = python
        self._model_dir = model_dir
        self._device = device
        self._max = max_characters
        self._worker: subprocess.Popen | None = None

    @property
    def version(self) -> str:
        return f"2-{_mapping_key()}"

    @property
    def rate(self) -> int:
        return RATE

    @property
    def max_characters(self) -> int | None:
        return self._max

    def voice_key(
        self,
        voice: VoiceRef,
        *,
        kind: str = NARRATION,
        exaggeration: float | None = None,
    ) -> str:
        """The recording a voice is taken from, and not the name of it.

        A better take written over the same path is a different voice and has
        to be made again. There is no exaggeration here: this engine takes its
        feeling from the words, which are in the key of the line already.
        """
        if isinstance(voice, Voice):
            return self._fingerprint(voice.name)
        return voice.key()

    def speak(
        self,
        text: str,
        voice: VoiceRef,
        *,
        kind: str = NARRATION,
        exaggeration: float | None = None,
    ) -> Audio:
        if not text.strip():
            raise OpenBookError("a speech engine was given nothing to say")
        if isinstance(voice, BlendedVoice):
            raise OpenBookError(
                "IndexTTS cannot blend two voices, because a voice here is a "
                "recording and not a style that can be averaged. For a line two "
                "characters say together use mix or mix_matched, which speak it "
                "once in each voice, or primary, which gives it to the first"
            )
        if not isinstance(voice, Voice):
            raise OpenBookError(f"IndexTTS was given a voice it cannot read: {voice!r}")

        # The caller's own file, answered before the worker is started. Loading
        # this model to find out that a recording is missing reports the wrong
        # problem and takes eighteen seconds.
        reference = self.reference_for(voice.name)
        said, feeling = feeling_for(text)
        if not said.strip():
            raise OpenBookError(
                f"the line {text!r} is nothing but tags, so there is nothing to say"
            )

        with tempfile.TemporaryDirectory() as where:
            out = Path(where) / "line.wav"
            answer = self._ask(
                {
                    "text": said,
                    "reference": str(reference),
                    "emotion": feeling,
                    "seed": self._seed(text, voice),
                    "out": str(out),
                }
            )
            if not answer.get("ok"):
                raise OpenBookError(
                    f"IndexTTS could not say {said!r}: {answer.get('error')}"
                )
            return _read(out)

    def reference_for(self, name: str) -> Path:
        """The recording a voice is taken from, named the way a person wrote it."""
        path = Path(name)
        if not path.is_absolute():
            path = self._directory / path
        if not path.exists():
            raise OpenBookError(
                f"the voice {name!r} is the recording {path}, and there is no "
                "file there. An IndexTTS voice is a path to a recording of the "
                "character, written in cast.toml and read from the project "
                "directory"
            )
        return path

    def close(self) -> None:
        """Let the worker go, and with it about seven gigabytes."""
        worker = self._worker
        self._worker = None
        if worker is None:
            return
        try:
            if worker.stdin:
                worker.stdin.close()
            worker.wait(timeout=30)
        except Exception:
            worker.kill()

    def __enter__(self) -> IndexTtsEngine:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _fingerprint(self, name: str) -> str:
        """Enough of the recording to tell one take from another."""
        path = self.reference_for(name)
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

    def _seed(self, text: str, voice: VoiceRef) -> int:
        """Make the same words in the same voice come out the same way.

        Worked out here rather than in the worker, so that it depends on the
        words and the voice and not on how many lines the worker has already
        said. A line remade next week has to match the chapter it sits in.
        """
        digest = hashlib.sha256(f"{voice.key()}\x1f{text}".encode()).digest()
        return int.from_bytes(digest[:4], "big")

    def _ask(self, request: dict) -> dict:
        worker = self._started()
        assert worker.stdin is not None and worker.stdout is not None
        worker.stdin.write(json.dumps(request) + "\n")
        worker.stdin.flush()
        line = worker.stdout.readline()
        if not line:
            self._worker = None
            raise OpenBookError(
                "the IndexTTS worker stopped while it was speaking a line. Its "
                "own error is above, on standard error"
            )
        return json.loads(line)

    def _started(self) -> subprocess.Popen:
        if self._worker is not None and self._worker.poll() is None:
            return self._worker
        python = self._interpreter()
        worker = Path(__file__).with_name("indextts_worker.py")
        command = [python, str(worker), "--model-dir", self._models()]
        if self._device:
            command += ["--device", self._device]
        started = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert started.stdout is not None
        hello = started.stdout.readline()
        if not hello:
            raise OpenBookError(
                f"the IndexTTS worker at {python} did not start. Its own error "
                "is above, on standard error"
            )
        answer = json.loads(hello)
        if not answer.get("ok"):
            raise OpenBookError(f"IndexTTS did not load: {answer.get('error')}")
        self._worker = started
        return started

    def _interpreter(self) -> str:
        named = self._python or os.environ.get("OPENBOOK_INDEXTTS_PYTHON")
        if named:
            if not Path(named).exists():
                raise OpenBookError(
                    f"OPENBOOK_INDEXTTS_PYTHON names {named}, and there is no "
                    "file there"
                )
            return named
        usual = Path.home() / ".openbook" / "indextts" / "bin" / "python"
        if usual.exists():
            return str(usual)
        raise OpenBookError(
            "IndexTTS needs a Python of its own, because it asks for a version "
            "and a torch that this project cannot hold at the same time as "
            f"Chatterbox. Nothing is at {usual}. Make one with:\n"
            "    uv venv --python 3.11 ~/.openbook/indextts\n"
            '    VIRTUAL_ENV=~/.openbook/indextts uv pip install "indextts @ '
            'git+https://github.com/index-tts/index-tts.git"\n'
            "Or name another with OPENBOOK_INDEXTTS_PYTHON"
        )

    def _models(self) -> str:
        named = self._model_dir or os.environ.get("OPENBOOK_INDEXTTS_MODEL")
        if named:
            if not Path(named).is_dir():
                raise OpenBookError(
                    f"OPENBOOK_INDEXTTS_MODEL names {named}, and there is no "
                    "directory there"
                )
            return named
        found = _in_cache()
        if found is None:
            raise OpenBookError(
                "the IndexTTS 2 weights are not on this machine. Get them with:"
                "\n    hf download IndexTeam/IndexTTS-2\n"
                "Or name a directory holding config.yaml with "
                "OPENBOOK_INDEXTTS_MODEL"
            )
        return found


def _in_cache() -> str | None:
    """The weights, where downloading them puts them."""
    hub = os.environ.get("HF_HUB_CACHE") or str(
        Path.home() / ".cache" / "huggingface" / "hub"
    )
    snapshots = Path(hub) / "models--IndexTeam--IndexTTS-2" / "snapshots"
    if not snapshots.is_dir():
        return None
    for found in sorted(snapshots.iterdir()):
        if (found / "config.yaml").exists():
            return str(found)
    return None


def _read(path: Path) -> Audio:
    """The worker writes 16 bit samples of one channel, which is what Audio is."""
    with wave.open(str(path), "rb") as handle:
        if handle.getsampwidth() != 2 or handle.getnchannels() != 1:
            raise OpenBookError(
                "the IndexTTS worker gave back audio in a form this cannot read"
            )
        return Audio(
            samples=handle.readframes(handle.getnframes()),
            rate=handle.getframerate(),
        )


def installed() -> bool:
    """Whether there is an interpreter with IndexTTS in it to talk to."""
    named = os.environ.get("OPENBOOK_INDEXTTS_PYTHON")
    if named:
        return Path(named).exists()
    return (Path.home() / ".openbook" / "indextts" / "bin" / "python").exists()
