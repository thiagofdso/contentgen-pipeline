"""Orquestrador do pipeline de geração de conteúdo.

Este módulo implementa o PipelineOrchestrator que coordena todo o fluxo
de processamento de mídia: extração de áudio, transcrição e geração
de conteúdo estruturado.
"""

import asyncio
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from ..core.media_processor import MediaProcessor
from ..core.transcriber import Transcriber
from ..generators.base import BaseContentGenerator
from ..utils import logger
from ..config import settings


class PipelineOrchestrator:
    """Orquestrador principal do pipeline de geração de conteúdo.
    
    Coordena todo o fluxo de processamento: extração de áudio, transcrição
    e geração de conteúdo estruturado (resumos, diagramas, mapas mentais).
    """
    
    def __init__(self, content_generator: BaseContentGenerator):
        """Inicializa o orquestrador do pipeline.
        
        Args:
            content_generator: Instância do gerador de conteúdo a ser usado.
        """
        self.content_generator = content_generator
        self.media_processor = MediaProcessor()
        self.transcriber = None  # Só inicializa se necessário
        logger.info(f"PipelineOrchestrator inicializado com gerador: {content_generator.get_provider_name()}")
    
    async def process_single_file(
        self,
        media_path: Path,
        extract_audio: bool = True,
        transcribe: bool = True,
        diagram: bool = True,
        summarize: bool = True,
        mindmap: bool = False,
    ) -> Dict[str, Any]:
        """Processa um único arquivo de mídia através do pipeline completo ou parcial.
        
        Args:
            media_path: Caminho para o arquivo de mídia a ser processado.
            extract_audio: Se True, extrai o áudio do vídeo.
            transcribe: Se True, transcreve o áudio.
            diagram: Se True, gera diagramação do texto.
            summarize: Se True, gera resumo do texto.
            mindmap: Se True, gera mapa mental a partir do(s) texto(s).
        Returns:
            Dicionário com informações sobre os arquivos gerados.
        """
        if not media_path.exists():
            raise FileNotFoundError(f"Arquivo de mídia não encontrado: {media_path}")
        logger.info(f"Iniciando processamento do arquivo: {media_path.name}")
        try:
            audio_path = None
            transcript_result = None
            transcript_files = {}
            content_files = {}
            mindmap_result = None
            base_name = media_path.stem
            output_dir = media_path.parent
            txt_path = output_dir / f"{base_name}.txt"
            srt_path = output_dir / f"{base_name}.srt"
            md_path = output_dir / f"{base_name}.md"

            # 1. Transcrição: só se não existirem .txt e .srt
            if transcribe:
                if txt_path.exists() and srt_path.exists():
                    logger.info(f"Transcrição e legenda já existem para {media_path.name}, pulando transcrição.")
                    transcript_text = txt_path.read_text(encoding="utf-8")
                    transcript_result = {"text": transcript_text, "segments": []}
                    transcript_files = {"transcript": str(txt_path), "subtitles": str(srt_path)}
                else:
                    if self.transcriber is None:
                        self.transcriber = Transcriber()
                    if extract_audio:
                        logger.info("Extraindo áudio do arquivo de mídia...")
                        audio_path = await self._extract_audio(media_path)
                    else:
                        audio_path = media_path.with_suffix('.mp3')
                        if not audio_path.exists():
                            raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}. Use --extract-audio para gerar.")
                    logger.info("Transcrevendo áudio...")
                    transcript_result = await self._transcribe_audio(audio_path)
                    transcript_files = await self._save_transcript_files(media_path, transcript_result)
                    if extract_audio and audio_path and audio_path.exists():
                        await self._cleanup_audio(audio_path)
            else:
                if not txt_path.exists():
                    raise FileNotFoundError(f"Arquivo de transcrição não encontrado: {txt_path}. Use --transcribe para gerar.")
                transcript_text = txt_path.read_text(encoding="utf-8")
                transcript_result = {"text": transcript_text, "segments": []}
                transcript_files = {"transcript": str(txt_path), "subtitles": str(srt_path) if srt_path.exists() else ""}

            # 2. Diagramação e 3. Resumo: só se não existir .md
            diagrammed_text = transcript_result["text"]
            if md_path.exists():
                logger.info(f"Resumo já existe para {media_path.name}, pulando diagramação e resumo.")
                summary = md_path.read_text(encoding="utf-8")
                content_files["summary"] = summary
            else:
                if diagram:
                    logger.info("Gerando diagramação...")
                    diagrammed_text = await self.content_generator.diagram(transcript_result["text"])
                    tamanho_original = len(transcript_result["text"].encode("utf-8"))
                    tamanho_diagramado = len(diagrammed_text.encode("utf-8"))
                    if tamanho_diagramado > tamanho_original:
                        txt_path.write_text(diagrammed_text, encoding="utf-8")
                        logger.info(f"Arquivo diagramado sobrescrito: {txt_path}")
                    else:
                        logger.info("Conteúdo diagramado não é maior que o original. Não sobrescrevendo o .txt.")
                    content_files["diagrammed"] = diagrammed_text
                else:
                    diagrammed_text = transcript_result["text"]
                if summarize:
                    logger.info("Gerando resumo...")
                    summary = await self.content_generator.summarize(diagrammed_text)
                    md_path.write_text(summary, encoding="utf-8")
                    logger.info(f"Resumo salvo em: {md_path}")
                    content_files["summary"] = summary
            # 4. Gerar mapa mental
            if mindmap:
                logger.info("Gerando mapa mental...")
                texts_for_mindmap = [content_files.get("summary") or diagrammed_text]
                mindmap_result = await self.content_generator.create_mindmap(texts_for_mindmap)
                content_files["mindmap"] = mindmap_result
            result = {
                "media_path": str(media_path),
                "transcript_files": transcript_files,
                "content_files": content_files,
                "processing_time": datetime.now().isoformat(),
                "status": "success"
            }
            logger.info(f"Processamento concluído com sucesso: {media_path.name}")
            return result
        except Exception as e:
            logger.error(f"Erro no processamento de {media_path.name}: {str(e)}")
            if 'audio_path' in locals() and audio_path and audio_path.exists() and transcribe and extract_audio:
                await self._cleanup_audio(audio_path)
            raise
    
    async def process_directory(
        self,
        directory_path: Path,
        extract_audio: bool = True,
        transcribe: bool = True,
        diagram: bool = True,
        summarize: bool = True,
        mindmap: bool = False,
    ) -> List[Dict[str, Any]]:
        """Processa todos os arquivos de mídia em um diretório, com controle de etapas."""
        if not directory_path.exists():
            raise FileNotFoundError(f"Diretório não encontrado: {directory_path}")
        if not directory_path.is_dir():
            raise ValueError(f"O caminho não é um diretório: {directory_path}")
        media_files = self._find_media_files(directory_path)
        if not media_files:
            logger.warning(f"Nenhum arquivo de mídia encontrado em: {directory_path}")
            return []
        logger.info(f"Encontrados {len(media_files)} arquivos de mídia para processar")
        tasks = [
            self.process_single_file(
                media_file,
                extract_audio=extract_audio,
                transcribe=transcribe,
                diagram=diagram,
                summarize=summarize,
                mindmap=mindmap
            )
            for media_file in media_files
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful_results = []
        errors = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Erro no processamento de {media_files[i].name}: {str(result)}")
                errors.append({
                    "file": str(media_files[i]),
                    "error": str(result),
                    "status": "error"
                })
            else:
                successful_results.append(result)
        logger.info(f"Processamento concluído: {len(successful_results)} sucessos, {len(errors)} erros")
        return successful_results + errors
    
    async def _extract_audio(self, media_path: Path) -> Path:
        """Extrai áudio do arquivo de mídia.
        
        Args:
            media_path: Caminho para o arquivo de mídia.
            
        Returns:
            Caminho para o arquivo de áudio extraído.
        """
        try:
            audio_path = await asyncio.get_event_loop().run_in_executor(
                None, self.media_processor.extract_audio, media_path
            )
            logger.debug(f"Áudio extraído: {audio_path}")
            return audio_path
        except Exception as e:
            logger.error(f"Erro na extração de áudio: {str(e)}")
            raise
    
    async def _transcribe_audio(self, audio_path: Path) -> Dict[str, Any]:
        """Transcreve o arquivo de áudio.
        
        Args:
            audio_path: Caminho para o arquivo de áudio.
            
        Returns:
            Dicionário com resultado da transcrição.
        """
        try:
            transcript_text, segments = await asyncio.get_event_loop().run_in_executor(
                None, self.transcriber.transcribe, audio_path
            )
            transcript_result = {
                "text": transcript_text,
                "segments": segments
            }
            logger.debug(f"Transcrição concluída: {len(transcript_text)} caracteres")
            return transcript_result
        except Exception as e:
            logger.error(f"Erro na transcrição: {str(e)}")
            raise
    
    async def _save_transcript_files(
        self, media_path: Path, transcript_result: Dict[str, Any]
    ) -> Dict[str, str]:
        """Salva os arquivos de transcrição (.txt e .srt).
        
        Args:
            media_path: Caminho original do arquivo de mídia.
            transcript_result: Resultado da transcrição.
            
        Returns:
            Dicionário com caminhos dos arquivos salvos.
        """
        base_name = media_path.stem
        output_dir = media_path.parent
        
        # Salvar transcrição em texto
        txt_path = output_dir / f"{base_name}.txt"
        txt_path.write_text(transcript_result["text"], encoding="utf-8")
        logger.debug(f"Transcrição salva: {txt_path}")
        
        # Salvar legendas SRT
        srt_path = output_dir / f"{base_name}.srt"
        srt_content = self._generate_srt_content(transcript_result["segments"])
        srt_path.write_text(srt_content, encoding="utf-8")
        logger.debug(f"Legendas salvas: {srt_path}")
        
        return {
            "transcript": str(txt_path),
            "subtitles": str(srt_path)
        }
    
    async def _cleanup_audio(self, audio_path: Path) -> None:
        """Remove o arquivo de áudio temporário.
        
        Args:
            audio_path: Caminho para o arquivo de áudio a ser removido.
        """
        try:
            if audio_path.exists():
                audio_path.unlink()
                logger.debug(f"Arquivo de áudio removido: {audio_path}")
        except Exception as e:
            logger.warning(f"Erro ao remover arquivo de áudio {audio_path}: {str(e)}")
    
    def _find_media_files(self, directory_path: Path) -> List[Path]:
        """Encontra todos os arquivos de mídia suportados em um diretório.
        
        Args:
            directory_path: Caminho para o diretório.
            
        Returns:
            Lista de caminhos para arquivos de mídia.
        """
        supported_extensions = {".mp4", ".avi", ".mkv", ".webm", ".mov", ".m4v"}
        media_files = []
        
        for file_path in directory_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                media_files.append(file_path)
        
        # Ordenar por nome para processamento consistente
        media_files.sort(key=lambda x: x.name)
        return media_files
    
    def _generate_srt_content(self, segments: List[Dict[str, Any]]) -> str:
        """Gera conteúdo SRT a partir dos segmentos da transcrição.
        
        Args:
            segments: Lista de segmentos com timestamps e texto.
            
        Returns:
            Conteúdo formatado em SRT.
        """
        srt_content = ""
        
        for i, segment in enumerate(segments, 1):
            start_time = self._format_timestamp(segment["start"])
            end_time = self._format_timestamp(segment["end"])
            text = segment["text"].strip()
            
            srt_content += f"{i}\n{start_time} --> {end_time}\n{text}\n\n"
        
        return srt_content
    
    def _format_timestamp(self, seconds: float) -> str:
        """Formata timestamp em segundos para formato SRT (HH:MM:SS,mmm).
        
        Args:
            seconds: Tempo em segundos.
            
        Returns:
            Timestamp formatado.
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
    
    async def health_check(self) -> Dict[str, Any]:
        """Verifica a saúde de todos os componentes do pipeline.
        
        Returns:
            Dicionário com status de cada componente.
        """
        health_status = {
            "orchestrator": "healthy",
            "media_processor": "unknown",
            "transcriber": "unknown",
            "content_generator": "unknown"
        }
        
        try:
            # Verificar gerador de conteúdo
            if await self.content_generator.health_check():
                health_status["content_generator"] = "healthy"
            else:
                health_status["content_generator"] = "unhealthy"
        except Exception as e:
            health_status["content_generator"] = f"error: {str(e)}"
        
        # Verificar transcriber (assumindo que está funcionando se foi inicializado)
        try:
            # Teste simples: verificar se o modelo foi carregado
            if hasattr(self.transcriber, 'model') and self.transcriber.model is not None:
                health_status["transcriber"] = "healthy"
            else:
                health_status["transcriber"] = "unhealthy"
        except Exception as e:
            health_status["transcriber"] = f"error: {str(e)}"
        
        # Verificar media processor (assumindo que está funcionando se foi inicializado)
        try:
            if hasattr(self.media_processor, 'ffmpeg_available'):
                health_status["media_processor"] = "healthy"
            else:
                health_status["media_processor"] = "unhealthy"
        except Exception as e:
            health_status["media_processor"] = f"error: {str(e)}"
        
        return health_status 