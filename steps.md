# Plano de Desenvolvimento: ContentGen Pipeline

Este documento descreve as etapas para o desenvolvimento do projeto **ContentGen Pipeline**, seguindo uma abordagem incremental e iterativa. Cada etapa representa um conjunto de funcionalidades que podem ser desenvolvidas, testadas e validadas de forma independente.

## Fase 1: Fundação do Projeto e Configuração

*Objetivo: Estabelecer a estrutura básica, configurações e dependências do projeto.*

**Etapa 1.1: Configuração do Ambiente de Desenvolvimento**
-   [x] Inicializar o projeto com `Poetry` (`poetry init`).
-   [x] Criar a estrutura de diretórios inicial conforme o `spec.md` (`src/contentgen_pipeline`, `prompts/`, etc.).
-   [x] Adicionar as dependências principais ao `pyproject.toml`: `python-dotenv`, `pydantic`, `typer`, `rich`, `loguru`.
-   [x] Criar o arquivo `.gitignore` para ignorar `__pycache__`, `.env`, `*.pyc`, e pastas de saída.
-   [x] Criar o arquivo `.env.example` com as variáveis de ambiente necessárias (ex: `ADAPTA_COOKIES_STR`, `WHISPER_MODEL`), mas com valores vazios.

**Etapa 1.2: Módulo de Configuração e Logging**
-   [x] Implementar o módulo `config.py` usando Pydantic para carregar e validar as variáveis do `.env`.
-   [x] Implementar o módulo `utils/logger.py` usando `loguru` para criar uma instância de logger centralizada e configurável.
-   [x] **Teste/Validação:** Criar um script simples em `main.py` para garantir que as configurações são carregadas corretamente e que os logs são exibidos no console.

**Implementações Adicionais da Fase 1:**
-   [x] Criar arquivo `main.py` como ponto de entrada da aplicação.
-   [x] Criar arquivo `cli.py` com estrutura básica da interface de linha de comando usando `typer`.
-   [x] Criar arquivo `README.md` com documentação básica do projeto.
-   [x] Adicionar `pydantic-settings` para compatibilidade com Pydantic 2.x.
-   [x] Criar script de teste `test_config.py` para validar configurações e logging.

---

## Fase 2: Processamento de Mídia e Transcrição

*Objetivo: Construir a primeira parte do pipeline, transformando um arquivo de mídia local em uma transcrição de texto.*

**Etapa 2.1: Implementar o `MediaProcessor`**
-   [x] Criar a classe `MediaProcessor` em `core/media_processor.py`.
-   [x] Implementar o método `extract_audio(video_path)`, que usa `ffmpeg` para extrair o áudio para um arquivo `.mp3` temporário.
-   [x] Adicionar tratamento de erros para o caso de `ffmpeg` não estar instalado ou falhar.
-   [x] **Teste/Validação:** Escrever um pequeno script de teste que chama `extract_audio()` em um arquivo de vídeo de exemplo e verifica se o arquivo de áudio foi criado corretamente.

**Implementações Adicionais da Etapa 2.1:**
-   [x] Criar script de teste `test_media_processor.py` para validar extração de áudio.
-   [x] Adicionar arquivos de mídia ao `.gitignore` (videoteste.webm, *.mp3, *.mp4, etc.).
-   [x] Implementar limpeza automática do arquivo de áudio após teste.

**Etapa 2.2: Implementar o `Transcriber`**
-   [x] Adicionar `faster-whisper` e suas dependências (`numba`, `torch`) ao `pyproject.toml`.
-   [x] Criar a classe `Transcriber` em `core/transcriber.py`.
-   [x] No `__init__`, carregar o modelo Whisper com base nas configurações (modelo, dispositivo, tipo de computação). Isso garante que o modelo seja carregado apenas uma vez.
-   [x] Implementar o método `transcribe(audio_path)`, que retorna a transcrição completa e os segmentos com timestamps.
-   [x] **Teste/Validação:** Escrever um script de teste que usa o áudio extraído da etapa anterior, passa para o `Transcriber` e imprime a transcrição no console. Validar a precisão manualmente.

**Implementações Adicionais da Etapa 2.2:**
-   [x] Criar script de teste `test_transcriber.py` para validar transcrição completa.
-   [x] Implementar detecção automática de CUDA Toolkit e configuração do PATH.
-   [x] Implementar suporte ao cuDNN com detecção automática do caminho `bin/12.9/`.
-   [x] Criar função `setup_cuda_environment()` para configurar ambiente CUDA/cuDNN.
-   [x] Implementar geração de arquivos `.txt` e `.srt` com legendas.
-   [x] Criar script de teste `test_cudnn_path.py` para validar configuração do cuDNN.
-   [x] Resolver problema de compatibilidade de versões do cuDNN (cudnn64_9.dll vs cudnn_ops64_9.dll).
-   [x] Configurar arquivo `.env` com caminho correto do cuDNN: `C:\Program Files\NVIDIA\CUDNN\v9.10`.

