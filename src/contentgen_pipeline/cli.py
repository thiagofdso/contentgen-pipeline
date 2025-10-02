"""Interface de linha de comando para o ContentGen Pipeline.

Este módulo implementa a CLI usando Typer para facilitar o uso
do pipeline de geração de conteúdo.
"""

import asyncio
import subprocess
from pathlib import Path
from typing import Optional, cast, Dict, List

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .pipeline.orchestrator import PipelineOrchestrator
from .generators.adapta import GeminiGenerator, ClaudeGenerator, GPTGenerator
from .generators.base import BaseContentGenerator
from .config import settings
from .utils.logger import logger, setup_logger

app = typer.Typer(
    name="contentgen",
    help="Pipeline de geração de conteúdo a partir de arquivos de mídia",
    add_completion=False
)

console = Console()

@app.callback()
def main(
    log_level: str = typer.Option(
        "info",
        "--log-level",
        help="Nível de log do console (debug, info, warning, error)"
    )
):
    setup_logger(log_level)


def get_content_generator(generator_type: str):
    """Cria uma instância do gerador de conteúdo baseado no tipo especificado.
    
    Args:
        generator_type: Tipo do gerador ("gemini", "claude", "gpt").
        
    Returns:
        Instância do gerador de conteúdo.
        
    Raises:
        ValueError: Se o tipo de gerador não for suportado.
    """
    if generator_type == "gemini":
        return GeminiGenerator()
    elif generator_type == "claude":
        return ClaudeGenerator()
    elif generator_type == "gpt":
        return GPTGenerator()
    else:
        raise ValueError(f"Tipo de gerador não suportado: {generator_type}")



