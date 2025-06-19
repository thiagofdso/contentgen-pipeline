#!/usr/bin/env python3
"""Script de teste para validar o Transcriber."""

import sys
from pathlib import Path

# Adiciona o diretório src ao path para importar os módulos
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from contentgen_pipeline.core.media_processor import MediaProcessor
    from contentgen_pipeline.core.transcriber import Transcriber
    from contentgen_pipeline.utils.logger import logger
    
    def main():
        """Testa a transcrição de áudio usando o Transcriber."""
        print("=== Teste do Transcriber ===\n")
        
        # Caminho para o arquivo de teste
        video_path = Path("videoteste.webm")
        
        if not video_path.exists():
            print(f"❌ Arquivo de teste não encontrado: {video_path}")
            return
        
        try:
            # 1. Extrai o áudio usando MediaProcessor
            print("1. Extraindo áudio do vídeo...")
            media_processor = MediaProcessor()
            audio_path = media_processor.extract_audio(video_path)
            print(f"   - ✓ Áudio extraído: {audio_path}")
            
            # 2. Transcreve o áudio usando Transcriber
            print("\n2. Transcrevendo áudio...")
            transcriber = Transcriber()
            transcript_text, segments = transcriber.transcribe(audio_path)
            
            print(f"   - ✓ Transcrição concluída")
            print(f"   - Segmentos processados: {len(segments)}")
            print(f"   - Tamanho do texto: {len(transcript_text)} caracteres")
            
            # 3. Salva os arquivos de transcrição
            print("\n3. Salvando arquivos de transcrição...")
            transcriber.save_transcript(audio_path, transcript_text, segments)
            
            # Verifica se os arquivos foram criados
            txt_path = audio_path.with_suffix('.txt')
            srt_path = audio_path.with_suffix('.srt')
            
            if txt_path.exists():
                print(f"   - ✓ Arquivo de transcrição criado: {txt_path}")
            if srt_path.exists():
                print(f"   - ✓ Arquivo de legendas criado: {srt_path}")
            
            # 4. Mostra uma amostra da transcrição
            print(f"\n4. Amostra da transcrição (primeiros 200 caracteres):")
            print(f"   {transcript_text[:200]}...")
            
            # 5. Limpeza - remove arquivos temporários
            print("\n5. Limpeza dos arquivos temporários...")
            audio_path.unlink()
            txt_path.unlink()
            srt_path.unlink()
            print("   - ✓ Arquivos temporários removidos")
            
            print("\n✓ Teste do Transcriber concluído com sucesso!")
            
        except Exception as e:
            print(f"   - ❌ Erro durante o teste: {e}")
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