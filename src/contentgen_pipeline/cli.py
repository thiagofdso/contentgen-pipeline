"""Interface de linha de comando para o ContentGen Pipeline.

Este módulo implementa a CLI usando Typer para facilitar o uso
do pipeline de geração de conteúdo.
"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .pipeline.orchestrator import PipelineOrchestrator
from .generators.adapta import GeminiGenerator, ClaudeGenerator, GPTGenerator
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
    path: Path = typer.Argument(
        ...,
        help="Caminho para arquivo de mídia ou diretório contendo arquivos de mídia"
    ),
    generator: str = typer.Option(
        "gemini",
        "--generator", "-g",
        help="Tipo de gerador de conteúdo (gemini, claude, gpt)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Diretório de saída (padrão: mesmo diretório dos arquivos de entrada)"
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
    """Processa arquivos de mídia através do pipeline completo ou parcial.
    
    Permite escolher quais etapas executar: extração de áudio, transcrição, diagramação, resumo, mapa mental.
    """
    try:
        # Configurar nível de log
        if verbose:
            logger.info("Modo verboso ativado")
        
        # Validar caminho de entrada
        if not path.exists():
            console.print(f"[red]Erro: Caminho não encontrado: {path}[/red]")
            raise typer.Exit(1)
        
        # Criar gerador de conteúdo
        try:
            content_generator = get_content_generator(generator)
            console.print(f"[green]Gerador de conteúdo inicializado: {generator}[/green]")
        except ValueError as e:
            console.print(f"[red]Erro: {e}[/red]")
            raise typer.Exit(1)
        
        # Criar orquestrador
        orchestrator = PipelineOrchestrator(content_generator)
        
        # Verificar saúde dos componentes
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Verificando componentes...", total=None)
            health_status = asyncio.run(orchestrator.health_check())
            progress.update(task, description="Componentes verificados")
        
        # Exibir status de saúde
        health_table = Table(title="Status dos Componentes")
        health_table.add_column("Componente", style="cyan")
        health_table.add_column("Status", style="green")
        
        for component, status in health_status.items():
            status_style = "green" if status == "healthy" else "red"
            health_table.add_row(component, f"[{status_style}]{status}[/{status_style}]")
        
        console.print(health_table)
        
        # Processar arquivo ou diretório
        if path.is_file():
            console.print(f"[blue]Processando arquivo: {path.name}[/blue]")
            results = asyncio.run(orchestrator.process_single_file(
                path,
                extract_audio=extract_audio,
                transcribe=transcribe,
                diagram=diagram,
                summarize=summarize,
                mindmap=mindmap
            ))
            results = [results]  # Converter para lista para compatibilidade
        else:
            console.print(f"[blue]Processando diretório: {path}[/blue]")
            results = asyncio.run(orchestrator.process_directory(
                path,
                extract_audio=extract_audio,
                transcribe=transcribe,
                diagram=diagram,
                summarize=summarize,
                mindmap=mindmap
            ))
        
        # Exibir resultados
        if results:
            results_table = Table(title="Resultados do Processamento")
            results_table.add_column("Arquivo", style="cyan")
            results_table.add_column("Status", style="green")
            results_table.add_column("Arquivos Gerados", style="yellow")
            
            for result in results:
                if result.get("status") == "success":
                    file_name = Path(result["media_path"]).name
                    generated_files = []
                    
                    # Adicionar arquivos de transcrição
                    if "transcript_files" in result:
                        transcript_files = result["transcript_files"]
                        if "transcript" in transcript_files:
                            generated_files.append("📄 .txt")
                        if "subtitles" in transcript_files:
                            generated_files.append("🎬 .srt")
                    
                    # Adicionar arquivos de conteúdo
                    if "content_files" in result:
                        content_files = result["content_files"]
                        if "diagrammed" in content_files:
                            generated_files.append("✏️ diagramado")
                        if "summary" in content_files:
                            generated_files.append("📝 resumo")
                    
                    status_style = "green"
                    status_text = "✅ Sucesso"
                    files_text = ", ".join(generated_files) if generated_files else "Nenhum"
                else:
                    file_name = result.get("file", "Desconhecido")
                    status_style = "red"
                    status_text = "❌ Erro"
                    files_text = result.get("error", "Erro desconhecido")
                
                results_table.add_row(
                    file_name,
                    f"[{status_style}]{status_text}[/{status_style}]",
                    files_text
                )
            
            console.print(results_table)
            
            # Estatísticas
            successful = sum(1 for r in results if r.get("status") == "success")
            failed = len(results) - successful
            
            console.print(f"\n[green]✅ Processados com sucesso: {successful}[/green]")
            if failed > 0:
                console.print(f"[red]❌ Falhas: {failed}[/red]")
        
        else:
            console.print("[yellow]Nenhum arquivo foi processado.[/yellow]")
    
    except Exception as e:
        logger.error(f"Erro durante o processamento: {str(e)}")
        console.print(f"[red]Erro: {str(e)}[/red]")
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
def version():
    """Exibe a versão do ContentGen Pipeline."""
    # TODO: Implementar versão dinâmica
    console.print("[blue]ContentGen Pipeline v1.0.0[/blue]")


if __name__ == "__main__":
    app() 