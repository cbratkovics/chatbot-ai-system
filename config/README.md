# Configuration Directory

This directory contains all configuration files for the AI Chatbot System.

## Structure

- `docker/` - Docker and container configurations
  - `compose/` - Docker Compose files for different environments
  - `dockerfiles/` - Dockerfile variants for different builds
- `requirements/` - Python dependency files
  - `base.txt` - Core dependencies (formerly config/requirements/base.txt)
  - `dev.txt` - Development dependencies
  - `prod.txt` - Production dependencies  
- `environments/` - Environment configurations
  - `config/environments/.env.example` - Environment variable template
  - `config/environments/render.yaml` - Render deployment configuration
- `ci/` - CI/CD related configurations

## Usage

All configuration files have been relocated here from the root directory to maintain a cleaner project structure. Symlinks have been created in the root for backward compatibility.