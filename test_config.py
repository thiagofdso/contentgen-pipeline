#!/usr/bin/env python3
"""Script de teste para validar a configuração inicial do ContentGen Pipeline."""

import sys
from pathlib import Path

# Adiciona o diretório src ao path para importar os módulos
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from contentgen_pipeline.config import settings
    from contentgen_pipeline.utils.logger import logger
    
    def main():
        """Testa o carregamento das configurações e o sistema de logging."""
        print("=== Teste de Configuração do ContentGen Pipeline ===\n")
        
        # Testa o carregamento das configurações
        print("1. Testando carregamento das configurações:")
        print(f"   - WHISPER_MODEL: {settings.whisper_model}")
        print(f"   - ADAPTA_COOKIES_STR: {'✓ Configurado' if settings.adapta_cookies_str else '✗ Não configurado'}")
        print()
        
        # Testa o sistema de logging
        print("2. Testando sistema de logging:")
        logger.info("Mensagem de informação de teste")
        logger.warning("Mensagem de aviso de teste")
        logger.debug("Mensagem de debug de teste")
        print()
        
        print("✓ Configuração inicial validada com sucesso!")
        
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {e}")
    print("Certifique-se de que todas as dependências estão instaladas:")
    print("  poetry install")
    sys.exit(1)
except Exception as e:
    print(f"❌ Erro durante o teste: {e}")
    sys.exit(1) 