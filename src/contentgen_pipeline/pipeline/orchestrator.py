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
from ..utils.logger import logger
from ..config import settings


class PipelineOrchestrator:
    """Orquestrador principal do pipeline de geração de conteúdo.
    
    Coordena todo o fluxo de processamento: extração de áudio, transcrição
    e geração de conteúdo estruturado (resumos, diagramas, mapas mentais).
    """
    
    def __init__(self, content_generator: BaseContentGenerator | Dict[str, BaseContentGenerator]):
        """Inicializa o orquestrador do pipeline.
        
        Args:
            content_generator: Instância do gerador de conteúdo ou dicionário com geradores específicos.
                              Se for dicionário, deve conter chaves: "default", "summarize", "diagram", 
                              "mindmap_preprocess", "mindmap".
        """
        if isinstance(content_generator, dict):
            self.generators = content_generator
            self.content_generator = content_generator.get("default")
            if not self.content_generator:
                raise ValueError("Dicionário de geradores deve conter chave 'default'")
        else:
            self.content_generator = content_generator
            self.generators = {
                "default": content_generator,
                "summarize": content_generator,
                "diagram": content_generator,
                "mindmap_preprocess": content_generator,
                "mindmap": content_generator
            }
        
        self.media_processor = MediaProcessor()
        self.transcriber = None  # Só inicializa se necessário
        logger.info(f"PipelineOrchestrator inicializado com geradores: {[gen.get_provider_name() for gen in self.generators.values()]}")
    
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

            # 1. Extração de áudio
            if extract_audio:
                audio_path = media_path.with_suffix('.mp3')
                if not audio_path.exists():
                    logger.info("Extraindo áudio do arquivo de mídia...")
                    audio_path = await self._extract_audio(media_path)
                else:
                    logger.info(f"Áudio já existe: {audio_path}")
            else:
                audio_path = media_path.with_suffix('.mp3')

            # 2. Transcrição
            if transcribe:
                if txt_path.exists() and srt_path.exists():
                    logger.info(f"Transcrição e legenda já existem para {media_path.name}, pulando transcrição.")
                    transcript_text = txt_path.read_text(encoding="utf-8")
                    transcript_result = {"text": transcript_text, "segments": []}
                    transcript_files = {"transcript": str(txt_path), "subtitles": str(srt_path)}
                else:
                    if self.transcriber is None:
                        self.transcriber = Transcriber()
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

            # 3. Diagramação e 4. Resumo
            diagrammed_text = transcript_result["text"]
            if md_path.exists():
                logger.info(f"Resumo já existe para {media_path.name}, pulando diagramação e resumo.")
                summary = md_path.read_text(encoding="utf-8")
                content_files["summary"] = summary
            else:
                if diagram:
                    logger.info("Gerando diagramação...")
                    diagrammed_text = await self.generators["diagram"].diagram(transcript_result["text"])
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
                    summary = await self.generators["summarize"].summarize(diagrammed_text)
                    md_path.write_text(summary, encoding="utf-8")
                    logger.info(f"Resumo salvo em: {md_path}")
                    content_files["summary"] = summary

            # 5. Mapa mental
            if mindmap:
                logger.info("Gerando mapa mental...")
                mindmap_path = md_path.with_suffix('.opml')
                if mindmap_path.exists():
                    logger.info(f"Mapa mental já existe para {media_path.name}, pulando geração: {mindmap_path}")
                    mindmap_result = mindmap_path.read_text(encoding="utf-8")
                else:
                    # Buscar e unir transcrição e resumo
                    txt_content = txt_path.read_text(encoding="utf-8") if txt_path.exists() else ""
                    md_content = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
                    if txt_content and md_content:
                        logger.info(f"Usando transcrição e resumo para o mapa mental: {txt_path.name}, {md_path.name}")
                        combined_content = f"Transcrição\n{txt_content}\n\nResumo\n{md_content}"
                    elif txt_content:
                        logger.info(f"Usando apenas transcrição para o mapa mental: {txt_path.name}")
                        combined_content = f"Transcrição\n{txt_content}"
                    elif md_content:
                        logger.info(f"Usando apenas resumo para o mapa mental: {md_path.name}")
                        combined_content = f"Resumo\n{md_content}"
                    else:
                        logger.warning(f"Nenhum .txt ou .md encontrado para {media_path.name}, não é possível gerar o mapa mental.")
                        combined_content = ""
                    if combined_content:
                        # Pré-processamento da estrutura
                        estrutura = await self.generators["mindmap_preprocess"].preprocess_mindmap([combined_content])
                        logger.debug(f"Estrutura pré-processada: {estrutura}")
                        # Carregar prompt do mindmap.txt
                        mindmap_prompt = self.generators["mindmap"]._load_prompt("mindmap")
                        # Montar prompt OPML
                        initial_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<opml version="2.0">\n<head>\n<title>{base_name}</title>\n<dateCreated>{datetime.now().isoformat()}</dateCreated>\n</head>\n<body>\n<outline text="{base_name}">\n'
                        prompt = (
                            f"{mindmap_prompt}\n\nEstrutura pré-processada:\n\n{base_name}:\n{estrutura}\n\nPor favor, gere o arquivo XML OPML 2.0 com base na estrutura fornecida. Responda apenas com o XML OPML 2.0!\n\nConsidere que o inicio do xml é o seguinte e continue EXATAMENTE após ele, sem enviar o mesmo inicio:\n\n{initial_xml}\n\nNÃO REPITA ESSE TRECHO NA SUA RESPOSTA!"
                        )
                        
                        # Mecanismo de reenvio até completar o OPML (replicando mapaMentalArquivo.py)
                        messages = [{"role": "user", "content": prompt}]
                        resposta = initial_xml
                        tentativa = 0
                        max_tentativas = 10  # Evitar loop infinito
                        
                        while tentativa < max_tentativas:
                            logger.debug(f"Rodada {tentativa + 1}")
                            logger.info(f"Gerando mapa mental - tentativa {tentativa + 1}")
                            
                            # Gerar conteúdo usando call_model_with_messages
                            nova_resposta = await self.generators["mindmap"].call_model_with_messages(messages)
                            
                            if nova_resposta is None:
                                logger.error(f"Erro na requisição na tentativa {tentativa + 1}")
                                tentativa += 1
                                continue
                            
                            resposta += nova_resposta
                            
                            # Verificar se o OPML está completo
                            if "</opml>" in resposta:
                                logger.info("OPML completo gerado com sucesso")
                                break
                            
                            # Preparar para próxima tentativa (replicando mapaMentalArquivo.py)
                            messages.append({"role": "assistant", "content": nova_resposta})
                            messages.append({"role": "user", "content": "Continue gerando o XML exatamente de onde parou."})
                            tentativa += 1
                        
                        if tentativa >= max_tentativas:
                            logger.warning(f"Limite de tentativas atingido para {media_path.name}. Salvando OPML parcial.")
                        
                        # Limpar caracteres especiais (replicando mapaMentalArquivo.py)
                        mindmap_result = resposta.replace("```xml", "").replace("```", "")
                        
                        mindmap_path.write_text(mindmap_result, encoding="utf-8")
                        logger.info(f"Mapa mental salvo em: {mindmap_path}")
                    else:
                        mindmap_result = ""
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
    
    def _find_video_files(self, directory_path: Path) -> List[Path]:
        """Encontra todos os arquivos de vídeo suportados em um diretório."""
        supported_extensions = {".mp4", ".avi", ".mkv", ".webm", ".mov", ".m4v"}
        files = [
            f for f in directory_path.iterdir()
            if f.is_file() and f.suffix.lower() in supported_extensions
        ]
        files.sort(key=lambda x: x.name)
        return files

    def _find_txt_files(self, directory_path: Path) -> List[Path]:
        """Encontra todos os arquivos .txt em um diretório, ordenados por nome."""
        files = [
            f for f in directory_path.iterdir()
            if f.is_file() and f.suffix.lower() == '.txt'
        ]
        files.sort(key=lambda x: x.name)
        return files

    def _find_md_files(self, directory_path: Path) -> List[Path]:
        """Encontra todos os arquivos .md em um diretório, ordenados por nome."""
        files = [
            f for f in directory_path.iterdir()
            if f.is_file() and f.suffix.lower() == '.md'
        ]
        files.sort(key=lambda x: x.name)
        return files

    async def process_directory(
        self,
        directory_path: Path,
        extract_audio: bool = True,
        transcribe: bool = True,
        diagram: bool = True,
        summarize: bool = True,
        mindmap: bool = False,
    ) -> List[Dict[str, Any]]:
        """Processa todos os arquivos relevantes em um diretório, de acordo com cada etapa do pipeline."""
        if not directory_path.exists():
            raise FileNotFoundError(f"Diretório não encontrado: {directory_path}")
        if not directory_path.is_dir():
            raise ValueError(f"O caminho não é um diretório: {directory_path}")
        results = []
        processed = set()
        # 1. Extração de áudio: vídeos
        if extract_audio:
            video_files = self._find_video_files(directory_path)
            logger.info(f"[Pipeline] Encontrados {len(video_files)} arquivos de vídeo para extração de áudio.")
            for video_file in video_files:
                if str(video_file) not in processed:
                    res = await self.process_single_file(
                        video_file,
                        extract_audio=True,
                        transcribe=False,
                        diagram=False,
                        summarize=False,
                        mindmap=False
                    )
                    results.append(res)
                    processed.add(str(video_file))
        # 2. Transcrição: áudios
        if transcribe:
            mp3_files = self._find_mp3_files(directory_path)
            logger.info(f"[Pipeline] Encontrados {len(mp3_files)} arquivos .mp3 para transcrição.")
            for mp3_file in mp3_files:
                if str(mp3_file) not in processed:
                    res = await self.process_single_file(
                        mp3_file,
                        extract_audio=False,
                        transcribe=True,
                        diagram=False,
                        summarize=False,
                        mindmap=False
                    )
                    results.append(res)
                    processed.add(str(mp3_file))
        # 3. Diagramação e 4. Resumo: .txt
        if diagram or summarize:
            txt_files = self._find_txt_files(directory_path)
            logger.info(f"[Pipeline] Encontrados {len(txt_files)} arquivos .txt para diagramação/resumo.")
            for txt_file in txt_files:
                if str(txt_file) not in processed:
                    res = await self.process_single_file(
                        txt_file,
                        extract_audio=False,
                        transcribe=False,
                        diagram=diagram,
                        summarize=summarize,
                        mindmap=False
                    )
                    results.append(res)
                    processed.add(str(txt_file))
        # 5. Mapa mental: .txt e .md
        if mindmap:
            mindmap_files = self._find_txt_files(directory_path) + self._find_md_files(directory_path)
            logger.info(f"[Pipeline] Encontrados {len(mindmap_files)} arquivos .txt/.md para mapa mental.")
            for mm_file in mindmap_files:
                if str(mm_file) not in processed:
                    res = await self.process_single_file(
                        mm_file,
                        extract_audio=False,
                        transcribe=False,
                        diagram=False,
                        summarize=False,
                        mindmap=True
                    )
                    results.append(res)
                    processed.add(str(mm_file))
        return results
    
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
            if self.transcriber is None:
                raise ValueError("Transcriber não foi inicializado")
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
    
    def _find_mp3_files(self, directory_path: Path) -> List[Path]:
        """Encontra todos os arquivos .mp3 em um diretório, ordenados por nome."""
        files = [
            f for f in directory_path.iterdir()
            if f.is_file() and f.suffix.lower() == '.mp3'
        ]
        files.sort(key=lambda x: x.name)
        return files

    def _find_text_and_md_files(self, directory_path: Path) -> List[Path]:
        """Encontra todos os arquivos .txt e .md em um diretório, ordenados por nome."""
        files = [
            f for f in directory_path.iterdir()
            if f.is_file() and f.suffix.lower() in {'.txt', '.md'}
        ]
        files.sort(key=lambda x: x.name)
        return files

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
            if self.transcriber is not None and hasattr(self.transcriber, 'model') and self.transcriber.model is not None:
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
    
    async def watch_directory(
        self,
        directory_path: Path,
        extract_audio: bool = True,
        transcribe: bool = True,
        diagram: bool = True,
        summarize: bool = True,
        mindmap: bool = False,
        delay: float = 10.0,
        max_cycles: Optional[int] = None,
    ) -> None:
        """Monitora continuamente um diretório e processa novos arquivos de mídia.

        Args:
            directory_path: Caminho para o diretório a ser monitorado.
            extract_audio: Se True, extrai o áudio do vídeo.
            transcribe: Se True, transcreve o áudio.
            diagram: Se True, gera diagramação do texto.
            summarize: Se True, gera resumo do texto.
            mindmap: Se True, gera mapa mental a partir do(s) texto(s).
            delay: Tempo (em segundos) entre cada varredura.
            max_cycles: Número máximo de ciclos de varredura (None para ilimitado).
        """
        if not directory_path.exists():
            raise FileNotFoundError(f"Diretório não encontrado: {directory_path}")
        if not directory_path.is_dir():
            raise ValueError(f"O caminho não é um diretório: {directory_path}")
        logger.info(f"Iniciando monitoramento contínuo da pasta: {directory_path}")
        processed_files = set()
        cycle = 0
        try:
            while max_cycles is None or cycle < max_cycles:
                cycle += 1
                logger.info(f"[Watcher] Ciclo {cycle} - Verificando novos arquivos...")
                media_files = self._find_media_files(directory_path)
                new_files = [f for f in media_files if str(f) not in processed_files]
                if new_files:
                    logger.info(f"[Watcher] {len(new_files)} novo(s) arquivo(s) encontrado(s) para processar.")
                    tasks = [
                        self.process_single_file(
                            media_file,
                            extract_audio=extract_audio,
                            transcribe=transcribe,
                            diagram=diagram,
                            summarize=summarize,
                            mindmap=mindmap
                        )
                        for media_file in new_files
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for i, result in enumerate(results):
                        processed_files.add(str(new_files[i]))
                        if isinstance(result, Exception):
                            logger.error(f"[Watcher] Erro ao processar {new_files[i].name}: {result}")
                        else:
                            logger.info(f"[Watcher] Processamento concluído: {new_files[i].name}")
                else:
                    logger.info("[Watcher] Nenhum novo arquivo encontrado.")
                logger.info(f"[Watcher] Aguardando {delay} segundos para próxima varredura...")
                await asyncio.sleep(delay)
            logger.info(f"[Watcher] Monitoramento encerrado após {cycle} ciclos.")
        except Exception as e:
            logger.error(f"[Watcher] Erro no monitoramento: {e}")
            raise

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

    async def process_mindmap_from_texts(
        self,
        directory_path: Path,
    ) -> List[Dict[str, Any]]:
        """Gera mapas mentais a partir de todos os arquivos .txt e .md do diretório.

        Args:
            directory_path: Caminho para o diretório.
        Returns:
            Lista de dicionários com informações dos mapas mentais gerados.
        """
        if not directory_path.exists():
            raise FileNotFoundError(f"Diretório não encontrado: {directory_path}")
        if not directory_path.is_dir():
            raise ValueError(f"O caminho não é um diretório: {directory_path}")
        logger.info(f"Buscando arquivos .txt e .md em: {directory_path}")
        text_files = self._find_text_and_md_files(directory_path)
        if not text_files:
            logger.warning(f"Nenhum arquivo .txt ou .md encontrado em: {directory_path}")
            return []
        results = []
        for file_path in text_files:
            logger.info(f"Lendo arquivo: {file_path.name}")
            mindmap_path = file_path.with_suffix('.opml')
            if mindmap_path.exists():
                logger.info(f"Mapa mental já existe para {file_path.name}, pulando geração: {mindmap_path}")
                mindmap = mindmap_path.read_text(encoding="utf-8")
            else:
                text = file_path.read_text(encoding="utf-8")
                logger.info(f"Gerando mapa mental para: {file_path.name}")
                mindmap = await self.generators["mindmap"].create_mindmap([text])
                mindmap_path.write_text(mindmap, encoding="utf-8")
                logger.info(f"Mapa mental salvo em: {mindmap_path}")
            results.append({
                "file": str(file_path),
                "mindmap_file": str(mindmap_path),
                "status": "success"
            })
        return results