@app.command()
def process(
    path: Optional[Path] = typer.Argument(
        None,
        help="Caminho para arquivo de midia ou diretorio contendo arquivos de midia (padrao: VIDEO_FOLDER do .env)"
    ),
    generator: str = typer.Option(
        "gemini",
        "--generator", "-g",
        help="Tipo de gerador de conteudo padrao (gemini, claude, gpt)"
    ),
    summarize_generator: Optional[str] = typer.Option(
        None,
        "--summarize-generator",
        help="Gerador especifico para resumo (gemini, claude, gpt)"
    ),
    diagram_generator: Optional[str] = typer.Option(
        None,
        "--diagram-generator",
        help="Gerador especifico para diagramacao (gemini, claude, gpt)"
    ),
    mindmap_preprocess_generator: Optional[str] = typer.Option(
        None,
        "--mindmap-preprocess-generator",
        help="Gerador especifico para pre-processamento do mapa mental (gemini, claude, gpt)"
    ),
    mindmap_generator: Optional[str] = typer.Option(
        None,
        "--mindmap-generator",
        help="Gerador especifico para geracao do mapa mental (gemini, claude, gpt)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Diretorio de saida (padrao: mesmo diretorio dos arquivos de entrada)"
    ),
    extract_audio: bool = typer.Option(
        True,
        "--extract-audio/--no-extract-audio",
        help="Extrair audio do video (default: True)"
    ),
    transcribe: bool = typer.Option(
        True,
        "--transcribe/--no-transcribe",
        help="Transcrever audio (default: True)"
    ),
    diagram: bool = typer.Option(
        True,
        "--diagram/--no-diagram",
        help="Gerar diagramacao do texto (default: True)"
    ),
    summarize: bool = typer.Option(
        True,
        "--summarize/--no-summarize",
        help="Gerar resumo do texto (default: True)"
    ),
    mindmap: bool = typer.Option(
        False,
        "--mindmap/--no-mindmap",
        help="Gerar mapa mental (default: False)"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Modo verboso com logs detalhados"
    ),
    download: Optional[str] = typer.Option(
        None,
        "--download",
        help="URL de um video do YouTube para baixar antes do processamento"
    ),
    download_batch: Optional[Path] = typer.Option(
        None,
        "--download-batch",
        help="Caminho para arquivo CSV com URLs para baixar antes do processamento"
    )
):
    """Processa arquivos de midia atraves do pipeline completo ou parcial."""
    try:
        if verbose:
            logger.info("Modo verboso ativado")

        if download and download_batch:
            console.print("[red]Erro: utilize apenas --download ou --download-batch por execucao[/red]")
            raise typer.Exit(1)

        base_path = path
        if base_path is None:
            if settings.video_folder:
                base_path = Path(settings.video_folder)
                console.print(f"[blue]Usando diretorio padrao do .env: {base_path}[/blue]")
            else:
                console.print("[red]Erro: Nenhum caminho especificado e VIDEO_FOLDER nao configurado no .env[/red]")
                console.print("[yellow]Use: contentgen process <caminho> ou configure VIDEO_FOLDER no .env[/yellow]")
                raise typer.Exit(1)

        base_path = Path(base_path)
        single_download_dir: Optional[Path] = None
        batch_download_dir: Optional[Path] = None
        processing_path: Optional[Path] = None

        if download:
            treat_as_file = base_path.exists() and base_path.is_file()
            if not base_path.exists() and base_path.suffix:
                treat_as_file = True
            single_download_dir = base_path.parent if treat_as_file else base_path
            if single_download_dir.is_file():
                console.print(f"[red]Erro: Diretorio de download invalido: {single_download_dir}[/red]")
                raise typer.Exit(1)
            if not single_download_dir.exists():
                single_download_dir.mkdir(parents=True, exist_ok=True)
                if verbose:
                    console.print(f"[blue]Diretorio criado para download: {single_download_dir}[/blue]")
        elif download_batch:
            treat_as_file = base_path.exists() and base_path.is_file()
            if not base_path.exists() and base_path.suffix:
                treat_as_file = True
            batch_download_dir = base_path.parent if treat_as_file else base_path
            if batch_download_dir.is_file():
                console.print(f"[red]Erro: Diretorio de download invalido: {batch_download_dir}[/red]")
                raise typer.Exit(1)
            if not batch_download_dir.exists():
                batch_download_dir.mkdir(parents=True, exist_ok=True)
                if verbose:
                    console.print(f"[blue]Diretorio criado para download: {batch_download_dir}[/blue]")
        else:
            if not base_path.exists():
                console.print(f"[red]Erro: Caminho nao encontrado: {base_path}[/red]")
                raise typer.Exit(1)

        try:
            content_generator = get_content_generator(generator)
            console.print(f"[green]Gerador de conteudo inicializado: {generator}[/green]")
        except ValueError as exc:
            console.print(f"[red]Erro: {exc}")
            raise typer.Exit(1)

        generators = {
            "default": content_generator,
            "summarize": get_content_generator(summarize_generator or settings.summarize_generator or "gemini"),
            "diagram": get_content_generator(diagram_generator or settings.diagram_generator or "gemini"),
            "mindmap_preprocess": get_content_generator(mindmap_preprocess_generator or settings.mindmap_preprocess_generator or "gemini"),
            "mindmap": get_content_generator(mindmap_generator or settings.mindmap_generator or "gemini"),
        }

        if verbose:
            console.print("[blue]Geradores configurados:[/blue]")
            console.print(f"  Resumo: {generators['summarize'].get_provider_name()}")
            console.print(f"  Diagramacao: {generators['diagram'].get_provider_name()}")
            console.print(f"  Pre-processamento MM: {generators['mindmap_preprocess'].get_provider_name()}")
            console.print(f"  Geracao MM: {generators['mindmap'].get_provider_name()}")

        orchestrator = PipelineOrchestrator(cast(Dict[str, BaseContentGenerator], generators))

        if download_batch:
            csv_file = Path(download_batch)
            if not csv_file.exists():
                console.print(f"[red]Erro: Arquivo CSV nao encontrado: {csv_file}[/red]")
                raise typer.Exit(1)
            target_dir = batch_download_dir or base_path
            console.print(f"[blue]Baixando videos do arquivo: {csv_file}[/blue]")
            batch_results = asyncio.run(orchestrator.download_videos_from_csv(
                csv_path=csv_file,
                output_dir=target_dir,
                batch_size=50,
                interactive=False,
                overwrite=False,
                verbose=verbose,
            ))

            table = Table(title="Resultados do Download em Lote")
            table.add_column("URL", style="cyan", max_width=50)
            table.add_column("Status", style="green")
            table.add_column("Detalhes", style="yellow")

            success_count = 0
            error_count = 0
            for item in batch_results:
                url_value = item.get("url", "desconhecida")
                status_value = item.get("status", "desconhecido")
                detail = item.get("error", "") if status_value != "success" else item.get("file_path", "")
                if status_value == "success":
                    success_count += 1
                    status_style = "green"
                    status_text = "Sucesso"
                    detail = detail or "Arquivo gerado"
                else:
                    error_count += 1
                    status_style = "red"
                    status_text = "Erro"
                    detail = detail or "Nao informado"
                display_url = url_value if len(url_value) <= 50 else url_value[:47] + "..."
                table.add_row(display_url, f"[{status_style}]{status_text}[/{status_style}]", detail)

            console.print(table)
            console.print(f"[green]Downloads concluídos: {success_count}[/green]")
            if error_count:
                console.print(f"[red]Falhas no download: {error_count}[/red]")
            if success_count == 0:
                console.print("[red]Erro: Nenhum video foi baixado com sucesso.[/red]")
                raise typer.Exit(1)

            processing_path = target_dir.resolve()

        if download:
            if single_download_dir is None:
                console.print("[red]Erro interno: diretorio de download nao definido.[/red]")
                raise typer.Exit(1)
            console.print(f"[blue]Baixando video informado: {download}[/blue]")
            download_result = asyncio.run(orchestrator.download_single_video(
                url=download,
                output_dir=single_download_dir,
                overwrite=False,
                verbose=verbose,
            ))
            if download_result.get("status") != "success":
                console.print(f"[red]Erro ao baixar video: {download_result.get('error', 'Erro desconhecido')}[/red]")
                raise typer.Exit(1)
            file_path_str = download_result.get("file_path")
            if not file_path_str:
                console.print("[red]Erro: Caminho do arquivo baixado nao informado.[/red]")
                raise typer.Exit(1)
            downloaded_path = Path(file_path_str)
            if not downloaded_path.is_absolute():
                downloaded_path = (single_download_dir / downloaded_path).resolve()
            if not downloaded_path.exists():
                console.print(f"[red]Erro: Arquivo baixado nao encontrado: {downloaded_path}[/red]")
                raise typer.Exit(1)
            console.print(f"[green]Download concluido: {downloaded_path}[/green]")

            treat_as_file = True
            if original_path:
                if original_path.exists():
                    treat_as_file = original_path.is_file()
                elif not original_path.suffix:
                    treat_as_file = False
            processing_path = downloaded_path if treat_as_file else single_download_dir.resolve()

        if processing_path is None:
            processing_path = base_path.resolve()

        if not processing_path.exists():
            console.print(f"[red]Erro: Caminho nao encontrado: {processing_path}[/red]")
            raise typer.Exit(1)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Verificando componentes...", total=None)
            health_status = asyncio.run(orchestrator.health_check())
            progress.update(task, description="Componentes verificados")

        health_table = Table(title="Status dos Componentes")
        health_table.add_column("Componente", style="cyan")
        health_table.add_column("Status", style="green")

        for component, status in health_status.items():
            status_style = "green" if status == "healthy" else "red"
            health_table.add_row(component, f"[{status_style}]{status}[/{status_style}]")

        console.print(health_table)

        if processing_path.is_file():
            console.print(f"[blue]Processando arquivo: {processing_path.name}[/blue]")
            results = asyncio.run(orchestrator.process_single_file(
                processing_path,
                extract_audio=extract_audio,
                transcribe=transcribe,
                diagram=diagram,
                summarize=summarize,
                mindmap=mindmap,
            ))
            results = [results]
        else:
            console.print(f"[blue]Processando diretorio: {processing_path}[/blue]")
            results = asyncio.run(orchestrator.process_directory(
                processing_path,
                extract_audio=extract_audio,
                transcribe=transcribe,
                diagram=diagram,
                summarize=summarize,
                mindmap=mindmap,
            ))

        if results:
            results_table = Table(title="Resultados do Processamento")
            results_table.add_column("Arquivo", style="cyan")
            results_table.add_column("Status", style="green")
            results_table.add_column("Arquivos Gerados", style="yellow")

            for result in results:
                if result.get("status") == "success":
                    file_name = Path(result["media_path"]).name
                    generated_files: List[str] = []

                    if "transcript_files" in result:
                        transcript_files = result["transcript_files"]
                        if "transcript" in transcript_files:
                            generated_files.append("Transcricao .txt")
                        if "subtitles" in transcript_files:
                            generated_files.append("Legendas .srt")

                    if "content_files" in result:
                        content_files = result["content_files"]
                        if "diagrammed" in content_files:
                            generated_files.append("Texto diagramado")
                        if "summary" in content_files:
                            generated_files.append("Resumo")

                    status_style = "green"
                    status_text = "Sucesso"
                    files_text = ", ".join(generated_files) if generated_files else "Nenhum"
                else:
                    file_name = result.get("file", "Desconhecido")
                    status_style = "red"
                    status_text = "Erro"
                    files_text = result.get("error", "Erro desconhecido")

                results_table.add_row(
                    file_name,
                    f"[{status_style}]{status_text}[/{status_style}]",
                    files_text,
                )

            console.print(results_table)

            successful = sum(1 for r in results if r.get("status") == "success")
            failed = len(results) - successful

            console.print(f"[green]Processados com sucesso: {successful}[/green]")
            if failed > 0:
                console.print(f"[red]Falhas: {failed}[/red]")
        else:
            console.print("[yellow]Nenhum arquivo foi processado.[/yellow]")

    except Exception as exc:
        logger.error(f"Erro durante o processamento: {str(exc)}")
        console.print(f"[red]Erro: {str(exc)}[/red]")
        raise typer.Exit(1)
