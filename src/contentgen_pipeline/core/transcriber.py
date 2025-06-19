"""Módulo de transcrição de áudio usando Whisper."""

import os
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from faster_whisper import WhisperModel
from numba import cuda
from tqdm import tqdm

from ..config import settings
from ..utils.logger import logger
from ..utils.sentence_splitter import split_sentences


def get_cuda_toolkit_path() -> Optional[str]:
    """Tenta localizar o toolkit CUDA instalado via Anaconda ou variável de ambiente."""
    # Primeiro, verifica se existe a variável de ambiente CUDA_PATH
    cuda_path = os.environ.get('CUDA_PATH')
    if cuda_path and os.path.exists(cuda_path):
        cuda_bin_path = os.path.join(cuda_path, 'bin')
        if os.path.exists(cuda_bin_path):
            return cuda_bin_path
    
    # Fallback: procura no Anaconda
    home_dir = os.path.expanduser('~')
    if os.name == "nt":
        anaconda_base_path = os.path.join(home_dir, "anaconda3", "pkgs")
        cuda_glob_pattern = os.path.join(anaconda_base_path, "cudatoolkit-*", "Library", "bin")
        import glob
        cuda_paths = glob.glob(cuda_glob_pattern)
        if cuda_paths:
            return cuda_paths[0]
    return None

def add_to_system_path(new_path: str) -> None:
    if new_path and new_path not in os.environ["PATH"].split(os.pathsep):
        os.environ["PATH"] = new_path + os.pathsep + os.environ["PATH"]

def get_cudnn_path() -> Optional[str]:
    """Obtém o caminho do cuDNN das configurações."""
    if settings.cudnn_path and os.path.exists(settings.cudnn_path):
        # Verifica se existe o caminho bin/12.9/ especificamente
        cudnn_bin_path = os.path.join(settings.cudnn_path, 'bin', '12.9')
        if os.path.exists(cudnn_bin_path):
            return cudnn_bin_path
        
        # Fallback para o caminho bin/ padrão
        cudnn_bin_path = os.path.join(settings.cudnn_path, 'bin')
        if os.path.exists(cudnn_bin_path):
            return cudnn_bin_path
    return None

def setup_cuda_environment() -> None:
    """Configura o ambiente CUDA adicionando os caminhos necessários ao PATH."""
    # Adiciona CUDA Toolkit
    cuda_toolkit_path = get_cuda_toolkit_path()
    if cuda_toolkit_path:
        add_to_system_path(cuda_toolkit_path)
        logger.info(f"CUDA Toolkit path adicionado ao PATH: {cuda_toolkit_path}")

    # Adiciona cuDNN
    cudnn_path = get_cudnn_path()
    if cudnn_path:
        add_to_system_path(cudnn_path)
        logger.info(f"cuDNN path adicionado ao PATH: {cudnn_path}")
        
        # Verifica se a DLL específica existe
        dll_path = os.path.join(cudnn_path, 'cudnn64_9.dll')
        if os.path.exists(dll_path):
            logger.info(f"cuDNN DLL encontrada: {dll_path}")
        else:
            logger.warning(f"cuDNN DLL não encontrada em: {dll_path}")
    else:
        logger.warning("Caminho do cuDNN não configurado ou não encontrado")

