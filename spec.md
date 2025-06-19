# Especificação Técnica: Ferramenta de Automação de Conteúdo

**Versão:** 1.0
**Data:** 25 de novembro de 2024
**Autor:** Thiago Oliveira

## 1. Definição do Problema e Objetivos

### 1.1. Problema
A criação de materiais de estudo de alta qualidade a partir de conteúdo de mídia (vídeos, áudios, cursos) é um processo manual, demorado e sujeito a inconsistências. Profissionais e criadores de conteúdo gastam horas transcrevendo, resumindo, estruturando e formatando informações, o que representa um gargalo significativo na produção e distribuição de conhecimento.

### 1.2. Solução Proposta
Desenvolver uma ferramenta de automação em Python, chamada provisoriamente de **"ContentGen Pipeline"**, que orquestra um pipeline completo para transformar mídias brutas em um conjunto coeso de materiais de estudo, incluindo transcrições formatadas, resumos, legendas, mapas mentais e estruturas de e-book.

### 1.3. Objetivos do Projeto
- **Automatizar 90% do fluxo de trabalho** de produção de conteúdo derivado de mídia.
- **Reduzir drasticamente o tempo** de criação de materiais, de dias para minutos/horas.
- **Padronizar a qualidade e o formato** dos materiais gerados.
- **Criar uma ferramenta modular e extensível**, que permita a fácil integração de diferentes provedores de IA para geração de conteúdo.

---

## 2. Escopo do Projeto

### 2.1. Funcionalidades Essenciais (MVP - Minimum Viable Product)
O foco inicial é construir um pipeline robusto para processamento de arquivos locais com um provedor de IA configurável.

1.  **Processamento de Mídia Local:**
    -   Suporte para processar arquivos de vídeo (`.mp4`, `.mkv`, `.avi`, `.webm`) e áudio (`.mp3`, `.wav`, `.aac`).
    -   Extração automática de faixas de áudio de arquivos de vídeo para transcrição.

2.  **Transcrição com IA:**
    -   Utilização do `faster-whisper` para transcrição de alta precisão.
    -   Suporte para aceleração via GPU (CUDA).
    -   Geração de transcrição em texto puro (`.txt`).
    -   Geração de legendas com timestamps em formato SRT (`.srt`).

3.  **Geração de Conteúdo com IA (Arquitetura Abstrata):**
    -   **Interface Comum:** Definir uma interface `ContentGenerator` que abstrai as operações de IA (ex: `summarize`, `create_mindmap`).
    -   **Implementação Inicial:** Criar uma implementação concreta para a API Adapta.one (`AdaptaClient`).
    -   **Funcionalidades de IA:**
        -   **Diagramação:** Formatação automática da transcrição bruta.
        -   **Resumo Detalhado:** Criação de um resumo em formato Markdown (`.md`).
        -   **Mapa Mental:** Geração de um mapa mental em formato OPML 2.0 (`.opml`).
        -   **Estrutura de E-book:** Geração de uma estrutura de tópicos para um e-book.

### 2.2. Funcionalidades Futuras (Pós-MVP)
-   **Novos Provedores de IA:** Adicionar implementações para OpenAI (`OpenAIClient`) e Google Gemini (`GeminiClient`).
-   **Suporte a URLs:** Processamento de vídeos diretamente de URLs do YouTube.
-   **GUI (Interface Gráfica do Usuário):** Criação de uma interface simples para facilitar o uso.
-   **API Exponível:** Transformar a lógica do pipeline em uma API REST.

---

## 3. Arquitetura e Padrões de Codificação

### 3.1. Padrão Arquitetônico: Pipeline de Dados com Strategy
O sistema continuará a usar um padrão de **Pipeline de Dados**. A novidade é a aplicação do padrão de design **Strategy** (ou Adapter) para o componente de geração de conteúdo.

-   **Pipeline:** `Mídia` -> `Áudio` -> `Transcrição` -> `Conteúdo Estruturado`.
-   **Strategy para Geração de Conteúdo:**
    -   Uma classe base abstrata `BaseContentGenerator` definirá os métodos que todo gerador de conteúdo deve implementar (ex: `async summarize(text: str)`).
    -   Classes concretas como `AdaptaGenerator`, `OpenAIGenerator`, etc., herdarão da classe base e implementarão a lógica específica de cada API.
    -   O orquestrador do pipeline receberá uma instância do gerador de conteúdo escolhido na configuração, desacoplando o pipeline da implementação específica da API.

**Fluxo com Strategy:**
`Texto Formatado` -> **[Orchestrator escolhe a estratégia (ex: `AdaptaGenerator`)]** -> `AdaptaGenerator.summarize()` -> `Resumo.md`

### 3.2. Convenções de Codificação
-   **Estilo de Código:** PEP 8 (imposto por `black` e `isort`).
-   **Tipagem Estática:** `Type Hinting` obrigatório.
-   **Princípio da Responsabilidade Única (SRP):** Cada classe tem uma responsabilidade clara.
-   **Inversão de Dependência:** O pipeline dependerá da abstração (`BaseContentGenerator`), não das implementações concretas.

---

## 4. Stack de Tecnologia

