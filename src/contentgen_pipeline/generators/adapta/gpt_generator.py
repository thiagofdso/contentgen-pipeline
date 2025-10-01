"""Gerador de conteúdo usando o modelo GPT via API Adapta.one.

Este módulo implementa o GPTGenerator que utiliza a API Adapta.one
para gerar conteúdo usando o modelo GPT.
"""

from typing import List, Optional, Dict
from pathlib import Path

from ..base import BaseContentGenerator
from .client import AdaptaClient
from ...config import settings


class GPTGenerator(BaseContentGenerator):
    """Gerador de conteúdo usando o modelo GPT via Adapta.one.
    
    Implementa todos os métodos da interface BaseContentGenerator
    utilizando o modelo GPT através da API Adapta.one.
    """
    
    def __init__(self, prompts_dir: Optional[Path] = None, cookies_str: Optional[str] = None,session_id: Optional[str] = None):
        """Inicializa o gerador GPT.
        
        Args:
            prompts_dir: Diretório contendo os arquivos de prompt.
            cookies_str: String de cookies para autenticação na Adapta.one.
        """
        super().__init__(prompts_dir)
        
        # Usar cookies das configurações se não fornecidos
        if cookies_str is None:
            cookies_str = settings.adapta_cookies_str

        if session_id is None:
            session_id = settings.adapta_session_id        
        # Usar timeouts mais altos para lidar com chamadas que podem demorar
        self.client = AdaptaClient(
            cookies_str=cookies_str,
            timeout=600.0,  # 10 minutos para timeout geral
            connect_timeout=120.0,  # 2 minutos para conexão
            read_timeout=600.0,  # 10 minutos para leitura
            session_id=session_id
        )
        self.model_name = "GPT_5"
        self._client_initialized = False
    
    async def _ensure_client_initialized(self):
        """Garante que o cliente está inicializado antes de usar."""
        if not self._client_initialized:
            await self.client._ensure_client()
            self._client_initialized = True
    
    async def summarize(self, text: str) -> str:
        """Gera um resumo do texto fornecido usando o modelo GPT.
        
        Args:
            text: Texto transcrito a ser resumido.
            
        Returns:
            Resumo do texto em formato markdown.
            
        Raises:
            Exception: Se houver erro na geração do resumo.
        """
        try:
            await self._ensure_client_initialized()
            prompt = self._load_prompt("summarize")
            formatted_prompt = prompt.format(text=text)
            
            messages = [
                {"role": "user", "content": formatted_prompt}
            ]
            
            result = await self.client.call_model(messages, self.model_name, new_line=True)
            
            if result is None:
                raise Exception("Falha ao gerar resumo com GPT")
            
            return result
            
        except Exception as e:
            raise Exception(f"Erro ao gerar resumo com GPT: {e}")
    
    async def diagram(self, text: str) -> str:
        """Gera um diagrama baseado no texto fornecido usando o modelo GPT.
        
        Args:
            text: Texto transcrito para gerar o diagrama.
            
        Returns:
            Diagrama em formato texto estruturado.
            
        Raises:
            Exception: Se houver erro na geração do diagrama.
        """
        try:
            await self._ensure_client_initialized()
            prompt = self._load_prompt("diagram")
            formatted_prompt = prompt.format(text=text)
            
            messages = [
                {"role": "user", "content": formatted_prompt}
            ]
            
            result = await self.client.call_model(messages, self.model_name, new_line=True)
            
            if result is None:
                raise Exception("Falha ao gerar diagrama com GPT")
            
            return result
            
        except Exception as e:
            raise Exception(f"Erro ao gerar diagrama com GPT: {e}")
    
    async def create_mindmap(self, texts: List[str]) -> str:
        """Cria um mapa mental a partir de uma lista de textos usando o modelo GPT.
        
        Args:
            texts: Lista de textos transcritos para criar o mapa mental.
            
        Returns:
            Mapa mental em formato OPML.
            
        Raises:
            Exception: Se houver erro na criação do mapa mental.
        """
        try:
            await self._ensure_client_initialized()
            prompt = self._load_prompt("mindmap")
            formatted_prompt = prompt.format(texts="\n\n".join(texts))
            
            messages = [
                {"role": "user", "content": formatted_prompt}
            ]
            
            result = await self.client.call_model(messages, self.model_name, new_line=True)
            
            if result is None:
                raise Exception("Falha ao gerar mapa mental com GPT")
            
            return result
            
        except Exception as e:
            raise Exception(f"Erro ao gerar mapa mental com GPT: {e}")
    
    async def generate_content(self, prompt: str, text: str) -> str:
        """Gera conteúdo personalizado baseado em um prompt e texto usando o modelo GPT.
        
        Args:
            prompt: Prompt específico para a geração.
            text: Texto transcrito como contexto.
            
        Returns:
            Conteúdo gerado conforme o prompt.
            
        Raises:
            Exception: Se houver erro na geração do conteúdo.
        """
        try:
            await self._ensure_client_initialized()
            # Combina o prompt personalizado com o texto
            full_prompt = f"{prompt}\n\nTexto: {text}"
            
            messages = [
                {"role": "user", "content": full_prompt}
            ]
            
            result = await self.client.call_model(messages, self.model_name, new_line=True)
            
            if result is None:
                raise Exception("Falha ao gerar conteúdo personalizado com GPT")
            
            return result
            
        except Exception as e:
            raise Exception(f"Erro ao gerar conteúdo personalizado com GPT: {e}")
    
    async def call_model_with_messages(self, messages: List[Dict[str, str]]) -> str:
        """Chama o modelo GPT diretamente com uma lista de mensagens.
        
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
        try:
            await self._ensure_client_initialized()
            
            result = await self.client.call_model(messages, self.model_name, new_line=True)
            
            if result is None:
                raise Exception("Falha ao chamar modelo GPT com mensagens")
            
            return result
            
        except Exception as e:
            raise Exception(f"Erro ao chamar modelo GPT com mensagens: {e}")
    
    async def health_check(self) -> bool:
        """Verifica se o provedor de IA está funcionando corretamente.
        
        Returns:
            True se o provedor estiver funcionando, False caso contrário.
        """
        try:
            await self._ensure_client_initialized()
            return await self.client.health_check()
        except Exception:
            return False
    
    def get_supported_models(self) -> List[str]:
        """Retorna a lista de modelos suportados pelo provedor.
        
        Returns:
            Lista de nomes dos modelos suportados.
        """
        return ["GPT_5"]
    
    def get_provider_name(self) -> str:
        """Retorna o nome do provedor de IA.
        
        Returns:
            Nome do provedor.
        """
        return "GPTGenerator" 