#!/bin/bash
# Validation script for repository reorganization
# This script validates that all files were copied correctly and no broken references exist

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

VALIDATION_ERRORS=0
VALIDATION_WARNINGS=0

# Function to print section headers
print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Function to print success
print_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

# Function to print error
print_error() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((VALIDATION_ERRORS++))
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((VALIDATION_WARNINGS++))
}

# Function to check if file exists
check_file() {
    local file=$1
    local description=$2

    if [ -f "$file" ]; then
        print_success "$description: $file"
        return 0
    else
        print_error "$description: $file NOT FOUND"
        return 1
    fi
}

# Function to check if directory exists
check_directory() {
    local dir=$1
    local description=$2

    if [ -d "$dir" ]; then
        print_success "$description: $dir"
        return 0
    else
        print_error "$description: $dir NOT FOUND"
        return 1
    fi
}

echo -e "${GREEN}Repository Reorganization Validation${NC}"
echo -e "${GREEN}Started at: $(date)${NC}"

# =============================================================================
# Phase 1: Directory Structure Validation
# =============================================================================
print_header "Phase 1: Validating Directory Structure"

check_directory "scripts/docker" "Scripts docker directory"
check_directory "scripts/deployment" "Scripts deployment directory"
check_directory "scripts/validation" "Scripts validation directory"
check_directory "scripts/utils" "Scripts utils directory"
check_directory "scripts/migration" "Scripts migration directory"

check_directory "docker/dockerfiles" "Docker dockerfiles directory"
check_directory "docker/compose" "Docker compose directory"
check_directory "docker/ignore" "Docker ignore directory"

check_directory "docs/deployment" "Docs deployment directory"
check_directory "docs/development" "Docs development directory"
check_directory "docs/architecture" "Docs architecture directory"
check_directory "docs/security" "Docs security directory"
check_directory "docs/performance" "Docs performance directory"

# =============================================================================
# Phase 2: File Existence Validation
# =============================================================================
print_header "Phase 2: Validating Copied Files"

# Docker files
check_file "docker/dockerfiles/Dockerfile" "Dockerfile (new location)"
check_file "docker/dockerfiles/Dockerfile.production" "Dockerfile.production (new location)"
check_file "docker/dockerfiles/Dockerfile.test" "Dockerfile.test (new location)"
check_file "docker/ignore/.dockerignore" "dockerignore (new location)"
check_file "docker/ignore/.dockerignore.test" "dockerignore.test (new location)"

# Docker compose files
check_file "docker/compose/docker-compose.yml" "docker-compose.yml (new location)"
check_file "docker/compose/docker-compose.prod.yml" "docker-compose.prod.yml (new location)"

# Scripts - deployment
check_file "scripts/deployment/setup.sh" "setup.sh (new location)"

# Scripts - validation
check_file "scripts/validation/production_checklist.sh" "production_checklist.sh (new location)"
check_file "scripts/validation/validate_project.sh" "validate_project.sh (new location)"
check_file "scripts/validation/verify_setup.sh" "verify_setup.sh (new location)"
check_file "scripts/validation/verify_workflow.sh" "verify_workflow.sh (new location)"
check_file "scripts/validation/verify_ci_setup.sh" "verify_ci_setup.sh (new location)"

# Scripts - utils
check_file "scripts/utils/fix_structure.sh" "fix_structure.sh (new location)"

# Documentation
check_file "docs/deployment/BRANCH_COMPARISON.md" "BRANCH_COMPARISON.md (new location)"

# Migration files
check_file "scripts/migration/MIGRATION_MANIFEST.md" "Migration manifest"

# =============================================================================
# Phase 3: Original Files Still Present (Backwards Compatibility)
# =============================================================================
print_header "Phase 3: Validating Original Files (Backwards Compatibility)"

check_file "Dockerfile" "Original Dockerfile"
check_file "Dockerfile.production" "Original Dockerfile.production"
check_file "Dockerfile.test" "Original Dockerfile.test"
check_file ".dockerignore" "Original .dockerignore"
check_file ".dockerignore.test" "Original .dockerignore.test"
check_file "docker-compose.yml" "Original docker-compose.yml"
check_file "docker-compose.prod.yml" "Original docker-compose.prod.yml"

