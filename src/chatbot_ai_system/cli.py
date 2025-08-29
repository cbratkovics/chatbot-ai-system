"""Command-line interface for AI Chatbot System."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional
from enum import Enum

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import uvicorn

from chatbot_ai_system import __version__, get_version
from chatbot_ai_system.config import settings
from chatbot_ai_system.sdk import ChatbotClient

app = typer.Typer(
    name="chatbotai",
    help="AI Chatbot System CLI - Production-ready multi-provider chatbot platform",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()


class OutputFormat(str, Enum):
    """Output format options."""
    json = "json"
    text = "text"
    table = "table"


@app.callback()
def callback():
    """AI Chatbot System - Enterprise-grade conversational AI platform."""
    pass


@app.command()
def version(
    format: OutputFormat = typer.Option(
        OutputFormat.text, "--format", "-f", help="Output format"
    ),
):
    """Display version and system information."""
    if format == OutputFormat.json:
        rprint(json.dumps({"version": __version__, "package": "chatbot-ai-system"}))
    elif format == OutputFormat.table:
        table = Table(title="AI Chatbot System Information")
        table.add_column("Component", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Version", __version__)
        table.add_row("Package", "chatbot-ai-system")
        table.add_row("Python", sys.version.split()[0])
        console.print(table)
    else:
        rprint(f"[bold green]AI Chatbot System[/bold green] v{__version__}")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Bind host"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of workers"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Auto-reload on changes"),
    env_file: Optional[Path] = typer.Option(None, "--env", "-e", help="Environment file"),
):
    """Start the API server with production configurations."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Starting server...", total=None)
        
        console.print(Panel.fit(
            f"[bold cyan]Starting AI Chatbot API Server[/bold cyan]\n"
            f"Host: [yellow]{host}:{port}[/yellow]\n"
            f"Workers: [yellow]{workers}[/yellow]\n"
            f"Reload: [yellow]{'enabled' if reload else 'disabled'}[/yellow]\n"
            f"Environment: [yellow]{env_file or 'default'}[/yellow]",
            title="🚀 Server Configuration"
        ))
        
        if env_file and env_file.exists():
            import dotenv
            dotenv.load_dotenv(env_file)
        
        uvicorn.run(
            "chatbot_ai_system.server.main:app",
            host=host,
            port=port,
            workers=1 if reload else workers,
            reload=reload,
            log_level="info",
            access_log=True,
            use_colors=True,
        )


@app.command()
def demo(
    provider: str = typer.Option("openai", "--provider", "-p", help="AI provider"),
    stream: bool = typer.Option(True, "--stream", "-s", help="Stream responses"),
):
    """Run interactive demo showcasing system capabilities."""
    asyncio.run(_run_demo(provider, stream))


async def _run_demo(provider: str, stream: bool):
    """Execute demo sequence."""
    console.print(Panel.fit(
        "[bold cyan]AI Chatbot System Demo[/bold cyan]\n"
        "This demo showcases multi-provider support, streaming, and failover capabilities.",
        title="🎭 Demo Mode"
    ))
    
    demos = [
        ("Simple greeting", "Hello! How are you today?"),
        ("Technical question", "Explain microservices architecture in 2 sentences."),
        ("Creative task", "Write a haiku about Python programming."),
    ]
    
    async with ChatbotClient() as client:
        # Health check
        with console.status("[bold green]Checking system health..."):
            health = await client.health_check()
            console.print(f"✅ System status: [green]{health['status']}[/green]")
        
        # Run demos
        for title, prompt in demos:
            console.print(f"\n[bold yellow]{title}:[/bold yellow]")
            console.print(f"[dim]User: {prompt}[/dim]")
            console.print("[dim]AI:[/dim] ", end="")
            
            if stream:
                async for chunk in client.chat_stream(prompt, provider=provider):
                    console.print(chunk, end="")
                console.print()
            else:
                response = await client.chat(prompt, provider=provider)
                console.print(response)


@app.command()
def bench(
    scenario: str = typer.Argument("quick", help="Benchmark scenario"),
    duration: int = typer.Option(30, "--duration", "-d", help="Test duration (seconds)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Run performance benchmarks."""
    from chatbot_ai_system.benchmarks import run_benchmark
    
    console.print(f"[bold cyan]Running benchmark: {scenario}[/bold cyan]")
    results = run_benchmark(scenario, duration)
    
    if output:
        output.write_text(json.dumps(results, indent=2))
        console.print(f"✅ Results saved to {output}")
    else:
        console.print(json.dumps(results, indent=2))


if __name__ == "__main__":
    app()