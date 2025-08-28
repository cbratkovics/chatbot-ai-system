# 📌 Main Branch - Full Enterprise System

This is the **main branch** containing the complete enterprise-grade AI Chatbot System with all features, tests, and infrastructure components.

## 🎯 Branch Purpose
The `main` branch contains the full production-ready system with:
- Complete enterprise features
- Comprehensive test suites
- Kubernetes deployments
- FinOps tracking
- Multi-region support
- Advanced monitoring

## 🔄 Available Versions

| Branch | Purpose | Setup Time |
|--------|---------|------------|
| **main** (current) | Full enterprise system | 30+ minutes |
| **demo** | Streamlined demo version | < 5 minutes |

## 🚀 Quick Switch to Demo

If you're looking for a quick demo deployment:

```bash
# Switch to the streamlined demo version
git checkout demo

# Or use the version switcher
./scripts/utils/switch_version.sh
```

The demo branch provides:
- ✅ 5-minute setup
- ✅ One-command deployment (`./setup_demo.sh`)
- ✅ Simplified configuration
- ✅ All core features
- ✅ Perfect for evaluation

## 📊 Main vs Demo Comparison

| Feature | Main (This Branch) | Demo Branch |
|---------|-------------------|-------------|
| **Files** | 258 files | ~150 files |
| **Dependencies** | 100+ packages | 35 packages |
| **Setup Time** | 30+ minutes | < 5 minutes |
| **Docker Build** | 10+ minutes | 2 minutes |
| **Memory Usage** | 2GB+ | 500MB |
| **Target Users** | Production deployments | Quick evaluation |

## 🏗️ Main Branch Structure

```
main/
├── api/                    # Full API implementation
├── tests/                  # Comprehensive test suites
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   ├── e2e/              # End-to-end tests
│   └── load_testing/     # Performance tests
├── benchmarks/            # Performance benchmarking
├── finops/               # Cost management platform
├── k8s/                  # Kubernetes manifests
├── infrastructure/       # Terraform & DR configs
└── monitoring/          # Full observability stack
```

## 📦 Latest Releases

- **Demo Version:** `v1.0.0-demo` - [Download](../../releases/tag/v1.0.0-demo)
- **Full Version:** `v1.0.0` - [Download](../../releases/tag/v1.0.0)

## 🔧 Development Workflow

### Working with Both Branches

```bash
# View all branches
git branch -a

# See differences between branches
git diff main..demo --stat

# Cherry-pick improvements from demo
git cherry-pick <commit-from-demo>

# Merge selective features
git merge demo --no-ff --no-commit
```

## 📚 Documentation

- **For Quick Demo:** Switch to `demo` branch and see `README.demo.md`
- **For Full System:** Continue with the main `README.md`
- **Branch Comparison:** See `docs/guides/BRANCH_COMPARISON.md`

## 🎯 Choose Your Path

### I want to quickly try the system
→ `git checkout demo` and run `./setup_demo.sh`

### I need the full enterprise system
→ Continue with this branch and follow `README.md`

### I want to contribute
→ Create feature branches from `main` for new features

### I want to share with others
→ Direct them to the `demo` branch for easy setup

## 📈 Version Management

This repository uses a dual-branch strategy:
- **main**: Stable, production-ready code
- **demo**: Simplified, demo-optimized version
- **feature/***: Development branches
- **hotfix/***: Urgent fixes

Tags follow this pattern:
- Production: `v1.0.0`
- Demo: `v1.0.0-demo`
- Pre-release: `v1.0.0-rc1`

---

**Note:** You're currently on the `main` branch with the full system. For a quick demo experience, switch to the `demo` branch.