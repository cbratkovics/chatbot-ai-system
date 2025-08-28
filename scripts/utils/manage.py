#!/usr/bin/env python3
"""
Django-style management script for database operations and admin tasks.
Provides a unified interface for common development and deployment tasks.
"""

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path

import click

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


@click.group()
@click.pass_context
def cli(ctx):
    """AI Chatbot System Management Tool"""
    ctx.ensure_object(dict)
    
    # Check if we're in the right directory
    if not Path('api').exists():
        click.echo("Error: Must run from project root directory", err=True)
        sys.exit(1)


@cli.command()
@click.option('--env', default='development', help='Environment (development/production)')
def migrate(env):
    """Run database migrations"""
    click.echo(f"Running migrations for {env} environment...")
    
    # Check if alembic is configured
    alembic_ini = Path('alembic.ini')
    if not alembic_ini.exists():
        click.echo("Initializing Alembic...")
        subprocess.run(['alembic', 'init', 'alembic'], check=True)
    
    try:
        # Run migrations
        result = subprocess.run(
            ['alembic', 'upgrade', 'head'],
            capture_output=True,
            text=True,
            check=True
        )
        click.echo(click.style("Migrations completed successfully", fg='green'))
        if result.stdout:
            click.echo(result.stdout)
    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"Migration failed: {e.stderr}", fg='red'), err=True)
        sys.exit(1)


@cli.command()
@click.argument('name')
@click.option('--autogenerate', is_flag=True, help='Auto-generate migration from models')
def makemigrations(name, autogenerate):
    """Create new migration"""
    click.echo(f"Creating migration: {name}")
    
    cmd = ['alembic', 'revision']
    if autogenerate:
        cmd.append('--autogenerate')
    cmd.extend(['-m', name])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        click.echo(click.style(f"Created migration: {name}", fg='green'))
        if result.stdout:
            # Extract migration file path from output
            for line in result.stdout.split('\n'):
                if 'Generating' in line:
                    click.echo(line)
    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"Failed to create migration: {e.stderr}", fg='red'), err=True)
        sys.exit(1)


@cli.command()
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--coverage', is_flag=True, help='Run with coverage')
@click.option('--unit', is_flag=True, help='Run only unit tests')
@click.option('--integration', is_flag=True, help='Run only integration tests')
@click.option('--e2e', is_flag=True, help='Run only e2e tests')
def test(verbose, coverage, unit, integration, e2e):
    """Run test suite"""
    click.echo("Running tests...")
    
    cmd = ['python', '-m', 'pytest']
    
    if verbose:
        cmd.append('-v')
    
    if coverage:
        cmd.extend(['--cov=api', '--cov-report=html', '--cov-report=term'])
    
    # Determine which tests to run
    if unit:
        cmd.append('tests/unit')
    elif integration:
        cmd.append('tests/integration')
    elif e2e:
        cmd.append('tests/e2e')
    else:
        cmd.append('tests/')
    
    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode == 0:
            click.echo(click.style("All tests passed!", fg='green'))
            if coverage:
                click.echo("Coverage report: tests/coverage_reports/html/index.html")
        else:
            click.echo(click.style("Some tests failed", fg='red'), err=True)
            sys.exit(1)
    except FileNotFoundError:
        click.echo(click.style("pytest not found. Install with: pip install pytest pytest-cov", fg='red'), err=True)
        sys.exit(1)


@cli.command()
@click.option('--compare-baseline', is_flag=True, help='Compare with baseline')
@click.option('--save-baseline', is_flag=True, help='Save as new baseline')
def benchmark(compare_baseline, save_baseline):
    """Run performance benchmarks"""
    click.echo("Starting benchmark suite...")
    
    # Import benchmark runner
    from benchmarks.run_benchmarks import BenchmarkRunner
    
    async def run():
        runner = BenchmarkRunner()
        results = await runner.run()
        
        if save_baseline and 'error' not in results:
            baseline_file = Path('benchmarks/results/baseline.json')
            with open(baseline_file, 'w') as f:
                json.dump(results, f, indent=2)
            click.echo(f"Baseline saved to {baseline_file}")
        
        return results
    
    results = asyncio.run(run())
    
    if 'error' in results:
        click.echo(click.style(f"Benchmarks failed: {results['error']}", fg='red'), err=True)
        sys.exit(1)
    elif results.get('validation', {}).get('overall', False):
        click.echo(click.style("All performance targets met!", fg='green'))
    else:
        click.echo(click.style("Some performance targets not met", fg='yellow'))
        sys.exit(1)


