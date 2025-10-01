"""Quick smoke-test for Distil-Whisper using TranscriptionManager and sample.wav."""

import asyncio
from pathlib import Path

from transcription_library.core.manager import TranscriptionManager
from transcription_library.providers.distil_whisper_provider import DistilWhisperProvider

AUDIO_FILE = Path("sample.wav")


def _format_result(result) -> str:
    lines = [
        f"Model used: {result.model_used}",
        f"Detected language: {getattr(result, 'language', 'unknown')}",
        f"Confidence: {getattr(result, 'confidence', 0.0):.3f}",
        f"Processing time: {getattr(result, 'processing_time', 0.0):.2f}s",
    ]
    text = (result.text or "").strip()
    if text:
        preview = text.replace("\n", " ")
        if len(preview) > 200:
            preview = preview[:197] + "..."
        lines.append(f"Preview: {preview}")
    if result.error_message:
        lines.append(f"Error: {result.error_message}")
    return "\n".join(lines)


async def run_test() -> None:
    if not AUDIO_FILE.exists():
        raise FileNotFoundError(f"Audio file not found: {AUDIO_FILE}")

    from transcription_library.core.config import settings as lib_settings
    lib_settings.PRIMARY_PROVIDER = "distil-whisper-pt"
    manager = TranscriptionManager()
    provider = DistilWhisperProvider()
    provider_name = provider.get_name()
    manager.register_provider("distil-whisper-pt", provider)

    print(f"Providers registered: {manager.get_all_providers_status().keys()}")
    print(f"Starting transcription for {AUDIO_FILE} with provider '{provider_name}'")

    result = await manager.transcribe_audio(AUDIO_FILE, language="pt")
    print("\nTranscription result:\n" + _format_result(result))

    segments = result.segments or []
    print(f"\nTotal segments: {len(segments)}")
    for idx, segment in enumerate(segments[:5], 1):
        start = segment.get("start", 0.0)
        end = segment.get("end", 0.0)
        text = segment.get("text", "").strip()
        print(f"Segment {idx:02d}: [{start:.2f}s - {end:.2f}s] {text}")


def main() -> None:
    asyncio.run(run_test())


if __name__ == "__main__":
    main()