**Etapa 2.3: Implementar a Geração de Legendas (SRT)**
-   [x] Adicionar um método ao `Transcriber` ou a uma classe utilitária para formatar os segmentos com timestamps no formato `.srt`.
-   [x] **Teste/Validação:** Verificar se o arquivo `.srt` gerado é válido e pode ser aberto em um player de vídeo com o vídeo original.

---

## Fase 3: Geração de Conteúdo (Abstração e Implementação Modular)

*Objetivo: Criar a arquitetura flexível para geração de conteúdo e implementar o provedor Adapta.one com estrutura modular.*

**Etapa 3.1: Definir a Interface do Gerador de Conteúdo**
-   [x] Criar a classe base abstrata `BaseContentGenerator` em `generators/base.py` usando o módulo `abc`.
-   [x] Definir os métodos abstratos que toda implementação deverá ter: `async summarize(text)`, `async diagram(text)`, `async create_mindmap(texts)`, `async preprocess_mindmap(texts)`, `async generate_content(prompt, text)`, `async health_check()`.
-   [x] Implementar métodos utilitários para carregamento de prompts e validação de diretórios.
-   [x] **Teste/Validação:** Criar script de teste `test_base_generator.py` com implementação mock para validar a interface.

**Etapa 3.2: Criar Estrutura Modular para Adapta.one**
-   [x] Criar sub-pacote `generators/adapta/` com estrutura modular:
    -   [x] `generators/adapta/__init__.py` - Exporta as classes principais
    -   [x] `generators/adapta/client.py` - Cliente de baixo nível para autenticação e requisições HTTP (refatorado do `ClientAdapta.py`)
    -   [x] `generators/adapta/gemini_generator.py` - Implementação para o modelo Gemini via Adapta
    -   [x] `generators/adapta/claude_generator.py` - Implementação para o modelo Claude via Adapta
    -   [x] `generators/adapta/gpt_generator.py` - Implementação para o modelo GPT via Adapta
-   [x] Implementar cliente assíncrono usando `httpx` em vez de `requests`.
-   [x] Adicionar tratamento de erros e retentativas no cliente.
-   [x] Implementar métodos `upload_arquivo()` e `excluir_arquivo()` do `ClientAdapta.py`.
-   [x] **Teste/Validação:** Criar script de teste `test_adapta_generators.py` para validar a estrutura modular.

**Etapa 3.3: Implementar Prompts Especializados**
-   [x] Criar prompt `prompts/summarize.txt` para geração de resumos detalhados em markdown.
-   [x] Criar prompt `prompts/diagram.txt` para formatação e correção de transcrições.
-   [x] Criar prompt `prompts/preprocess_mindmap.txt` para pré-processamento hierárquico.
-   [x] Criar prompt `prompts/mindmap.txt` para geração de mapas mentais em OPML 2.0.
-   [ ] **Teste/Validação:** Validar que todos os prompts são carregados corretamente e formatados adequadamente.

**Etapa 3.4: Implementar Geradores Específicos**
-   [x] Implementar `GeminiGenerator` com suporte a todos os métodos da interface base.
-   [x] Implementar `ClaudeGenerator` com suporte a todos os métodos da interface base.
-   [x] Implementar `GPTGenerator` com suporte a todos os métodos da interface base.
-   [ ] Adicionar factory pattern para criação de geradores baseado em configuração.
-   [ ] **Teste/Validação:** Testar cada gerador com diferentes tipos de conteúdo e validar qualidade das saídas.

---

## Fase 4: Orquestração do Pipeline e CLI

*Objetivo: Unir todos os componentes em um pipeline funcional e expô-lo através de uma interface de linha de comando.*

**Etapa 4.1: Implementar o `PipelineOrchestrator`**
-   [ ] Criar a classe `PipelineOrchestrator` em `pipeline/orchestrator.py`.
-   [ ] O `__init__` deve receber uma instância de um `BaseContentGenerator` (injeção de dependência).
-   [ ] Criar um método `async process_single_file(media_path)`, que:
    1.  Chama `MediaProcessor.extract_audio()`.
    2.  Chama `Transcriber.transcribe()`.
    3.  Salva os arquivos `.txt` e `.srt`.
    4.  Chama os métodos do `ContentGenerator` injetado (`diagram`, `summarize`, `create_mindmap`).
    5.  Salva as saídas (`.md`, `.opml`).
