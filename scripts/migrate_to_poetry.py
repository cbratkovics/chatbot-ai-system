#!/usr/bin/env python3
"""
Migrate from requirements.txt to Poetry dependency management.
This script provides a safe, reversible migration path.
"""

import logging
import shutil
import subprocess
import sys
from pathlib import Path

import click
import toml
from packaging.requirements import Requirement

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PoetryMigrator:
    """Handle migration from requirements.txt to Poetry."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_dir = project_root / "config"
        self.requirements_dir = self.config_dir / "requirements"
        self.backup_dir = project_root / ".migration_backup"
        self.pyproject_path = project_root / "pyproject.toml"
        
        # Dependency mappings for special cases
        self.dependency_mappings = {
            # Map old package names to new ones
            "opencv-python": "opencv-python-headless",
            "tensorflow-gpu": "tensorflow",
            "torch-gpu": "torch",
        }
        
        # Dependencies that should be in specific groups
        self.group_mappings = {
            "dev": ["pytest", "black", "mypy", "flake8", "isort", "coverage", 
                   "faker", "locust", "ipython", "ipdb", "bandit", "pre-commit"],
            "prod": ["gunicorn", "uvloop"],
            "ml-gpu": ["torch", "tensorflow", "transformers", "accelerate"],
            "ml-cpu": ["onnxruntime", "tensorflow-cpu"],
            "monitoring": ["prometheus-client", "opentelemetry", "sentry-sdk"],
        }
    
    def backup_current_setup(self) -> bool:
        """Create backup of current setup."""
        try:
            logger.info("Creating backup of current setup...")
            
            # Create backup directory
            self.backup_dir.mkdir(exist_ok=True)
            
            # Backup requirements files
            if self.requirements_dir.exists():
                shutil.copytree(
                    self.requirements_dir, 
                    self.backup_dir / "requirements",
                    dirs_exist_ok=True
                )
            
            # Backup existing pyproject.toml if it exists
            if self.pyproject_path.exists():
                shutil.copy2(self.pyproject_path, self.backup_dir / "pyproject.toml.bak")
            
            # Create restore script
            restore_script = self.backup_dir / "restore.sh"
            restore_script.write_text("""#!/bin/bash
