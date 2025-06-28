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
from ..core.video_downloader import VideoDownloader
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

            # 1. Extração de áudio (só se não existir transcrição)
            if extract_audio:
                # Verificar se já existe transcrição (.txt ou .srt)
                if txt_path.exists() or srt_path.exists():
                    logger.info(f"Transcrição já existe para {media_path.name} (.txt ou .srt encontrado), pulando extração de áudio.")
                    audio_path = media_path.with_suffix('.mp3')
                else:
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

            # 3. Diagramação, 4. Resumo e 5. Mapa mental (executados em paralelo)
            if md_path.exists():
                logger.info(f"Resumo já existe para {media_path.name}, pulando diagramação e resumo.")
                summary = md_path.read_text(encoding="utf-8")
                content_files["summary"] = summary
                # Mesmo com resumo existente, ainda podemos fazer diagramação e mapa mental
                diagrammed_text = transcript_result["text"]
            else:
                diagrammed_text = transcript_result["text"]
                summary = None

            # Executar diagramação, resumo e mapa mental em paralelo
            tasks = []
            task_names = []
            
            # Tarefa de diagramação (só se não existir resumo)
            if diagram and not md_path.exists():
                tasks.append(self._generate_diagram(transcript_result["text"], txt_path))
                task_names.append("diagramação")
            elif diagram and md_path.exists():
                logger.info(f"Resumo já existe para {media_path.name}, pulando diagramação.")
            
            # Tarefa de resumo
            if summarize and not md_path.exists():
                tasks.append(self._generate_summary(transcript_result["text"], md_path))
                task_names.append("resumo")
            
            # Tarefa de mapa mental
            if mindmap:
                mindmap_path = md_path.with_suffix('.opml')
                if mindmap_path.exists():
                    logger.info(f"Mapa mental já existe para {media_path.name}, pulando geração: {mindmap_path}")
                    mindmap_result = mindmap_path.read_text(encoding="utf-8")
                    content_files["mindmap"] = mindmap_result
                else:
                    tasks.append(self._generate_mindmap(transcript_result["text"], mindmap_path, base_name))
                    task_names.append("mapa mental")
            
            # Executar tarefas em paralelo
            if tasks:
                logger.info(f"Executando em paralelo: {', '.join(task_names)}")
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Processar resultados
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Erro na {task_names[i]}: {str(result)}")
                    else:
                        if task_names[i] == "diagramação":
                            content_files["diagrammed"] = result
                        elif task_names[i] == "resumo":
                            content_files["summary"] = result
                        elif task_names[i] == "mapa mental":
                            content_files["mindmap"] = result
            else:
                logger.info("Nenhuma tarefa de conteúdo para executar.")

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
        """Encontra todos os arquivos de vídeo suportados em um diretório e subpastas."""
        supported_extensions = {".mp4", ".avi", ".mkv", ".webm", ".mov", ".m4v"}
        files = []
        for extension in supported_extensions:
            files.extend(directory_path.rglob(f"*{extension}"))
            files.extend(directory_path.rglob(f"*{extension.upper()}"))
        files.sort(key=lambda x: x.name)
        return files

    def _find_txt_files(self, directory_path: Path) -> List[Path]:
        """Encontra todos os arquivos .txt em um diretório e subpastas, ordenados por nome."""
        files = list(directory_path.rglob("*.txt"))
        files.extend(directory_path.rglob("*.TXT"))
        files.sort(key=lambda x: x.name)
        return files

    def _find_md_files(self, directory_path: Path) -> List[Path]:
        """Encontra todos os arquivos .md em um diretório e subpastas, ordenados por nome."""
        files = list(directory_path.rglob("*.md"))
        files.extend(directory_path.rglob("*.MD"))
        files.sort(key=lambda x: x.name)
        return files

    def _find_all_input_files(self, directory_path: Path) -> List[Tuple[Path, int]]:
        """Encontra todos os arquivos que podem ser processados, ordenados por prioridade.
        
        Prioridade (do mais processado para o menos):
        1 = .md (resumo já existe)
        2 = .txt (transcrição já existe) 
        3 = .mp3 (áudio já existe)
        4 = vídeos (.mp4, .avi, etc.)
        
        Args:
            directory_path: Caminho para o diretório.
            
        Returns:
            Lista de tuplas: (caminho_arquivo, prioridade) ordenada por prioridade.
        """
        input_files = []
        
        # 1. Arquivos .md (prioridade 1)
        md_files = self._find_md_files(directory_path)
        for file_path in md_files:
            input_files.append((file_path, 1))
        
        # 2. Arquivos .txt (prioridade 2)
        txt_files = self._find_txt_files(directory_path)
        for file_path in txt_files:
            input_files.append((file_path, 2))
        
        # 3. Arquivos .mp3 (prioridade 3)
        mp3_files = self._find_mp3_files(directory_path)
        for file_path in mp3_files:
            input_files.append((file_path, 3))
        
        # 4. Arquivos de vídeo (prioridade 4)
        video_files = self._find_video_files(directory_path)
        for file_path in video_files:
            input_files.append((file_path, 4))
        
        # Ordenar por prioridade (menor número = maior prioridade)
        input_files.sort(key=lambda x: x[1])
        
        return input_files

    async def process_directory(
        self,
        directory_path: Path,
        extract_audio: bool = True,
        transcribe: bool = True,
        diagram: bool = True,
        summarize: bool = True,
        mindmap: bool = False,
    ) -> List[Dict[str, Any]]:
        """Processa todos os arquivos de entrada em um diretório através do pipeline completo.
        
        Este método encontra todos os tipos de arquivos processáveis (vídeo, áudio, texto, resumo)
        e executa o pipeline sequencial completo para cada um, respeitando a ordem de prioridade.
        
        Args:
            directory_path: Caminho para o diretório contendo arquivos de entrada.
            extract_audio: Se True, extrai o áudio do vídeo.
            transcribe: Se True, transcreve o áudio.
            diagram: Se True, gera diagramação do texto.
            summarize: Se True, gera resumo do texto.
            mindmap: Se True, gera mapa mental a partir do(s) texto(s).
            
        Returns:
            Lista de dicionários com informações sobre os arquivos processados.
        """
        if not directory_path.exists():
            raise FileNotFoundError(f"Diretório não encontrado: {directory_path}")
        if not directory_path.is_dir():
            raise ValueError(f"O caminho não é um diretório: {directory_path}")
        
        # Encontrar todos os arquivos de entrada ordenados por prioridade
        input_files = self._find_all_input_files(directory_path)
        
        if not input_files:
            logger.warning(f"Nenhum arquivo de entrada encontrado em: {directory_path}")
            return []
        
        logger.info(f"Encontrados {len(input_files)} arquivos de entrada para processamento:")
        for file_path, priority in input_files:
            priority_name = {1: "resumo", 2: "transcrição", 3: "áudio", 4: "vídeo"}[priority]
            logger.info(f"  - {file_path.name} ({priority_name})")
        
        results = []
        for i, (file_path, priority) in enumerate(input_files, 1):
            priority_name = {1: "resumo", 2: "transcrição", 3: "áudio", 4: "vídeo"}[priority]
            logger.info(f"Processando arquivo {i}/{len(input_files)}: {file_path.name} ({priority_name})")
            try:
                result = await self.process_single_file(
                    file_path,
                    extract_audio=extract_audio,
                    transcribe=transcribe,
                    diagram=diagram,
                    summarize=summarize,
                    mindmap=mindmap
                )
                results.append(result)
                logger.info(f"✓ Concluído: {file_path.name}")
            except Exception as e:
                logger.error(f"✗ Erro ao processar {file_path.name}: {str(e)}")
                results.append({
                    "media_path": str(file_path),
                    "error": str(e),
                    "status": "error"
                })
        
        logger.info(f"Processamento do diretório concluído. {len(results)} arquivos processados.")
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
        """Encontra todos os arquivos .mp3 em um diretório e subpastas, ordenados por nome."""
        files = list(directory_path.rglob("*.mp3"))
        files.extend(directory_path.rglob("*.MP3"))
        files.sort(key=lambda x: x.name)
        return files

    def _find_text_and_md_files(self, directory_path: Path) -> List[Path]:
        """Encontra todos os arquivos .txt e .md em um diretório e subpastas, ordenados por nome."""
        files = []
        # Buscar arquivos .txt
        files.extend(directory_path.rglob("*.txt"))
        files.extend(directory_path.rglob("*.TXT"))
        # Buscar arquivos .md
        files.extend(directory_path.rglob("*.md"))
        files.extend(directory_path.rglob("*.MD"))
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
            "content_generator": "unknown",
            "video_downloader": "unknown"
        }
        
        try:
            # Verificar gerador de conteúdo
            if self.content_generator and await self.content_generator.health_check():
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
        
        # Verificar video downloader
        try:
            video_downloader = VideoDownloader()
            downloader_health = video_downloader.health_check()
            health_status["video_downloader"] = downloader_health["status"]
        except Exception as e:
            health_status["video_downloader"] = f"error: {str(e)}"
        
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
        """Encontra todos os arquivos de mídia suportados em um diretório e subpastas.
        
        Args:
            directory_path: Caminho para o diretório.
            
        Returns:
            Lista de caminhos para arquivos de mídia.
        """
        supported_extensions = {".mp4", ".avi", ".mkv", ".webm", ".mov", ".m4v"}
        media_files = []
        
        for extension in supported_extensions:
            media_files.extend(directory_path.rglob(f"*{extension}"))
            media_files.extend(directory_path.rglob(f"*{extension.upper()}"))
        
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

    async def _generate_diagram(self, text: str, txt_path: Path) -> str:
        """Gera diagramação do texto transcrito.
        
        Args:
            text: Texto transcrito para diagramar.
            txt_path: Caminho do arquivo .txt para salvar.
            
        Returns:
            Texto diagramado.
        """
        logger.info("Gerando diagramação...")
        diagrammed_text = await self.generators["diagram"].diagram(text)
        tamanho_original = len(text.encode("utf-8"))
        tamanho_diagramado = len(diagrammed_text.encode("utf-8"))
        if tamanho_diagramado > tamanho_original:
            txt_path.write_text(diagrammed_text, encoding="utf-8")
            logger.info(f"Arquivo diagramado sobrescrito: {txt_path}")
        else:
            logger.info("Conteúdo diagramado não é maior que o original. Não sobrescrevendo o .txt.")
        return diagrammed_text

    async def _generate_summary(self, text: str, md_path: Path) -> str:
        """Gera resumo do texto transcrito.
        
        Args:
            text: Texto transcrito para resumir.
            md_path: Caminho do arquivo .md para salvar.
            
        Returns:
            Resumo em formato markdown.
        """
        logger.info("Gerando resumo...")
        summary = await self.generators["summarize"].summarize(text)
        md_path.write_text(summary, encoding="utf-8")
        logger.info(f"Resumo salvo em: {md_path}")
        return summary

    async def _generate_mindmap(self, text: str, mindmap_path: Path, base_name: str) -> str:
        """Gera mapa mental a partir do texto transcrito.
        
        Args:
            text: Texto transcrito para gerar mapa mental.
            mindmap_path: Caminho do arquivo .opml para salvar.
            base_name: Nome base do arquivo.
            
        Returns:
            Conteúdo do mapa mental em formato OPML.
        """
        logger.info("Gerando mapa mental...")
        
        # Pré-processamento da estrutura
        estrutura = await self.generators["mindmap_preprocess"].preprocess_mindmap([text])
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
            logger.warning(f"Limite de tentativas atingido. Salvando OPML parcial.")
        
        # Limpar caracteres especiais (replicando mapaMentalArquivo.py)
        mindmap_result = resposta.replace("```xml", "").replace("```", "")
        
        mindmap_path.write_text(mindmap_result, encoding="utf-8")
        logger.info(f"Mapa mental salvo em: {mindmap_path}")
        return mindmap_result

    async def download_videos_from_csv(
        self,
        csv_path: Path,
        output_dir: Optional[Path] = None,
        batch_size: int = 50,
        interactive: bool = True,
        overwrite: bool = False,
        verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """Baixa vídeos do YouTube a partir de um arquivo CSV.
        
        Args:
            csv_path: Caminho para o arquivo CSV com URLs.
            output_dir: Diretório de saída para os vídeos.
            batch_size: Número de vídeos por lote.
            interactive: Se True, pergunta ao usuário para continuar entre lotes.
            overwrite: Se True, sobrescreve arquivos existentes.
            verbose: Se True, exibe logs detalhados.
            
        Returns:
            Lista de dicionários com resultados dos downloads.
        """
        # Criar downloader
        downloader = VideoDownloader(output_dir=output_dir)
        
        # Verificar saúde do yt-dlp
        health_status = downloader.health_check()
        if health_status["status"] != "healthy":
            raise RuntimeError(f"yt-dlp não está disponível: {health_status.get('error', 'Erro desconhecido')}")
        
        logger.info(f"yt-dlp disponível: versão {health_status.get('version', 'desconhecida')}")
        logger.info(f"Diretório de saída: {downloader.output_dir}")
        
        # Executar download
        return await downloader.download_from_csv(
            csv_path=csv_path,
            batch_size=batch_size,
            interactive=interactive,
            overwrite=overwrite,
            verbose=verbose
        )
    
    async def download_single_video(
        self,
        url: str,
        output_dir: Optional[Path] = None,
        overwrite: bool = False,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """Baixa um único vídeo do YouTube.
        
        Args:
            url: URL do vídeo do YouTube.
            output_dir: Diretório de saída para o vídeo.
            overwrite: Se True, sobrescreve arquivo existente.
            verbose: Se True, exibe logs detalhados.
            
        Returns:
            Dicionário com resultado do download.
        """
        # Criar downloader
        downloader = VideoDownloader(output_dir=output_dir)
        
        # Verificar saúde do yt-dlp
        health_status = downloader.health_check()
        if health_status["status"] != "healthy":
            raise RuntimeError(f"yt-dlp não está disponível: {health_status.get('error', 'Erro desconhecido')}")
        
        logger.info(f"yt-dlp disponível: versão {health_status.get('version', 'desconhecida')}")
        logger.info(f"Diretório de saída: {downloader.output_dir}")
        
        # Executar download
        return await downloader.download_single_url(
            url=url,
            overwrite=overwrite,
            verbose=verbose
        )

    async def create_example_csv(self, csv_path: Path) -> None:
        """Cria um arquivo CSV de exemplo com URLs do YouTube.
        
        Args:
            csv_path: Caminho para o arquivo CSV a ser criado.
        """
        import pandas as pd
        
        example_data = {
            'url': [
                'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                'https://www.youtube.com/watch?v=example2',
                'https://www.youtube.com/watch?v=example3'
            ]
        }
        
        df = pd.DataFrame(example_data)
        df.to_csv(csv_path, index=False)
        logger.info(f"Arquivo CSV de exemplo criado: {csv_path}")