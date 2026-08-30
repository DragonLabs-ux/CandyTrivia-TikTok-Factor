from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path


def ensure_edge_tts():
    try:
        import edge_tts  # type: ignore
        return edge_tts
    except ImportError:
        print("edge-tts not installed; installing it for premium neural voiceovers...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "edge-tts>=7,<8"])
        import edge_tts  # type: ignore
        return edge_tts


edge_tts = ensure_edge_tts()

DEFAULT_VOICE = "en-US-AvaNeural"
FALLBACK_VOICE = "en-US-JennyNeural"


def clean_for_speech(text: str) -> str:
    return " ".join(text.strip().replace("/", " or ").split())


async def synthesize(text: str, output: Path, voice: str, rate: str, pitch: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    communicator = edge_tts.Communicate(
        clean_for_speech(text),
        voice,
        rate=rate,
        volume="+0%",
        pitch=pitch,
    )
    await communicator.save(str(output))
    if not output.exists() or output.stat().st_size < 512:
        raise RuntimeError(f"Voice generation produced an invalid file: {output}")


async def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/generate-voice.py <request.json> <output-dir>")
        return 2

    request_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    request = json.loads(request_path.read_text(encoding="utf-8"))

    primary_voice = os.environ.get("TTS_VOICE", DEFAULT_VOICE).strip() or DEFAULT_VOICE
    rate = os.environ.get("TTS_RATE", "+24%").strip() or "+24%"
    pitch = os.environ.get("TTS_PITCH", "+2Hz").strip() or "+2Hz"

    clips = {
        "voice-q1.mp3": request["q1"],
        "voice-a1.mp3": request["a1"],
        "voice-q2.mp3": request["q2"],
        "voice-a2.mp3": request["a2"],
        "voice-q3.mp3": request["q3"],
        "voice-cta.mp3": request.get("cta", "Answer in the comments."),
    }

    async def generate_with(voice: str) -> None:
        for filename, text in clips.items():
            await synthesize(text, output_dir / filename, voice, rate, pitch)

    try:
        await generate_with(primary_voice)
        selected_voice = primary_voice
    except Exception as first_error:
        if primary_voice == FALLBACK_VOICE:
            raise
        print(f"Primary voice {primary_voice} failed: {first_error}")
        print(f"Retrying with {FALLBACK_VOICE}...")
        await generate_with(FALLBACK_VOICE)
        selected_voice = FALLBACK_VOICE

    print(json.dumps({
        "voice": selected_voice,
        "rate": rate,
        "pitch": pitch,
        "outputDir": str(output_dir),
        "clips": list(clips.keys()),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
