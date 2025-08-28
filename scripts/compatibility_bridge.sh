#!/bin/bash
# Compatibility bridge to maintain requirements.txt files from Poetry
# This ensures backward compatibility during the migration period

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REQUIREMENTS_DIR="$PROJECT_ROOT/config/requirements"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Poetry is installed
check_poetry() {
    if ! command -v poetry &> /dev/null && ! python3 -m poetry --version &> /dev/null; then
        log_error "Poetry is not installed. Please install Poetry first."
        exit 1
    fi
}

# Export base requirements
export_base() {
    log_info "Exporting base requirements..."
    python3 -m poetry export \
        --format requirements.txt \
        --output "$REQUIREMENTS_DIR/base.txt" \
        --without-hashes \
        --without dev,test,docs,ml-gpu,ml-cpu \
        2>/dev/null || {
            log_warning "Failed to export base requirements with groups, trying without..."
            python3 -m poetry export \
                --format requirements.txt \
                --output "$REQUIREMENTS_DIR/base.txt" \
                --without-hashes \
                2>/dev/null
        }
    
    # Add header
    sed -i.bak '1i\
# Auto-generated from Poetry - DO NOT EDIT MANUALLY\
# Generated: '"$(date)"'\
# Run scripts/compatibility_bridge.sh to regenerate\
' "$REQUIREMENTS_DIR/base.txt"
    rm -f "$REQUIREMENTS_DIR/base.txt.bak"
}

# Export dev requirements
export_dev() {
    log_info "Exporting dev requirements..."
    python3 -m poetry export \
        --format requirements.txt \
        --output "$REQUIREMENTS_DIR/dev.txt" \
        --without-hashes \
        --with dev \
        --without test,docs,ml-gpu,ml-cpu \
        2>/dev/null || {
            log_warning "Failed to export dev requirements with specific groups"
            python3 -m poetry export \
                --format requirements.txt \
                --output "$REQUIREMENTS_DIR/dev.txt" \
                --without-hashes \
                --dev \
                2>/dev/null
        }
    
    # Add header
    sed -i.bak '1i\
# Auto-generated from Poetry - DO NOT EDIT MANUALLY\
# Development dependencies\
# Generated: '"$(date)"'\
' "$REQUIREMENTS_DIR/dev.txt"
    rm -f "$REQUIREMENTS_DIR/dev.txt.bak"
}

# Export prod requirements
export_prod() {
    log_info "Exporting prod requirements..."
    python3 -m poetry export \
        --format requirements.txt \
        --output "$REQUIREMENTS_DIR/prod.txt" \
        --without-hashes \
        --with prod \
        --extras "all" \
        2>/dev/null || {
            log_warning "Using base requirements for prod"
            cp "$REQUIREMENTS_DIR/base.txt" "$REQUIREMENTS_DIR/prod.txt"
        }
    
    # Add header
    sed -i.bak '1i\
# Auto-generated from Poetry - DO NOT EDIT MANUALLY\
# Production dependencies with all extras\
# Generated: '"$(date)"'\
' "$REQUIREMENTS_DIR/prod.txt"
    rm -f "$REQUIREMENTS_DIR/prod.txt.bak"
}

# Export ML requirements based on environment
export_ml() {
    local env="${1:-cpu}"
    
    log_info "Exporting ML requirements for $env environment..."
    
    if [ "$env" == "gpu" ]; then
        python3 -m poetry export \
            --format requirements.txt \
            --output "$REQUIREMENTS_DIR/ml-gpu.txt" \
            --without-hashes \
            --with ml-gpu \
            2>/dev/null || log_warning "No ML-GPU group found"
    else
        python3 -m poetry export \
            --format requirements.txt \
            --output "$REQUIREMENTS_DIR/ml-cpu.txt" \
            --without-hashes \
            --with ml-cpu \
            2>/dev/null || log_warning "No ML-CPU group found"
    fi
}

# Validate exported files
validate_exports() {
    log_info "Validating exported requirements..."
    
    local all_valid=true
    
    for file in base.txt dev.txt prod.txt; do
        if [ -f "$REQUIREMENTS_DIR/$file" ]; then
            local line_count=$(wc -l < "$REQUIREMENTS_DIR/$file")
            if [ "$line_count" -lt 5 ]; then
                log_warning "$file seems too small ($line_count lines)"
                all_valid=false
            else
                log_info "✓ $file validated ($line_count lines)"
            fi
        else
            log_error "$file not found"
            all_valid=false
        fi
    done
    
    if [ "$all_valid" = true ]; then
        log_info "✅ All requirements files validated successfully"
        return 0
    else
        log_error "❌ Validation failed for some files"
        return 1
    fi
}

# Create compatibility symlinks
create_symlinks() {
    log_info "Creating compatibility symlinks..."
    
    # Create root-level requirements.txt as symlink to base.txt
    ln -sf "config/requirements/base.txt" "$PROJECT_ROOT/requirements.txt"
    ln -sf "config/requirements/dev.txt" "$PROJECT_ROOT/requirements-dev.txt"
    ln -sf "config/requirements/prod.txt" "$PROJECT_ROOT/requirements-prod.txt"
    
    log_info "Symlinks created for backward compatibility"
}

# Generate constraints file
generate_constraints() {
    log_info "Generating constraints file..."
    
    cat > "$PROJECT_ROOT/config/dependencies/constraints.txt" << 'EOF'
# Upper bound constraints for stability
# These prevent unexpected breaking changes

# Core dependencies
fastapi<1.0.0
pydantic<3.0.0
uvicorn<1.0.0

# ML/AI libraries
openai<2.0.0
numpy<2.0.0
pandas<3.0.0

# Infrastructure
redis<6.0.0
aiohttp<4.0.0
httpx<1.0.0

# Testing
pytest<8.0.0
EOF
    
    log_info "Constraints file generated"
}

# Watch mode - auto-export on pyproject.toml changes
watch_mode() {
    log_info "Starting watch mode..."
    log_info "Watching for changes to pyproject.toml..."
    
    # Check if fswatch is available
    if ! command -v fswatch &> /dev/null; then
        log_warning "fswatch not installed. Install with: brew install fswatch"
        log_info "Falling back to periodic checks..."
        
        while true; do
            sleep 10
            if [ "$PROJECT_ROOT/pyproject.toml" -nt "$REQUIREMENTS_DIR/base.txt" ]; then
                log_info "Change detected, regenerating..."
                main
            fi
        done
    else
        fswatch -o "$PROJECT_ROOT/pyproject.toml" | while read num; do
            log_info "Change detected, regenerating..."
            main
        done
    fi
}

# Main export function
main() {
    check_poetry
    
    # Create directories if needed
    mkdir -p "$REQUIREMENTS_DIR"
    mkdir -p "$PROJECT_ROOT/config/dependencies"
    
    # Export all formats
    export_base
    export_dev
    export_prod
    export_ml "cpu"
    export_ml "gpu"
    
    # Additional tasks
    create_symlinks
    generate_constraints
    
    # Validate
    validate_exports
}

# Parse arguments
case "${1:-}" in
    watch)
        main
        watch_mode
        ;;
    validate)
        validate_exports
        ;;
    constraints)
        generate_constraints
        ;;
    *)
        main
        ;;
esac