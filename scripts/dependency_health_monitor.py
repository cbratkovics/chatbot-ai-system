#!/usr/bin/env python3
"""
Dependency health monitoring system for AI/ML projects.
Tracks package health, security, and provides actionable insights.
"""

import asyncio
import json
import logging
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

import click
import httpx
import toml
from rich.console import Console
from rich.progress import track
from rich.table import Table

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
console = Console()


@dataclass
class PackageHealth:
    """Health metrics for a package."""
    name: str
    current_version: str
    latest_version: str
    days_behind: int
    security_score: float
    popularity_score: float
    maintenance_score: float
    dependencies_count: int
    update_frequency: str
    last_release_date: str
    vulnerabilities: list[dict]
    recommendation: str


@dataclass 
class DependencyReport:
    """Complete dependency health report."""
    timestamp: str
    total_packages: int
    outdated_packages: int
    vulnerable_packages: int
    health_score: float
    critical_updates: list[str]
    package_health: list[PackageHealth]
    recommendations: list[str]


class DependencyHealthMonitor:
    """Monitor and analyze dependency health for AI/ML projects."""
    
    def __init__(self, project_root: Path | None = None):
        if project_root is None:
            project_root = Path.cwd()
        self.project_root = project_root
        self.pyproject_path = project_root / "pyproject.toml"
        self.cache_dir = project_root / ".dependency_cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.report_dir = project_root / "dependency_reports"
        self.report_dir.mkdir(exist_ok=True)
        
        # PyPI API base URL
        self.pypi_api = "https://pypi.org/pypi"
        
        # Package health thresholds
        self.thresholds = {
            "days_outdated_warning": 90,
            "days_outdated_critical": 180,
            "min_popularity_score": 0.5,
            "min_maintenance_score": 0.7,
        }
    
    async def get_package_info(self, package: str) -> dict | None:
        """Fetch package information from PyPI."""
        cache_file = self.cache_dir / f"{package}.json"
        
        # Check cache (24 hour expiry)
        if cache_file.exists():
            cache_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - cache_time < timedelta(hours=24):
                with open(cache_file) as f:
                    return json.load(f)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.pypi_api}/{package}/json")
                if response.status_code == 200:
                    data = response.json()
                    # Cache the response
                    with open(cache_file, 'w') as f:
                        json.dump(data, f)
                    return data
        except Exception as e:
            logger.warning(f"Failed to fetch info for {package}: {e}")
        
        return None
    
    def calculate_days_behind(self, current: str, latest: str, release_date: str) -> int:
        """Calculate how many days behind the current version is."""
        try:
            release_dt = datetime.fromisoformat(release_date.replace('Z', '+00:00'))
            return (datetime.now(release_dt.tzinfo) - release_dt).days
        except Exception:
            return 0
    
    def calculate_popularity_score(self, package_info: dict) -> float:
        """Calculate popularity score based on downloads and stars."""
        # Simplified scoring - in production would use pypistats API
        score = 0.5  # Base score
        
        # Check for GitHub stars if available
        if "project_urls" in package_info["info"]:
            urls = package_info["info"]["project_urls"] or {}
            if any("github" in str(url).lower() for url in urls.values()):
                score += 0.2
        
        # Check for documentation
        if package_info["info"].get("docs_url"):
            score += 0.1
        
        # Check for license
        if package_info["info"].get("license"):
            score += 0.1
        
        # Active releases
        releases = package_info.get("releases", {})
        if len(releases) > 10:
            score += 0.1
        
        return min(score, 1.0)
    
    def calculate_maintenance_score(self, package_info: dict) -> float:
        """Calculate maintenance score based on release frequency."""
        releases = package_info.get("releases", {})
        if not releases:
            return 0.0
        
        # Get release dates
        release_dates = []
        for version_files in releases.values():
            for file_info in version_files:
                if "upload_time_iso_8601" in file_info:
                    try:
                        dt = datetime.fromisoformat(file_info["upload_time_iso_8601"].replace('Z', '+00:00'))
                        release_dates.append(dt)
                    except Exception:
                        pass
        
        if not release_dates:
            return 0.5
        
        release_dates.sort()
        
        # Check recent activity
        latest_release = release_dates[-1]
        days_since_release = (datetime.now(latest_release.tzinfo) - latest_release).days
        
        if days_since_release < 30:
            return 1.0
        elif days_since_release < 90:
            return 0.9
        elif days_since_release < 180:
            return 0.7
        elif days_since_release < 365:
            return 0.5
        else:
            return 0.3
    
    def check_vulnerabilities(self, package: str, version: str) -> list[dict]:
        """Check for known vulnerabilities."""
        vulnerabilities = []
        
        try:
            # Use pip-audit for vulnerability checking
            result = subprocess.run(
                ["pip-audit", "--format", "json", "--desc", "on"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout:
                audit_data = json.loads(result.stdout)
                for vuln in audit_data.get("vulnerabilities", []):
                    if vuln.get("name") == package:
                        vulnerabilities.append({
                            "id": vuln.get("id"),
                            "description": vuln.get("description"),
                            "fix_version": vuln.get("fix_versions", ["Unknown"])[0]
                        })
        except Exception:
            pass
        
        return vulnerabilities
    
    def generate_recommendation(self, health: PackageHealth) -> str:
        """Generate actionable recommendation for a package."""
        if health.vulnerabilities:
            return f"🔴 CRITICAL: Update to {health.vulnerabilities[0]['fix_version']} to fix security vulnerabilities"
        
        if health.days_behind > self.thresholds["days_outdated_critical"]:
            return f"🟠 UPDATE: Package is {health.days_behind} days behind latest version"
        
        if health.maintenance_score < self.thresholds["min_maintenance_score"]:
            return "🟡 MONITOR: Package appears to be less actively maintained"
        
        if health.days_behind > self.thresholds["days_outdated_warning"]:
            return f"🟡 CONSIDER: Update to {health.latest_version} for improvements"
        
        return "✅ HEALTHY: Package is up-to-date and well-maintained"
    
    async def analyze_package(self, name: str, current_version: str) -> PackageHealth:
        """Analyze health of a single package."""
        package_info = await self.get_package_info(name)
        
        if not package_info:
            return PackageHealth(
                name=name,
                current_version=current_version,
                latest_version="Unknown",
                days_behind=0,
                security_score=0.5,
                popularity_score=0.5,
                maintenance_score=0.5,
                dependencies_count=0,
                update_frequency="Unknown",
                last_release_date="Unknown",
                vulnerabilities=[],
                recommendation="⚠️ Unable to fetch package information"
            )
        
        latest_version = package_info["info"]["version"]
        
        # Get latest release date
        releases = package_info.get("releases", {})
        latest_release_date = "Unknown"
        if latest_version in releases and releases[latest_version]:
            latest_release_date = releases[latest_version][0].get("upload_time_iso_8601", "Unknown")
        
        days_behind = self.calculate_days_behind(current_version, latest_version, latest_release_date)
        
        health = PackageHealth(
            name=name,
            current_version=current_version,
            latest_version=latest_version,
            days_behind=days_behind,
            security_score=1.0,  # Will be updated based on vulnerabilities
            popularity_score=self.calculate_popularity_score(package_info),
            maintenance_score=self.calculate_maintenance_score(package_info),
            dependencies_count=len(package_info["info"].get("requires_dist", [])),
            update_frequency=self._calculate_update_frequency(package_info),
            last_release_date=latest_release_date,
            vulnerabilities=self.check_vulnerabilities(name, current_version),
            recommendation=""
        )
        
        # Adjust security score based on vulnerabilities
        if health.vulnerabilities:
            health.security_score = 0.0
        
        health.recommendation = self.generate_recommendation(health)
        
        return health
    
    def _calculate_update_frequency(self, package_info: dict) -> str:
        """Calculate average update frequency."""
        releases = package_info.get("releases", {})
        if len(releases) < 2:
            return "Unknown"
        
        release_dates = []
        for version_files in releases.values():
            for file_info in version_files:
                if "upload_time_iso_8601" in file_info:
                    try:
                        dt = datetime.fromisoformat(file_info["upload_time_iso_8601"].replace('Z', '+00:00'))
                        release_dates.append(dt)
                        break
                    except Exception:
                        pass
        
        if len(release_dates) < 2:
            return "Unknown"
        
        release_dates.sort()
        
        # Calculate average days between releases (last 5 releases)
        recent_releases = release_dates[-5:]
        if len(recent_releases) < 2:
            return "Unknown"
        
        total_days = 0
        for i in range(1, len(recent_releases)):
            total_days += (recent_releases[i] - recent_releases[i-1]).days
        
        avg_days = total_days / (len(recent_releases) - 1)
        
        if avg_days < 14:
            return "Weekly"
        elif avg_days < 35:
            return "Monthly"
        elif avg_days < 100:
            return "Quarterly"
        elif avg_days < 200:
            return "Bi-annual"
        else:
            return "Annual"
    
    async def analyze_all_dependencies(self) -> DependencyReport:
        """Analyze all project dependencies."""
        if not self.pyproject_path.exists():
            logger.error("pyproject.toml not found")
            return None
        
        with open(self.pyproject_path) as f:
            pyproject = toml.load(f)
        
        dependencies = {}
        
        # Get main dependencies
        poetry_deps = pyproject.get("tool", {}).get("poetry", {}).get("dependencies", {})
        for name, spec in poetry_deps.items():
            if name != "python":
                # Extract version from spec
                version_str = spec if isinstance(spec, str) else spec.get("version", "*")
                # Remove version specifiers
                version_str = re.sub(r'[\^\~\>\<\=\!]', '', version_str)
                dependencies[name] = version_str
        
        # Analyze each package
        console.print("[bold blue]Analyzing dependency health...[/bold blue]")
        
        package_healths = []
        for name, version in track(dependencies.items(), description="Analyzing packages"):
            health = await self.analyze_package(name, version)
            package_healths.append(health)
        
        # Calculate overall health score
        total_score = sum(
            (h.security_score * 0.4 + h.popularity_score * 0.2 + 
             h.maintenance_score * 0.4) for h in package_healths
        ) / len(package_healths) if package_healths else 0
        
        # Generate report
        report = DependencyReport(
            timestamp=datetime.now().isoformat(),
            total_packages=len(dependencies),
            outdated_packages=sum(1 for h in package_healths if h.days_behind > 0),
            vulnerable_packages=sum(1 for h in package_healths if h.vulnerabilities),
            health_score=total_score,
            critical_updates=[h.name for h in package_healths if h.vulnerabilities],
            package_health=package_healths,
            recommendations=self._generate_recommendations(package_healths)
        )
        
        return report
    
    def _generate_recommendations(self, healths: list[PackageHealth]) -> list[str]:
        """Generate overall recommendations."""
        recommendations = []
        
        # Check for critical vulnerabilities
        vulnerable = [h for h in healths if h.vulnerabilities]
        if vulnerable:
            recommendations.append(
                f"🔴 Fix {len(vulnerable)} security vulnerabilities immediately"
            )
        
        # Check for severely outdated packages
        severely_outdated = [h for h in healths if h.days_behind > self.thresholds["days_outdated_critical"]]
        if severely_outdated:
            recommendations.append(
                f"🟠 Update {len(severely_outdated)} severely outdated packages"
            )
        
        # Check for unmaintained packages
        unmaintained = [h for h in healths if h.maintenance_score < 0.5]
        if unmaintained:
            recommendations.append(
                f"🟡 Consider replacing {len(unmaintained)} unmaintained packages"
            )
        
        if not recommendations:
            recommendations.append("✅ All dependencies are healthy!")
        
        return recommendations
    
    def save_report(self, report: DependencyReport) -> Path:
        """Save report to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.report_dir / f"health_report_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(asdict(report), f, indent=2)
        
        # Also save as latest
        latest_file = self.report_dir / "latest_report.json"
        with open(latest_file, 'w') as f:
            json.dump(asdict(report), f, indent=2)
        
        return report_file
    
    def display_report(self, report: DependencyReport):
        """Display report in terminal."""
        console.print("\n[bold]Dependency Health Report[/bold]")
        console.print(f"Generated: {report.timestamp}")
        console.print(f"Total Packages: {report.total_packages}")
        console.print(f"Outdated: {report.outdated_packages}")
        console.print(f"Vulnerable: {report.vulnerable_packages}")
        
        # Health score with color
        score_color = "green" if report.health_score > 0.8 else "yellow" if report.health_score > 0.6 else "red"
        console.print(f"Health Score: [{score_color}]{report.health_score:.2f}[/{score_color}]/1.00")
        
        # Recommendations
        if report.recommendations:
            console.print("\n[bold]Recommendations:[/bold]")
            for rec in report.recommendations:
                console.print(f"  {rec}")
        
        # Critical updates
        if report.critical_updates:
            console.print("\n[bold red]Critical Security Updates Required:[/bold red]")
            for pkg in report.critical_updates:
                console.print(f"  - {pkg}")
        
        # Package table
        table = Table(title="\nPackage Health Details")
        table.add_column("Package", style="cyan")
        table.add_column("Current", style="yellow")
        table.add_column("Latest", style="green")
        table.add_column("Days Behind")
        table.add_column("Maintenance")
        table.add_column("Recommendation")
        
        # Sort by health (vulnerabilities first, then days behind)
        sorted_health = sorted(
            report.package_health,
            key=lambda h: (len(h.vulnerabilities) > 0, h.days_behind),
            reverse=True
        )
        
        for health in sorted_health[:20]:  # Show top 20
            maint_color = "green" if health.maintenance_score > 0.7 else "yellow" if health.maintenance_score > 0.5 else "red"
            table.add_row(
                health.name,
                health.current_version,
                health.latest_version,
                str(health.days_behind) if health.days_behind > 0 else "✓",
                f"[{maint_color}]{health.maintenance_score:.1f}[/{maint_color}]",
                health.recommendation
            )
        
        console.print(table)
    
    def generate_markdown_report(self, report: DependencyReport) -> str:
        """Generate markdown formatted report."""
        md = []
        md.append("# Dependency Health Report")
        md.append(f"\n**Generated:** {report.timestamp}")
        md.append("\n## Summary")
        md.append(f"- **Total Packages:** {report.total_packages}")
        md.append(f"- **Outdated:** {report.outdated_packages}")
        md.append(f"- **Vulnerable:** {report.vulnerable_packages}")
        md.append(f"- **Health Score:** {report.health_score:.2f}/1.00")
        
        if report.recommendations:
            md.append("\n## Recommendations")
            for rec in report.recommendations:
                md.append(f"- {rec}")
        
        if report.critical_updates:
            md.append("\n## ⚠️ Critical Security Updates")
            for pkg in report.critical_updates:
                md.append(f"- **{pkg}** - Security vulnerability detected")
        
        md.append("\n## Package Details")
        md.append("\n| Package | Current | Latest | Days Behind | Health | Status |")
        md.append("|---------|---------|--------|-------------|--------|--------|")
        
        for health in sorted(report.package_health, key=lambda h: h.days_behind, reverse=True):
            status = "🔴" if health.vulnerabilities else "🟡" if health.days_behind > 90 else "✅"
            md.append(f"| {health.name} | {health.current_version} | {health.latest_version} | "
                     f"{health.days_behind} | {health.maintenance_score:.1f} | {status} |")
        
        return "\n".join(md)
    
    async def monitor_continuous(self, interval_hours: int = 24):
        """Run continuous monitoring."""
        console.print(f"[bold green]Starting continuous monitoring (every {interval_hours} hours)[/bold green]")
        
        while True:
            try:
                report = await self.analyze_all_dependencies()
                if report:
                    self.save_report(report)
                    self.display_report(report)
                    
                    # Check for critical issues
                    if report.vulnerable_packages > 0:
                        console.print("\n[bold red]⚠️ ALERT: Security vulnerabilities detected![/bold red]")
                
                # Wait for next check
                await asyncio.sleep(interval_hours * 3600)
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Monitoring stopped[/yellow]")
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error


@click.group()
def cli():
    """Dependency health monitoring for AI/ML projects."""
    pass


@cli.command()
@click.option('--format', type=click.Choice(['terminal', 'json', 'markdown']), 
              default='terminal', help='Output format')
@click.option('--save', is_flag=True, help='Save report to file')
def analyze(format: str, save: bool):
    """Analyze dependency health."""
    monitor = DependencyHealthMonitor()
    report = asyncio.run(monitor.analyze_all_dependencies())
    
    if not report:
        console.print("[red]Failed to generate report[/red]")
        return
    
    if format == 'terminal':
        monitor.display_report(report)
    elif format == 'json':
        print(json.dumps(asdict(report), indent=2))
    elif format == 'markdown':
        print(monitor.generate_markdown_report(report))
    
    if save:
        report_file = monitor.save_report(report)
        console.print(f"\n[green]Report saved to {report_file}[/green]")


@cli.command()
@click.option('--interval', type=int, default=24, help='Check interval in hours')
def monitor(interval: int):
    """Start continuous monitoring."""
    monitor = DependencyHealthMonitor()
    asyncio.run(monitor.monitor_continuous(interval))


@cli.command()
def dashboard():
    """Launch interactive dashboard (web UI)."""
    console.print("[yellow]Dashboard feature coming soon![/yellow]")
    console.print("For now, use 'analyze' command to generate reports")


if __name__ == "__main__":
    cli()