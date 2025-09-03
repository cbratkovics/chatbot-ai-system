#!/bin/bash

# Comprehensive setup script for AI Chatbot System
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="AI Chatbot System"
MIN_DOCKER_VERSION="20.10.0"
MIN_DOCKER_COMPOSE_VERSION="2.0.0"
MIN_PYTHON_VERSION="3.11"
MIN_NODE_VERSION="18"

# ASCII Art Banner
show_banner() {
    echo -e "${CYAN}"
    cat << "EOF"
    ___    ____   ________          __  __          __ 
   /   |  /  _/  / ____/ /_  ____ _/ /_/ /_  ____  / /_
  / /| |  / /   / /   / __ \/ __ `/ __/ __ \/ __ \/ __/
 / ___ |_/ /   / /___/ / / / /_/ / /_/ /_/ / /_/ / /_  
/_/  |_/___/   \____/_/ /_/\__,_/\__/_.___/\____/\__/  
                                                        
EOF
    echo -e "${NC}"
    echo -e "${GREEN}Welcome to $PROJECT_NAME Setup${NC}"
    echo "============================================="
    echo ""
}

# Logging functions
log() {
    echo -e "${GREEN}[✓]${NC} $1"
}

error() {
    echo -e "${RED}[✗]${NC} $1" >&2
    exit 1
}

warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

info() {
    echo -e "${BLUE}[i]${NC} $1"
}

# Progress indicator
show_progress() {
    local pid=$1
    local delay=0.1
    local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

# Version comparison
version_ge() {
    [ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

# Check system requirements
check_requirements() {
    echo -e "${BLUE}Checking system requirements...${NC}"
    echo ""
    
    # Check OS
    OS="$(uname -s)"
    case "${OS}" in
        Linux*)     OS_TYPE=Linux;;
        Darwin*)    OS_TYPE=Mac;;
        CYGWIN*)    OS_TYPE=Windows;;
        MINGW*)     OS_TYPE=Windows;;
        *)          OS_TYPE="UNKNOWN";;
    esac
    
    if [ "$OS_TYPE" = "UNKNOWN" ]; then
        error "Unsupported operating system: ${OS}"
    fi
    log "Operating System: $OS_TYPE"
    
    # Check Docker
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        if version_ge "$DOCKER_VERSION" "$MIN_DOCKER_VERSION"; then
            log "Docker $DOCKER_VERSION found"
        else
            warning "Docker $DOCKER_VERSION found, but $MIN_DOCKER_VERSION or higher recommended"
        fi
    else
        error "Docker not found. Please install Docker from https://docs.docker.com/get-docker/"
    fi
    
    # Check Docker Compose
    if command -v docker-compose &> /dev/null; then
        DC_VERSION=$(docker-compose --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        log "Docker Compose $DC_VERSION found"
    elif docker compose version &> /dev/null; then
        DC_VERSION=$(docker compose version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        log "Docker Compose $DC_VERSION found (plugin)"
        DOCKER_COMPOSE_CMD="docker compose"
    else
        error "Docker Compose not found. Please install Docker Compose"
    fi
    
    # Check Python (optional for local development)
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
        if version_ge "$PYTHON_VERSION" "$MIN_PYTHON_VERSION"; then
            log "Python $PYTHON_VERSION found (optional)"
        else
            info "Python $PYTHON_VERSION found, $MIN_PYTHON_VERSION recommended for development"
        fi
    else
        info "Python not found (optional for local development)"
    fi
    
    # Check Node.js (optional for frontend development)
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version | grep -oE '[0-9]+' | head -1)
        if [ "$NODE_VERSION" -ge 18 ]; then
            log "Node.js $(node --version) found (optional)"
        else
            info "Node.js $(node --version) found, v$MIN_NODE_VERSION+ recommended"
        fi
    else
        info "Node.js not found (optional for frontend development)"
    fi
    
    # Check Git
    if command -v git &> /dev/null; then
        log "Git $(git --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1) found"
    else
        warning "Git not found. Recommended for version control"
    fi
    
    echo ""
}

# Setup environment
setup_environment() {
    echo -e "${BLUE}Setting up environment...${NC}"
    echo ""
    
    # Check if .env exists
    if [ -f .env ]; then
        warning ".env file already exists"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Keeping existing .env file"
            return
        fi
    fi
    
    # Copy .env.example to .env
    if [ -f .env.example ]; then
        cp .env.example .env
        log "Created .env from .env.example"
    else
        error ".env.example not found"
    fi
    
    # Prompt for API keys
    echo ""
    echo -e "${CYAN}API Key Configuration${NC}"
    echo "----------------------"
    
    # OpenAI API Key
    read -p "Enter your OpenAI API key (or press Enter to skip): " OPENAI_KEY
    if [ ! -z "$OPENAI_KEY" ]; then
        sed -i.bak "s/OPENAI_API_KEY=.*/OPENAI_API_KEY=$OPENAI_KEY/" .env
        log "OpenAI API key configured"
    else
        warning "OpenAI API key not configured"
    fi
    
    # Anthropic API Key
    read -p "Enter your Anthropic API key (or press Enter to skip): " ANTHROPIC_KEY
    if [ ! -z "$ANTHROPIC_KEY" ]; then
        sed -i.bak "s/ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=$ANTHROPIC_KEY/" .env
        log "Anthropic API key configured"
    else
        warning "Anthropic API key not configured"
    fi
    
    # Clean up backup files
    rm -f .env.bak
    
    if [ -z "$OPENAI_KEY" ] && [ -z "$ANTHROPIC_KEY" ]; then
        warning "No API keys configured. At least one is required for the chatbot to work."
        echo "You can add them later by editing the .env file"
    fi
    
    echo ""
}

# Create necessary directories
create_directories() {
    echo -e "${BLUE}Creating necessary directories...${NC}"
    echo ""
    
    directories=(
        "logs"
        "data"
        "secrets"
        "nginx/ssl"
        "nginx/cache"
        "scripts/backup"
    )
    
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            log "Created directory: $dir"
        else
            info "Directory exists: $dir"
        fi
    done
    
    echo ""
}

# Build Docker images
build_docker_images() {
    echo -e "${BLUE}Building Docker images...${NC}"
    echo ""
    
    info "This may take several minutes on first build..."
    
    # Build all services
    ${DOCKER_COMPOSE_CMD:-docker-compose} build --no-cache &
    show_progress $!
    
    if [ $? -eq 0 ]; then
        log "Docker images built successfully"
    else
        error "Failed to build Docker images"
    fi
    
    echo ""
}

# Start services
start_services() {
    echo -e "${BLUE}Starting services...${NC}"
    echo ""
    
    ${DOCKER_COMPOSE_CMD:-docker-compose} up -d &
    show_progress $!
    
    if [ $? -eq 0 ]; then
        log "Services started successfully"
    else
        error "Failed to start services"
    fi
    
    echo ""
    
    # Show service status
    echo -e "${BLUE}Service Status:${NC}"
    ${DOCKER_COMPOSE_CMD:-docker-compose} ps
    echo ""
}

# Run health checks
run_health_checks() {
    echo -e "${BLUE}Running health checks...${NC}"
    echo ""
    
    info "Waiting for services to be ready..."
    sleep 10
    
    # Check backend health
    if curl -f -s http://localhost:8000/health > /dev/null; then
        log "Backend API is healthy"
    else
        warning "Backend API is not responding yet"
    fi
    
    # Check frontend health
    if curl -f -s http://localhost:3000 > /dev/null; then
        log "Frontend is healthy"
    else
        warning "Frontend is not responding yet"
    fi
    
    # Check Redis
    if docker exec chatbot-redis redis-cli ping > /dev/null 2>&1; then
        log "Redis is healthy"
    else
        warning "Redis is not responding"
    fi
    
    # Check PostgreSQL
    if docker exec chatbot-postgres pg_isready > /dev/null 2>&1; then
        log "PostgreSQL is healthy"
    else
        warning "PostgreSQL is not ready"
    fi
    
    echo ""
}

# Show access information
show_access_info() {
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}Setup Complete!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    echo ""
    echo -e "${CYAN}Access URLs:${NC}"
    echo "• Frontend:    http://localhost:3000"
    echo "• Backend API: http://localhost:8000"
    echo "• API Docs:    http://localhost:8000/docs"
    echo "• Health:      http://localhost:8000/health"
    echo ""
    echo -e "${CYAN}Useful Commands:${NC}"
    echo "• View logs:        docker-compose logs -f"
    echo "• Stop services:    docker-compose down"
    echo "• Restart services: docker-compose restart"
    echo "• Health check:     ./scripts/healthcheck.sh"
    echo "• Backup data:      ./scripts/backup.sh"
    echo ""
    echo -e "${CYAN}Troubleshooting:${NC}"
    echo "• If services don't start: Check logs with 'docker-compose logs'"
    echo "• If ports are in use:     Change ports in docker-compose.yml"
    echo "• If build fails:          Check Docker daemon is running"
    echo "• For more help:           See README.md and docs/"
    echo ""
}

# Cleanup function
cleanup() {
    if [ $? -ne 0 ]; then
        echo ""
        error "Setup failed. Check the logs for details."
    fi
}

# Main setup flow
main() {
    trap cleanup EXIT
    
    show_banner
    check_requirements
    setup_environment
    create_directories
    
    # Ask if user wants to build and start services
    echo -e "${CYAN}Ready to build and start services${NC}"
    read -p "Do you want to continue? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        info "Setup complete. Run 'docker-compose up -d' when ready to start."
        exit 0
    fi
    
    build_docker_images
    start_services
    run_health_checks
    show_access_info
    
    # Optional: Open browser
    if [ "$OS_TYPE" = "Mac" ]; then
        read -p "Open browser to http://localhost:3000? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            open http://localhost:3000
        fi
    elif [ "$OS_TYPE" = "Linux" ]; then
        if command -v xdg-open &> /dev/null; then
            read -p "Open browser to http://localhost:3000? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                xdg-open http://localhost:3000
            fi
        fi
    fi
}

# Run main function
main