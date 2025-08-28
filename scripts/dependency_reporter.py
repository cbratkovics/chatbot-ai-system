#!/usr/bin/env python3
"""
Automated dependency reporting system.
Generates regular reports and notifications for dependency health.
"""

import json
import logging
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import click
import schedule
import toml
from jinja2 import Template
from rich.console import Console

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
console = Console()


@dataclass
class ReportConfig:
    """Configuration for dependency reporting."""
    schedule_time: str = "09:00"  # Daily at 9 AM
    weekly_day: str = "monday"    # Weekly report day
    email_enabled: bool = False
    email_recipients: list[str] = None
    slack_enabled: bool = False
    slack_webhook: str = None
    github_enabled: bool = True
    report_types: list[str] = None


class DependencyReporter:
    """Automated dependency reporting system."""
    
    def __init__(self, project_root: Path | None = None):
        if project_root is None:
            project_root = Path.cwd()
        self.project_root = project_root
        self.config_file = project_root / "config" / "dependency_reporter.toml"
        self.report_dir = project_root / "dependency_reports"
        self.report_dir.mkdir(exist_ok=True)
        
        self.config = self.load_config()
        
        # Report templates
        self.templates = {
            "email": self.get_email_template(),
            "slack": self.get_slack_template(),
            "markdown": self.get_markdown_template(),
        }
    
    def load_config(self) -> ReportConfig:
        """Load reporter configuration."""
        if self.config_file.exists():
            with open(self.config_file) as f:
                config_data = toml.load(f)
                return ReportConfig(**config_data.get("reporter", {}))
        
        # Create default config
        default_config = ReportConfig(
            report_types=["security", "updates", "health", "metrics"]
        )
        self.save_config(default_config)
        return default_config
    
    def save_config(self, config: ReportConfig):
        """Save reporter configuration."""
        self.config_file.parent.mkdir(exist_ok=True)
        
        config_dict = {"reporter": asdict(config)}
        with open(self.config_file, 'w') as f:
            toml.dump(config_dict, f)
    
    def get_email_template(self) -> Template:
        """Get email report template."""
        return Template("""
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; }
        .header { background: #2c3e50; color: white; padding: 20px; }
        .content { padding: 20px; }
        .alert { background: #e74c3c; color: white; padding: 10px; margin: 10px 0; }
        .warning { background: #f39c12; color: white; padding: 10px; margin: 10px 0; }
        .success { background: #27ae60; color: white; padding: 10px; margin: 10px 0; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #34495e; color: white; }
        .metrics { display: flex; justify-content: space-around; margin: 20px 0; }
        .metric { text-align: center; padding: 20px; background: #ecf0f1; }
        .metric-value { font-size: 2em; font-weight: bold; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Dependency Report - {{ project_name }}</h1>
        <p>Generated: {{ timestamp }}</p>
    </div>
    
    <div class="content">
        {% if critical_alerts %}
        <div class="alert">
            <h2>⚠️ Critical Alerts</h2>
            <ul>
            {% for alert in critical_alerts %}
                <li>{{ alert }}</li>
            {% endfor %}
            </ul>
        </div>
        {% endif %}
        
        <div class="metrics">
            <div class="metric">
                <div class="metric-value">{{ total_packages }}</div>
                <div>Total Packages</div>
            </div>
            <div class="metric">
                <div class="metric-value" style="color: {% if health_score > 0.8 %}green{% else %}orange{% endif %}">
                    {{ "%.1f"|format(health_score * 100) }}%
                </div>
                <div>Health Score</div>
            </div>
            <div class="metric">
                <div class="metric-value" style="color: {% if vulnerable_count > 0 %}red{% else %}green{% endif %}">
                    {{ vulnerable_count }}
                </div>
                <div>Vulnerabilities</div>
            </div>
            <div class="metric">
                <div class="metric-value">{{ outdated_count }}</div>
                <div>Outdated</div>
            </div>
        </div>
        
        {% if vulnerabilities %}
        <h2>Security Vulnerabilities</h2>
        <table>
            <tr>
                <th>Package</th>
                <th>Current</th>
                <th>Vulnerability</th>
                <th>Fix Version</th>
            </tr>
            {% for vuln in vulnerabilities %}
            <tr>
                <td>{{ vuln.package }}</td>
                <td>{{ vuln.current_version }}</td>
                <td>{{ vuln.cve }}</td>
                <td>{{ vuln.fix_version }}</td>
            </tr>
            {% endfor %}
        </table>
        {% endif %}
        
        {% if updates_available %}
        <h2>Available Updates</h2>
        <table>
            <tr>
                <th>Package</th>
                <th>Current</th>
                <th>Latest</th>
                <th>Days Behind</th>
            </tr>
            {% for update in updates_available[:10] %}
            <tr>
                <td>{{ update.package }}</td>
                <td>{{ update.current }}</td>
                <td>{{ update.latest }}</td>
                <td>{{ update.days_behind }}</td>
            </tr>
            {% endfor %}
        </table>
        {% endif %}
        
        <h2>Recommendations</h2>
        <ul>
        {% for rec in recommendations %}
            <li>{{ rec }}</li>
        {% endfor %}
        </ul>
    </div>
</body>
</html>
        """)
    
    def get_slack_template(self) -> Template:
        """Get Slack report template."""
        return Template("""
{
    "text": "Dependency Report for {{ project_name }}",
    "blocks": [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📊 Dependency Report"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": "*Total Packages:* {{ total_packages }}"
                },
                {
                    "type": "mrkdwn",
                    "text": "*Health Score:* {{ "%.1f"|format(health_score * 100) }}%"
                },
                {
                    "type": "mrkdwn",
                    "text": "*Vulnerabilities:* {{ vulnerable_count }}"
                },
                {
                    "type": "mrkdwn",
                    "text": "*Outdated:* {{ outdated_count }}"
                }
            ]
        }
        {% if critical_alerts %},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*🚨 Critical Alerts:*\\n{{ critical_alerts|join('\\n• ') }}"
            }
        }
        {% endif %}
        {% if recommendations %},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*📋 Recommendations:*\\n• {{ recommendations|join('\\n• ') }}"
            }
        }
        {% endif %}
    ]
}
        """)
    
    def get_markdown_template(self) -> Template:
        """Get Markdown report template."""
        return Template("""
# Dependency Report

**Project:** {{ project_name }}  
**Generated:** {{ timestamp }}  

## Summary

| Metric | Value |
|--------|-------|
| Total Packages | {{ total_packages }} |
| Health Score | {{ "%.1f"|format(health_score * 100) }}% |
| Vulnerabilities | {{ vulnerable_count }} |
| Outdated Packages | {{ outdated_count }} |

{% if critical_alerts %}
## 🚨 Critical Alerts

{% for alert in critical_alerts %}
- {{ alert }}
{% endfor %}
{% endif %}

{% if vulnerabilities %}
## Security Vulnerabilities

| Package | Current | CVE | Fix Version |
|---------|---------|-----|-------------|
{% for vuln in vulnerabilities %}
| {{ vuln.package }} | {{ vuln.current_version }} | {{ vuln.cve }} | {{ vuln.fix_version }} |
{% endfor %}
{% endif %}

{% if updates_available %}
## Available Updates (Top 10)

| Package | Current | Latest | Days Behind |
|---------|---------|--------|-------------|
{% for update in updates_available[:10] %}
| {{ update.package }} | {{ update.current }} | {{ update.latest }} | {{ update.days_behind }} |
{% endfor %}
{% endif %}

## Recommendations

{% for rec in recommendations %}
- {{ rec }}
{% endfor %}

---
*Report generated automatically by dependency-reporter*
        """)
    
    def collect_report_data(self) -> dict:
        """Collect data for report generation."""
        data = {
            "project_name": self.project_root.name,
            "timestamp": datetime.now().isoformat(),
            "total_packages": 0,
            "health_score": 0.0,
            "vulnerable_count": 0,
            "outdated_count": 0,
            "critical_alerts": [],
            "vulnerabilities": [],
            "updates_available": [],
            "recommendations": []
        }
        
        # Load latest health report
        latest_report = self.report_dir / "latest_report.json"
        if latest_report.exists():
            with open(latest_report) as f:
                health_data = json.load(f)
                
                data["total_packages"] = health_data.get("total_packages", 0)
                data["health_score"] = health_data.get("health_score", 0.0)
                data["vulnerable_count"] = health_data.get("vulnerable_packages", 0)
                data["outdated_count"] = health_data.get("outdated_packages", 0)
                data["recommendations"] = health_data.get("recommendations", [])
                
                # Process package health
                for pkg_health in health_data.get("package_health", []):
                    if pkg_health.get("vulnerabilities"):
                        for vuln in pkg_health["vulnerabilities"]:
                            data["vulnerabilities"].append({
                                "package": pkg_health["name"],
                                "current_version": pkg_health["current_version"],
                                "cve": vuln.get("id", "Unknown"),
                                "fix_version": vuln.get("fix_version", "Unknown")
                            })
                        data["critical_alerts"].append(
                            f"{pkg_health['name']} has security vulnerabilities"
                        )
                    
                    if pkg_health.get("days_behind", 0) > 0:
                        data["updates_available"].append({
                            "package": pkg_health["name"],
                            "current": pkg_health["current_version"],
                            "latest": pkg_health["latest_version"],
                            "days_behind": pkg_health["days_behind"]
                        })
        
        # Sort updates by days behind
        data["updates_available"].sort(key=lambda x: x["days_behind"], reverse=True)
        
        return data
    
    def generate_report(self, format: str = "markdown") -> str:
        """Generate report in specified format."""
        data = self.collect_report_data()
        
        if format in self.templates:
            template = self.templates[format]
            return template.render(**data)
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def send_email_report(self, report_html: str):
        """Send email report."""
        if not self.config.email_enabled or not self.config.email_recipients:
            logger.info("Email reporting not configured")
            return
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Dependency Report - {self.project_root.name}"
        msg['From'] = "dependency-reporter@system"
        msg['To'] = ", ".join(self.config.email_recipients)
        
        html_part = MIMEText(report_html, 'html')
        msg.attach(html_part)
        
        # Send email (configure SMTP settings as needed)
        try:
            # This is a placeholder - configure with actual SMTP settings
            logger.info(f"Email would be sent to: {self.config.email_recipients}")
            # with smtplib.SMTP('localhost') as s:
            #     s.send_message(msg)
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
    
    def send_slack_report(self, report_json: str):
        """Send Slack report."""
        if not self.config.slack_enabled or not self.config.slack_webhook:
            logger.info("Slack reporting not configured")
            return
        
        try:
            import requests
            response = requests.post(
                self.config.slack_webhook,
                json=json.loads(report_json),
                headers={'Content-Type': 'application/json'}
            )
            if response.status_code == 200:
                logger.info("Slack notification sent successfully")
            else:
                logger.error(f"Slack notification failed: {response.text}")
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
    
    def create_github_issue(self, report_md: str):
        """Create GitHub issue for critical updates."""
        if not self.config.github_enabled:
            logger.info("GitHub reporting not configured")
            return
        
        data = self.collect_report_data()
        
        if data["vulnerable_count"] > 0 or len(data["critical_alerts"]) > 0:
            try:
                # Create issue using gh CLI
                title = f"Dependency Alert: {data['vulnerable_count']} vulnerabilities found"
                
                result = subprocess.run(
                    ["gh", "issue", "create", 
                     "--title", title,
                     "--body", report_md,
                     "--label", "dependencies,security"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    logger.info(f"GitHub issue created: {result.stdout.strip()}")
                else:
                    logger.error(f"Failed to create GitHub issue: {result.stderr}")
            
            except Exception as e:
                logger.error(f"Failed to create GitHub issue: {e}")
    
    def save_report(self, report_content: str, format: str):
        """Save report to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "markdown":
            ext = "md"
        elif format == "email":
            ext = "html"
        else:
            ext = "txt"
        
        report_file = self.report_dir / f"report_{timestamp}.{ext}"
        
        with open(report_file, 'w') as f:
            f.write(report_content)
        
        logger.info(f"Report saved to {report_file}")
        return report_file
    
    def run_daily_report(self):
        """Run daily dependency report."""
        console.print("[bold blue]Running daily dependency report...[/bold blue]")
        
        # Generate health report first
        try:
            subprocess.run(
                ["python", "scripts/dependency_health_monitor.py", "analyze", "--save"],
                cwd=self.project_root,
                check=True
            )
        except Exception as e:
            logger.error(f"Failed to generate health report: {e}")
        
        # Generate reports in different formats
        if "security" in self.config.report_types or "health" in self.config.report_types:
            # Markdown report
            md_report = self.generate_report("markdown")
            self.save_report(md_report, "markdown")
            
            # Email report
            if self.config.email_enabled:
                email_report = self.generate_report("email")
                self.send_email_report(email_report)
            
            # Slack report
            if self.config.slack_enabled:
                slack_report = self.generate_report("slack")
                self.send_slack_report(slack_report)
            
            # GitHub issue for critical items
            if self.config.github_enabled:
                self.create_github_issue(md_report)
        
        console.print("[bold green]✅ Daily report completed[/bold green]")
    
    def run_weekly_report(self):
        """Run weekly comprehensive report."""
        console.print("[bold blue]Running weekly comprehensive report...[/bold blue]")
        
        # Generate dependency graph
        try:
            subprocess.run(
                ["python", "scripts/dependency_visualizer.py", "visualize"],
                cwd=self.project_root,
                check=True
            )
        except Exception as e:
            logger.error(f"Failed to generate dependency graph: {e}")
        
        # Run security audit
        try:
            subprocess.run(
                ["python", "scripts/dependency_manager.py", "check-security"],
                cwd=self.project_root,
                check=True
            )
        except Exception as e:
            logger.error(f"Failed to run security audit: {e}")
        
        # Generate comprehensive report
        report_data = self.collect_report_data()
        
        # Add weekly-specific sections
        weekly_report = f"""
# Weekly Dependency Report

**Week of:** {datetime.now().strftime('%Y-%m-%d')}

## Executive Summary

- Total Dependencies: {report_data['total_packages']}
- Overall Health Score: {report_data['health_score']:.1%}
- Security Vulnerabilities: {report_data['vulnerable_count']}
- Outdated Packages: {report_data['outdated_count']}

## Action Items

### Immediate (Security)
{chr(10).join('- ' + alert for alert in report_data['critical_alerts'][:5]) if report_data['critical_alerts'] else '- None'}

### This Week (Updates)
{chr(10).join(f"- Update {u['package']} from {u['current']} to {u['latest']}" for u in report_data['updates_available'][:5]) if report_data['updates_available'] else '- None'}

### Planning (Maintenance)
{chr(10).join('- ' + rec for rec in report_data['recommendations']) if report_data['recommendations'] else '- None'}

## Metrics Trend

*Trend analysis will be available after multiple weekly reports*

---
*Full report available in dependency_reports/latest_report.json*
        """
        
        self.save_report(weekly_report, "markdown")
        
        console.print("[bold green]✅ Weekly report completed[/bold green]")
    
    def schedule_reports(self):
        """Schedule automated reports."""
        # Daily report
        schedule.every().day.at(self.config.schedule_time).do(self.run_daily_report)
        
        # Weekly report
        if self.config.weekly_day.lower() == "monday":
            schedule.every().monday.at(self.config.schedule_time).do(self.run_weekly_report)
        elif self.config.weekly_day.lower() == "friday":
            schedule.every().friday.at(self.config.schedule_time).do(self.run_weekly_report)
        
        console.print(f"[bold green]Scheduled daily reports at {self.config.schedule_time}[/bold green]")
        console.print(f"[bold green]Scheduled weekly reports on {self.config.weekly_day}s[/bold green]")
        
        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute


@click.group()
def cli():
    """Automated dependency reporting system."""
    pass


@cli.command()
@click.option('--format', type=click.Choice(['markdown', 'email', 'slack']), 
              default='markdown', help='Report format')
def generate(format: str):
    """Generate a dependency report."""
    reporter = DependencyReporter()
    report = reporter.generate_report(format)
    
    if format == "markdown":
        print(report)
    
    report_file = reporter.save_report(report, format)
    console.print(f"[green]Report saved to {report_file}[/green]")


@cli.command()
def daily():
    """Run daily dependency report."""
    reporter = DependencyReporter()
    reporter.run_daily_report()


@cli.command()
def weekly():
    """Run weekly comprehensive report."""
    reporter = DependencyReporter()
    reporter.run_weekly_report()


@cli.command(name="schedule")
def run_schedule():
    """Start scheduled reporting."""
    reporter = DependencyReporter()
    console.print("[bold blue]Starting scheduled reporting service...[/bold blue]")
    
    try:
        reporter.schedule_reports()
    except KeyboardInterrupt:
        console.print("\n[yellow]Scheduled reporting stopped[/yellow]")


@cli.command()
@click.option('--email', multiple=True, help='Email recipients')
@click.option('--slack-webhook', help='Slack webhook URL')
@click.option('--github/--no-github', default=True, help='Enable GitHub issues')
@click.option('--schedule-time', default='09:00', help='Daily report time')
@click.option('--weekly-day', default='monday', help='Weekly report day')
def configure(email, slack_webhook, github, schedule_time, weekly_day):
    """Configure reporting settings."""
    reporter = DependencyReporter()
    
    config = reporter.config
    
    if email:
        config.email_enabled = True
        config.email_recipients = list(email)
    
    if slack_webhook:
        config.slack_enabled = True
        config.slack_webhook = slack_webhook
    
    config.github_enabled = github
    config.schedule_time = schedule_time
    config.weekly_day = weekly_day
    
    reporter.save_config(config)
    
    console.print("[green]✅ Configuration saved[/green]")
    console.print(f"Email: {'Enabled' if config.email_enabled else 'Disabled'}")
    console.print(f"Slack: {'Enabled' if config.slack_enabled else 'Disabled'}")
    console.print(f"GitHub: {'Enabled' if config.github_enabled else 'Disabled'}")
    console.print(f"Schedule: Daily at {config.schedule_time}, Weekly on {config.weekly_day}")


if __name__ == "__main__":
    cli()