| Categoria                | Ferramenta/Biblioteca                                      | Justificativa                                                                   |
| ------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------------- |
| **Linguagem**            | **Python 3.10+**                                           | Ecossistema maduro para IA, automação e processamento de dados.                 |
| **IA e Transcrição**     | **`faster-whisper`, `numba`, `CUDA`**                      | Desempenho otimizado para transcrição local, com suporte a GPU.                 |
| **Geração de Conteúdo**  | **`requests`, `httpx` (para async), `openai`, `google-generativeai`** | Bibliotecas específicas para cada API, encapsuladas por trás de uma interface comum. |
| **Processamento de Mídia** | **`ffmpeg` (via `subprocess`), `pydub`**                   | Padrão da indústria para manipulação de áudio/vídeo. `pydub` simplifica tarefas. |
| **Processamento de Texto** | **`spacy`**                                                | Ferramenta robusta e eficiente para análise de texto e segmentação de sentenças. |
| **Execução Paralela**    | **`asyncio`, `concurrent.futures.ThreadPoolExecutor`**     | Essencial para lidar com I/O (chamadas de API) de forma não-bloqueante e paralela. |
| **Gerenciamento de Segredos** | **`python-dotenv`**                                        | Separa segredos do código, melhorando a segurança e a portabilidade.            |
| **Logging**              | **`loguru` ou `logging` (padrão)**                         | Fornece um sistema de log mais informativo e configurável do que `print()`.     |
| **CLI (Interface de Linha de Comando)** | **`typer` ou `click`**                               | Facilita a criação de CLIs robustas e auto-documentadas.                        |
| **Modelagem de Dados**     | **`pydantic`**                                             | Garante a validação de dados e a clareza das estruturas de dados do sistema.    |

---

## 5. Estrutura do Projeto (Blueprint)

A estrutura de diretórios é adaptada para acomodar múltiplos provedores de IA de forma clara.

```
contentgen-pipeline/
├── .env                    # Arquivo para segredos (cookies, API keys) - NÃO versionar.
├── .gitignore              # Arquivos e pastas a serem ignorados pelo Git.
├── pyproject.toml          # Gerenciamento de dependências e projeto (Poetry).
├── README.md               # Documentação geral do projeto.
└── src/
    └── contentgen_pipeline/
        ├── __init__.py
        ├── main.py         # Ponto de entrada da aplicação (invoca a CLI).
        ├── cli.py          # Definição dos comandos da CLI.
        ├── config.py       # Carregamento e validação das configurações.
        ├── data_models.py  # Modelos de dados (Curso, Vídeo, etc.).
        │
        ├── core/           # Módulos com a lógica de negócio principal.
        │   ├── __init__.py
        │   ├── media_processor.py # Lida com extração de áudio e metadados.
        │   └── transcriber.py     # Encapsula a lógica de transcrição.
        │
        ├── generators/     # Módulo para os geradores de conteúdo (Strategy Pattern).
        │   ├── __init__.py
        │   ├── base.py            # Define a interface BaseContentGenerator.
        │   ├── adapta_generator.py # Implementação para a API Adapta.one.
        │   └── openai_generator.py # Implementação para a API OpenAI (exemplo futuro).
        │
        ├── pipeline/       # Módulos que orquestram o fluxo de trabalho.
        │   ├── __init__.py
        │   └── orchestrator.py    # Define e executa o pipeline, injetando o generator.
        │
        ├── utils/          # Funções de utilidade e helpers.
        │   ├── __init__.py
        │   ├── error_handler.py   # Decoradores para retentativas (retry).
        │   ├── file_handler.py    # Funções para manipulação de arquivos.
        │   └── logger.py          # Configuração do sistema de logging.
        │
        └── prompts/        # Templates de prompts para a IA.
            ├── summarize.txt
            ├── create_mindmap.txt
            └── create_ebook_topics.txt
```

---

## 6. Melhores Práticas

-   **Gerenciamento de Segredos:** Nenhuma chave de API, token ou cookie será comitado no código. Todos os segredos serão gerenciados através de um arquivo `.env` e carregados em tempo de execução.
-   **Logging Robusto:** Todas as operações importantes, erros e avisos serão registrados usando um sistema de logging configurado.
-   **Tratamento de Erros:** Implementação de mecanismos de `try...except` em pontos críticos, especialmente em operações de I/O e chamadas de API.
-   **Retentativas (Retries) para API:** As chamadas para APIs externas implementarão uma política de retentativas com *exponential backoff*.
-   **Testabilidade:** A arquitetura desacoplada facilitará a criação de testes. Será possível testar o pipeline usando um "mock" (simulado) `ContentGenerator` sem fazer chamadas de rede reais.

---

## 7. Componentes Principais e Priorização

| Componente                        | Descrição                                                                                                  | Prioridade |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------- | ---------- |
| **`MediaProcessor`, `Transcriber`** | Componentes base do pipeline para processamento de mídia.                                                   | **Essencial** |
| **`BaseContentGenerator` (Interface)** | Define o contrato para todos os geradores de conteúdo.                                                     | **Essencial** |
| **`AdaptaGenerator` (Implementação)** | Primeira implementação concreta da interface de geração de conteúdo.                                        | **Essencial** |
| **`PipelineOrchestrator`**        | Orquestra o fluxo de trabalho, agora com injeção de dependência para o gerador de conteúdo.                   | **Essencial** |
| **`CLI Interface`**               | Ponto de entrada para o usuário, agora com uma opção para selecionar o provedor de IA (ex: `--provider adapta`). | **Importante** |
| **`Data Models (Pydantic)`**      | Define as estruturas de dados consistentes para o pipeline.                                                | **Importante** |
| **`Config Loader`**               | Carrega configurações, incluindo qual provedor de IA usar e suas respectivas credenciais.                   | **Importante** |
| **`OpenAIGenerator`, `GeminiGenerator`** | Implementações futuras para outros provedores de IA.                                                       | **Ótimo**   |
| **`Logging System`, `Error Handler`**| Componentes de suporte que aumentam a robustez do sistema.                                                 | **Ótimo**   |
| **`Web Agent Module`**            | Módulo separado para automação web, mantido como opcional.                                                 | **Opcional (Pós-MVP)** |