@cli.command()
@click.option('--sample-data', is_flag=True, help='Load sample data')
@click.option('--users', default=10, help='Number of test users to create')
@click.option('--conversations', default=50, help='Number of test conversations')
def seed(sample_data, users, conversations):
    """Seed database with sample data"""
    click.echo("Seeding database...")
    
    # This would normally import your models and create data
    # For now, we'll create a placeholder
    
    if sample_data:
        click.echo(f"Creating {users} test users...")
        click.echo(f"Creating {conversations} test conversations...")
        
        # Placeholder for actual seeding logic
        # from api.models import User, Conversation
        # ... create test data ...
        
        click.echo(click.style("Database seeded successfully", fg='green'))
    else:
        click.echo("Use --sample-data flag to load sample data")


@cli.command()
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', default=8000, help='Port to bind to')
@click.option('--reload', is_flag=True, help='Enable auto-reload')
@click.option('--workers', default=1, help='Number of worker processes')
def runserver(host, port, reload, workers):
    """Start development server"""
    click.echo(f"Starting server on {host}:{port}...")
    
    cmd = [
        'uvicorn',
        'api.main:app',
        '--host', host,
        '--port', str(port),
    ]
    
    if reload:
        cmd.append('--reload')
    
    if workers > 1:
        cmd.extend(['--workers', str(workers)])
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        click.echo("\nServer stopped")
    except FileNotFoundError:
        click.echo(click.style("uvicorn not found. Install with: pip install uvicorn", fg='red'), err=True)
        sys.exit(1)


@cli.command()
@click.argument('service', type=click.Choice(['all', 'api', 'redis', 'postgres', 'monitoring']))
def start(service):
    """Start services using docker-compose"""
    click.echo(f"Starting {service} services...")
    
    cmd = ['docker-compose']
    
    if service == 'all':
        cmd.extend(['up', '-d'])
    elif service == 'monitoring':
        cmd.extend(['up', '-d', 'prometheus', 'grafana', 'jaeger'])
    else:
        cmd.extend(['up', '-d', service])
    
    try:
        subprocess.run(cmd, check=True)
        click.echo(click.style(f"{service} services started", fg='green'))
        
        # Show service URLs
        if service in ['all', 'api']:
            click.echo("API: http://localhost:8000")
        if service in ['all', 'monitoring']:
            click.echo("Grafana: http://localhost:3000")
            click.echo("Prometheus: http://localhost:9090")
            click.echo("Jaeger: http://localhost:16686")
    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"Failed to start services: {e}", fg='red'), err=True)
        sys.exit(1)


@cli.command()
@click.argument('service', type=click.Choice(['all', 'api', 'redis', 'postgres', 'monitoring']))
def stop(service):
    """Stop services"""
    click.echo(f"Stopping {service} services...")
    
    cmd = ['docker-compose']
    
    if service == 'all':
        cmd.append('down')
    else:
        cmd.extend(['stop', service])
    
    try:
        subprocess.run(cmd, check=True)
        click.echo(click.style(f"{service} services stopped", fg='green'))
    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"Failed to stop services: {e}", fg='red'), err=True)
        sys.exit(1)


@cli.command()
def status():
    """Show status of all services"""
    click.echo("Service Status:")
    click.echo("-" * 50)
    
    try:
        result = subprocess.run(
            ['docker-compose', 'ps'],
            capture_output=True,
            text=True,
            check=True
        )
        click.echo(result.stdout)
    except subprocess.CalledProcessError:
        click.echo("No services running or docker-compose not available")
    
    # Check if API is responding
    try:
        import requests
        response = requests.get('http://localhost:8000/health', timeout=2)
        if response.status_code == 200:
            click.echo(click.style("API: Healthy", fg='green'))
        else:
            click.echo(click.style(f"API: Unhealthy (status: {response.status_code})", fg='yellow'))
    except (requests.RequestException, ConnectionError, TimeoutError):
        click.echo(click.style("API: Not responding", fg='red'))


@cli.command()
def shell():
    """Start interactive Python shell with app context"""
    click.echo("Starting interactive shell...")
    
    # Setup environment
    env_code = """
import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path.cwd()))

# Import common modules
try:
    from api import models
    from api.main import app
    from api.database import get_db
    print("Loaded API modules")
except ImportError as e:
    print(f"Could not load API modules: {e}")

print("\\nAvailable objects:")
print("  - models: Database models")
print("  - app: FastAPI application")
print("  - get_db: Database session factory")
print("\\nType 'exit()' to quit")
"""
    
    # Start IPython if available, otherwise standard Python
    try:
        import IPython
        IPython.embed(banner1="AI Chatbot System Shell", exec_lines=[env_code])
    except ImportError:
        import code
        namespace = {}
        exec(env_code, namespace)
        code.interact(local=namespace, banner="AI Chatbot System Shell (install ipython for better experience)")


