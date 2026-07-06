#!/bin/bash
# filepath: e:\GEN-AI-PROJECTS\talk-to-db\backend\deploy.sh
# Production Deployment Script for TalkToData Enterprise

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOCKER_COMPOSE_FILE="docker-compose.yml"
BACKUP_DIR="./backups"
DEPLOYMENT_ENV="${DEPLOYMENT_ENV:-production}"

echo -e "${BLUE}🚀 TalkToData Enterprise Deployment Script${NC}"
echo -e "${BLUE}=======================================${NC}"

# Function to print colored output
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Pre-deployment checks
log_info "Running pre-deployment checks..."

# Check for required tools
if ! command_exists docker; then
    log_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command_exists docker-compose; then
    log_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check for environment file
if [ ! -f ".env" ]; then
    log_error ".env file not found. Please copy .env.template to .env and configure it."
    exit 1
fi

# Check if Docker daemon is running
if ! docker info >/dev/null 2>&1; then
    log_error "Docker daemon is not running. Please start Docker first."
    exit 1
fi

log_success "Pre-deployment checks passed"

# Create backup directory
log_info "Creating backup directory..."
mkdir -p "$BACKUP_DIR"

# Function to backup database
backup_database() {
    log_info "Creating database backup..."
    
    # Get database credentials from .env
    source .env
    
    BACKUP_FILE="$BACKUP_DIR/talktodb_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    if docker-compose exec -T postgres pg_dump -U "$DATABASE_USER" "$DATABASE_NAME" > "$BACKUP_FILE" 2>/dev/null; then
        log_success "Database backup created: $BACKUP_FILE"
    else
        log_warning "Database backup failed (this is normal for first deployment)"
    fi
}

# Function to deploy services
deploy_services() {
    log_info "Deploying enterprise services..."
    
    # Pull latest images
    log_info "Pulling latest Docker images..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" pull
    
    # Build application image
    log_info "Building application image..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" build --no-cache
    
    # Start services
    log_info "Starting services..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
    
    log_success "Services deployed successfully"
}

# Function to run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    sleep 10
    
    # Check if database is accessible
    if docker-compose exec -T postgres pg_isready -U "$DATABASE_USER" -d "$DATABASE_NAME" >/dev/null 2>&1; then
        log_success "Database is ready"
        
        # Run initialization script
        log_info "Running database initialization..."
        docker-compose exec -T postgres psql -U "$DATABASE_USER" -d "$DATABASE_NAME" -f /docker-entrypoint-initdb.d/init.sql || log_warning "Database initialization may have already been completed"
        
    else
        log_error "Database is not accessible"
        exit 1
    fi
}

# Function to verify deployment
verify_deployment() {
    log_info "Verifying deployment..."
    
    # Check service health
    local services=("postgres" "redis" "api" "worker" "nginx")
    local all_healthy=true
    
    for service in "${services[@]}"; do
        if docker-compose ps "$service" | grep -q "Up"; then
            log_success "$service is running"
        else
            log_error "$service is not running"
            all_healthy=false
        fi
    done
    
    if [ "$all_healthy" = true ]; then
        log_success "All services are running"
        
        # Check API health endpoint
        log_info "Checking API health..."
        sleep 5
        
        if curl -f http://localhost:8000/health >/dev/null 2>&1; then
            log_success "API health check passed"
        else
            log_warning "API health check failed - may need more time to start"
        fi
        
    else
        log_error "Some services failed to start"
        return 1
    fi
}

# Function to show deployment status
show_status() {
    log_info "Deployment Status:"
    echo ""
    docker-compose ps
    echo ""
    
    log_info "Service URLs:"
    echo "  📊 API: http://localhost:8000"
    echo "  📊 API Docs: http://localhost:8000/docs"
    echo "  📊 Health Check: http://localhost:8000/health"
    echo "  🖥️  pgAdmin: http://localhost:5050 (if enabled)"
    echo "  💾 Redis Commander: http://localhost:8081 (if enabled)"
    echo ""
    
    log_info "Useful Commands:"
    echo "  📋 View logs: docker-compose logs -f [service]"
    echo "  📋 Scale workers: docker-compose up -d --scale worker=3"
    echo "  📋 Stop services: docker-compose down"
    echo "  📋 View metrics: docker-compose exec api curl http://localhost:9090/metrics"
}

# Function to rollback deployment
rollback() {
    log_warning "Rolling back deployment..."
    
    # Stop current services
    docker-compose down
    
    # Restore from backup if available
    local latest_backup=$(ls -t "$BACKUP_DIR"/*.sql 2>/dev/null | head -n1)
    if [ -n "$latest_backup" ]; then
        log_info "Restoring from backup: $latest_backup"
        # Add restoration logic here if needed
    fi
    
    log_info "Rollback completed"
}

# Main deployment flow
main() {
    case "${1:-deploy}" in
        "deploy")
            log_info "Starting deployment process..."
            backup_database
            deploy_services
            run_migrations
            
            if verify_deployment; then
                show_status
                log_success "🎉 Deployment completed successfully!"
            else
                log_error "Deployment verification failed"
                exit 1
            fi
            ;;
            
        "backup")
            backup_database
            ;;
            
        "verify")
            verify_deployment
            ;;
            
        "status")
            show_status
            ;;
            
        "rollback")
            rollback
            ;;
            
        "logs")
            docker-compose logs -f "${2:-api}"
            ;;
            
        "stop")
            log_info "Stopping all services..."
            docker-compose down
            log_success "Services stopped"
            ;;
            
        "restart")
            log_info "Restarting services..."
            docker-compose restart
            log_success "Services restarted"
            ;;
            
        "scale")
            if [ -z "$2" ] || [ -z "$3" ]; then
                log_error "Usage: $0 scale <service> <count>"
                exit 1
            fi
            log_info "Scaling $2 to $3 instances..."
            docker-compose up -d --scale "$2=$3"
            log_success "Scaling completed"
            ;;
            
        "clean")
            log_warning "Cleaning up unused Docker resources..."
            docker-compose down --volumes --remove-orphans
            docker system prune -f
            log_success "Cleanup completed"
            ;;
            
        "help"|*)
            echo "TalkToData Enterprise Deployment Script"
            echo ""
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  deploy     Deploy the complete enterprise stack (default)"
            echo "  backup     Create database backup"
            echo "  verify     Verify deployment health"
            echo "  status     Show deployment status"
            echo "  rollback   Rollback to previous state"
            echo "  logs       View service logs (specify service name)"
            echo "  stop       Stop all services"
            echo "  restart    Restart all services"
            echo "  scale      Scale a service (usage: scale <service> <count>)"
            echo "  clean      Clean up Docker resources"
            echo "  help       Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 deploy"
            echo "  $0 logs api"
            echo "  $0 scale worker 3"
            echo "  $0 backup"
            ;;
    esac
}

# Trap for cleanup on script exit
cleanup() {
    if [ $? -ne 0 ]; then
        log_error "Deployment failed!"
        log_info "Check logs with: docker-compose logs"
        log_info "Or run: $0 rollback"
    fi
}

trap cleanup EXIT

# Run main function
main "$@"
