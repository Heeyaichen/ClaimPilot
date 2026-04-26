"""CLI smoke script for Speech STT transcription.

Usage:
    python scripts/transcribe_audio.py <audio_path>

Requires AZURE_SPEECH_ENDPOINT to be set.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from backend.core.config import get_settings
from backend.services.speech import SpeechService


async def main(audio_path: str) -> None:
    settings = get_settings()
    if not settings.azure_speech_endpoint:
        print("Error: AZURE_SPEECH_ENDPOINT is not configured.", file=sys.stderr)
        sys.exit(1)

    service = SpeechService()
    result = await service.transcribe_voice_statement(audio_path)
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe a voice statement via Azure Speech STT")
    parser.add_argument("audio_path", help="Path to local audio file (WAV/MP3)")
    args = parser.parse_args()
    asyncio.run(main(args.audio_path))
