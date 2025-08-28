# Demo Branch CI/CD Documentation

## Overview

The demo branch has a dedicated CI/CD pipeline optimized for quick setup and validation. This ensures the demo remains functional while maintaining its 5-minute setup promise.

## Workflow Files

### 1. `.github/workflows/demo-ci.yml`
- **Trigger**: Push to demo branch or PRs targeting demo
- **Purpose**: Validate, build, test, and scan the demo environment
- **Timeout**: 10 minutes maximum
- **Key Features**:
  - File validation
  - Docker build with caching
  - Health checks
  - Basic smoke tests
  - Security scanning (non-blocking)

### 2. `.github/workflows/demo-monitor.yml`
- **Trigger**: After successful CI/CD runs and daily schedule
- **Purpose**: Monitor demo complexity and prevent feature creep
- **Metrics Tracked**:
  - File count (<150 target)
  - Dependency count (<35 target)
  - Docker layers (<15 target)
  - Setup time estimation

## Docker Configuration

### Files
- `config/docker/dockerfiles/Dockerfile.demo`: Simplified single-stage build for backend
- `frontend/Dockerfile.demo`: Optimized frontend build
- `config/docker/compose/docker-compose.demo.yml`: Demo-specific compose configuration

### Optimization Strategies
1. Single-stage builds where possible
2. Minimal dependencies
3. Build caching enabled
4. Health checks integrated
5. Non-root user for security

## Setup Script

The `scripts/setup/setup_demo.sh` script supports two modes:
- **Normal Mode**: Interactive setup with user prompts
- **CI Mode**: Automated setup for testing (`--ci-mode` flag)

## Testing Locally

```bash
# 1. Switch to demo branch
git checkout demo

# 2. Run setup
./scripts/setup/setup_demo.sh

# 3. Verify services
docker-compose -f config/docker/compose/docker-compose.demo.yml ps

# 4. Check health
curl http://localhost:8000/health
curl http://localhost:3000
```

## Troubleshooting

### Build Failures
1. Check Docker daemon is running
2. Verify all required files exist
3. Check .env.example has all required variables
4. Review docker-compose.demo.yml for correct paths

### Health Check Failures
1. Increase wait time in CI workflow
2. Check service logs: `docker-compose -f docker-compose.demo.yml logs`
3. Verify port availability (8000, 3000, 6379, 5432)

### Slow Builds
1. Enable Docker BuildKit: `export DOCKER_BUILDKIT=1`
2. Use cached layers from registry
3. Minimize COPY operations in Dockerfile
4. Reduce dependency count

## Best Practices

1. **Keep It Simple**: Demo should showcase features, not complexity
2. **Fast Feedback**: CI should complete in <10 minutes
3. **Clear Errors**: Fail fast with descriptive messages
4. **Monitor Growth**: Regular complexity checks prevent bloat
5. **Cache Aggressively**: Use Docker and dependency caching

## Maintenance

### Weekly Tasks
- Review monitoring reports
- Update dependencies for security
- Test setup time locally

### Monthly Tasks
- Prune unnecessary files
- Optimize Docker images
- Review and update documentation

## Rollback Procedure

If CI/CD fails after changes:

```bash
# Revert last commit
git revert HEAD
git push origin demo

# Or reset to known good state
git reset --hard <last-good-commit>
git push origin demo --force-with-lease
```