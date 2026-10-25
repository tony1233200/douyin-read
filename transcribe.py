#!/usr/bin/env python3
"""Offline speech-to-text with SenseVoice-Small (sherpa-onnx runtime, CPU).

Usage:
    python transcribe.py <audio or video file> <output .txt path>

Non-16kHz-mono input is converted with ffmpeg first. Audio longer than one
recognition window (~30 s for SenseVoice) is transcribed in 25-second
chunks and concatenated.

Model:
    SenseVoice-Small (Alibaba FunAudioLLM), int8 ONNX build packaged by
    sherpa-onnx (k2-fsa). On first run the model archive (~230 MB) is
    downloaded automatically into ./models/ (also mirrored on ModelScope).
    To use a model you already have, set SENSEVOICE_MODEL_DIR to the
    directory containing model.int8.onnx and tokens.txt.
"""
import os
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import wave

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL_NAME = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"
MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    + MODEL_NAME + ".tar.bz2"
)
DEFAULT_MODEL_DIR = os.path.join(BASE, "models", MODEL_NAME)
CHUNK_SEC = 25


def model_dir() -> str:
    return os.environ.get("SENSEVOICE_MODEL_DIR", DEFAULT_MODEL_DIR)


def ensure_model() -> str:
    """Return the model directory, downloading the archive on first run."""
    d = model_dir()
    if os.path.exists(os.path.join(d, "model.int8.onnx")):
        return d
    archive = os.path.join(BASE, "models", MODEL_NAME + ".tar.bz2")
    os.makedirs(os.path.dirname(archive), exist_ok=True)
    print(f"Downloading SenseVoice-Small model:\n  {MODEL_URL}")
    urllib.request.urlretrieve(MODEL_URL, archive)
    with tarfile.open(archive, "r:bz2") as tf:
        tf.extractall(os.path.dirname(archive))
    os.remove(archive)
    if not os.path.exists(os.path.join(d, "model.int8.onnx")):
        raise RuntimeError(f"Model download/extract failed, check {d}")
    print(f"Model ready: {d}")
    return d


def ensure_wav(src: str, workdir: str) -> str:
    """Convert any audio/video file to 16 kHz mono wav, return its path."""
    out = os.path.join(workdir, "audio_16k.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", src,
         "-vn", "-ac", "1", "-ar", "16000", out],
        check=True,
    )
    return out


def read_wav(path: str):
    import numpy as np

    with wave.open(path, "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1
        frames = w.readframes(w.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def transcribe(audio_path: str, mdl_dir: str) -> str:
    import sherpa_onnx

    recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=os.path.join(mdl_dir, "model.int8.onnx"),
        tokens=os.path.join(mdl_dir, "tokens.txt"),
        num_threads=2,
        language="zh",
        use_itn=True,
        debug=False,
    )
    samples = read_wav(audio_path)
    sr = 16000
    chunk = CHUNK_SEC * sr
    texts = []
    for start in range(0, len(samples), chunk):
        seg = samples[start:start + chunk]
        if len(seg) < sr // 2:  # skip a too-short tail
            continue
        stream = recognizer.create_stream()
        stream.accept_waveform(sr, seg)
        recognizer.decode_stream(stream)
        texts.append(stream.result.text.strip())
    return "".join(texts)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src, out_txt = sys.argv[1], sys.argv[2]
    os.makedirs(os.path.dirname(os.path.abspath(out_txt)), exist_ok=True)

    mdl_dir = ensure_model()
    t0 = time.time()
    with tempfile.TemporaryDirectory() as workdir:
        wav = ensure_wav(src, workdir)
        t1 = time.time()
        text = transcribe(wav, mdl_dir)
    t2 = time.time()

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"ffmpeg convert: {t1 - t0:.1f}s | SenseVoice ASR: {t2 - t1:.1f}s")
    print(f"Transcript: {len(text)} chars -> {out_txt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
