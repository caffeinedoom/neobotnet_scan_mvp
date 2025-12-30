"""
Scan Command Module

Trigger and monitor reconnaissance scans via AWS ECS.
"""
import typer
import boto3
import json
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import time

app = typer.Typer(help="Scan operations")
console = Console()

# Default modules for scanning
DEFAULT_MODULES = ["subfinder", "dnsx", "httpx"]


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
    
    return list(set(domains))


@app.command("run")
def run_scan(
    program: str = typer.Argument(..., help="Program name to scan"),
    domains: Optional[str] = typer.Option(
        None, "--domains", "-d",
        help="Additional domains to add (comma-separated)"
    ),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f",
        help="Path to file with domains (one per line)"
    ),
    modules: str = typer.Option(
        ",".join(DEFAULT_MODULES), "--modules", "-m",
        help="Scan modules to run (comma-separated)"
    ),
    scale: int = typer.Option(
        1, "--scale", "-s",
        help="Number of parallel tasks per consumer module (1-10)",
        min=1, max=10
    ),
    timeout: int = typer.Option(
        10800, "--timeout", "-t",
        help="Pipeline timeout in seconds (default: 3 hours = 10800s)",
        min=1800, max=86400
    ),
    wait: bool = typer.Option(
        False, "--wait", "-w",
        help="Wait for scan to complete"
    )
):
    """
    Run a reconnaissance scan on a program.
    
    The scan orchestrator will:
    1. Create the program if it doesn't exist
    2. Add any new domains
    3. Run the scan pipeline (Subfinder → DNSx + HTTPx → Katana)
    
    Example:
        neobotnet scan run hackerone --domains hackerone.com,api.hackerone.com
        neobotnet scan run hackerone --file domains.txt --wait
    """
    from ..config import get_config
    
    config = get_config()
    missing = config.validate()
    
    if missing:
        console.print("[bold red]❌ Configuration incomplete. Run 'neobotnet config' to check.[/bold red]")
        raise typer.Exit(1)
    
    # Parse domains
    domain_list = []
    if domains:
        domain_list.extend([d.strip().lower() for d in domains.split(',') if d.strip()])
    if file:
        domain_list.extend(read_domains_from_file(file))
    domain_list = list(set(domain_list))
    
    # Parse modules
    module_list = [m.strip() for m in modules.split(',') if m.strip()]
    
    console.print(f"\n[bold blue]🚀 Starting Scan[/bold blue]")
    console.print(f"   Program: {program}")
    console.print(f"   Domains: {len(domain_list) if domain_list else '(use existing)'}")
    console.print(f"   Modules: {', '.join(module_list)}")
    if scale > 1:
        console.print(f"   Scale: {scale}x parallel tasks per module")
    console.print(f"   Timeout: {timeout // 3600}h {(timeout % 3600) // 60}m ({timeout}s)")
    console.print()
    
    try:
        # Create ECS client
        ecs_client = boto3.client('ecs', region_name=config.aws.region)
        
        # Prepare container overrides with environment variables
        # Include OPERATOR_USER_ID for proper database associations
        import os
        operator_user_id = os.environ.get('OPERATOR_USER_ID', '')
        
        container_overrides = {
            "containerOverrides": [
                {
                    "name": "orchestrator",
                    "environment": [
                        {"name": "PROGRAM_NAME", "value": program},
                        {"name": "DOMAINS", "value": ",".join(domain_list)},
                        {"name": "MODULES", "value": ",".join(module_list)},
                        {"name": "OPERATOR_USER_ID", "value": operator_user_id},
                        {"name": "SCALE_FACTOR", "value": str(scale)},
                        {"name": "PIPELINE_TIMEOUT", "value": str(timeout)}
                    ]
                }
            ]
        }
        
        # Launch ECS task
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            progress.add_task("Launching orchestrator task...", total=None)
            
            response = ecs_client.run_task(
                cluster=config.aws.ecs_cluster,
                taskDefinition=config.aws.orchestrator_task_family,
                launchType='FARGATE',
                networkConfiguration={
                    'awsvpcConfiguration': {
                        'subnets': config.aws.subnets,
                        'securityGroups': [config.aws.security_group],
                        'assignPublicIp': 'ENABLED'
                    }
                },
                overrides=container_overrides,
                tags=[
                    {'key': 'Program', 'value': program},
                    {'key': 'Source', 'value': 'neobotnet-cli'}
                ]
            )
        
        if not response.get('tasks'):
            failures = response.get('failures', [])
            if failures:
                console.print(f"[bold red]❌ Task launch failed: {failures[0].get('reason')}[/bold red]")
            else:
                console.print("[bold red]❌ Task launch failed (unknown reason)[/bold red]")
            raise typer.Exit(1)
        
        task = response['tasks'][0]
        task_arn = task['taskArn']
        task_id = task_arn.split('/')[-1]
        
        console.print(f"[bold green]✅ Orchestrator launched![/bold green]")
        console.print(f"   Task ID: {task_id[:8]}...")
        console.print(f"   Status: {task['lastStatus']}")
        console.print()
        
        if wait:
            console.print("[dim]Waiting for scan to complete (Ctrl+C to detach)...[/dim]")
            wait_for_task(ecs_client, config.aws.ecs_cluster, task_arn)
        else:
            console.print(f"[dim]Monitor with: neobotnet scan status {task_id[:8]}[/dim]")
        
    except boto3.exceptions.Boto3Error as e:
        console.print(f"[bold red]❌ AWS Error: {e}[/bold red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")
        raise typer.Exit(1)


