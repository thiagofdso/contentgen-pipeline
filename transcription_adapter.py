"""
Adapter temporário para migração gradual para a biblioteca de transcrição pluggável.
Mantém compatibilidade com a interface atual durante a transição.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from transcription_library.core.manager import TranscriptionManager
from transcription_library.providers.distil_whisper_provider import DistilWhisperProvider
from transcription_library.providers.faster_whisper_provider import FasterWhisperProvider
from transcription_library.providers.gemini_provider import GeminiProvider

from models import AIProcessingResult, ProcessingJobConfig
from config.settings import settings

logger = logging.getLogger(__name__)


class TranscriptionAdapter:
    """
    Adapter temporário para migração gradual da biblioteca de transcrição.
    Mantém interface atual enquanto usa nova biblioteca internamente.
    """

    def __init__(self):
        self.manager = TranscriptionManager()
        self.gemini_provider = None  # Referência direta ao provider Gemini
        self._setup_providers()
        self._map_settings()
        self.initialization_complete = False

    def _setup_providers(self):
        """Registra provedores conforme configurações atuais."""
        try:
            # Registrar Distil-Whisper (português otimizado) como primário para áudio
            distil_provider = DistilWhisperProvider()
            self.manager.register_provider("distil-whisper-pt", distil_provider)
            logger.info("Registered Distil-Whisper provider")

            # Registrar faster-whisper como fallback para áudio
            if settings.ai.enable_whisper_fallback:
                faster_provider = FasterWhisperProvider()
                self.manager.register_provider("faster-whisper", faster_provider)
                logger.info("Registered faster-whisper provider")

            # Registrar Gemini para vídeos e como fallback de emergência
            if settings.ai.gemini_api_key:
                self.gemini_provider = GeminiProvider()
                # Usar o nome padrão do provider como no teste
                provider_name = self.gemini_provider.get_name()
                self.manager.register_provider(provider_name, self.gemini_provider)
                logger.info(f"Registered Gemini provider as '{provider_name}'")

        except Exception as e:
            logger.error(f"Error setting up transcription providers: {e}")
            raise

    def _map_settings(self):
        """Mapeia configurações atuais para biblioteca nova."""
        try:
            from transcription_library.core.config import settings as lib_settings

            # Configurar provedor primário para áudio
            lib_settings.PRIMARY_PROVIDER = "distil-whisper-pt"

            # Configurar cadeia de fallback
            fallback_providers = []
            if settings.ai.enable_whisper_fallback:
                fallback_providers.append("faster-whisper")
            if settings.ai.gemini_api_key:
                # Usar nome correto do provider Gemini
                fallback_providers.append("gemini-hybrid")

            lib_settings.FALLBACK_PROVIDERS = fallback_providers
            lib_settings.CONFIDENCE_THRESHOLD = 0.6  # Manter threshold atual

            # Mapear configurações específicas
            lib_settings.FASTER_WHISPER_MODEL_SIZE = settings.ai.whisper_model
            lib_settings.GEMINI_API_KEY = settings.ai.gemini_api_key
            lib_settings.MAX_VIDEO_SIZE_MB = settings.ai.max_video_size_mb
            lib_settings.VIDEO_TIMEOUT = settings.ai.gemini_video_timeout

            logger.info("Settings mapped successfully to transcription library")

        except Exception as e:
            logger.warning(f"Could not map settings to transcription library: {e}")
            # Continua sem falhar - configurações podem ser padrão

    async def initialize(self) -> bool:
        """Inicializa o adapter (não precisa inicializar manager explicitamente)."""
        try:
            logger.info("Initializing transcription adapter...")

            # O TranscriptionManager não precisa de inicialização explícita
            # Os provedores são inicializados automaticamente quando usados
            self.initialization_complete = True
            logger.info("Transcription adapter initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Error initializing transcription adapter: {e}")
            return False

    async def process_audio(
        self,
        audio_file_path: Path,
        config: ProcessingJobConfig,
        job_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> AIProcessingResult:
        """
        Processa áudio mantendo interface atual, usando nova biblioteca com retry automático.

        Args:
            audio_file_path: Caminho para arquivo de áudio
            config: Configuração de processamento atual
            job_id: ID do job (opcional)
            description: Descrição do conteúdo (opcional)

        Returns:
            AIProcessingResult: Resultado no formato atual
        """
        if not self.initialization_complete:
            await self.initialize()

        # Implementar retry para processamento de áudio (3 tentativas)
        language = config.language_hint or "pt"
        max_attempts = 3
        retry_delay = 1.0  # segundos (menor delay para áudio)

        last_error = None
        for attempt in range(max_attempts):
            try:
                if attempt > 0:
                    logger.info(f"Audio transcription retry attempt {attempt + 1}/{max_attempts} for {audio_file_path}")
                    await asyncio.sleep(retry_delay * attempt)  # Delay progressivo

                logger.info(f"Processing audio with new library (attempt {attempt + 1}): {audio_file_path}")

                # Usar nova biblioteca para transcrição
                result = await self.manager.transcribe_audio(audio_file_path, language=language)

                # Se chegou aqui sem exception e não tem erro, processamento foi bem-sucedido
                if not result.error_message:
                    ai_result = self._convert_transcription_result(result)
                    logger.info(f"Audio transcription completed with {result.model_used} on attempt {attempt + 1}")
                    return ai_result

                # Se tem error_message mas não exception, log e tenta novamente
                last_error = result.error_message
                logger.warning(f"Audio transcription attempt {attempt + 1} failed with error: {result.error_message}")

                # Se é o último attempt, retorna o erro
                if attempt == max_attempts - 1:
                    logger.error(f"Audio transcription failed after {max_attempts} attempts: {result.error_message}")
                    return AIProcessingResult(
                        error_message=f"Audio transcription failed after {max_attempts} attempts: {result.error_message}",
                        service_used=result.model_used,
                        processing_time=result.processing_time
                    )

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Audio transcription attempt {attempt + 1} failed with exception: {e}")

                # Se é o último attempt, relança a exception
                if attempt == max_attempts - 1:
                    logger.error(f"Audio transcription failed after {max_attempts} attempts with exceptions")
                    error_msg = f"Audio processing failed with adapter after {max_attempts} attempts: {str(e)}"
                    logger.error(error_msg)
                    return AIProcessingResult(
                        error_message=error_msg,
                        service_used="transcription-adapter",
                        processing_time=0.0
                    )

                # Para erros de rede/API, aguarda antes de tentar novamente
                if any(keyword in str(e).lower() for keyword in ["ssl", "eof", "network", "connection", "timeout"]):
                    logger.info(f"Network/API error detected, waiting {retry_delay * (attempt + 1)} seconds before retry")
                    await asyncio.sleep(retry_delay * (attempt + 1))

        # Este ponto não deveria ser alcançado, mas por segurança
        return AIProcessingResult(
            error_message=f"Audio transcription failed after {max_attempts} attempts: {last_error}",
            service_used="transcription-adapter",
            processing_time=0.0
        )

    async def process_video(
        self,
        video_file_path: Path,
        config: ProcessingJobConfig,
        job_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> AIProcessingResult:
        """
        Processa vídeo usando Gemini provider da nova biblioteca com retry automático.
        """
        if not self.initialization_complete:
            await self.initialize()

        try:
            logger.info(f"Processing video with new library: {video_file_path}")

            # Para vídeos, usar Gemini provider diretamente
            if not self.gemini_provider:
                return AIProcessingResult(
                    error_message="Gemini provider not available for video processing",
                    service_used="transcription-adapter",
                    processing_time=0.0
                )

            # Implementar retry para upload de vídeo (3 tentativas)
            language = config.language_hint or "pt-BR"
            max_attempts = 3
            retry_delay = 2.0  # segundos

            last_error = None
            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        logger.info(f"Video transcription retry attempt {attempt + 1}/{max_attempts} for {video_file_path}")
                        await asyncio.sleep(retry_delay * attempt)  # Delay progressivo

                    # Usar provider Gemini diretamente para vídeo
                    result = await self.gemini_provider.transcribe(video_file_path, language=language)

                    # Se chegou aqui sem exception e não tem erro, processamento foi bem-sucedido
                    if not result.error_message:
                        ai_result = self._convert_transcription_result(result)
                        logger.info(f"Video transcription completed with {result.model_used} on attempt {attempt + 1}")
                        return ai_result

                    # Se tem error_message mas não exception, log e tenta novamente
                    last_error = result.error_message
                    logger.warning(f"Video transcription attempt {attempt + 1} failed with error: {result.error_message}")

                    # Se é o último attempt, retorna o erro
                    if attempt == max_attempts - 1:
                        logger.error(f"Video transcription failed after {max_attempts} attempts: {result.error_message}")
                        return AIProcessingResult(
                            error_message=f"Video transcription failed after {max_attempts} attempts: {result.error_message}",
                            service_used=result.model_used,
                            processing_time=result.processing_time
                        )

                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"Video transcription attempt {attempt + 1} failed with exception: {e}")

                    # Se é o último attempt, relança a exception
                    if attempt == max_attempts - 1:
                        logger.error(f"Video transcription failed after {max_attempts} attempts with exceptions")
                        raise

                    # Para erros de SSL/EOF, aguarda um pouco mais antes de tentar novamente
                    if "EOF occurred in violation of protocol" in str(e) or "SSL" in str(e):
                        logger.info(f"SSL/EOF error detected, waiting {retry_delay * (attempt + 1)} seconds before retry")
                        await asyncio.sleep(retry_delay * (attempt + 1))

            # Este ponto não deveria ser alcançado, mas por segurança
            return AIProcessingResult(
                error_message=f"Video transcription failed after {max_attempts} attempts: {last_error}",
                service_used="transcription-adapter",
                processing_time=0.0
            )

        except Exception as e:
            error_msg = f"Video processing failed with adapter after retries: {str(e)}"
            logger.error(error_msg)
            return AIProcessingResult(
                error_message=error_msg,
                service_used="transcription-adapter",
                processing_time=0.0
            )

    def _convert_transcription_result(self, tr_result) -> AIProcessingResult:
        """
        Converte TranscriptionResult da nova biblioteca para AIProcessingResult atual.
        """
        return AIProcessingResult(
            transcription=tr_result.text,
            confidence_score=tr_result.confidence,
            service_used=tr_result.model_used,
            processing_time=tr_result.processing_time,
            language_detected=tr_result.language,
            error_message=tr_result.error_message,
            # Campos de sumarização ficarão None por enquanto
            # (sumarização continua no sistema atual)
            summary=None,
            enhanced_title=None,
            categoria=None,
            tags=None,
            tokens_used=0  # Será calculado pelo sistema atual se necessário
        )

    async def get_processing_status(self) -> Dict[str, Any]:
        """Retorna status dos provedores via nova biblioteca."""
        try:
            if not self.initialization_complete:
                return {
                    "adapter_status": "not_initialized",
                    "providers": {}
                }

            # Obter status de todos os provedores
            all_status = self.manager.get_all_providers_status()

            # Construir cadeia de fallback dinamicamente
            fallback_chain = ["distil-whisper-pt"]
            if settings.ai.enable_whisper_fallback:
                fallback_chain.append("faster-whisper")
            if settings.ai.gemini_api_key:
                fallback_chain.append("gemini-hybrid")

            return {
                "adapter_status": "active",
                "library_version": "transcription_library",
                "primary_provider": "distil-whisper-pt",
                "providers": all_status,
                "fallback_chain": fallback_chain
            }

        except Exception as e:
            logger.error(f"Error getting processing status: {e}")
            return {
                "adapter_status": "error",
                "error": str(e)
            }

    def clear_cache(self) -> None:
        """Limpa caches de todos os provedores."""
        try:
            self.manager.clear_all_caches()
            logger.info("All transcription caches cleared via adapter")
        except Exception as e:
            logger.error(f"Error clearing caches: {e}")