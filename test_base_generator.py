#!/usr/bin/env python3
"""Script de teste para validar a classe BaseContentGenerator."""

import asyncio
import sys
from pathlib import Path

# Adiciona o diretório src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from contentgen_pipeline.generators import BaseContentGenerator


def log_info(message: str) -> None:
    """Função simples de logging."""
    print(f"INFO: {message}")


def log_error(message: str) -> None:
    """Função simples de logging de erro."""
    print(f"ERROR: {message}")


class MockContentGenerator(BaseContentGenerator):
    """Implementação mock para testar a classe abstrata."""
    
    async def summarize(self, text: str) -> str:
        """Implementação mock do método summarize."""
        prompt = self._load_prompt("summarize")
        formatted_prompt = prompt.format(text=text[:100] + "..." if len(text) > 100 else text)
        return f"# Resumo Mock\n\n{formatted_prompt}\n\nResumo gerado para: {text[:50]}..."
    
    async def diagram(self, text: str) -> str:
        """Implementação mock do método diagram."""
        prompt = self._load_prompt("diagram")
        formatted_prompt = prompt.format(text=text[:100] + "..." if len(text) > 100 else text)
        return f"Diagrama Mock:\n{formatted_prompt}\n\nDiagrama gerado para: {text[:50]}..."
    
    async def create_mindmap(self, texts: list[str]) -> str:
        """Implementação mock do método create_mindmap."""
        prompt = self._load_prompt("mindmap")
        formatted_prompt = prompt.format(texts="\n".join(texts))
        return f"<opml version='1.0'>\n<head>\n<title>Mapa Mental Mock</title>\n</head>\n<body>\n<outline text='Tema Central'>\n{formatted_prompt}\n</outline>\n</body>\n</opml>"
    
    async def generate_content(self, prompt: str, text: str) -> str:
        """Implementação mock do método generate_content."""
        return f"Conteúdo gerado com prompt: {prompt[:50]}...\nTexto: {text[:50]}..."
    
    async def health_check(self) -> bool:
        """Implementação mock do método health_check."""
        return True
    
    def get_supported_models(self) -> list[str]:
        """Retorna modelos suportados mock."""
        return ["mock-model-1", "mock-model-2"]
    
    def get_provider_name(self) -> str:
        """Retorna nome do provedor mock."""
        return "MockProvider"


async def test_base_generator():
    """Testa a funcionalidade da classe BaseContentGenerator."""
    log_info("Iniciando testes da classe BaseContentGenerator...")
    
    try:
        # Teste 1: Criação da instância
        log_info("Teste 1: Criando instância do gerador mock...")
        generator = MockContentGenerator()
        log_info(f"✓ Gerador criado: {generator.get_provider_name()}")
        
        # Teste 2: Verificação de prompts
        log_info("Teste 2: Verificando carregamento de prompts...")
        summarize_prompt = generator._load_prompt("summarize")
        diagram_prompt = generator._load_prompt("diagram")
        mindmap_prompt = generator._load_prompt("mindmap")
        preprocess_prompt = generator._load_prompt("preprocess_mindmap")
        log_info(f"✓ Prompts carregados: summarize ({len(summarize_prompt)} chars), diagram ({len(diagram_prompt)} chars), mindmap ({len(mindmap_prompt)} chars), preprocess_mindmap ({len(preprocess_prompt)} chars)")
        
        # Teste 3: Teste do método summarize
        log_info("Teste 3: Testando método summarize...")
        test_text = "Este é um texto de teste para verificar se o método summarize está funcionando corretamente. Ele deve gerar um resumo estruturado em markdown."
        summary = await generator.summarize(test_text)
        log_info(f"✓ Resumo gerado: {len(summary)} caracteres")
        print(f"Resumo: {summary[:200]}...")
        
        # Teste 4: Teste do método diagram
        log_info("Teste 4: Testando método diagram...")
        diagram = await generator.diagram(test_text)
        log_info(f"✓ Diagrama gerado: {len(diagram)} caracteres")
        print(f"Diagrama: {diagram[:200]}...")
        
        # Teste 5: Teste do método create_mindmap
        log_info("Teste 5: Testando método create_mindmap...")
        test_texts = [
            "Primeiro texto sobre inteligência artificial",
            "Segundo texto sobre machine learning",
            "Terceiro texto sobre deep learning"
        ]
        mindmap = await generator.create_mindmap(test_texts)
        log_info(f"✓ Mapa mental gerado: {len(mindmap)} caracteres")
        print(f"Mapa mental: {mindmap[:200]}...")
        
        # Teste 6: Teste do método preprocess_mindmap
        log_info("Teste 6: Testando método preprocess_mindmap...")
        preprocessed = await generator.preprocess_mindmap(test_texts)
        log_info(f"✓ Pré-processamento gerado: {len(preprocessed)} caracteres")
        print(f"Pré-processamento: {preprocessed[:200]}...")
        
        # Teste 7: Teste do método generate_content
        log_info("Teste 7: Testando método generate_content...")
        custom_prompt = "Crie um resumo executivo em 3 pontos principais"
        content = await generator.generate_content(custom_prompt, test_text)
        log_info(f"✓ Conteúdo personalizado gerado: {len(content)} caracteres")
        print(f"Conteúdo: {content[:200]}...")
        
        # Teste 8: Teste do método health_check
        log_info("Teste 8: Testando método health_check...")
        health_status = await generator.health_check()
        log_info(f"✓ Status de saúde: {health_status}")
        
        # Teste 9: Teste dos métodos de informação
        log_info("Teste 9: Testando métodos de informação...")
        models = generator.get_supported_models()
        provider_name = generator.get_provider_name()
        log_info(f"✓ Modelos suportados: {models}")
        log_info(f"✓ Nome do provedor: {provider_name}")
        
        log_info("🎉 Todos os testes da classe BaseContentGenerator passaram com sucesso!")
        
    except Exception as e:
        log_error(f"❌ Erro durante os testes: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_base_generator()) 