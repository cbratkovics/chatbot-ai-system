#!/bin/bash
# Rollback script for repository reorganization
# This script removes the new directory structure and restores backup files if needed

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${RED}========================================${NC}"
echo -e "${RED}Repository Reorganization Rollback${NC}"
echo -e "${RED}========================================${NC}"
echo ""
echo -e "${YELLOW}WARNING: This script will remove the new directory structure${NC}"
echo -e "${YELLOW}and restore configuration files from backups.${NC}"
echo ""
echo -e "${YELLOW}The following actions will be performed:${NC}"
echo "1. Restore backed up configuration files"
echo "2. Remove new Docker directories"
echo "3. Remove new script subdirectories"
echo "4. Remove new documentation directories"
echo "5. Keep scripts/migration for reference"
echo ""

# Ask for confirmation
read -p "Are you sure you want to proceed with rollback? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${GREEN}Rollback cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}Starting rollback process...${NC}"
echo ""

ROLLBACK_ERRORS=0

# Function to print success
print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Function to print error
print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    ((ROLLBACK_ERRORS++))
}

# Function to print info
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# =============================================================================
# Step 1: Restore Configuration Files from Backups
# =============================================================================
echo -e "${BLUE}Step 1: Restoring configuration files from backups${NC}"
echo ""

restore_backup() {
    local backup_file=$1
    local original_file=$2

    if [ -f "$backup_file" ]; then
        if cp "$backup_file" "$original_file"; then
            print_success "Restored $original_file from backup"
        else
            print_error "Failed to restore $original_file"
        fi
    else
        print_info "No backup found for $original_file (skipping)"
    fi
}

restore_backup "Makefile.backup" "Makefile"
restore_backup ".github/workflows/ci.yml.backup" ".github/workflows/ci.yml"
restore_backup "docker-compose.yml.backup" "docker-compose.yml"
restore_backup "docker-compose.prod.yml.backup" "docker-compose.prod.yml"
restore_backup "README.md.backup" "README.md"

echo ""

# =============================================================================
# Step 2: Remove New Docker Directory Structure
# =============================================================================
echo -e "${BLUE}Step 2: Removing new Docker directory structure${NC}"
echo ""

if [ -d "docker/dockerfiles" ]; then
    if rm -rf docker/dockerfiles; then
        print_success "Removed docker/dockerfiles/"
    else
        print_error "Failed to remove docker/dockerfiles/"
    fi
else
    print_info "docker/dockerfiles/ does not exist (skipping)"
fi

if [ -d "docker/compose" ]; then
    if rm -rf docker/compose; then
        print_success "Removed docker/compose/"
    else
        print_error "Failed to remove docker/compose/"
    fi
else
    print_info "docker/compose/ does not exist (skipping)"
fi

if [ -d "docker/ignore" ]; then
    if rm -rf docker/ignore; then
        print_success "Removed docker/ignore/"
    else
        print_error "Failed to remove docker/ignore/"
    fi
else
    print_info "docker/ignore/ does not exist (skipping)"
fi

# Remove docker/ directory if empty
if [ -d "docker" ] && [ -z "$(ls -A docker)" ]; then
    if rmdir docker; then
        print_success "Removed empty docker/ directory"
    else
        print_error "Failed to remove docker/ directory"
    fi
fi

echo ""

# =============================================================================
# Step 3: Remove New Script Subdirectories
# =============================================================================
echo -e "${BLUE}Step 3: Removing new script subdirectories${NC}"
echo ""

# Note: We keep scripts/migration/ for reference
if [ -d "scripts/docker" ]; then
    if rm -rf scripts/docker; then
        print_success "Removed scripts/docker/"
    else
        print_error "Failed to remove scripts/docker/"
    fi
else
    print_info "scripts/docker/ does not exist (skipping)"
fi

if [ -d "scripts/deployment" ]; then
    if rm -rf scripts/deployment; then
        print_success "Removed scripts/deployment/"
    else
        print_error "Failed to remove scripts/deployment/"
    fi
else
    print_info "scripts/deployment/ does not exist (skipping)"
fi

if [ -d "scripts/validation" ]; then
    if rm -rf scripts/validation; then
        print_success "Removed scripts/validation/"
    else
        print_error "Failed to remove scripts/validation/"
    fi
else
    print_info "scripts/validation/ does not exist (skipping)"
