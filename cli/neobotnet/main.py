#!/usr/bin/env python3
"""
NeoBot-Net CLI - Main Entry Point

Usage:
    neobotnet scan run <program> [--domains example.com,test.com] [--file domains.txt]
    neobotnet scan status <scan-id>
    neobotnet programs list
    neobotnet programs add <name> [--domains example.com] [--file domains.txt]
    neobotnet config check
"""
import typer
from rich.console import Console

from . import __version__
from .commands import scan, programs

# Create main Typer app
app = typer.Typer(
    name="neobotnet",
    help="NeoBot-Net CLI - Operator Reconnaissance Scanner",
    add_completion=False
)

# Add sub-commands
app.add_typer(scan.app, name="scan", help="Scan operations")
app.add_typer(programs.app, name="programs", help="Program management")

console = Console()


@app.command()
def version():
    """Show CLI version."""
    console.print(f"[bold blue]NeoBot-Net CLI[/bold blue] v{__version__}")


@app.command("config")
def check_config():
    """Check CLI configuration."""
    from .config import get_config
    
    config = get_config()
    missing = config.validate()
    
    if missing:
        console.print("[bold red]❌ Missing Configuration:[/bold red]")
        for item in missing:
            console.print(f"   • {item}")
        console.print("\n[dim]Set these as environment variables or in ~/.neobotnet/.env[/dim]")
        raise typer.Exit(1)
    
    console.print("[bold green]✅ Configuration Valid[/bold green]")
    console.print(f"   AWS Region: {config.aws.region}")
    console.print(f"   ECS Cluster: {config.aws.ecs_cluster}")
    console.print(f"   Orchestrator Task: {config.aws.orchestrator_task_family}")
    console.print(f"   Supabase: {config.supabase.url[:40]}...")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()