def wait_for_task(ecs_client, cluster: str, task_arn: str):
    """Wait for an ECS task to complete."""
    start_time = time.time()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Waiting for task...", total=None)
        
        while True:
            try:
                response = ecs_client.describe_tasks(
                    cluster=cluster,
                    tasks=[task_arn]
                )
                
                if not response.get('tasks'):
                    progress.update(task, description="[red]Task not found[/red]")
                    break
                
                ecs_task = response['tasks'][0]
                status = ecs_task['lastStatus']
                elapsed = int(time.time() - start_time)
                
                progress.update(task, description=f"Status: {status} ({elapsed}s)")
                
                if status == 'STOPPED':
                    exit_code = None
                    containers = ecs_task.get('containers', [])
                    if containers:
                        exit_code = containers[0].get('exitCode')
                    
                    progress.stop()
                    
                    if exit_code == 0:
                        console.print(f"\n[bold green]✅ Scan completed successfully! ({elapsed}s)[/bold green]")
                    else:
                        stop_reason = ecs_task.get('stoppedReason', 'Unknown')
                        console.print(f"\n[bold red]❌ Task stopped: {stop_reason} (exit: {exit_code})[/bold red]")
                    break
                
                time.sleep(10)
                
            except KeyboardInterrupt:
                progress.stop()
                console.print("\n[yellow]Detached. Task continues running.[/yellow]")
                console.print(f"[dim]Check logs: aws logs tail /aws/ecs/neobotnet-v2-dev --follow[/dim]")
                break


