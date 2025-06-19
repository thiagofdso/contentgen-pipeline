"""Módulo generators - Implementações de provedores de IA para geração de conteúdo."""

from .base import BaseContentGenerator

# Importa geradores do sub-pacote adapta
try:
    from .adapta import (
        AdaptaClient,
        GeminiGenerator,
        ClaudeGenerator,
        GPTGenerator
    )
    __all__ = [
        "BaseContentGenerator",
        "AdaptaClient",
        "GeminiGenerator",
        "ClaudeGenerator", 
        "GPTGenerator"
    ]
except ImportError:
    # Se o sub-pacote adapta não estiver disponível, exporta apenas a base
    __all__ = ["BaseContentGenerator"] 