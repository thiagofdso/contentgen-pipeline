"""Interface base para geradores de conteúdo.

Este módulo define a classe abstrata BaseContentGenerator que estabelece
o contrato que todos os provedores de IA devem implementar para geração
de conteúdo no pipeline ContentGen.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from pathlib import Path


class BaseContentGenerator(ABC):
    """Classe base abstrata para geradores de conteúdo.
    
    Define a interface que todos os provedores de IA devem implementar
    para integrar com o pipeline ContentGen. Cada implementação deve
    fornecer métodos para gerar diferentes tipos de conteúdo a partir
    de texto transcrito.
    """
    
    def __init__(self, prompts_dir: Optional[Path] = None):
        """Inicializa o gerador de conteúdo.
        
        Args:
            prompts_dir: Diretório contendo os arquivos de prompt.
                        Se None, usa o diretório padrão do projeto.
        """
        if prompts_dir is None:
            # Usa o diretório padrão do projeto
            current_file = Path(__file__)
            prompts_dir = current_file.parent.parent / "prompts"
        
        self.prompts_dir = Path(prompts_dir)
        self._validate_prompts_directory()
    
    def _validate_prompts_directory(self) -> None:
        """Valida se o diretório de prompts existe.
        
        Raises:
            FileNotFoundError: Se o diretório de prompts não existir.
        """
        if not self.prompts_dir.exists():
            raise FileNotFoundError(
                f"Diretório de prompts não encontrado: {self.prompts_dir}"
            )
    
    def _load_prompt(self, prompt_name: str) -> str:
        """Carrega um prompt do arquivo correspondente.
        
        Args:
            prompt_name: Nome do arquivo de prompt (sem extensão).
            
        Returns:
            Conteúdo do prompt como string.
            
        Raises:
            FileNotFoundError: Se o arquivo de prompt não existir.
        """
        prompt_file = self.prompts_dir / f"{prompt_name}.txt"
        
        if not prompt_file.exists():
            raise FileNotFoundError(
                f"Arquivo de prompt não encontrado: {prompt_file}"
            )
        
        return prompt_file.read_text(encoding="utf-8")
    
    @abstractmethod
    async def summarize(self, text: str) -> str:
        """Gera um resumo do texto fornecido.
        
        Args:
            text: Texto transcrito a ser resumido.
            
        Returns:
            Resumo do texto em formato markdown.
            
        Raises:
            Exception: Se houver erro na geração do resumo.
        """
        pass
    
    @abstractmethod
    async def diagram(self, text: str) -> str:
        """Gera um diagrama baseado no texto fornecido.
        
        Args:
            text: Texto transcrito para gerar o diagrama.
            
        Returns:
            Diagrama em formato texto estruturado.
            
        Raises:
            Exception: Se houver erro na geração do diagrama.
        """
        pass
    
    @abstractmethod
    async def create_mindmap(self, texts: List[str]) -> str:
        """Cria um mapa mental a partir de uma lista de textos.
        
        Args:
            texts: Lista de textos transcritos para criar o mapa mental.
            
        Returns:
            Mapa mental em formato OPML.
            
        Raises:
            Exception: Se houver erro na criação do mapa mental.
        """
        pass
    
    async def preprocess_mindmap(self, texts: List[str]) -> str:
        """Pré-processa textos para criação de mapa mental.
        
        Args:
            texts: Lista de textos transcritos para pré-processar.
            
        Returns:
            Estrutura hierárquica pré-processada.
            
        Raises:
            Exception: Se houver erro no pré-processamento.
        """
        prompt = self._load_prompt("preprocess_mindmap")
        formatted_prompt = prompt.format(texts="\n\n".join(texts))
        return await self.generate_content(formatted_prompt, "")
    
    @abstractmethod
    async def generate_content(self, prompt: str, text: str) -> str:
        """Gera conteúdo personalizado baseado em um prompt e texto.
        
        Args:
            prompt: Prompt específico para a geração.
            text: Texto transcrito como contexto.
            
        Returns:
            Conteúdo gerado conforme o prompt.
            
        Raises:
            Exception: Se houver erro na geração do conteúdo.
        """
        pass
    
    @abstractmethod
    async def call_model_with_messages(self, messages: List[Dict[str, str]]) -> str:
        """Chama o modelo diretamente com uma lista de mensagens.
        
        Este método permite enviar diretamente uma lista de mensagens para o modelo,
        mantendo o histórico da conversa. É essencial para implementar lógicas
        como reenvios para completar conteúdo (ex: mapas mentais OPML).
        
        Args:
            messages: Lista de mensagens no formato [{"role": "user/assistant", "content": "..."}]
            
        Returns:
            Conteúdo da resposta do modelo.
            
        Raises:
            Exception: Se houver erro na chamada do modelo.
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica se o provedor de IA está funcionando corretamente.
        
        Returns:
            True se o provedor estiver funcionando, False caso contrário.
        """
        pass
    
    def get_supported_models(self) -> List[str]:
        """Retorna a lista de modelos suportados pelo provedor.
        
        Returns:
            Lista de nomes dos modelos suportados.
        """
        return []
    
    def get_provider_name(self) -> str:
        """Retorna o nome do provedor de IA.
        
        Returns:
            Nome do provedor (ex: "Adapta", "OpenAI", etc.).
        """
        return self.__class__.__name__ 