@app.command("status")
def scan_status(
    task_id: str = typer.Argument(..., help="ECS task ID (first 8 chars or full)")
):
    """Check status of a running scan task."""
    from ..config import get_config
    
    config = get_config()
    
    try:
        ecs_client = boto3.client('ecs', region_name=config.aws.region)
        
        # List tasks to find matching ID
        running = ecs_client.list_tasks(
            cluster=config.aws.ecs_cluster,
            family=config.aws.orchestrator_task_family,
            desiredStatus='RUNNING'
        )
        
        stopped = ecs_client.list_tasks(
            cluster=config.aws.ecs_cluster,
            family=config.aws.orchestrator_task_family,
            desiredStatus='STOPPED'
        )
        
        all_tasks = running.get('taskArns', []) + stopped.get('taskArns', [])
        
        # Find matching task
        matching_arn = None
        for arn in all_tasks:
            if task_id in arn:
                matching_arn = arn
                break
        
        if not matching_arn:
            console.print(f"[yellow]Task not found: {task_id}[/yellow]")
            console.print("[dim]Note: ECS tasks are only retained for a short time after stopping.[/dim]")
            raise typer.Exit(1)
        
        # Get task details
        response = ecs_client.describe_tasks(
            cluster=config.aws.ecs_cluster,
            tasks=[matching_arn]
        )
        
        if not response.get('tasks'):
            console.print("[red]Task details not available[/red]")
            raise typer.Exit(1)
        
        task = response['tasks'][0]
        full_id = matching_arn.split('/')[-1]
        
        console.print(f"\n[bold]Task: {full_id[:16]}...[/bold]")
        console.print(f"   Status: {task['lastStatus']}")
        console.print(f"   Desired: {task['desiredStatus']}")
        console.print(f"   Created: {task.get('createdAt', 'N/A')}")
        
        if task['lastStatus'] == 'STOPPED':
            console.print(f"   Stopped: {task.get('stoppedAt', 'N/A')}")
            console.print(f"   Reason: {task.get('stoppedReason', 'N/A')}")
            
            containers = task.get('containers', [])
            if containers:
                console.print(f"   Exit Code: {containers[0].get('exitCode', 'N/A')}")
        
        console.print(f"\n[dim]View logs: aws logs tail /aws/ecs/neobotnet-v2-dev --filter-pattern '{full_id[:8]}'[/dim]")
        
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")
        raise typer.Exit(1)


@app.command("list")
def list_scans(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of scans to show"),
    status: str = typer.Option("all", "--status", "-s", help="Filter by status: running, stopped, all")
):
    """List recent scan tasks."""
    from ..config import get_config
    
    config = get_config()
    
    try:
        ecs_client = boto3.client('ecs', region_name=config.aws.region)
        
        all_arns = []
        
        if status in ['running', 'all']:
            running = ecs_client.list_tasks(
                cluster=config.aws.ecs_cluster,
                family=config.aws.orchestrator_task_family,
                desiredStatus='RUNNING'
            )
            all_arns.extend(running.get('taskArns', []))
        
        if status in ['stopped', 'all']:
            stopped = ecs_client.list_tasks(
                cluster=config.aws.ecs_cluster,
                family=config.aws.orchestrator_task_family,
                desiredStatus='STOPPED'
            )
            all_arns.extend(stopped.get('taskArns', []))
        
        if not all_arns:
            console.print("[yellow]No scan tasks found.[/yellow]")
            return
        
        # Get task details
        response = ecs_client.describe_tasks(
            cluster=config.aws.ecs_cluster,
            tasks=all_arns[:limit]
        )
        
        tasks = response.get('tasks', [])
        
        table = Table(title=f"Recent Scans ({len(tasks)} shown)")
        table.add_column("Task ID", style="dim", max_width=12)
        table.add_column("Status", justify="center")
        table.add_column("Created", style="green")
        table.add_column("Exit", justify="center")
        
        for task in tasks:
            task_id = task['taskArn'].split('/')[-1][:12]
            status_str = task['lastStatus']
            created = str(task.get('createdAt', ''))[:19]
            
            exit_code = "—"
            if task.get('containers'):
                ec = task['containers'][0].get('exitCode')
                if ec is not None:
                    exit_code = "✅" if ec == 0 else f"❌ {ec}"
            
            # Color status
            if status_str == 'RUNNING':
                status_str = f"[blue]{status_str}[/blue]"
            elif status_str == 'STOPPED':
                status_str = f"[dim]{status_str}[/dim]"
            
            table.add_row(task_id, status_str, created, exit_code)
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")
        raise typer.Exit(1)