class Transcriber:
    """Classe responsável pela transcrição de áudio usando Whisper."""

    def __init__(self, force_cpu: bool = False):
        """Inicializa o Transcriber com o modelo Whisper configurado.

        Args:
            force_cpu: Se True, força o uso de CPU mesmo se CUDA estiver disponível.
        """
        self.model = None
        self.force_cpu = force_cpu
        self._load_model()

    def _load_model(self) -> None:
        """Carrega o modelo Whisper com base nas configurações e disponibilidade de CUDA."""
        model_name = settings.whisper_model
        logger.info(f"Carregando modelo Whisper: {model_name}")

        # Permite override para CPU
        if self.force_cpu:
            device = "cpu"
            compute_type = "auto"
            logger.info("Override: Forçando uso de CPU para transcrição.")
        elif cuda.is_available():
            device = "cuda"
            compute_type = "float16"
            logger.info("CUDA disponível. Usando GPU para transcrição.")
        else:
            device = "cpu"
            compute_type = "auto"
            logger.info("CUDA não disponível. Usando CPU para transcrição.")

        try:
            self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
            logger.info(f"Modelo Whisper carregado com sucesso: {model_name}")
        except Exception as e:
            logger.error(f"Erro ao carregar modelo Whisper: {e}")
            raise RuntimeError(f"Falha ao carregar modelo Whisper: {e}") from e

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Obtém a duração do áudio usando ffprobe."""
        try:
            command = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(audio_path)
            ]

            result = subprocess.run(command, capture_output=True, text=True, check=True,encoding="utf-8")
            metadata = json.loads(result.stdout)

            if 'format' in metadata and 'duration' in metadata['format']:
                return float(metadata['format']['duration'])
            if 'streams' in metadata:
                for stream in metadata['streams']:
                    if stream.get('codec_type') == 'audio' and 'duration' in stream:
                        return float(stream['duration'])
            logger.warning(f"Não foi possível obter a duração do áudio: {audio_path}")
            return 0.0
        except subprocess.CalledProcessError as e:
            logger.error(f"Erro ao obter duração do áudio: {e}")
            return 0.0

    def transcribe(self, audio_path: Path) -> Tuple[str, List[Dict]]:
        """Transcreve um arquivo de áudio usando Whisper.

        Args:
            audio_path: Caminho para o arquivo de áudio.

        Returns:
            Tupla contendo (texto_transcrito, lista_de_segmentos_com_metadados).
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Arquivo de áudio não encontrado: {audio_path}")

        # Configura o ambiente CUDA antes da transcrição
        setup_cuda_environment()

        logger.info(f"Iniciando transcrição de: {audio_path}")
        audio_duration = self._get_audio_duration(audio_path)
        logger.debug(f"Duração de áudio: {audio_duration}")
        combined_sentences = []
        segments_metadata = []

        try:
            with tqdm(total=audio_duration, desc=f"Transcrevendo {audio_path.name}", unit="s") as pbar:
                segments, info = self.model.transcribe(
                    str(audio_path),
                    beam_size=10,
                    vad_filter=True,
                    language="pt"
                )
                for segment in segments:
                    pbar.update(segment.end - segment.start)
                    # Extrai sentenças do texto do segmento
                    sentences = split_sentences(segment.text)
                    combined_sentences.extend(sentences)
                    metadata = {
                        "start": round(segment.start, 2),
                        "end": round(segment.end, 2),
                        "text": segment.text,
                        "avg_logprob": round(segment.avg_logprob, 2)
                    }
                    segments_metadata.append(metadata)
            logger.info(f"Transcrição concluída: {len(segments_metadata)} segmentos processados")
            combined_text = " ".join(combined_sentences)
            return combined_text.strip(), segments_metadata
        except Exception as e:
            logger.error(f"Erro durante a transcrição: {e}")
            raise RuntimeError(f"Falha na transcrição de {audio_path}: {e}") from e

    def save_transcript(self, audio_path: Path, transcript_text: str, segments: List[Dict]) -> None:
        base_path = audio_path.with_suffix('')
        txt_path = base_path.with_suffix('.txt')
        try:
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(transcript_text)
            logger.info(f"Transcrição salva em: {txt_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar transcrição: {e}")
            raise
        srt_path = base_path.with_suffix('.srt')
        try:
            self._save_srt_file(srt_path, segments)
            logger.info(f"Legendas salvas em: {srt_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar legendas: {e}")
            raise

    def _save_srt_file(self, srt_path: Path, segments: List[Dict]) -> None:
        srt_content = ""
        for i, segment in enumerate(segments, 1):
            start_time = self._format_timestamp(segment['start'])
            end_time = self._format_timestamp(segment['end'])
            srt_content += f"{i}\n{start_time} --> {end_time}\n{segment['text']}\n\n"
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)

    def _format_timestamp(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}" 