#!/bin/bash
# filepath: e:\GEN-AI-PROJECTS\talk-to-db\backend\test_enterprise.sh
# Enterprise Testing Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

echo -e "${BLUE}🧪 TalkToData Enterprise Testing Suite${NC}"
echo -e "${BLUE}====================================${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
    log_info "Creating virtual environment..."
    python -m venv venv
    log_success "Virtual environment created"
fi

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate || source venv/Scripts/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate || source .venv/Scripts/activate
fi

log_info "Installing test dependencies..."
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-mock pytest-cov

# Ensure test environment variables
if [ ! -f ".env.test" ]; then
    log_info "Creating test environment file..."
    cp .env.template .env.test
    
    # Set test-specific values
    sed -i 's/DATABASE_NAME=talktodb/DATABASE_NAME=talktodb_test/' .env.test
    sed -i 's/REDIS_DB=0/REDIS_DB=1/' .env.test
    sed -i 's/DEBUG=false/DEBUG=true/' .env.test
fi

export TESTING=true
export ENV_FILE=.env.test

case "${1:-all}" in
    "unit")
        log_info "Running unit tests..."
        pytest tests/unit/ -v --tb=short
        ;;
        
    "integration")
        log_info "Running integration tests..."
        pytest tests/integration/ -v --tb=short --asyncio-mode=auto
        ;;
        
    "performance")
        log_info "Running performance tests..."
        pytest tests/performance/ -v --tb=short --asyncio-mode=auto
        ;;
        
    "workflow")
        log_info "Running enterprise workflow tests..."
        pytest tests/integration/test_enterprise_workflow.py -v --tb=short --asyncio-mode=auto
        ;;
        
    "coverage")
        log_info "Running tests with coverage..."
        pytest tests/ --cov=core --cov=agents --cov=enterprise_graph --cov-report=html --cov-report=term
        log_success "Coverage report generated in htmlcov/"
        ;;
        
    "all")
        log_info "Running all tests..."
        pytest tests/ -v --tb=short --asyncio-mode=auto
        ;;
        
    "quick")
        log_info "Running quick test subset..."
        pytest tests/unit/test_config.py tests/unit/test_cache.py tests/integration/test_enterprise_workflow.py::TestEnterpriseWorkflow::test_simple_query_workflow -v
        ;;
        
    "debug")
        log_info "Running tests in debug mode..."
        pytest tests/ -v -s --tb=long --asyncio-mode=auto --pdb
        ;;
        
    "help"|*)
        echo "TalkToData Enterprise Testing Script"
        echo ""
        echo "Usage: $0 [test_type]"
        echo ""
        echo "Test Types:"
        echo "  unit           Run unit tests only"
        echo "  integration    Run integration tests only"
        echo "  performance    Run performance tests only"
        echo "  workflow       Run enterprise workflow tests only"
        echo "  coverage       Run all tests with coverage report"
        echo "  all            Run all tests (default)"
        echo "  quick          Run quick test subset"
        echo "  debug          Run tests in debug mode"
        echo "  help           Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 unit"
        echo "  $0 workflow"
        echo "  $0 coverage"
        ;;
esac

if [ $? -eq 0 ]; then
    log_success "✅ Tests completed successfully!"
else
    log_error "❌ Some tests failed"
    exit 1
fi
