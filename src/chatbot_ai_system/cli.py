"""Command-line interface for AI Chatbot System."""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from chatbot_ai_system import __version__
from chatbot_ai_system.config import settings

app = typer.Typer(
    name="chatbotai",
    help="AI Chatbot System CLI - Manage and interact with your AI chatbot infrastructure",
    add_completion=True,
)
console = Console()


@app.callback()
def callback():
    """AI Chatbot System - Production-ready multi-provider chatbot platform."""
    pass


@app.command()
def version():
    """Display version information."""
    rprint(f"[bold green]AI Chatbot System[/bold green] version {__version__}")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Server host"),
    port: int = typer.Option(8000, "--port", "-p", help="Server port"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of workers"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload"),
    env: str = typer.Option("development", "--env", "-e", help="Environment"),
):
    """Start the API server."""
    import uvicorn
    
    console.print(Panel.fit(
        f"[bold cyan]Starting AI Chatbot API Server[/bold cyan]\n"
        f"Host: {host}:{port}\n"
        f"Workers: {workers}\n"
        f"Environment: {env}",
        title="Server Configuration"
    ))
    
    if reload:
        uvicorn.run(
            "chatbot_ai_system.server.main:app",
            host=host,
            port=port,
            reload=True,
            log_level="info",
        )
    else:
        uvicorn.run(
            "chatbot_ai_system.server.main:app",
            host=host,
            port=port,
            workers=workers,
            log_level="info",
        )


@app.command()
def config(
    show: bool = typer.Option(False, "--show", "-s", help="Show current configuration"),
    validate: bool = typer.Option(False, "--validate", "-v", help="Validate configuration"),
):
    """Manage application configuration."""
    if show:
        table = Table(title="Current Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in settings.model_dump().items():
            if "KEY" in key or "SECRET" in key or "PASSWORD" in key:
                value = "***HIDDEN***"
            table.add_row(key, str(value))
        
        console.print(table)
    
    if validate:
        try:
            settings.model_validate(settings.model_dump())
            rprint("[bold green]✓[/bold green] Configuration is valid")
        except Exception as e:
            rprint(f"[bold red]✗[/bold red] Configuration error: {e}")
            raise typer.Exit(1)


@app.command()
def chat(
    provider: str = typer.Option("openai", "--provider", "-p", help="AI provider to use"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    stream: bool = typer.Option(True, "--stream", help="Enable streaming responses"),
):
    """Interactive chat session with an AI model."""
    asyncio.run(_chat_session(provider, model, stream))


async def _chat_session(provider: str, model: Optional[str], stream: bool):
    """Run an interactive chat session."""
    from chatbot_ai_system.sdk import ChatbotClient
    
    client = ChatbotClient()
    
    console.print(Panel.fit(
        f"[bold cyan]AI Chat Session[/bold cyan]\n"
        f"Provider: {provider}\n"
        f"Model: {model or 'default'}\n"
        f"Streaming: {'enabled' if stream else 'disabled'}\n"
        f"Type 'exit' or 'quit' to end the session",
        title="Chat Configuration"
    ))
    
    while True:
        try:
            user_input = typer.prompt("\n[You]", prompt_suffix=" ")
            
            if user_input.lower() in ["exit", "quit"]:
                console.print("[yellow]Ending chat session...[/yellow]")
                break
            
            console.print("\n[AI] ", end="")
            
            if stream:
                async for chunk in client.chat_stream(
                    message=user_input,
                    provider=provider,
                    model=model
                ):
                    console.print(chunk, end="")
                console.print()
            else:
                response = await client.chat(
                    message=user_input,
                    provider=provider,
                    model=model
                )
                console.print(response)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Chat session interrupted[/yellow]")
            break
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")


@app.command()
def test(
    coverage: bool = typer.Option(False, "--coverage", "-c", help="Run with coverage"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Run test suite."""
    import subprocess
    
    cmd = ["pytest"]
    
    if coverage:
        cmd.extend(["--cov=chatbot_ai_system", "--cov-report=term-missing"])
    
    if verbose:
        cmd.append("-v")
    
    console.print("[cyan]Running tests...[/cyan]")
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        rprint("[bold green]✓[/bold green] All tests passed")
    else:
        rprint("[bold red]✗[/bold red] Some tests failed")
        raise typer.Exit(1)


@app.command()
def migrate(
    check: bool = typer.Option(False, "--check", help="Check for pending migrations"),
    rollback: int = typer.Option(0, "--rollback", help="Rollback N migrations"),
):
    """Manage database migrations."""
    console.print("[cyan]Migration management not yet implemented[/cyan]")


@app.command()
def health(
    url: str = typer.Option("http://localhost:8000", "--url", "-u", help="API URL"),
):
    """Check API health status."""
    import httpx
    
    try:
        response = httpx.get(f"{url}/health")
        if response.status_code == 200:
            data = response.json()
            rprint(f"[bold green]✓[/bold green] API is healthy")
            
            table = Table(title="Health Status")
            table.add_column("Component", style="cyan")
            table.add_column("Status", style="green")
            
            for key, value in data.items():
                table.add_row(key, str(value))
            
            console.print(table)
        else:
            rprint(f"[bold red]✗[/bold red] API returned status {response.status_code}")
    except Exception as e:
        rprint(f"[bold red]✗[/bold red] Failed to connect: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()