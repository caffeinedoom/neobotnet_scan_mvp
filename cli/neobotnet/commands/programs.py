"""
Programs (Assets) Command Module

Manage bug bounty programs and their domains.
"""
import typer
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from datetime import datetime
import uuid

app = typer.Typer(help="Program (asset) management")
console = Console()


def read_domains_from_file(file_path: Path) -> List[str]:
    """Read domains from a file, one per line."""
    if not file_path.exists():
        console.print(f"[bold red]❌ File not found: {file_path}[/bold red]")
        raise typer.Exit(1)
    
    domains = []
    with open(file_path, 'r') as f:
        for line in f:
            domain = line.strip()
            if domain and not domain.startswith('#'):
                domains.append(domain.lower())
    
    return list(set(domains))  # Deduplicate


@app.command("list")
def list_programs(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum programs to display")
):
    """List all programs (assets)."""
    from ..config import get_supabase_client
    
    try:
        client = get_supabase_client()
        result = client.table('assets').select(
            'id, name, description, is_active, created_at, updated_at'
        ).order('created_at', desc=True).limit(limit).execute()
        
        if not result.data:
            console.print("[yellow]No programs found.[/yellow]")
            return
        
        table = Table(title=f"Programs ({len(result.data)} shown)")
        table.add_column("ID", style="dim", max_width=8)
        table.add_column("Name", style="bold cyan")
        table.add_column("Active", justify="center")
        table.add_column("Created", style="green")
        table.add_column("Description", max_width=40)
        
        for program in result.data:
            created = program.get('created_at', '')[:10]
            active = "✅" if program.get('is_active') else "❌"
            desc = (program.get('description') or '')[:40]
            
            table.add_row(
                program['id'][:8],
                program['name'],
                active,
                created,
                desc
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")
        raise typer.Exit(1)


@app.command("show")
def show_program(
    name: str = typer.Argument(..., help="Program name or ID")
):
    """Show program details with domains."""
    from ..config import get_supabase_client
    
    try:
        client = get_supabase_client()
        
        # Try to find by name first, then by ID prefix
        result = client.table('assets').select('*').eq('name', name).execute()
        
        if not result.data:
            # Try by ID prefix
            result = client.table('assets').select('*').ilike('id', f'{name}%').execute()
        
        if not result.data:
            console.print(f"[bold red]❌ Program not found: {name}[/bold red]")
            raise typer.Exit(1)
        
        program = result.data[0]
        
        # Get domains
        domains_result = client.table('apex_domains').select(
            'domain, is_active, created_at'
        ).eq('asset_id', program['id']).execute()
        
        console.print(f"\n[bold blue]Program: {program['name']}[/bold blue]")
        console.print(f"   ID: {program['id']}")
        console.print(f"   Active: {'✅' if program.get('is_active') else '❌'}")
        console.print(f"   Created: {program.get('created_at', '')[:19]}")
        console.print(f"   Description: {program.get('description', 'N/A')}")
        console.print(f"   Bug Bounty URL: {program.get('bug_bounty_url', 'N/A')}")
        
        if domains_result.data:
            console.print(f"\n[bold]Domains ({len(domains_result.data)}):[/bold]")
            for d in domains_result.data:
                active = "✅" if d.get('is_active') else "❌"
                console.print(f"   {active} {d['domain']}")
        else:
            console.print("\n[yellow]No domains configured.[/yellow]")
        
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")
        raise typer.Exit(1)


@app.command("add")
def add_program(
    name: str = typer.Argument(..., help="Program name"),
    domains: Optional[str] = typer.Option(
        None, "--domains", "-d",
        help="Comma-separated domains (e.g., example.com,test.com)"
    ),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f",
        help="Path to file with domains (one per line)"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", "--desc",
        help="Program description"
    ),
    bug_bounty_url: Optional[str] = typer.Option(
        None, "--url",
        help="Bug bounty program URL"
    )
):
    """Add a new program with domains."""
    from ..config import get_supabase_client
    
    # Parse domains from both sources
    domain_list = []
    
    if domains:
        domain_list.extend([d.strip().lower() for d in domains.split(',') if d.strip()])
    
    if file:
        domain_list.extend(read_domains_from_file(file))
    
    # Deduplicate
    domain_list = list(set(domain_list))
    
    try:
        client = get_supabase_client()
        
        # Check if program exists
        existing = client.table('assets').select('id').eq('name', name).execute()
        
        if existing.data:
            console.print(f"[yellow]⚠️  Program '{name}' already exists. Adding domains...[/yellow]")
            asset_id = existing.data[0]['id']
        else:
            # Create new program
            # Use a system user ID for CLI-created programs
            system_user_id = '00000000-0000-0000-0000-000000000000'
            
            asset_data = {
                'id': str(uuid.uuid4()),
                'user_id': system_user_id,
                'name': name,
                'description': description or f'Created via CLI on {datetime.utcnow().date()}',
                'bug_bounty_url': bug_bounty_url,
                'is_active': True,
                'priority': 3,
                'tags': ['cli-created'],
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            insert_result = client.table('assets').insert(asset_data).execute()
            
            if not insert_result.data:
                console.print("[bold red]❌ Failed to create program[/bold red]")
                raise typer.Exit(1)
            
            asset_id = insert_result.data[0]['id']
            console.print(f"[bold green]✅ Created program: {name}[/bold green]")
        
        # Add domains
        if domain_list:
            # Get existing domains
            existing_domains = client.table('apex_domains').select('domain').eq('asset_id', asset_id).execute()
            existing_set = {d['domain'].lower() for d in (existing_domains.data or [])}
            
            # Filter new domains
            new_domains = [d for d in domain_list if d.lower() not in existing_set]
            
            if new_domains:
                domain_records = [
                    {
                        'id': str(uuid.uuid4()),
                        'asset_id': asset_id,
                        'domain': d,
                        'is_active': True,
                        'created_at': datetime.utcnow().isoformat(),
                        'updated_at': datetime.utcnow().isoformat()
                    }
                    for d in new_domains
                ]
                
                client.table('apex_domains').insert(domain_records).execute()
                console.print(f"[green]   Added {len(new_domains)} domains[/green]")
                
                if len(domain_list) > len(new_domains):
                    skipped = len(domain_list) - len(new_domains)
                    console.print(f"[dim]   Skipped {skipped} existing domains[/dim]")
            else:
                console.print("[dim]   All domains already exist[/dim]")
        
        console.print(f"\n[bold]Program ID: {asset_id}[/bold]")
        
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")
        raise typer.Exit(1)


@app.command("delete")
def delete_program(
    name: str = typer.Argument(..., help="Program name or ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")
):
    """Delete a program and all its data."""
    from ..config import get_supabase_client
    
    try:
        client = get_supabase_client()
        
        # Find program
        result = client.table('assets').select('id, name').eq('name', name).execute()
        
        if not result.data:
            result = client.table('assets').select('id, name').ilike('id', f'{name}%').execute()
        
        if not result.data:
            console.print(f"[bold red]❌ Program not found: {name}[/bold red]")
            raise typer.Exit(1)
        
        program = result.data[0]
        
        if not force:
            confirm = typer.confirm(
                f"Delete program '{program['name']}' ({program['id'][:8]})? This cannot be undone."
            )
            if not confirm:
                console.print("[dim]Cancelled.[/dim]")
                raise typer.Exit(0)
        
        # Delete (cascade will handle related data if configured)
        client.table('assets').delete().eq('id', program['id']).execute()
        
        console.print(f"[bold green]✅ Deleted program: {program['name']}[/bold green]")
        
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")
        raise typer.Exit(1)