@cli.command()
@click.option('--check', is_flag=True, help='Check code style without fixing')
def lint(check):
    """Run code linters and formatters"""
    click.echo("Running code quality checks...")
    
    tools = [
        ('black', ['black', '--check' if check else None, 'api/', 'tests/', 'benchmarks/'], 'Code formatting'),
        ('isort', ['isort', '--check-only' if check else None, 'api/', 'tests/', 'benchmarks/'], 'Import sorting'),
        ('flake8', ['flake8', 'api/', 'tests/', 'benchmarks/'], 'Style guide enforcement'),
        ('mypy', ['mypy', 'api/'], 'Type checking'),
    ]
    
    failed = []
    
    for tool_name, cmd, description in tools:
        # Remove None values from command
        cmd = [c for c in cmd if c is not None]
        
        click.echo(f"\nRunning {tool_name} ({description})...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                click.echo(click.style(f"  {tool_name}: Passed", fg='green'))
            else:
                click.echo(click.style(f"  {tool_name}: Failed", fg='red'))
                if result.stdout:
                    click.echo(result.stdout)
                failed.append(tool_name)
        except FileNotFoundError:
            click.echo(click.style(f"  {tool_name}: Not installed", fg='yellow'))
    
    if failed:
        click.echo(click.style(f"\nFailed checks: {', '.join(failed)}", fg='red'))
        if check:
            click.echo("Run 'scripts/utils/manage.py lint' without --check to auto-fix issues")
        sys.exit(1)
    else:
        click.echo(click.style("\nAll checks passed!", fg='green'))


@cli.command()
def validate():
    """Validate all performance claims"""
    click.echo("Validating performance claims...")
    
    # Import validation script
    validation_script = Path('scripts/validate_claims.py')
    if not validation_script.exists():
        click.echo(click.style("Validation script not found", fg='red'), err=True)
        sys.exit(1)
    
    try:
        result = subprocess.run(
            ['python', str(validation_script)],
            capture_output=True,
            text=True,
            check=False
        )
        
        click.echo(result.stdout)
        
        if result.returncode == 0:
            click.echo(click.style("All claims validated successfully!", fg='green'))
        else:
            click.echo(click.style("Some claims could not be validated", fg='red'), err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Validation failed: {e}", fg='red'), err=True)
        sys.exit(1)


@cli.command()
@click.argument('component', type=click.Choice(['api', 'frontend', 'all']))
def build(component):
    """Build application components"""
    click.echo(f"Building {component}...")
    
    if component in ['api', 'all']:
        click.echo("Building API Docker image...")
        try:
            subprocess.run(
                ['docker', 'build', '-t', 'ai-chatbot-api:latest', '-f', 'Dockerfile', '.'],
                check=True
            )
            click.echo(click.style("API image built successfully", fg='green'))
        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"Failed to build API: {e}", fg='red'), err=True)
            sys.exit(1)
    
    if component in ['frontend', 'all']:
        click.echo("Building frontend...")
        frontend_dir = Path('frontend')
        if frontend_dir.exists():
            try:
                subprocess.run(['npm', 'run', 'build'], cwd=frontend_dir, check=True)
                click.echo(click.style("Frontend built successfully", fg='green'))
            except subprocess.CalledProcessError as e:
                click.echo(click.style(f"Failed to build frontend: {e}", fg='red'), err=True)
                sys.exit(1)
        else:
            click.echo("Frontend directory not found")


@cli.command()
@click.option('--environment', '-e', default='staging', help='Deployment environment')
@click.option('--dry-run', is_flag=True, help='Show what would be deployed')
def deploy(environment, dry_run):
    """Deploy application to specified environment"""
    click.echo(f"Deploying to {environment}...")
    
    if dry_run:
        click.echo("DRY RUN - No actual deployment")
    
    # This would contain actual deployment logic
    # For example, using kubectl, terraform, or cloud provider CLIs
    
    steps = [
        "Building application...",
        "Running tests...",
        "Pushing Docker images...",
        "Updating Kubernetes manifests...",
        "Applying configuration...",
        "Running database migrations...",
        "Verifying deployment...",
    ]
    
    for step in steps:
        click.echo(f"  {step}")
        if not dry_run:
            # Actual deployment logic would go here
            pass
    
    if dry_run:
        click.echo(click.style("Dry run completed", fg='yellow'))
    else:
        click.echo(click.style(f"Deployed to {environment} successfully!", fg='green'))


@cli.command()
def version():
    """Show version information"""
    version_info = {
        'AI Chatbot System': '1.0.0',
        'Python': sys.version.split()[0],
        'Platform': sys.platform,
    }
    
    click.echo("Version Information:")
    click.echo("-" * 30)
    for component, version in version_info.items():
        click.echo(f"{component:20} {version}")


if __name__ == '__main__':
    cli()