check_file "scripts/setup.sh" "Original setup.sh"
check_file "scripts/production_checklist.sh" "Original production_checklist.sh"
check_file "scripts/validate_project.sh" "Original validate_project.sh"
check_file "scripts/verify_setup.sh" "Original verify_setup.sh"

# =============================================================================
# Phase 4: Backup Files Validation
# =============================================================================
print_header "Phase 4: Validating Backup Files"

check_file "Makefile.backup" "Makefile backup"
check_file ".github/workflows/ci.yml.backup" "CI workflow backup"
check_file "docker-compose.yml.backup" "docker-compose.yml backup"
check_file "docker-compose.prod.yml.backup" "docker-compose.prod.yml backup"
check_file "README.md.backup" "README.md backup"

# =============================================================================
# Phase 5: File Permissions Validation
# =============================================================================
print_header "Phase 5: Validating File Permissions"

# Check that scripts are executable
for script in \
    "scripts/deployment/setup.sh" \
    "scripts/validation/production_checklist.sh" \
    "scripts/validation/validate_project.sh" \
    "scripts/validation/verify_setup.sh" \
    "scripts/validation/verify_workflow.sh" \
    "scripts/validation/verify_ci_setup.sh" \
    "scripts/utils/fix_structure.sh"; do

    if [ -f "$script" ]; then
        if [ -x "$script" ]; then
            print_success "Executable: $script"
        else
            print_warning "Not executable: $script (may need chmod +x)"
        fi
    fi
done

# =============================================================================
# Phase 6: Content Integrity Validation
# =============================================================================
print_header "Phase 6: Validating File Content Integrity"

# Compare original and copied files to ensure they're identical
compare_files() {
    local original=$1
    local copy=$2
    local description=$3

    if [ -f "$original" ] && [ -f "$copy" ]; then
        if cmp -s "$original" "$copy"; then
            print_success "Content match: $description"
        else
            print_error "Content mismatch: $description"
        fi
    fi
}

compare_files "Dockerfile" "docker/dockerfiles/Dockerfile" "Dockerfile"
compare_files "Dockerfile.production" "docker/dockerfiles/Dockerfile.production" "Dockerfile.production"
compare_files "Dockerfile.test" "docker/dockerfiles/Dockerfile.test" "Dockerfile.test"
compare_files ".dockerignore" "docker/ignore/.dockerignore" ".dockerignore"
compare_files ".dockerignore.test" "docker/ignore/.dockerignore.test" ".dockerignore.test"

compare_files "docker-compose.yml" "docker/compose/docker-compose.yml" "docker-compose.yml"
compare_files "docker-compose.prod.yml" "docker/compose/docker-compose.prod.yml" "docker-compose.prod.yml"

compare_files "scripts/setup.sh" "scripts/deployment/setup.sh" "setup.sh"
compare_files "scripts/production_checklist.sh" "scripts/validation/production_checklist.sh" "production_checklist.sh"
compare_files "scripts/validate_project.sh" "scripts/validation/validate_project.sh" "validate_project.sh"
compare_files "scripts/verify_setup.sh" "scripts/validation/verify_setup.sh" "verify_setup.sh"
compare_files "scripts/ci/verify_workflow.sh" "scripts/validation/verify_workflow.sh" "verify_workflow.sh"
compare_files "scripts/ci/verify_setup.sh" "scripts/validation/verify_ci_setup.sh" "verify_ci_setup.sh"
compare_files "scripts/ci/fix_structure.sh" "scripts/utils/fix_structure.sh" "fix_structure.sh"

compare_files "docs/guides/BRANCH_COMPARISON.md" "docs/deployment/BRANCH_COMPARISON.md" "BRANCH_COMPARISON.md"

# =============================================================================
# Phase 7: Reference Validation
# =============================================================================
print_header "Phase 7: Checking for Broken References"

# Check if any files still reference old script paths (they shouldn't based on our analysis)
echo "Checking Makefile for old script references..."
if grep -q "scripts/setup.sh\|scripts/production_checklist.sh\|scripts/validate_project.sh\|scripts/verify_setup.sh" Makefile 2>/dev/null; then
    print_warning "Makefile contains references to old script paths"