@app.command()
def health(
    generator: str = typer.Option(
        "gemini",
        "--generator", "-g",
        help="Tipo de gerador de conteúdo para testar"
    )
):
    """Verifica a saúde de todos os componentes do pipeline."""
    try:
        # Criar gerador de conteúdo
        content_generator = get_content_generator(generator)
        
        # Criar orquestrador
        orchestrator = PipelineOrchestrator(content_generator)
        
        # Verificar saúde
        health_status = asyncio.run(orchestrator.health_check())
        
        # Exibir resultados
        health_table = Table(title="Status de Saúde do Pipeline")
        health_table.add_column("Componente", style="cyan")
        health_table.add_column("Status", style="green")
        health_table.add_column("Detalhes", style="yellow")
        
        for component, status in health_status.items():
            if status == "healthy":
                status_style = "green"
                status_text = "✅ Saudável"
                details = "Componente funcionando corretamente"
            elif status == "unhealthy":
                status_style = "red"
                status_text = "❌ Não Saudável"
                details = "Componente com problemas"
            elif status.startswith("error:"):
                status_style = "red"
                status_text = "❌ Erro"
                details = status[6:]  # Remove "error: "
            else:
                status_style = "yellow"
                status_text = "⚠️ Desconhecido"
                details = "Status não determinado"
            
            health_table.add_row(
                component,
                f"[{status_style}]{status_text}[/{status_style}]",
                details
            )
        
        console.print(health_table)
        
        # Resumo
        healthy_count = sum(1 for status in health_status.values() if status == "healthy")
        total_count = len(health_status)
        
        if healthy_count == total_count:
            console.print(f"\n[green]🎉 Todos os {total_count} componentes estão saudáveis![/green]")
        else:
            console.print(f"\n[yellow]⚠️ {healthy_count}/{total_count} componentes estão saudáveis.[/yellow]")
    
    except Exception as e:
        logger.error(f"Erro na verificação de saúde: {str(e)}")
        console.print(f"[red]Erro: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def download(
    csv_file: Optional[Path] = typer.Argument(
        None,
        help="Caminho para arquivo CSV com URLs dos vídeos (padrão: videos.csv)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Diretório de saída para os vídeos (padrão: VIDEO_FOLDER do .env)"
    ),
    batch_size: int = typer.Option(
        50,
        "--batch-size", "-b",
        help="Número de vídeos por lote (default: 50)"
    ),
    no_interactive: bool = typer.Option(
        False,
        "--no-interactive",
        help="Não perguntar para continuar entre lotes (executa tudo automaticamente)"
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Sobrescrever arquivos existentes"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Modo verboso com logs detalhados"
    )
):
    """Baixa vídeos do YouTube a partir de um arquivo CSV.
    
    O arquivo CSV deve ter uma coluna chamada 'url' com as URLs dos vídeos.
    """
    try:
        # Determinar arquivo CSV
        if csv_file is None:
            csv_file = Path("videos.csv")
            if not csv_file.exists():
                console.print("[yellow]Arquivo videos.csv não encontrado. Criando exemplo...[/yellow]")
                # Criar orquestrador temporário para criar o CSV
                temp_orchestrator = PipelineOrchestrator({})
                asyncio.run(temp_orchestrator.create_example_csv(csv_file))
                console.print(f"[green]Arquivo de exemplo criado: {csv_file}[/green]")
                console.print("[blue]Adicione as URLs dos vídeos na coluna 'url' e execute novamente.[/blue]")
                raise typer.Exit(0)
        
        # Validar arquivo CSV
        if not csv_file.exists():
            console.print(f"[red]Erro: Arquivo CSV não encontrado: {csv_file}[/red]")
            raise typer.Exit(1)
        
        # Criar orquestrador
        default_generator = GeminiGenerator()
        generators = {
            "default": default_generator,
            "summarize": default_generator,
            "diagram": default_generator,
            "mindmap_preprocess": default_generator,
            "mindmap": default_generator
        }
        orchestrator = PipelineOrchestrator(generators)
        
        # Executar download via orquestrador
        console.print(f"[blue]Iniciando download de vídeos do arquivo: {csv_file}[/blue]")
        
        results = asyncio.run(orchestrator.download_videos_from_csv(
            csv_path=csv_file,
            output_dir=output_dir,
            batch_size=batch_size,
            interactive=not no_interactive,
            overwrite=overwrite,
            verbose=verbose
        ))
        
        # Exibir resultados
        if results:
            results_table = Table(title="Resultados dos Downloads")
            results_table.add_column("URL", style="cyan", max_width=50)
            results_table.add_column("Status", style="green")
            results_table.add_column("Detalhes", style="yellow")
            
            successful = 0
            failed = 0
            skipped = 0
            
            for result in results:
                url = result.get("url", "Desconhecida")
                status = result.get("status", "desconhecido")
                
                if status == "success":
                    status_style = "green"
                    status_text = "✅ Sucesso"
                    details = "Vídeo baixado com sucesso"
                    successful += 1
                elif status == "skipped":
                    status_style = "yellow"
                    status_text = "⏭️ Pulado"
                    details = result.get("error", "URL inválida")
                    skipped += 1
                else:
                    status_style = "red"
                    status_text = "❌ Erro"
                    details = result.get("error", "Erro desconhecido")
                    failed += 1
                
                # Truncar URL para exibição
                display_url = url[:47] + "..." if len(url) > 50 else url
                
                results_table.add_row(
                    display_url,
                    f"[{status_style}]{status_text}[/{status_style}]",
                    details
                )
            
            console.print(results_table)
            
            # Estatísticas
            console.print(f"\n[green]✅ Sucessos: {successful}[/green]")
            if failed > 0:
                console.print(f"[red]❌ Falhas: {failed}[/red]")
            if skipped > 0:
                console.print(f"[yellow]⏭️ Pulados: {skipped}[/yellow]")
        
        else:
            console.print("[yellow]Nenhum vídeo foi processado.[/yellow]")
    
    except Exception as e:
        logger.error(f"Erro durante o download: {str(e)}")
        console.print(f"[red]Erro: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def download_url(
    url: str = typer.Argument(
        ...,
        help="URL do vídeo do YouTube para baixar"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Diretório de saída para o vídeo (padrão: VIDEO_FOLDER do .env)"
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Sobrescrever arquivo existente"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Modo verboso com logs detalhados"
    )
):
    """Baixa um único vídeo do YouTube a partir da URL fornecida."""
    try:
        # Validar URL
        if not url.strip().startswith('http'):
            console.print("[red]Erro: URL inválida. Deve começar com 'http'[/red]")
            raise typer.Exit(1)
        
        # Criar orquestrador
        default_generator = GeminiGenerator()
        generators = {
            "default": default_generator,
            "summarize": default_generator,
            "diagram": default_generator,
            "mindmap_preprocess": default_generator,
            "mindmap": default_generator
        }
        orchestrator = PipelineOrchestrator(generators)
        
        # Executar download via orquestrador
        console.print(f"[blue]Baixando vídeo: {url}[/blue]")
        
        result = asyncio.run(orchestrator.download_single_video(
            url=url,
            output_dir=output_dir,
            overwrite=overwrite,
            verbose=verbose
        ))
        
        # Exibir resultado
        if result["status"] == "success":
            console.print(f"[green]✅ Vídeo baixado com sucesso![/green]")
            if result.get("file_path"):
                console.print(f"[blue]Arquivo: {result['file_path']}[/blue]")
        else:
            console.print(f"[red]❌ Erro ao baixar vídeo: {result.get('error', 'Erro desconhecido')}[/red]")
            raise typer.Exit(1)
    
    except Exception as e:
        logger.error(f"Erro durante o download: {str(e)}")
        console.print(f"[red]Erro: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def version():
    """Exibe a versão do ContentGen Pipeline."""
    # TODO: Implementar versão dinâmica
    console.print("[blue]ContentGen Pipeline v1.0.0[/blue]")


@app.command()
def watch(
    path: Optional[Path] = typer.Argument(
        None,
        help="Diretório a ser monitorado para novos arquivos de mídia (padrão: VIDEO_FOLDER do .env)"
    ),
    generator: str = typer.Option(
        "gemini",
        "--generator", "-g",
        help="Tipo de gerador de conteúdo padrão (gemini, claude, gpt)"
    ),
    summarize_generator: str = typer.Option(
        None,
        "--summarize-generator",
        help="Gerador específico para resumo (gemini, claude, gpt)"
    ),
    diagram_generator: str = typer.Option(
        None,
        "--diagram-generator",
        help="Gerador específico para diagramação (gemini, claude, gpt)"
    ),
    mindmap_preprocess_generator: str = typer.Option(
        None,
        "--mindmap-preprocess-generator",
        help="Gerador específico para pré-processamento do mapa mental (gemini, claude, gpt)"
    ),
    mindmap_generator: str = typer.Option(
        None,
        "--mindmap-generator",
        help="Gerador específico para geração do mapa mental (gemini, claude, gpt)"
    ),
    max_cycles: Optional[int] = typer.Option(
        None,
        "--max-cycles",
        help="Número máximo de ciclos de varredura (default: ilimitado)"
    ),
    no_limit: bool = typer.Option(
        False,
        "--no-limit",
        help="Executar ciclos ilimitados (ignora --max-cycles)"
    ),
    delay: float = typer.Option(
        10.0,
        "--delay",
        help="Delay (em segundos) entre cada varredura (default: 10)"
    ),
    extract_audio: bool = typer.Option(
        True,
        "--extract-audio/--no-extract-audio",
        help="Extrair áudio do vídeo (default: True)"
    ),
    transcribe: bool = typer.Option(
        True,
        "--transcribe/--no-transcribe",
        help="Transcrever áudio (default: True)"
    ),
    diagram: bool = typer.Option(
        True,
        "--diagram/--no-diagram",
        help="Gerar diagramação do texto (default: True)"
    ),
    summarize: bool = typer.Option(
        True,
        "--summarize/--no-summarize",
        help="Gerar resumo do texto (default: True)"
    ),
    mindmap: bool = typer.Option(
        False,
        "--mindmap/--no-mindmap",
        help="Gerar mapa mental (default: False)"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Modo verboso com logs detalhados"
    )
):
    """
    Monitora continuamente um diretório e processa novos arquivos de mídia automaticamente.
    """
    try:
        if verbose:
            logger.info("Modo verboso ativado")

        # Determinar o caminho a ser usado
        if path is None:
            if settings.video_folder:
                path = Path(settings.video_folder)
                console.print(f"[blue]Usando diretório padrão do .env: {path}[/blue]")
            else:
                console.print("[red]Erro: Nenhum caminho especificado e VIDEO_FOLDER não configurado no .env[/red]")
                console.print("[yellow]Use: contentgen watch <caminho> ou configure VIDEO_FOLDER no .env[/yellow]")
                raise typer.Exit(1)

        if not path.exists() or not path.is_dir():
            console.print(f"[red]Erro: Diretório não encontrado: {path}[/red]")
            raise typer.Exit(1)

        try:
            content_generator = get_content_generator(generator)
            console.print(f"[green]Gerador de conteúdo inicializado: {generator}[/green]")
        except ValueError as e:
            console.print(f"[red]Erro: {e}[/red]")
            raise typer.Exit(1)

        # Criar geradores específicos para cada etapa
        generators = {
            "default": content_generator,
            "summarize": get_content_generator(summarize_generator or settings.summarize_generator or "gemini"),
            "diagram": get_content_generator(diagram_generator or settings.diagram_generator or "gemini"),
            "mindmap_preprocess": get_content_generator(mindmap_preprocess_generator or settings.mindmap_preprocess_generator or "gemini"),
            "mindmap": get_content_generator(mindmap_generator or settings.mindmap_generator or "gemini")
        }

        # Log dos geradores configurados
        if verbose:
            console.print(f"[blue]Geradores configurados:[/blue]")
            console.print(f"  Resumo: {generators['summarize'].get_provider_name()}")
            console.print(f"  Diagramação: {generators['diagram'].get_provider_name()}")
            console.print(f"  Pré-processamento MM: {generators['mindmap_preprocess'].get_provider_name()}")
            console.print(f"  Geração MM: {generators['mindmap'].get_provider_name()}")

        orchestrator = PipelineOrchestrator(cast(Dict[str, BaseContentGenerator], generators))

        # Determina o número de ciclos
        cycles = None if no_limit else max_cycles

        console.print(f"[blue]Monitorando diretório: {path}[/blue]")
        asyncio.run(orchestrator.watch_directory(
            directory_path=path,
            extract_audio=extract_audio,
            transcribe=transcribe,
            diagram=diagram,
            summarize=summarize,
            mindmap=mindmap,
            delay=delay,
            max_cycles=cycles
        ))

    except Exception as e:
        logger.error(f"Erro durante o monitoramento: {str(e)}")
        console.print(f"[red]Erro: {str(e)}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app() 
