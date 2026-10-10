"""On-demand offline voice. No wake-word process or microphone at idle."""
from pathlib import Path
import json
import shutil
import subprocess
import threading


def speak(text):
    if not shutil.which("espeak-ng"):
        raise RuntimeError("Install espeak-ng for offline speech output")
    # stdin, not argv: text cannot be interpreted as command options.
    process = subprocess.Popen(["espeak-ng", "--stdin"], stdin=subprocess.PIPE,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
    try:
        process.communicate(text[:12000], timeout=120)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise RuntimeError("Speech output timed out") from None


def transcribe(model_path, seconds=8, cancel=None):
    if not model_path or not Path(model_path).is_dir():
        raise RuntimeError("Configure a downloaded offline Vosk model first")
    try:
        import vosk
    except ImportError:
        raise RuntimeError("Optional Vosk dependency is not installed") from None
    if not shutil.which("parec"):
        raise RuntimeError("Install pulseaudio-utils for microphone capture")
    vosk.SetLogLevel(-1)
    model = vosk.Model(str(model_path))
    recognizer = vosk.KaldiRecognizer(model, 16000)
    cancel = cancel or threading.Event()
    # The process exists only during a visible push-to-talk recording.
    process = subprocess.Popen(["parec", "--raw", "--format=s16le", "--rate=16000", "--channels=1"],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    pieces = []
    # Timer terminates capture even if audio input stalls.
    timer = threading.Timer(seconds + 2, process.terminate)
    timer.start()
    try:
        for _ in range(seconds * 8):
            if cancel.is_set():
                break
            data = process.stdout.read(4000)
            if not data:
                break
            if recognizer.AcceptWaveform(data):
                pieces.append(json.loads(recognizer.Result()).get("text", ""))
        pieces.append(json.loads(recognizer.FinalResult()).get("text", ""))
        return " ".join(p for p in pieces if p)
    finally:
        timer.cancel()
        process.terminate()
        process.wait(timeout=3)
        process.stdout.close()