else
    print_success "Makefile: No old script path references found"
fi

echo "Checking GitHub workflows for old script references..."
if grep -q "scripts/setup.sh\|scripts/production_checklist.sh\|scripts/validate_project.sh\|scripts/verify_setup.sh" .github/workflows/*.yml 2>/dev/null; then
    print_warning "GitHub workflows contain references to old script paths"
else
    print_success "GitHub workflows: No old script path references found"
fi

echo "Checking docker-compose files for old script references..."
if grep -q "scripts/setup.sh\|scripts/production_checklist.sh\|scripts/validate_project.sh\|scripts/verify_setup.sh" docker-compose*.yml 2>/dev/null; then
    print_warning "Docker-compose files contain references to old script paths"
else
    print_success "Docker-compose files: No old script path references found"
fi

# =============================================================================
# Phase 8: Basic Functionality Tests
# =============================================================================
print_header "Phase 8: Basic Functionality Tests"

# Test Makefile help
echo "Testing: make help"
if make help >/dev/null 2>&1; then
    print_success "make help executes successfully"
else
    print_error "make help failed"
fi

# Test Docker compose config validation
echo "Testing: docker-compose config validation"
if docker-compose -f docker-compose.yml config >/dev/null 2>&1; then
    print_success "docker-compose.yml validates successfully"
else
    print_error "docker-compose.yml validation failed"
fi

if docker-compose -f docker-compose.prod.yml config >/dev/null 2>&1; then
    print_success "docker-compose.prod.yml validates successfully"
else
    print_error "docker-compose.prod.yml validation failed"
fi

# Test that new compose files also validate
echo "Testing: New compose file locations"
if docker-compose -f docker/compose/docker-compose.yml config >/dev/null 2>&1; then
    print_success "docker/compose/docker-compose.yml validates successfully"
else
    print_error "docker/compose/docker-compose.yml validation failed"
fi

if docker-compose -f docker/compose/docker-compose.prod.yml config >/dev/null 2>&1; then
    print_success "docker/compose/docker-compose.prod.yml validates successfully"
else
    print_error "docker/compose/docker-compose.prod.yml validation failed"
fi

# Test script syntax
echo "Testing: Script syntax validation"
for script in \
    "scripts/deployment/setup.sh" \
    "scripts/validation/production_checklist.sh" \
    "scripts/validation/validate_project.sh" \
    "scripts/validation/verify_setup.sh" \
    "scripts/validation/verify_workflow.sh" \
    "scripts/validation/verify_ci_setup.sh" \
    "scripts/utils/fix_structure.sh"; do

    if [ -f "$script" ]; then
        if bash -n "$script" 2>/dev/null; then
            print_success "Syntax valid: $script"
        else
            print_error "Syntax error: $script"
        fi
    fi
done

# =============================================================================
# Final Summary
# =============================================================================
print_header "Validation Summary"

echo ""
echo -e "${BLUE}Total Checks:${NC}"
echo -e "  Errors:   ${RED}$VALIDATION_ERRORS${NC}"
echo -e "  Warnings: ${YELLOW}$VALIDATION_WARNINGS${NC}"
echo ""

if [ $VALIDATION_ERRORS -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}VALIDATION PASSED${NC}"
    echo -e "${GREEN}All checks completed successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "The repository reorganization appears to be successful."
    echo "Original files remain in place for backwards compatibility."
    echo ""
    echo "Next steps:"
    echo "1. Test all build processes manually"
    echo "2. Run CI/CD pipeline"
    echo "3. Test deployment processes"
    echo "4. Monitor for 1-2 weeks"
    echo "5. Create cleanup plan to remove original files"
    echo ""
    exit 0
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}VALIDATION FAILED${NC}"
    echo -e "${RED}Found $VALIDATION_ERRORS error(s)${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo "Please review the errors above and fix them before proceeding."
    echo "If needed, run the rollback script: bash scripts/migration/rollback.sh"
    echo ""
    exit 1
fi
