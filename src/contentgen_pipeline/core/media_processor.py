from pathlib import Path
import subprocess
from typing import Tuple

from ..utils.logger import logger

class MediaProcessor:
    """Classe responsável por extrair o áudio de arquivos de vídeo."""

    @staticmethod
    def extract_audio(video_path: Path) -> Path:
        """Extrai o áudio de um arquivo de vídeo para um arquivo .mp3.

        Args:
            video_path: Caminho para o arquivo de vídeo.

        Returns:
            Caminho para o arquivo de áudio extraído (.mp3).
        """
        audio_file_path = video_path.with_suffix('.mp3')
        logger.info(f"Extraindo áudio de {video_path} para {audio_file_path}")
        if not audio_file_path.exists():
            try:
                command = [
                    'ffmpeg',
                    '-i', str(video_path),
                    '-vn',
                    '-acodec', 'libmp3lame',
                    '-b:a', '192k',
                    str(audio_file_path)
                ]
                subprocess.run(command, check=True, capture_output=True,encoding="utf-8")
                logger.info(f"Áudio extraído com sucesso: {audio_file_path}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Erro ao extrair áudio: {e.stderr.decode() if e.stderr else e}")
                raise RuntimeError(f"Falha ao extrair áudio de {video_path}") from e
        else:
            logger.warning(f"Arquivo de áudio já existe: {audio_file_path}")
        return audio_file_path 