-   [ ] Criar um método `async process_directory(directory_path)` que encontra todos os arquivos de mídia e executa `process_single_file` para cada um em paralelo (usando `asyncio.gather`).

**Etapa 4.2: Construir a Interface de Linha de Comando (CLI)**
-   [ ] Implementar `cli.py` usando `typer`.
-   [ ] Criar um comando `process` que aceita um caminho de diretório como argumento.
-   [ ] Dentro do comando:
    1.  Instanciar o `MediaProcessor`, `Transcriber` e o gerador apropriado (baseado em configuração).
    2.  Instanciar o `PipelineOrchestrator`, passando o gerador para ele.
    3.  Chamar o método `orchestrator.process_directory()`.
    4.  Usar `asyncio.run()` para executar a função assíncrona.
-   [ ] Ligar a CLI ao `main.py`.
-   **Teste/Validação:** Executar a ferramenta a partir da linha de comando em um diretório com 2-3 arquivos de mídia. Verificar se todos os artefatos (`.txt`, `.srt`, `.md`, `.opml`) são gerados corretamente para cada arquivo.

---

## Fase 5: Refinamento e Robustez

*Objetivo: Adicionar funcionalidades que tornem a ferramenta mais confiável e pronta para uso.*

**Etapa 5.1: Implementar Tratamento de Erros e Retentativas**
-   [ ] Criar um decorador `retry` em `utils/error_handler.py` que re-executa uma função em caso de exceções específicas (ex: `httpx.RequestError`).
-   [ ] Aplicar o decorador `retry` aos métodos de chamada de API nos geradores.
-   [ ] Adicionar blocos `try...except` robustos no `PipelineOrchestrator` para que a falha em um arquivo não pare o processamento de todo o lote.

**Etapa 5.2: Adicionar Geração de E-book e Mapa Mental Agregado**
-   [ ] Estender o `PipelineOrchestrator` com um método que, após processar todos os arquivos de um diretório, agregue os resumos ou mapas mentais.
-   [ ] Chamar o `ContentGenerator` com um prompt específico para criar a estrutura do e-book ou o mapa mental consolidado do curso.
-   [ ] Adicionar um novo comando à CLI: `process-course` para essa funcionalidade.
-   **Teste/Validação:** Executar o novo comando em um diretório e verificar a qualidade e coerência do artefato final agregado.

---

## Fase 6: Documentação e Empacotamento

*Objetivo: Preparar o projeto para distribuição e uso por outras pessoas.*

**Etapa 6.1: Escrever a Documentação**
-   [ ] Atualizar o `README.md` com instruções detalhadas de instalação, configuração (como preencher o `.env`) e uso da CLI.
-   [ ] Adicionar docstrings a todas as classes e funções públicas.
-   [ ] Criar documentação da API para desenvolvedores que queiram adicionar novos provedores de IA.
-   [ ] Documentar a estrutura modular de generators e como criar novos provedores.

**Etapa 6.2: Empacotamento e Distribuição**
-   [ ] Configurar `pyproject.toml` para empacotamento com Poetry.
-   [ ] Criar scripts de instalação e configuração automática.
-   [ ] Preparar releases no GitHub com changelog.
-   [ ] **Teste/Validação:** Testar instalação em ambiente limpo e verificar se todas as funcionalidades funcionam corretamente.

---

## 🔧 TODO: Revisão de Endpoints e Problemas Identificados

*Baseado nos resultados dos testes, foram identificados problemas que precisam ser corrigidos:*

### **Problemas Críticos Identificados:**

1. **Endpoint de Upload de Arquivo (404 Not Found)**:
   - ❌ **Problema**: `https://adapta-one-services-production.up.railway.app/v1/files` retorna 404
   - 🔍 **Ação**: Verificar endpoint correto no `ClientAdapta.py` original
   - 📝 **TODO**: 
     - [ ] Consultar documentação da API Adapta.one
     - [ ] Verificar se o endpoint mudou
     - [ ] Testar com cURL para confirmar endpoint correto
     - [ ] Atualizar URL no método `upload_arquivo()`

2. **Endpoint de Exclusão de Arquivo (405 Method Not Allowed)**:
   - ❌ **Problema**: `https://app.adapta.one/api/v1/file/{id}` retorna 405
   - 🔍 **Ação**: Verificar método HTTP correto (DELETE vs POST)
   - 📝 **TODO**:
     - [ ] Verificar se deve usar POST em vez de DELETE
     - [ ] Consultar `ClientAdapta.py` para método correto
     - [ ] Testar diferentes métodos HTTP
     - [ ] Atualizar método no `excluir_arquivo()`
