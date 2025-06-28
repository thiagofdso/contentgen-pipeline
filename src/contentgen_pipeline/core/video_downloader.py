"""Módulo para download de vídeos do YouTube.

Este módulo implementa funcionalidades para baixar vídeos do YouTube
usando yt-dlp, com suporte a arquivos CSV e processamento em lotes.
"""

import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

from ..utils.logger import logger
from ..config import settings


class VideoDownloader:
    """Classe responsável por baixar vídeos do YouTube usando yt-dlp."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """Inicializa o downloader de vídeos.
        
        Args:
            output_dir: Diretório de saída para os vídeos (padrão: VIDEO_FOLDER do .env).
        """
        self.output_dir = output_dir or Path(settings.video_folder) if settings.video_folder else Path.cwd()
        self._ensure_output_dir()
        logger.info(f"VideoDownloader inicializado com diretório de saída: {self.output_dir}")
    
    def _ensure_output_dir(self) -> None:
        """Garante que o diretório de saída existe."""
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Diretório de saída criado: {self.output_dir}")
    
    async def download_from_csv(
        self,
        csv_path: Path,
        batch_size: int = 50,
        interactive: bool = True,
        overwrite: bool = False,
        verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """Baixa vídeos listados em um arquivo CSV.
        
        Args:
            csv_path: Caminho para o arquivo CSV com URLs.
            batch_size: Número de vídeos por lote.
            interactive: Se True, pergunta ao usuário para continuar entre lotes.
            overwrite: Se True, sobrescreve arquivos existentes.
            verbose: Se True, exibe logs detalhados.
            
        Returns:
            Lista de dicionários com resultados dos downloads.
        """
        if not csv_path.exists():
            raise FileNotFoundError(f"Arquivo CSV não encontrado: {csv_path}")
        
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            raise ValueError(f"Erro ao ler arquivo CSV '{csv_path}': {e}")
        
        if 'url' not in df.columns:
            raise ValueError(f"Coluna 'url' não encontrada no arquivo CSV '{csv_path}'")
        
        logger.info(f"Iniciando downloads do arquivo '{csv_path}'")
        logger.info(f"Total de URLs: {len(df)}")
        logger.info(f"Tamanho do lote: {batch_size}")
        
        results = []
        download_count_in_batch = 0
        total_processed = 0
        
        for index, row in df.iterrows():
            video_url = row['url']
            total_processed += 1
            
            # Validar URL
            if pd.isna(video_url) or not str(video_url).strip().startswith('http'):
                logger.warning(f"Linha {index + 2}: URL inválida ou vazia ('{video_url}'). Pulando.")
                results.append({
                    "url": video_url,
                    "status": "skipped",
                    "error": "URL inválida ou vazia",
                    "index": index
                })
                continue
            
            download_count_in_batch += 1
            logger.info(f"Processando URL {total_processed}/{len(df)}: {video_url}")
            
            try:
                result = await self._download_single_video(
                    video_url, 
                    overwrite=overwrite, 
                    verbose=verbose
                )
                result["index"] = index
                results.append(result)
                
                if result["status"] == "success":
                    logger.info(f"✓ Sucesso: {video_url}")
                else:
                    logger.warning(f"⚠ Falha: {video_url} - {result.get('error', 'Erro desconhecido')}")
                    
            except Exception as e:
                logger.error(f"✗ Erro inesperado ao processar {video_url}: {e}")
                results.append({
                    "url": video_url,
                    "status": "error",
                    "error": str(e),
                    "index": index
                })
            
            # Verificar se o lote está completo
            if download_count_in_batch >= batch_size and index < len(df) - 1:
                if interactive:
                    if not await self._ask_continue(download_count_in_batch, total_processed):
                        logger.info("Download interrompido pelo usuário.")
                        break
                download_count_in_batch = 0
        
        logger.info(f"Processo de download concluído. {total_processed} URLs processadas.")
        return results
    
    async def download_single_url(
        self, 
        url: str, 
        overwrite: bool = False, 
        verbose: bool = False
    ) -> Dict[str, Any]:
        """Baixa um único vídeo do YouTube.
        
        Args:
            url: URL do vídeo do YouTube.
            overwrite: Se True, sobrescreve arquivo existente.
            verbose: Se True, exibe logs detalhados.
            
        Returns:
            Dicionário com resultado do download.
        """
        logger.info(f"Baixando vídeo: {url}")
        return await self._download_single_video(url, overwrite, verbose)
    
    async def download_multiple_urls(
        self, 
        urls: List[str], 
        overwrite: bool = False, 
        verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """Baixa múltiplos vídeos do YouTube.
        
        Args:
            urls: Lista de URLs dos vídeos.
            overwrite: Se True, sobrescreve arquivos existentes.
            verbose: Se True, exibe logs detalhados.
            
        Returns:
            Lista de dicionários com resultados dos downloads.
        """
        logger.info(f"Iniciando download de {len(urls)} vídeos")
        
        tasks = [
            self._download_single_video(url, overwrite, verbose)
            for url in urls
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Processar resultados
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "url": urls[i],
                    "status": "error",
                    "error": str(result)
                })
            else:
                processed_results.append(result)
        
        logger.info(f"Download de {len(urls)} vídeos concluído")
        return processed_results
    
    async def _download_single_video(
        self, 
        url: str, 
        overwrite: bool = False, 
        verbose: bool = False
    ) -> Dict[str, Any]:
        """Baixa um único vídeo usando yt-dlp.
        
        Args:
            url: URL do vídeo.
            overwrite: Se True, sobrescreve arquivo existente.
            verbose: Se True, exibe logs detalhados.
            
        Returns:
            Dicionário com resultado do download.
        """
        command = [
            'yt-dlp',
            '--ignore-errors',
            '--no-playlist',
        ]
        
        if not overwrite:
            command.append('--no-overwrites')
        
        if verbose:
            command.append('--verbose')
        
        # Adicionar diretório de saída
        command.extend(['-o', str(self.output_dir / '%(title)s.%(ext)s')])
        
        # Adicionar URL
        command.append(url)
        
        try:
            logger.debug(f"Executando comando: {' '.join(command)}")
            
            # Executar comando de forma assíncrona
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return {
                    "url": url,
                    "status": "success",
                    "output": stdout.decode('utf-8') if stdout else "",
                    "file_path": self._extract_file_path(stdout.decode('utf-8') if stdout else "")
                }
            else:
                error_msg = stderr.decode('utf-8') if stderr else "Erro desconhecido"
                return {
                    "url": url,
                    "status": "error",
                    "error": error_msg,
                    "return_code": process.returncode
                }
                
        except Exception as e:
            return {
                "url": url,
                "status": "error",
                "error": str(e)
            }
    
    def _extract_file_path(self, output: str) -> Optional[str]:
        """Extrai o caminho do arquivo baixado da saída do yt-dlp.
        
        Args:
            output: Saída do comando yt-dlp.
            
        Returns:
            Caminho do arquivo baixado ou None se não encontrado.
        """
        # Implementação básica - pode ser melhorada para extrair o caminho real
        lines = output.split('\n')
        for line in lines:
            if '[download] Destination:' in line:
                return line.split('[download] Destination:')[1].strip()
        return None
    
    async def _ask_continue(self, batch_count: int, total_processed: int) -> bool:
        """Pergunta ao usuário se deseja continuar para o próximo lote.
        
        Args:
            batch_count: Número de vídeos no lote atual.
            total_processed: Total de vídeos processados.
            
        Returns:
            True se deve continuar, False caso contrário.
        """
        # Em ambiente CLI, usar input síncrono
        loop = asyncio.get_event_loop()
        
        while True:
            response = await loop.run_in_executor(
                None, 
                input,
                f"\nLote de {batch_count} vídeos processados (Total: {total_processed}). "
                f"Deseja continuar para o próximo lote? (s/n): "
            )
            
            response = response.lower().strip()
            if response in ['s', 'sim', 'y', 'yes']:
                return True
            elif response in ['n', 'não', 'nao', 'no']:
                return False
            else:
                print("Resposta inválida. Digite 's' para sim ou 'n' para não.")
    
    def health_check(self) -> Dict[str, str]:
        """Verifica se o yt-dlp está disponível no sistema.
        
        Returns:
            Dicionário com status de saúde do downloader.
        """
        try:
            result = subprocess.run(
                ['yt-dlp', '--version'],
                capture_output=True,
                text=True,
                check=True
            )
            version = result.stdout.strip()
            logger.info(f"yt-dlp disponível: versão {version}")
            return {
                "status": "healthy",
                "version": version,
                "output_dir": str(self.output_dir)
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"yt-dlp não está funcionando: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
        except FileNotFoundError:
            logger.error("yt-dlp não encontrado no sistema")
            return {
                "status": "unhealthy",
                "error": "yt-dlp não encontrado no PATH"
            } 