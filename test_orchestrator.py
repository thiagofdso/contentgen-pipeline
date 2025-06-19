#!/usr/bin/env python3
"""Script de teste para o PipelineOrchestrator.

Este script testa a funcionalidade do orquestrador do pipeline
sem depender de arquivos de mídia reais.
"""

import asyncio
import sys
from pathlib import Path

# Adicionar o diretório src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from contentgen_pipeline.pipeline.orchestrator import PipelineOrchestrator
from contentgen_pipeline.generators.base import BaseContentGenerator


class MockContentGenerator(BaseContentGenerator):
    """Gerador de conteúdo mock para testes."""
    
    def __init__(self):
        super().__init__()
        self.name = "MockGenerator"
    
    async def summarize(self, text: str) -> str:
        """Gera um resumo mock."""
        return f"# Resumo Mock\n\nEste é um resumo gerado para o texto: {text[:100]}..."
    
    async def diagram(self, text: str) -> str:
        """Gera diagramação mock."""
        return f"Texto diagramado: {text[:100]}..."
    
    async def create_mindmap(self, texts: list) -> str:
        """Cria mapa mental mock."""
        return f"<opml version='2.0'><head><title>Mapa Mental Mock</title></head><body><outline text='Conteúdo Mock'/></body></opml>"
    
    async def preprocess_mindmap(self, texts: list) -> str:
        """Pré-processa para mapa mental mock."""
        return "Estrutura hierárquica mock"
    
    async def generate_content(self, prompt: str, text: str) -> str:
        """Gera conteúdo personalizado mock."""
        return f"Conteúdo gerado: {text[:50]}..."
    
    async def health_check(self) -> bool:
        """Verifica saúde mock."""
        return True
    
    def get_provider_name(self) -> str:
        """Retorna nome do provedor mock."""
        return self.name


async def test_orchestrator_health_check():
    """Testa a verificação de saúde do orquestrador."""
    print("🧪 Testando verificação de saúde do orquestrador...")
    
    try:
        mock_generator = MockContentGenerator()
        orchestrator = PipelineOrchestrator(mock_generator)
        
        health_status = await orchestrator.health_check()
        
        print("✅ Verificação de saúde concluída:")
        for component, status in health_status.items():
            print(f"  - {component}: {status}")
        
        return True
    except Exception as e:
        print(f"❌ Erro na verificação de saúde: {e}")
        return False


async def test_orchestrator_initialization():
    """Testa a inicialização do orquestrador."""
    print("🧪 Testando inicialização do orquestrador...")
    
    try:
        mock_generator = MockContentGenerator()
        orchestrator = PipelineOrchestrator(mock_generator)
        
        print(f"✅ Orquestrador inicializado com gerador: {orchestrator.content_generator.get_provider_name()}")
        return True
    except Exception as e:
        print(f"❌ Erro na inicialização: {e}")
        return False


async def test_content_generation():
    """Testa a geração de conteúdo."""
    print("🧪 Testando geração de conteúdo...")
    
    try:
        mock_generator = MockContentGenerator()
        
        # Teste de diagramação
        test_text = "Este é um texto de teste para verificar a funcionalidade de diagramação."
        diagrammed = await mock_generator.diagram(test_text)
        print(f"✅ Diagramação: {diagrammed[:50]}...")
        
        # Teste de resumo
        summary = await mock_generator.summarize(test_text)
        print(f"✅ Resumo: {summary[:50]}...")
        
        return True
    except Exception as e:
        print(f"❌ Erro na geração de conteúdo: {e}")
        return False


async def test_media_file_discovery():
    """Testa a descoberta de arquivos de mídia."""
    print("🧪 Testando descoberta de arquivos de mídia...")
    
    try:
        mock_generator = MockContentGenerator()
        orchestrator = PipelineOrchestrator(mock_generator)
        
        # Criar diretório temporário para teste
        test_dir = Path("test_media_files")
        test_dir.mkdir(exist_ok=True)
        
        # Criar arquivos de teste
        test_files = [
            "video1.mp4",
            "video2.avi",
            "video3.mkv",
            "document.txt",  # Não deve ser encontrado
            "image.jpg"      # Não deve ser encontrado
        ]
        
        for file_name in test_files:
            (test_dir / file_name).touch()
        
        # Testar descoberta
        media_files = orchestrator._find_media_files(test_dir)
        
        print(f"✅ Arquivos de mídia encontrados: {len(media_files)}")
        for file_path in media_files:
            print(f"  - {file_path.name}")
        
        # Limpar arquivos de teste
        for file_path in test_dir.iterdir():
            file_path.unlink()
        test_dir.rmdir()
        
        return len(media_files) == 3  # Deve encontrar apenas os 3 arquivos de vídeo
    except Exception as e:
        print(f"❌ Erro na descoberta de arquivos: {e}")
        return False


async def test_srt_generation():
    """Testa a geração de arquivos SRT."""
    print("🧪 Testando geração de arquivos SRT...")
    
    try:
        mock_generator = MockContentGenerator()
        orchestrator = PipelineOrchestrator(mock_generator)
        
        # Dados de teste
        test_segments = [
            {"start": 0.0, "end": 5.0, "text": "Primeiro segmento"},
            {"start": 5.0, "end": 10.0, "text": "Segundo segmento"},
            {"start": 10.0, "end": 15.0, "text": "Terceiro segmento"}
        ]
        
        srt_content = orchestrator._generate_srt_content(test_segments)
        
        print("✅ Conteúdo SRT gerado:")
        print(srt_content)
        
        return True
    except Exception as e:
        print(f"❌ Erro na geração SRT: {e}")
        return False


async def main():
    """Função principal de teste."""
    print("🚀 Iniciando testes do PipelineOrchestrator\n")
    
    tests = [
        ("Inicialização", test_orchestrator_initialization),
        ("Verificação de Saúde", test_orchestrator_health_check),
        ("Geração de Conteúdo", test_content_generation),
        ("Descoberta de Arquivos", test_media_file_discovery),
        ("Geração SRT", test_srt_generation),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Teste: {test_name}")
        print('='*50)
        
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Erro inesperado no teste {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumo dos resultados
    print(f"\n{'='*50}")
    print("RESUMO DOS TESTES")
    print('='*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nResultado: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 Todos os testes passaram!")
        return 0
    else:
        print("⚠️ Alguns testes falharam.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 