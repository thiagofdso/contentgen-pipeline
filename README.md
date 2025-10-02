# ContentGen Pipeline

ContentGen Pipeline automatiza a extracao de audio, transcricao, resumo e geracao de materiais de estudo a partir de arquivos de midia.

## Requisitos

- Python 3.12
- [Poetry](https://python-poetry.org/) para gerenciar dependencias
- [FFmpeg](https://ffmpeg.org/) acessivel no PATH (necessario para extrair audio)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) instalado no PATH ou copiado para a pasta do projeto
  - Windows: instale via `pip install yt-dlp` ou baixe `yt-dlp.exe` e coloque ao lado do projeto
  - macOS/Linux: instale via `python3 -m pip install yt-dlp` ou gerenciador de pacotes

## Instalacao

```bash
git clone <url-do-repositorio>
cd contentgen-pipeline
poetry install
```

## Configuracao

1. Copie o arquivo `.env.example` para `.env`.
2. Edite `.env` e preencha as variaveis conforme necessario (autenticacao, pastas de midia, cookies, provedores de transcricao).
3. Verifique se `yt-dlp` e `ffmpeg` estao acessiveis no PATH antes de executar os comandos.

As variaveis disponiveis estao documentadas no proprio `.env.example`, incluindo opcoes para os provedores de transcricao (Distil-Whisper, Faster-Whisper, Gemini) e cookies de Facebook/Instagram.

## Uso basico

```bash
poetry run python -m src.contentgen_pipeline.main process <caminho>
```

### Opcoes relevantes do comando `process`

- `--download <url>`: baixa um video antes de iniciar o pipeline e processa o arquivo baixado.
- `--download-batch <arquivo.csv>`: baixa todas as URLs listadas em um CSV (coluna `url`) e, apos concluir o download, processa o diretorio de destino.
- `--output`, `--extract-audio`, `--transcribe`, `--diagram`, `--summarize`, `--mindmap`: controlam as etapas do pipeline como nas versoes anteriores.

Exemplos:

```bash
# Processa um diretorio existente
poetry run python -m src.contentgen_pipeline.main process ./midia

# Baixa um unico video para ./midia e processa o arquivo resultante
poetry run python -m src.contentgen_pipeline.main process ./midia --download https://youtu.be/<id>

# Baixa uma lista de videos definida em videos.csv e processa o diretorio
poetry run python -m src.contentgen_pipeline.main process ./midia --download-batch videos.csv
```

### Outros comandos CLI

```bash
poetry run python -m src.contentgen_pipeline.main download <videos.csv>
poetry run python -m src.contentgen_pipeline.main download-url <url>
poetry run python -m src.contentgen_pipeline.main health
```

## Testes rapidos

```bash
poetry run pytest
```

## Licenca

Projeto licenciado sob a Licenca MIT.
