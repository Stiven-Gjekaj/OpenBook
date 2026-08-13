"""Speaks lines with IndexTTS 2, in a Python that is not this project's.

This file is run by the IndexTTS engine and never imported by it. It imports
nothing from OpenBook on purpose, because the interpreter that runs it cannot
hold OpenBook at all: indextts asks for Python below 3.12 and torch 2.8, and
this project asks for 3.12 and holds torch 2.6 for Chatterbox. Two pins that
cannot both be met in one environment, and one model too useful to give up
over it. So it runs beside the project instead of inside it.

It reads one request for each line, as JSON, one to a line of standard input,
and answers with one line of JSON. It loads the model once and keeps it, which
is the whole reason it is a long running process and not a command: loading
takes about eighteen seconds and a book has thousands of lines.

    {"text": "...", "reference": "/path/voice.wav", "seed": 12345,
     "emotion": [0, 0.8, 0, 0, 0, 0, 0, 0], "out": "/path/line.wav"}

    {"ok": true, "seconds": 2.77}
    {"ok": false, "error": "..."}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import wave

# Python puts the directory of a script first on the path, and this script
# sits beside indextts.py, the engine that starts it. So 'import indextts'
# finds that file rather than the package, and the error it gives is about a
# relative import, which says nothing about the cause. Taking this directory
# off the path is the whole fix.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]

# The answers go out on a copy of standard output, and standard output itself
# is pointed at standard error before anything is imported.
#
# The library talks. It announces every file it loads and prints the time each
# stage of every line took, and torch and transformers print warnings of their
# own. All of it lands on standard output, where one stray line ends the
# conversation, because the engine reads exactly one line of JSON for each one
# it sends. Moving the descriptor rather than reassigning sys.stdout catches
# what native code writes as well.
_ANSWERS = os.fdopen(os.dup(1), "w")
os.dup2(2, 1)


def main() -> int:
    parsed = argparse.ArgumentParser(description=__doc__)
    parsed.add_argument("--model-dir", required=True)
    parsed.add_argument("--device", default=None)
    arguments = parsed.parse_args()

    try:
        model = _load(arguments.model_dir, arguments.device)
    except Exception as error:
        _say({"ok": False, "error": f"{type(error).__name__}: {error}"})
        return 1
    _say({"ok": True, "ready": True})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            _say(_one(model, json.loads(line)))
        except Exception as error:
            # A bad line is one line. The process stays up, because the
            # eighteen seconds to load again would be paid for every one.
            _say({"ok": False, "error": f"{type(error).__name__}: {error}"})
    return 0


def _load(model_dir: str, device: str | None):
    import torch
    from indextts.infer_v2 import IndexTTS2

    # The Qwen model is 1.2 GB and serves only the route where a feeling is
    # described in words. The engine sends the vector already worked out, so
    # that route is never taken and the memory is better spent elsewhere.
    return IndexTTS2(
        cfg_path=os.path.join(model_dir, "config.yaml"),
        model_dir=model_dir,
        use_fp16=False,
        device=device,
        use_qwen_emo=False,
        aux_paths=_aux_paths(model_dir),
    ), torch


# The four models IndexTTS needs beyond its own weights, and the one file of
# each that it reads.
AUXILIARY = (
    ("w2v_bert", "facebook/w2v-bert-2.0", None),
    ("semantic_codec", "amphion/MaskGCT", "semantic_codec/model.safetensors"),
    ("campplus", "funasr/campplus", "campplus_cn_common.bin"),
    ("bigvgan", "nvidia/bigvgan_v2_22khz_80band_256x", None),
)


def _aux_paths(model_dir: str):
    """Where the four extra models are, without making a second copy of them.

    Left to itself the library copies all four into {model_dir}/hf_cache. That
    is 2.98 GB of files that are already on the disk, and when the model
    directory is the HuggingFace cache, as it is by default, it writes them
    into the cache beside the originals.

    So they are found where downloading them put them and handed over. If any
    one of them is missing the library is asked to fetch them after all, into
    a directory it may write to.
    """
    found = {}
    for key, repo, inside in AUXILIARY:
        where = _snapshot(repo)
        if where is None:
            return _fetched(model_dir)
        whole = os.path.join(where, *inside.split("/")) if inside else where
        if not os.path.exists(whole):
            return _fetched(model_dir)
        found[key] = whole
    return found


def _snapshot(repo: str):
    """A repository in the HuggingFace cache, or None if it is not there."""
    hub = os.environ.get("HF_HUB_CACHE") or os.path.join(
        os.path.expanduser("~"), ".cache", "huggingface", "hub"
    )
    snapshots = os.path.join(hub, "models--" + repo.replace("/", "--"), "snapshots")
    if not os.path.isdir(snapshots):
        return None
    for name in sorted(os.listdir(snapshots)):
        whole = os.path.join(snapshots, name)
        if os.path.isdir(whole) and os.listdir(whole):
            return whole
    return None


def _fetched(model_dir: str):
    """Let the library download what is missing, somewhere it may write.

    Not into the model directory, which is the HuggingFace cache by default
    and is not this project's to write in.
    """
    from indextts.utils.model_download import ensure_models_available

    work = os.environ.get("OPENBOOK_INDEXTTS_WORK") or os.path.join(
        os.path.expanduser("~"), ".openbook", "indextts-aux"
    )
    os.makedirs(work, exist_ok=True)
    return ensure_models_available(work)


def _one(loaded, request: dict) -> dict:
    model, torch = loaded
    out = request["out"]

    # The same words in the same voice come out the same way, on this engine
    # as on the others. The seed is worked out by the caller from the words
    # and the voice, so a line remade next week matches the chapter it sits in.
    torch.manual_seed(int(request["seed"]))

    model.infer(
        spk_audio_prompt=request["reference"],
        text=request["text"],
        output_path=out,
        emo_vector=request.get("emotion"),
        emo_alpha=1.0,
        use_random=False,
        verbose=False,
    )
    return {"ok": True, "seconds": _rewrite(out)}


def _rewrite(path: str) -> float:
    """Put the file into 16 bit samples of one channel, and say how long it is.

    The engine reads this with the standard library, which has no opinion on
    a float wav. Doing the conversion here keeps numpy on this side of the
    process boundary, where it already is.
    """
    import numpy
    import soundfile

    samples, rate = soundfile.read(path, always_2d=True)
    mono = samples.mean(axis=1)
    held = numpy.clip(mono, -1.0, 1.0)
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes((held * 32767.0).astype("<i2").tobytes())
    return len(mono) / rate


def _say(message: dict) -> None:
    _ANSWERS.write(json.dumps(message) + "\n")
    _ANSWERS.flush()


if __name__ == "__main__":
    raise SystemExit(main())
