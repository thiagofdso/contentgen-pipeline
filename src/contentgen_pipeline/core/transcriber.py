"""Modulo de transcricao de audio usando a biblioteca Distil-Whisper."""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

from transcription_library.core.manager import TranscriptionManager
from transcription_library.providers.distil_whisper_provider import DistilWhisperProvider

from ..utils.logger import logger
from ..utils.sentence_splitter import split_sentences


class Transcriber:
    """Classe responsavel pela transcricao de audio usando a nova biblioteca."""

    def __init__(self):
        """Inicializa o Transcriber registrando o provedor Distil-Whisper."""
        self.manager = TranscriptionManager()
        self.provider = DistilWhisperProvider()
        self.provider_name = self.provider.get_name()
        self.manager.register_provider("distil-whisper-pt", self.provider)

    def _run_async(self, coroutine):
        '''Executa uma coroutine garantindo compatibilidade com contextos sincronos.'''
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coroutine)
            finally:
                new_loop.close()
        return asyncio.run(coroutine)

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Obtem a duracao do audio usando ffprobe."""
        try:
            command = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(audio_path),
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
            )
            metadata = json.loads(result.stdout)
            if "format" in metadata and "duration" in metadata["format"]:
                return float(metadata["format"]["duration"])
            if "streams" in metadata:
                for stream in metadata["streams"]:
                    if stream.get("codec_type") == "audio" and "duration" in stream:
                        return float(stream["duration"])
            logger.warning(f"Nao foi possivel obter a duracao do audio: {audio_path}")
        except subprocess.CalledProcessError as exc:  # pragma: no cover - ffprobe externa
            logger.error(f"Erro ao obter duracao do audio: {exc}")
        return 0.0

    def transcribe(self, audio_path: Path) -> Tuple[str, List[Dict]]:
        """Transcreve um arquivo de audio via biblioteca Distil-Whisper."""
        if not audio_path.exists():
            raise FileNotFoundError(f"Arquivo de audio nao encontrado: {audio_path}")
        logger.info(f"Iniciando transcricao de: {audio_path}")
        audio_duration = self._get_audio_duration(audio_path)
        logger.debug(f"Duracao de audio: {audio_duration}")
        try:
            result = self._run_async(
                self.manager.transcribe_audio(
                    audio_path,
                    language="pt",
                )
            )
        except Exception as exc:  # pragma: no cover - captura falhas do provedor async
            logger.error(f"Erro durante a transcricao: {exc}")
            raise RuntimeError(f"Falha na transcricao de {audio_path}: {exc}") from exc
        if getattr(result, "error_message", None):
            logger.error(f"Biblioteca retornou erro: {result.error_message}")
            raise RuntimeError(
                f"Falha na transcricao de {audio_path}: {result.error_message}"
            )
        combined_sentences, segments_metadata = self._process_segments(result)
        combined_text = (getattr(result, "text", "") or "").strip()
        if not combined_text:
            combined_text = " ".join(combined_sentences).strip()
        elif combined_sentences:
            combined_text = " ".join(combined_sentences).strip()
        logger.info(f"Transcricao concluida: {len(segments_metadata)} segmentos processados")
        return combined_text, segments_metadata

    def _process_segments(self, result) -> Tuple[List[str], List[Dict]]:
        """Converte os segmentos retornados pela biblioteca em metadados locais."""
        combined_sentences: List[str] = []
        segments_metadata: List[Dict] = []
        for raw_segment in getattr(result, "segments", None) or []:
            text = (raw_segment.get("text") or "").strip()
            if text:
                combined_sentences.extend(split_sentences(text))
            start = float(raw_segment.get("start", 0.0))
            end = float(raw_segment.get("end", start))
            metadata: Dict = {
                "start": round(start, 2),
                "end": round(end, 2),
                "text": text,
            }
            confidence = raw_segment.get("confidence")
            if confidence is not None:
                metadata["avg_logprob"] = round(float(confidence), 2)
            segments_metadata.append(metadata)
        if not combined_sentences and getattr(result, "text", None):
            combined_sentences.append(result.text.strip())
        return combined_sentences, segments_metadata

    def save_transcript(
        self, audio_path: Path, transcript_text: str, segments: List[Dict]
    ) -> None:
        base_path = audio_path.with_suffix("")
        txt_path = base_path.with_suffix(".txt")
        try:
            with open(txt_path, "w", encoding="utf-8") as handler:
                handler.write(transcript_text)
            logger.info(f"Transcricao salva em: {txt_path}")
        except Exception as exc:  # pragma: no cover - IO externa
            logger.error(f"Erro ao salvar transcricao: {exc}")
            raise
        srt_path = base_path.with_suffix(".srt")
        try:
            self._save_srt_file(srt_path, segments)
            logger.info(f"Legendas salvas em: {srt_path}")
        except Exception as exc:  # pragma: no cover - IO externa
            logger.error(f"Erro ao salvar legendas: {exc}")
            raise

    def _save_srt_file(self, srt_path: Path, segments: List[Dict]) -> None:
        srt_content = ""
        for index, segment in enumerate(segments, 1):
            start_time = self._format_timestamp(segment["start"])
            end_time = self._format_timestamp(segment["end"])
            srt_content += f"{index}\n{start_time} --> {end_time}\n{segment['text']}\n\n"
        with open(srt_path, "w", encoding="utf-8") as handler:
            handler.write(srt_content)

    def _format_timestamp(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"



