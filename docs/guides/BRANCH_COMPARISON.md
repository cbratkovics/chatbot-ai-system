# 📊 Branch Comparison: Main vs Demo

## Overview
This repository maintains two primary branches for different use cases:

| Aspect | `main` Branch | `demo` Branch |
|--------|--------------|---------------|
| **Purpose** | Full enterprise system | Streamlined demo |
| **Target Audience** | Enterprise deployments | Developers trying the system |
| **Setup Time** | 30+ minutes | < 5 minutes |
| **Complexity** | High | Low |
| **Files** | 258 files | ~150 files |
| **Dependencies** | 100+ packages | 35 packages |

## 🌳 Branch Structure

```
main (default)
├── Full enterprise features
├── Complete test suites
├── Kubernetes configurations
├── FinOps dashboards
├── Benchmarking tools
├── CI/CD pipelines
└── Terraform infrastructure

demo
├── Simplified configuration
├── One-command setup
├── Essential features only
├── Optimized Docker setup
├── Clear documentation
└── Quick deployment scripts
```

## 🔄 Switching Between Branches

### Using the Script
```bash
./scripts/utils/switch_version.sh
```

### Manual Switching
```bash
# Switch to main (full system)
git checkout main

# Switch to demo (streamlined)
git checkout demo

# See differences
git diff main..demo --stat
```

## 📦 Version Tags

### Demo Releases
- `v1.0.0-demo` - Initial demo release
- `v1.1.0-demo` - (planned) Add UI improvements
- `v1.2.0-demo` - (planned) Add more providers

### Main Releases
- `v1.0.0` - Full system release
- `v2.0.0` - (planned) Enterprise features

## 🚀 When to Use Each Branch

### Use `main` Branch When:
- Deploying to production
- Need full enterprise features
- Require extensive testing
- Building custom integrations
- Contributing new features
- Need Kubernetes deployment
- Require FinOps tracking

### Use `demo` Branch When:
- Showcasing to stakeholders
- Quick proof of concept
- Developer evaluation
- Conference demos
- Tutorial creation
- Blog post examples
- Quick testing

## 🔧 Maintaining Both Branches

### Cherry-Picking Improvements
```bash
# Apply a specific commit from demo to main
git checkout main
git cherry-pick <commit-hash>

# Apply a fix from main to demo
git checkout demo
git cherry-pick <commit-hash>
```

### Keeping Demo Updated
```bash
# Merge selective changes from main
git checkout demo
git merge main --no-ff --no-commit
# Then selectively stage changes
git add <files-to-include>
git commit -m "feat: Sync selected features from main"
```

## 📊 Feature Comparison

| Feature | Main | Demo |
|---------|------|------|
| **Core Features** | | |
| Multi-LLM Support | ✅ | ✅ |
| WebSocket Streaming | ✅ | ✅ |
| Redis Caching | ✅ | ✅ |
| Rate Limiting | ✅ | ✅ |
| **Enterprise Features** | | |
| Kubernetes Support | ✅ | ❌ |
| Multi-region | ✅ | ❌ |
| FinOps Dashboard | ✅ | ❌ |
| Advanced Monitoring | ✅ | Basic |
| Load Testing | ✅ | ❌ |
| **Developer Experience** | | |
| Setup Complexity | High | Low |
| Documentation | Extensive | Focused |
| Configuration | 50+ vars | 10 vars |
| Docker Build Time | 10 min | 2 min |

## 🎯 Release Strategy

### Demo Branch Releases
1. Tag with `-demo` suffix: `v1.0.0-demo`
2. Create GitHub release from demo branch
3. Include simplified documentation
4. Highlight ease of deployment

### Main Branch Releases
1. Tag with standard semver: `v1.0.0`
2. Create comprehensive release notes
3. Include migration guides
4. Document all features

## 📝 Contributing Guidelines

### For Demo Branch
- Focus on simplicity
- Minimize dependencies
- Improve setup experience
- Enhance documentation

### For Main Branch
- Add enterprise features
- Improve scalability
- Add comprehensive tests
- Enhance monitoring

## 🔍 Quick Commands

```bash
# Show current branch
git branch --show-current

# List all branches
git branch -a

# Show branch history
git log --oneline --graph --branches

# Compare file counts
git ls-tree -r main --name-only | wc -l
git ls-tree -r demo --name-only | wc -l

# See what's different
git diff main..demo --name-status

# Show size difference
git diff main..demo --stat
```

## 📈 Metrics

### Demo Branch Success Metrics
- Setup time < 5 minutes ✅
- Single command deployment ✅
- Clear documentation ✅
- Minimal dependencies ✅

### Main Branch Capabilities
- Enterprise scale ready ✅
- Full test coverage ✅
- Production monitoring ✅
- Multi-cloud support ✅

---

**Remember:** The `demo` branch is optimized for first impressions and ease of use, while the `main` branch contains the full production-ready system with all enterprise features.