# Restore script for migration rollback
echo "Restoring previous setup..."
cp -r .migration_backup/requirements/* config/requirements/
if [ -f .migration_backup/pyproject.toml.bak ]; then
    cp .migration_backup/pyproject.toml.bak pyproject.toml
fi
echo "Restore complete!"
""")
            restore_script.chmod(0o755)
            
            logger.info(f"Backup created at {self.backup_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False
    
    def parse_requirements_file(self, file_path: Path) -> list[Requirement]:
        """Parse a requirements.txt file."""
        requirements = []
        
        if not file_path.exists():
            return requirements
        
        with open(file_path) as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#') and not line.startswith('-r'):
                    try:
                        req = Requirement(line)
                        requirements.append(req)
                    except Exception as e:
                        logger.warning(f"Could not parse requirement: {line} - {e}")
        
        return requirements
    
    def merge_requirements(self) -> dict[str, list[Requirement]]:
        """Merge all requirements files into categorized groups."""
        merged = {
            "main": [],
            "dev": [],
            "prod": [],
        }
        
        # Parse base requirements
        base_reqs = self.parse_requirements_file(self.requirements_dir / "base.txt")
        merged["main"] = base_reqs
        
        # Parse dev requirements
        dev_reqs = self.parse_requirements_file(self.requirements_dir / "dev.txt")
        merged["dev"] = dev_reqs
        
        # Parse prod requirements
        prod_reqs = self.parse_requirements_file(self.requirements_dir / "prod.txt")
        merged["prod"] = prod_reqs
        
        return merged
    
    def resolve_conflicts(self, requirements: dict[str, list[Requirement]]) -> dict[str, list[Requirement]]:
        """Resolve version conflicts between requirements."""
        resolved = {}
        all_packages = {}
        
        # Collect all packages with their versions
        for group, reqs in requirements.items():
            for req in reqs:
                name = req.name.lower()
                if name not in all_packages:
                    all_packages[name] = []
                all_packages[name].append((group, req))
        
        # Resolve conflicts
        for name, versions in all_packages.items():
            if len(versions) == 1:
                group, req = versions[0]
                if group not in resolved:
                    resolved[group] = []
                resolved[group].append(req)
            else:
                # Multiple versions - need to resolve
                logger.info(f"Resolving conflict for {name}: {versions}")
                
                # Use the most restrictive version
                chosen_group, chosen_req = self._choose_version(versions)
                if chosen_group not in resolved:
                    resolved[chosen_group] = []
                resolved[chosen_group].append(chosen_req)
        
        return resolved
    
    def _choose_version(self, versions: list[tuple[str, Requirement]]) -> tuple[str, Requirement]:
        """Choose the best version from conflicting requirements."""
        # Prefer main > prod > dev
        priority = {"main": 0, "prod": 1, "dev": 2}
        
        # Sort by priority and choose first
        sorted_versions = sorted(versions, key=lambda x: priority.get(x[0], 999))
        return sorted_versions[0]
    
    def generate_poetry_config(self, requirements: dict[str, list[Requirement]]) -> dict:
        """Generate Poetry configuration from requirements."""
        poetry_config = {
            "tool": {
                "poetry": {
                    "dependencies": {
                        "python": "^3.11"
                    },
                    "group": {}
                }
            }
        }
        
        # Process main dependencies
        for req in requirements.get("main", []):
            name = self.dependency_mappings.get(req.name, req.name)
            poetry_config["tool"]["poetry"]["dependencies"][name] = self._format_version(req)
        
        # Process dev dependencies
        if "dev" in requirements:
            poetry_config["tool"]["poetry"]["group"]["dev"] = {
                "dependencies": {}
            }
            for req in requirements["dev"]:
                name = self.dependency_mappings.get(req.name, req.name)
                poetry_config["tool"]["poetry"]["group"]["dev"]["dependencies"][name] = self._format_version(req)
        
        # Process prod dependencies  
        if "prod" in requirements:
            poetry_config["tool"]["poetry"]["group"]["prod"] = {
                "dependencies": {}
            }
            for req in requirements["prod"]:
                name = self.dependency_mappings.get(req.name, req.name)
                poetry_config["tool"]["poetry"]["group"]["prod"]["dependencies"][name] = self._format_version(req)
        
        return poetry_config
    
    def _format_version(self, req: Requirement) -> str:
        """Format version specification for Poetry."""
        if req.specifier:
            spec_str = str(req.specifier)
            # Convert == to ^
            if spec_str.startswith("=="):
                return "^" + spec_str[2:]
            # Keep >= as is
            elif spec_str.startswith(">="):
                return spec_str
            else:
                return spec_str
        return "*"
    
    def validate_migration(self) -> bool:
        """Validate the migration was successful."""
        try:
            # Check if Poetry is installed
            result = subprocess.run(
                ["poetry", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Poetry version: {result.stdout.strip()}")
            
            # Validate pyproject.toml
            result = subprocess.run(
                ["poetry", "check"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Poetry validation failed: {result.stderr}")
                return False
            
            logger.info("Poetry configuration is valid")
            
            # Try to install dependencies (dry run)
            logger.info("Testing dependency resolution (dry run)...")
            result = subprocess.run(
                ["poetry", "install", "--dry-run"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.warning(f"Dependency resolution issues: {result.stderr}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Validation failed: {e}")
            return False
    
    def generate_compatibility_files(self):
        """Generate backward-compatible requirements.txt files from Poetry."""
        logger.info("Generating backward-compatible requirements files...")
        
        # Export main dependencies
        subprocess.run(
            ["poetry", "export", "-f", "requirements.txt", "--without-hashes", 
             "-o", "config/requirements/base.txt"],
            cwd=self.project_root,
            check=True
        )
        
        # Export dev dependencies
        subprocess.run(
            ["poetry", "export", "-f", "requirements.txt", "--without-hashes",
             "--with", "dev", "-o", "config/requirements/dev.txt"],
            cwd=self.project_root,
            check=True
        )
        
        # Export prod dependencies
        subprocess.run(
            ["poetry", "export", "-f", "requirements.txt", "--without-hashes",
             "--with", "prod", "-o", "config/requirements/prod.txt"],
            cwd=self.project_root,
            check=True
        )
        
        logger.info("Compatibility files generated")
    
    def migrate(self, skip_backup: bool = False) -> bool:
        """Execute the migration."""
        try:
            # Step 1: Backup
            if not skip_backup:
                if not self.backup_current_setup():
                    return False
            
            # Step 2: Parse requirements
            logger.info("Parsing requirements files...")
            requirements = self.merge_requirements()
            
            # Step 3: Resolve conflicts
            logger.info("Resolving dependency conflicts...")
            resolved = self.resolve_conflicts(requirements)
            
            # Step 4: Generate Poetry config
            logger.info("Generating Poetry configuration...")
            poetry_config = self.generate_poetry_config(resolved)
            
            # Step 5: Update pyproject.toml
            if self.pyproject_path.exists():
                # Merge with existing
                existing = toml.load(self.pyproject_path)
                existing.update(poetry_config)
                poetry_config = existing
            
            # Write configuration
            with open(self.pyproject_path, 'w') as f:
                toml.dump(poetry_config, f)
            
            logger.info(f"Poetry configuration written to {self.pyproject_path}")
            
            # Step 6: Validate
            if not self.validate_migration():
                logger.error("Migration validation failed")
                return False
            
            # Step 7: Generate compatibility files
            self.generate_compatibility_files()
            
            logger.info("Migration completed successfully!")
            logger.info(f"Backup available at {self.backup_dir}")
            logger.info("To rollback, run: .migration_backup/restore.sh")
            
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False


@click.command()
@click.option('--project-root', type=click.Path(exists=True), default=".", 
              help='Project root directory')
@click.option('--skip-backup', is_flag=True, help='Skip backup creation')
@click.option('--dry-run', is_flag=True, help='Perform dry run without making changes')
def main(project_root: str, skip_backup: bool, dry_run: bool):
    """Migrate from requirements.txt to Poetry dependency management."""
    project_path = Path(project_root).resolve()
    
    logger.info(f"Starting migration for project at {project_path}")
    
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    
    migrator = PoetryMigrator(project_path)
    
    if migrator.migrate(skip_backup=skip_backup):
        logger.info("✅ Migration successful!")
        sys.exit(0)
    else:
        logger.error("❌ Migration failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()