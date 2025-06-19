# Plano de Desenvolvimento: ContentGen Pipeline

Este documento descreve as etapas para o desenvolvimento do projeto **ContentGen Pipeline**, seguindo uma abordagem incremental e iterativa. Cada etapa representa um conjunto de funcionalidades que podem ser desenvolvidas, testadas e validadas de forma independente.

## Fase 1: Fundação do Projeto e Configuração

*Objetivo: Estabelecer a estrutura básica, configurações e dependências do projeto.*

**Etapa 1.1: Configuração do Ambiente de Desenvolvimento**
-   [ ] Inicializar o projeto com `Poetry` (`poetry init`).
-   [ ] Criar a estrutura de diretórios inicial conforme o `spec.md` (`src/contentgen_pipeline`, `prompts/`, etc.).
-   [ ] Adicionar as dependências principais ao `pyproject.toml`: `python-dotenv`, `pydantic`, `typer`, `rich`, `loguru`.
-   [ ] Criar o arquivo `.gitignore` para ignorar `__pycache__`, `.env`, `*.pyc`, e pastas de saída.
-   [ ] Criar o arquivo `.env.example` com as variáveis de ambiente necessárias (ex: `ADAPTA_COOKIES_STR`, `WHISPER_MODEL`), mas com valores vazios.

**Etapa 1.2: Módulo de Configuração e Logging**
-   [ ] Implementar o módulo `config.py` usando Pydantic para carregar e validar as variáveis do `.env`.
-   [ ] Implementar o módulo `utils/logger.py` usando `loguru` para criar uma instância de logger centralizada e configurável.
-   **Teste/Validação:** Criar um script simples em `main.py` para garantir que as configurações são carregadas corretamente e que os logs são exibidos no console.

---

## Fase 2: Processamento de Mídia e Transcrição

*Objetivo: Construir a primeira parte do pipeline, transformando um arquivo de mídia local em uma transcrição de texto.*

**Etapa 2.1: Implementar o `MediaProcessor`**
-   [ ] Criar a classe `MediaProcessor` em `core/media_processor.py`.
-   [ ] Implementar o método `extract_audio(video_path)`, que usa `ffmpeg` para extrair o áudio para um arquivo `.mp3` temporário.
-   [ ] Adicionar tratamento de erros para o caso de `ffmpeg` não estar instalado ou falhar.
-   **Teste/Validação:** Escrever um pequeno script de teste que chama `extract_audio()` em um arquivo de vídeo de exemplo e verifica se o arquivo de áudio foi criado corretamente.

**Etapa 2.2: Implementar o `Transcriber`**
-   [ ] Adicionar `faster-whisper` e suas dependências (`numba`, `torch`) ao `pyproject.toml`.
-   [ ] Criar a classe `Transcriber` em `core/transcriber.py`.
-   [ ] No `__init__`, carregar o modelo Whisper com base nas configurações (modelo, dispositivo, tipo de computação). Isso garante que o modelo seja carregado apenas uma vez.
-   [ ] Implementar o método `transcribe(audio_path)`, que retorna a transcrição completa e os segmentos com timestamps.
-   **Teste/Validação:** Escrever um script de teste que usa o áudio extraído da etapa anterior, passa para o `Transcriber` e imprime a transcrição no console. Validar a precisão manualmente.

**Etapa 2.3: Implementar a Geração de Legendas (SRT)**
-   [ ] Adicionar um método ao `Transcriber` ou a uma classe utilitária para formatar os segmentos com timestamps no formato `.srt`.
-   **Teste/Validação:** Verificar se o arquivo `.srt` gerado é válido e pode ser aberto em um player de vídeo com o vídeo original.

---

## Fase 3: Geração de Conteúdo (Abstração e Implementação Inicial)

*Objetivo: Criar a arquitetura flexível para geração de conteúdo e implementar o primeiro provedor (Adapta.one).*

**Etapa 3.1: Definir a Interface do Gerador de Conteúdo**
-   [ ] Criar a classe base abstrata `BaseContentGenerator` em `generators/base.py` usando o módulo `abc`.
-   [ ] Definir os métodos abstratos que toda implementação deverá ter: `async summarize(text)`, `async diagram(text)`, `async create_mindmap(texts)`.

**Etapa 3.2: Implementar o `AdaptaGenerator`**
-   [ ] Criar a classe `AdaptaGenerator` em `generators/adapta_generator.py`, herdando de `BaseContentGenerator`.
-   [ ] Implementar a lógica de comunicação com a API Adapta.one (baseada no seu `ClientAdapta.py` original, mas refatorado e assíncrono usando `httpx`).
-   [ ] Carregar os prompts da pasta `prompts/` para cada método.
-   [ ] Implementar o método `async summarize(text)`.
-   **Teste/Validação:** Escrever um script de teste que instancia o `AdaptaGenerator` e chama o método `summarize` com uma transcrição de exemplo. Validar se o resumo retornado é coerente.

**Etapa 3.3: Implementar os Outros Métodos de Geração**
-   [ ] Implementar `async diagram(text)` no `AdaptaGenerator`.
-   [ ] Implementar `async create_mindmap(texts)` no `AdaptaGenerator`.
-   **Teste/Validação:** Testar cada método individualmente, validando o formato e a qualidade da saída (`.txt` formatado, `.opml` válido).

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
    1.  Instanciar o `MediaProcessor`, `Transcriber` e o `AdaptaGenerator`.
    2.  Instanciar o `PipelineOrchestrator`, passando o `AdaptaGenerator` para ele.
    3.  Chamar o método `orchestrator.process_directory()`.
    4.  Usar `asyncio.run()` para executar a função assíncrona.
-   [ ] Ligar a CLI ao `main.py`.
-   **Teste/Validação:** Executar a ferramenta a partir da linha de comando em um diretório com 2-3 arquivos de mídia. Verificar se todos os artefatos (`.txt`, `.srt`, `.md`, `.opml`) são gerados corretamente para cada arquivo.

---

## Fase 5: Refinamento e Robustez

*Objetivo: Adicionar funcionalidades que tornem a ferramenta mais confiável e pronta para uso.*

**Etapa 5.1: Implementar Tratamento de Erros e Retentativas**
-   [ ] Criar um decorador `retry` em `utils/error_handler.py` que re-executa uma função em caso de exceções específicas (ex: `httpx.RequestError`).
-   [ ] Aplicar o decorador `retry` aos métodos de chamada de API no `AdaptaGenerator`.
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

**Etapa 6.2: Empacotamento (Opcional)**
-   [ ] Configurar o `pyproject.toml` para que o projeto possa ser empacotado e instalado via `pip` usando `poetry build`.