fi

# Note: scripts/utils/ existed before migration, so we only remove migrated files
if [ -f "scripts/utils/fix_structure.sh" ]; then
    # Check if this was added during migration by comparing with original
    if [ -f "scripts/ci/fix_structure.sh" ]; then
        if rm scripts/utils/fix_structure.sh; then
            print_success "Removed migrated scripts/utils/fix_structure.sh"
        else
            print_error "Failed to remove scripts/utils/fix_structure.sh"
        fi
    fi
fi

print_info "Kept scripts/migration/ for reference and history"

echo ""

# =============================================================================
# Step 4: Remove New Documentation Directories
# =============================================================================
echo -e "${BLUE}Step 4: Cleaning up new documentation directories${NC}"
echo ""

# Remove migrated files from docs/deployment/
if [ -f "docs/deployment/BRANCH_COMPARISON.md" ]; then
    # This was migrated from docs/guides/, so remove it
    if rm docs/deployment/BRANCH_COMPARISON.md; then
        print_success "Removed docs/deployment/BRANCH_COMPARISON.md"
    else
        print_error "Failed to remove docs/deployment/BRANCH_COMPARISON.md"
    fi
fi

# Remove docs/deployment if empty
if [ -d "docs/deployment" ] && [ -z "$(ls -A docs/deployment)" ]; then
    if rmdir docs/deployment; then
        print_success "Removed empty docs/deployment/"
    else
        print_error "Failed to remove docs/deployment/"
    fi
fi

# Remove docs/development if empty
if [ -d "docs/development" ] && [ -z "$(ls -A docs/development)" ]; then
    if rmdir docs/development; then
        print_success "Removed empty docs/development/"
    else
        print_error "Failed to remove docs/development/"
    fi
fi

# Note: docs/architecture, docs/security, docs/performance existed before migration
print_info "Kept existing docs directories (architecture, security, performance)"

echo ""

# =============================================================================
# Step 5: Clean Up Backup Files
# =============================================================================
echo -e "${BLUE}Step 5: Cleaning up backup files (optional)${NC}"
echo ""

read -p "Do you want to remove backup files? (yes/no): " REMOVE_BACKUPS

if [ "$REMOVE_BACKUPS" == "yes" ]; then
    for backup in Makefile.backup .github/workflows/ci.yml.backup docker-compose.yml.backup docker-compose.prod.yml.backup README.md.backup; do
        if [ -f "$backup" ]; then
            if rm "$backup"; then
                print_success "Removed $backup"
            else
                print_error "Failed to remove $backup"
            fi
        fi
    done
else
    print_info "Kept backup files for reference"
fi

echo ""

# =============================================================================
# Final Summary
# =============================================================================
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Rollback Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ $ROLLBACK_ERRORS -eq 0 ]; then
    echo -e "${GREEN}Rollback completed successfully!${NC}"
    echo ""
    echo "The repository has been restored to its pre-migration state."
    echo ""
    echo "What was done:"
    echo "- Restored configuration files from backups"
    echo "- Removed new directory structure"
    echo "- Kept original files in place"
    echo "- Kept scripts/migration/ for reference"
    echo ""
    echo "Next steps:"
    echo "1. Verify system functionality with original structure"
    echo "2. Review scripts/migration/MIGRATION_MANIFEST.md for lessons learned"
    echo "3. Consider addressing any issues before attempting migration again"
    echo ""
else
    echo -e "${RED}Rollback completed with $ROLLBACK_ERRORS error(s)${NC}"
    echo ""
    echo "Some operations failed during rollback."
    echo "Please review the errors above and manually correct any issues."
    echo ""
fi

# =============================================================================
# Verification Steps
# =============================================================================
echo -e "${BLUE}Verification Steps${NC}"
echo ""
echo "Run these commands to verify the rollback:"
echo ""
echo "1. Check original files exist:"
echo "   ls -la Dockerfile docker-compose.yml scripts/setup.sh"
echo ""
echo "2. Check new directories removed:"
echo "   ls docker/ scripts/deployment/ scripts/validation/ 2>/dev/null || echo 'Directories removed'"
echo ""
echo "3. Test make commands:"
echo "   make help"
echo ""
echo "4. Validate docker-compose:"
echo "   docker-compose config"
echo ""

exit $ROLLBACK_ERRORS
