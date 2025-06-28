# Comandos de Download de Vídeos

O ContentGen Pipeline agora inclui comandos para baixar vídeos do YouTube usando yt-dlp.

## Pré-requisitos

1. **yt-dlp**: Instale o yt-dlp para download de vídeos
   ```bash
   pip install yt-dlp
   ```

2. **pandas**: Para processamento de arquivos CSV
   ```bash
   pip install pandas
   ```

## Comandos Disponíveis

### 1. Download de Múltiplos Vídeos (CSV)

Baixa vídeos listados em um arquivo CSV:

```bash
# Usar arquivo padrão (videos.csv)
contentgen download

# Especificar arquivo CSV
contentgen download meu_arquivo.csv

# Com opções
contentgen download videos.csv --batch-size 10 --no-interactive --verbose
```

**Opções:**
- `--output, -o`: Diretório de saída (padrão: VIDEO_FOLDER do .env)
- `--batch-size, -b`: Número de vídeos por lote (padrão: 50)
- `--no-interactive`: Não perguntar para continuar entre lotes
- `--overwrite`: Sobrescrever arquivos existentes
- `--verbose, -v`: Modo verboso

### 2. Download de URL Individual

Baixa um único vídeo do YouTube:

```bash
# Download básico
contentgen download-url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Com opções
contentgen download-url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --output ./videos --verbose
```

**Opções:**
- `--output, -o`: Diretório de saída
- `--overwrite`: Sobrescrever arquivo existente
- `--verbose, -v`: Modo verboso

## Formato do Arquivo CSV

O arquivo CSV deve ter uma coluna chamada `url` com as URLs dos vídeos:

```csv
url
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://www.youtube.com/watch?v=example2
https://www.youtube.com/watch?v=example3
```

## Exemplos de Uso

### Exemplo 1: Download Básico
```bash
# Criar arquivo CSV de exemplo (se não existir)
contentgen download

# Baixar vídeos
contentgen download videos.csv
```

### Exemplo 2: Download com Configurações Específicas
```bash
# Baixar em lotes de 5 vídeos, sem interação
contentgen download videos.csv --batch-size 5 --no-interactive --output ./meus_videos
```

### Exemplo 3: Download de URL Individual
```bash
# Baixar um vídeo específico
contentgen download-url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --verbose
```

### Exemplo 4: Verificar Saúde dos Componentes
```bash
# Verificar se yt-dlp está funcionando
contentgen health
```

## Integração com o Pipeline

Os vídeos baixados podem ser processados automaticamente pelo pipeline:

```bash
# 1. Baixar vídeos
contentgen download videos.csv --output ./videos

# 2. Processar vídeos baixados
contentgen process ./videos --generator gemini
```

## Tratamento de Erros

- **URLs inválidas**: São puladas automaticamente
- **Vídeos já existentes**: Não são baixados novamente (use `--overwrite` para forçar)
- **Erros de rede**: São registrados e o processo continua
- **yt-dlp não encontrado**: Exibe instruções de instalação

## Logs e Verbosidade

Use `--verbose` para ver logs detalhados:

```bash
contentgen download videos.csv --verbose
```

Isso mostrará:
- Comandos yt-dlp executados
- Progresso detalhado
- Informações de debug 