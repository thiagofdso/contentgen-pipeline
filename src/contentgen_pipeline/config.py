"""Módulo de configuração para o ContentGen Pipeline."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações da aplicação carregadas do arquivo .env."""

    # Configurações do Adapta.one
    adapta_cookies_str: str = Field(..., description="Cookies de autenticação do Adapta.one")

    # Configurações do Whisper
    whisper_model: str = Field(default="medium", description="Modelo do Whisper a ser usado")

    # Configurações do CUDA/cuDNN
    cudnn_path: Optional[str] = Field(default=None, description="Caminho para o cuDNN (ex: C:\\Program Files\\NVIDIA\\CUDNN\\v9.10\\)")

    # Configurações de diretórios
    video_folder: Optional[str] = Field(default=None, description="Diretório padrão de vídeos (usado quando não especificado na CLI)")

    # Geradores específicos (lidos de variáveis de ambiente em caixa alta)
    summarize_generator: Optional[str] = Field(default=None, description="Gerador para resumo (ex: SUMMARIZE_GENERATOR=claude)")
    diagram_generator: Optional[str] = Field(default=None, description="Gerador para diagramação (ex: DIAGRAM_GENERATOR=gpt)")
    mindmap_preprocess_generator: Optional[str] = Field(default=None, description="Gerador para pré-processamento de mapa mental (ex: MINDMAP_PREPROCESS_GENERATOR=gemini)")
    mindmap_generator: Optional[str] = Field(default=None, description="Gerador para mapa mental (ex: MINDMAP_GENERATOR=claude)")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Instância global das configurações
settings = Settings() 