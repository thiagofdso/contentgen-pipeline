#!/usr/bin/env python3
"""Script de teste para validar o MediaProcessor."""

import sys
from pathlib import Path

# Adiciona o diretório src ao path para importar os módulos
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from contentgen_pipeline.core.media_processor import MediaProcessor
    from contentgen_pipeline.utils.logger import logger
    
    def main():
        """Testa a extração de áudio do MediaProcessor."""
        print("=== Teste do MediaProcessor ===\n")
        
        # Caminho para o arquivo de teste
        video_path = Path("videoteste.webm")
        
        if not video_path.exists():
            print(f"❌ Arquivo de teste não encontrado: {video_path}")
            return
        
        print(f"1. Testando extração de áudio de: {video_path}")
        print(f"   - Tamanho do arquivo: {video_path.stat().st_size / (1024*1024):.2f} MB")
        
        try:
            # Testa a extração de áudio
            audio_path = MediaProcessor.extract_audio(video_path)
            
            if audio_path.exists():
                print(f"   - ✓ Áudio extraído com sucesso: {audio_path}")
                print(f"   - Tamanho do áudio: {audio_path.stat().st_size / (1024*1024):.2f} MB")
                
                # Remove o arquivo de áudio após o teste
                audio_path.unlink()
                print(f"   - ✓ Arquivo de áudio removido após o teste")
                
                print("\n✓ Teste do MediaProcessor concluído com sucesso!")
            else:
                print(f"   - ❌ Falha: arquivo de áudio não foi criado")
                
        except Exception as e:
            print(f"   - ❌ Erro durante a extração: {e}")
            logger.error(f"Erro no teste: {e}")
        
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