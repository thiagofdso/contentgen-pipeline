"""Configuração do sistema de logging para o ContentGen Pipeline."""

import sys
from pathlib import Path

from loguru import logger


def setup_logger(console_level: str = "INFO"):
    """Configura o logger centralizado da aplicação.
    Args:
        console_level: Nível de log do console (ex: 'DEBUG', 'INFO', 'WARNING', 'ERROR')
    """
    # Remove o logger padrão
    logger.remove()
    
    # Adiciona logger para console com formatação colorida
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=console_level.upper(),
        colorize=True,
    )
    
    # Adiciona logger para arquivo
    log_file = Path("logs") / "contentgen-pipeline.log"
    log_file.parent.mkdir(exist_ok=True)
    
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
    )


# Configura o logger na importação do módulo (padrão INFO)
setup_logger()

# Exporta o logger configurado
__all__ = ["logger", "setup_logger"] 