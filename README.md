# ContentGen Pipeline

Pipeline de automação para geração de conteúdo a partir de mídia.

## Descrição

O ContentGen Pipeline é uma ferramenta que automatiza o processo de transformação de arquivos de mídia (vídeos, áudios) em materiais de estudo estruturados, incluindo transcrições, resumos, legendas e mapas mentais.

## Instalação

```bash
# Clone o repositório
git clone <url-do-repositorio>
cd contentgen-pipeline

# Instale as dependências
poetry install
```

## Configuração

1. Copie o arquivo `.env.example` para `.env`
2. Preencha as variáveis de ambiente necessárias:
   - `ADAPTA_COOKIES_STR`: Cookies de autenticação do Adapta.one
   - `WHISPER_MODEL`: Modelo do Whisper a ser usado (padrão: medium)

## Uso

```bash
# Executar o pipeline
poetry run python -m contentgen_pipeline.main process <caminho-do-diretorio>
```

## Desenvolvimento

Este projeto está em desenvolvimento ativo. Consulte o arquivo `steps.md` para ver o progresso das funcionalidades. 