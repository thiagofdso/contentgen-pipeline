"""Modulo de configuracao para o ContentGen Pipeline."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracoes da aplicacao carregadas do arquivo .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Configuracoes do Adapta.one
    adapta_cookies_str: str = Field(..., description="Cookies de autenticacao do Adapta.one")

    # Configuracoes do Whisper
    whisper_model: str = Field(default="medium", description="Modelo do Whisper a ser usado")

    # Configuracoes do CUDA/cuDNN
    cudnn_path: Optional[str] = Field(
        default=None,
        description="Caminho para o cuDNN (ex: C:\\Program Files\\NVIDIA\\CUDNN\\v9.10\\)",
    )

    # Configuracoes de diretorios
    video_folder: Optional[str] = Field(
        default=None,
        description="Diretorio padrao de videos (usado quando nao especificado na CLI)",
    )

    # Geradores especificos (lidos de variaveis de ambiente em caixa alta)
    summarize_generator: Optional[str] = Field(
        default=None,
        description="Gerador para resumo (ex: SUMMARIZE_GENERATOR=claude)",
    )
    diagram_generator: Optional[str] = Field(
        default=None,
        description="Gerador para diagramacao (ex: DIAGRAM_GENERATOR=gpt)",
    )
    mindmap_preprocess_generator: Optional[str] = Field(
        default=None,
        description="Gerador para pre-processamento de mapa mental (ex: MINDMAP_PREPROCESS_GENERATOR=gemini)",
    )
    mindmap_generator: Optional[str] = Field(
        default=None,
        description="Gerador para mapa mental (ex: MINDMAP_GENERATOR=claude)",
    )


# Instancia global das configuracoes
settings = Settings()
