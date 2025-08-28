#!/usr/bin/env python3
"""
Intelligent dependency manager for AI/ML workloads.
Handles GPU/CPU detection, conflict resolution, and automated updates.
"""

import json
import logging
import os
import platform
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import click
import toml

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ComputeEnvironment(Enum):
    """Available compute environments."""
    CPU = "cpu"
    CUDA = "cuda"
    ROCM = "rocm"
    MPS = "mps"  # Apple Silicon


@dataclass
class DependencyProfile:
    """Dependency profile for different environments."""
    name: str
    environment: ComputeEnvironment
    packages: dict[str, str]
    optional_packages: set[str]
    conflicting_packages: set[str]


class DependencyManager:
    """Manage dependencies intelligently for AI/ML workloads."""
    
    def __init__(self, project_root: Path | None = None):
        if project_root is None:
            project_root = Path.cwd()
        self.project_root = project_root
        self.pyproject_path = project_root / "pyproject.toml"
        self.config_dir = project_root / "config" / "dependencies"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # ML package configurations
        self.ml_packages = {
            "torch": {
                "cpu": "torch==2.1.2+cpu",
                "cuda": "torch==2.1.2+cu121",
                "rocm": "torch==2.1.2+rocm5.6",
                "mps": "torch==2.1.2",
            },
            "tensorflow": {
                "cpu": "tensorflow-cpu==2.15.0",
                "cuda": "tensorflow[and-cuda]==2.15.0",
                "rocm": "tensorflow-rocm==2.15.0",
                "mps": "tensorflow-macos==2.15.0",
            },
            "jax": {
                "cpu": "jax[cpu]==0.4.23",
                "cuda": "jax[cuda12_pip]==0.4.23",
                "rocm": "jax==0.4.23",
                "mps": "jax-metal==0.0.5",
            }
        }
        
        # Dependency profiles
        self.profiles = {
            "development": DependencyProfile(
                name="development",
                environment=ComputeEnvironment.CPU,
                packages={
                    "ipython": "^8.18.0",
                    "jupyter": "^1.0.0",
                    "notebook": "^7.0.0",
                    "jupyterlab": "^4.0.0",
                },
                optional_packages={"debugpy", "memory-profiler"},
                conflicting_packages=set()
            ),
            "production": DependencyProfile(
                name="production",
                environment=ComputeEnvironment.CPU,
                packages={
                    "gunicorn": "^21.2.0",
                    "uvloop": "^0.19.0",
                },
                optional_packages={"prometheus-client", "sentry-sdk"},
                conflicting_packages={"ipython", "jupyter", "notebook"}
            ),
            "edge": DependencyProfile(
                name="edge",
                environment=ComputeEnvironment.CPU,
                packages={
                    "onnxruntime": "^1.16.0",
                    "tflite-runtime": "^2.14.0",
                },
                optional_packages=set(),
                conflicting_packages={"torch", "tensorflow", "jax"}
            ),
        }
    
    def detect_compute_environment(self) -> ComputeEnvironment:
        """Detect available compute environment."""
        logger.info("Detecting compute environment...")
        
        # Check for CUDA
        if self._check_cuda():
            logger.info("CUDA environment detected")
            return ComputeEnvironment.CUDA
        
        # Check for ROCm
        if self._check_rocm():
            logger.info("ROCm environment detected")
            return ComputeEnvironment.ROCM
        
        # Check for Apple Silicon
        if platform.system() == "Darwin" and platform.processor() == "arm":
            logger.info("Apple Silicon (MPS) environment detected")
            return ComputeEnvironment.MPS
        
        logger.info("CPU-only environment detected")
        return ComputeEnvironment.CPU
    
    def _check_cuda(self) -> bool:
        """Check if CUDA is available."""
        try:
            # Check nvidia-smi
            result = subprocess.run(
                ["nvidia-smi"], 
                capture_output=True, 
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Also check CUDA version
                result = subprocess.run(
                    ["nvcc", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        
        # Check environment variable
        return os.environ.get("CUDA_HOME") is not None
    
    def _check_rocm(self) -> bool:
        """Check if ROCm is available."""
        try:
            result = subprocess.run(
                ["rocm-smi"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        
        return os.environ.get("ROCM_HOME") is not None
    
    def resolve_ml_dependencies(self, environment: ComputeEnvironment) -> dict[str, str]:
        """Resolve ML dependencies for the given environment."""
        resolved = {}
        
        for package, variants in self.ml_packages.items():
            env_key = environment.value
            if env_key in variants:
                resolved[package] = variants[env_key]
        
        return resolved
    
    def detect_conflicts(self, dependencies: dict[str, str]) -> list[tuple[str, str, str]]:
        """Detect potential conflicts in dependencies."""
        conflicts = []
        
        # Known conflict patterns
        conflict_patterns = [
            ("tensorflow", "tensorflow-cpu", "Cannot install both tensorflow and tensorflow-cpu"),
            ("torch", "tensorflow", "PyTorch and TensorFlow may have CUDA conflicts"),
            ("opencv-python", "opencv-python-headless", "Cannot install both opencv variants"),
            ("pandas>=2.0", "numpy<1.24", "Pandas 2.0+ requires numpy>=1.24"),
        ]
        
        for pkg1, pkg2, message in conflict_patterns:
            if pkg1 in dependencies and pkg2 in dependencies:
                conflicts.append((pkg1, pkg2, message))
        
        return conflicts
    
    def generate_lock_file(self) -> bool:
        """Generate Poetry lock file."""
        logger.info("Generating lock file...")
        
        try:
            result = subprocess.run(
                ["python3", "-m", "poetry", "lock", "--no-update"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Lock file generation failed: {result.stderr}")
                return False
            
            logger.info("Lock file generated successfully")
            return True
            
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to generate lock file: {e}")
            return False
    
    def export_requirements(self, profile: str = "main") -> bool:
        """Export requirements.txt files from Poetry."""
        logger.info(f"Exporting requirements for profile: {profile}")
        
        output_dir = self.project_root / "config" / "requirements"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Export base requirements
            result = subprocess.run(
                ["python3", "-m", "poetry", "export", "-f", "requirements.txt", 
                 "--without-hashes", "-o", str(output_dir / "base.txt")],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Export failed: {result.stderr}")
                return False
            
            # Export dev requirements if they exist
            result = subprocess.run(
                ["python3", "-m", "poetry", "export", "-f", "requirements.txt",
                 "--without-hashes", "--with", "dev", "-o", str(output_dir / "dev.txt")],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            # Export prod requirements if they exist
            result = subprocess.run(
                ["python3", "-m", "poetry", "export", "-f", "requirements.txt",
                 "--without-hashes", "--with", "prod", "-o", str(output_dir / "prod.txt")],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            logger.info("Requirements exported successfully")
            return True
            
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to export requirements: {e}")
            return False
    
    def check_security(self) -> list[dict]:
        """Check for security vulnerabilities in dependencies."""
        logger.info("Checking for security vulnerabilities...")
        
        vulnerabilities = []
        
        try:
            # Use pip-audit for security scanning
            result = subprocess.run(
                ["pip-audit", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and result.stdout:
                audit_data = json.loads(result.stdout)
                for vuln in audit_data.get("vulnerabilities", []):
                    vulnerabilities.append({
                        "package": vuln.get("name"),
                        "version": vuln.get("version"),
                        "vulnerability": vuln.get("id"),
                        "description": vuln.get("description"),
                        "fix_version": vuln.get("fix_versions", ["No fix available"])[0]
                    })
            
        except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError):
            logger.warning("pip-audit not available or failed")
        
        return vulnerabilities
    
    def generate_sbom(self) -> dict:
        """Generate Software Bill of Materials."""
        logger.info("Generating SBOM...")
        
        sbom = {
            "timestamp": subprocess.run(
                ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                capture_output=True,
                text=True
            ).stdout.strip(),
            "project": str(self.project_root),
            "dependencies": []
        }
        
        try:
            # Get installed packages
            result = subprocess.run(
                ["python3", "-m", "poetry", "show", "--no-dev"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        sbom["dependencies"].append({
                            "name": parts[0],
                            "version": parts[1],
                            "license": parts[2] if len(parts) > 2 else "Unknown"
                        })
        
        except subprocess.SubprocessError:
            logger.warning("Failed to generate complete SBOM")
        
        return sbom
    
    def optimize_for_environment(self, environment: ComputeEnvironment, profile: str = "production"):
        """Optimize dependencies for specific environment."""
        logger.info(f"Optimizing for {environment.value} environment with {profile} profile")
        
        # Load current pyproject.toml
        with open(self.pyproject_path) as f:
            config = toml.load(f)
        
        # Get ML dependencies for environment
        ml_deps = self.resolve_ml_dependencies(environment)
        
        # Update configuration
        if environment in [ComputeEnvironment.CUDA, ComputeEnvironment.ROCM]:
            # Add GPU-specific dependencies
            config["tool"]["poetry"]["group"]["ml-gpu"]["dependencies"].update(ml_deps)
        else:
            # Add CPU-specific dependencies
            config["tool"]["poetry"]["group"]["ml-cpu"]["dependencies"].update(ml_deps)
        
        # Apply profile
        if profile in self.profiles:
            profile_config = self.profiles[profile]
            config["tool"]["poetry"]["dependencies"].update(profile_config.packages)
        
        # Write updated configuration
        with open(self.pyproject_path, 'w') as f:
            toml.dump(config, f)
        
        logger.info("Configuration optimized")
        
        # Generate lock file
        self.generate_lock_file()
        
        # Export requirements
        self.export_requirements(profile)
    
    def create_update_pr(self, updates: list[dict]) -> bool:
        """Create a pull request for dependency updates."""
        logger.info("Creating update PR...")
        
        # Create branch
        branch_name = f"deps/update-{subprocess.run(['date', '+%Y%m%d'], capture_output=True, text=True).stdout.strip()}"
        
        try:
            subprocess.run(["git", "checkout", "-b", branch_name], check=True)
            
            # Update dependencies
            for update in updates:
                subprocess.run(
                    ["python3", "-m", "poetry", "add", f"{update['package']}@latest"],
                    check=True
                )
            
            # Commit changes
            subprocess.run(["git", "add", "pyproject.toml", "poetry.lock"], check=True)
            subprocess.run(
                ["git", "commit", "-m", "chore: update dependencies\n\nUpdates:\n" + 
                 "\n".join([f"- {u['package']}: {u['old_version']} -> {u['new_version']}" for u in updates])],
                check=True
            )
            
            # Push branch
            subprocess.run(["git", "push", "origin", branch_name], check=True)
            
            logger.info(f"Update branch created: {branch_name}")
            return True
            
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to create update PR: {e}")
            return False


@click.group()
def cli():
    """AI/ML dependency manager for optimized workloads."""
    pass


@cli.command()
@click.option('--environment', type=click.Choice(['auto', 'cpu', 'cuda', 'rocm', 'mps']), 
              default='auto', help='Compute environment')
@click.option('--profile', type=click.Choice(['development', 'production', 'edge']), 
              default='production', help='Deployment profile')
def optimize(environment: str, profile: str):
    """Optimize dependencies for the target environment."""
    manager = DependencyManager()
    
    if environment == 'auto':
        env = manager.detect_compute_environment()
    else:
        env = ComputeEnvironment(environment)
    
    manager.optimize_for_environment(env, profile)
    logger.info("✅ Optimization complete!")


@cli.command()
def check_security():
    """Check for security vulnerabilities."""
    manager = DependencyManager()
    vulnerabilities = manager.check_security()
    
    if vulnerabilities:
        logger.warning(f"Found {len(vulnerabilities)} vulnerabilities:")
        for vuln in vulnerabilities:
            logger.warning(f"  - {vuln['package']} {vuln['version']}: {vuln['vulnerability']}")
    else:
        logger.info("✅ No vulnerabilities found!")


@cli.command()
def export():
    """Export requirements.txt files."""
    manager = DependencyManager()
    if manager.export_requirements():
        logger.info("✅ Requirements exported!")
    else:
        logger.error("❌ Export failed!")


@cli.command()
def detect_env():
    """Detect compute environment."""
    manager = DependencyManager()
    env = manager.detect_compute_environment()
    logger.info(f"Detected environment: {env.value}")


@cli.command()
def generate_sbom():
    """Generate Software Bill of Materials."""
    manager = DependencyManager()
    sbom = manager.generate_sbom()
    
    output_file = Path.cwd() / "sbom.json"
    with open(output_file, 'w') as f:
        json.dump(sbom, f, indent=2)
    
    logger.info(f"✅ SBOM generated: {output_file}")


if __name__ == "__main__":
    cli()