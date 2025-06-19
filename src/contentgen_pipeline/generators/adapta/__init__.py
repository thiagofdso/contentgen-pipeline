"""Sub-pacote adapta - Implementações específicas para a API Adapta.one.

Este módulo contém as implementações dos geradores de conteúdo que utilizam
a API Adapta.one, incluindo suporte para diferentes modelos de IA (GPT, Gemini, Claude).
"""

from .client import AdaptaClient
from .gemini_generator import GeminiGenerator
from .claude_generator import ClaudeGenerator
from .gpt_generator import GPTGenerator

__all__ = [
    "AdaptaClient",
    "GeminiGenerator", 
    "ClaudeGenerator",
    "GPTGenerator"
] 