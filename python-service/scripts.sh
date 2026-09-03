#!/bin/bash

# Python Service Development Scripts

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Setup virtual environment
setup_env() {
    print_status "Setting up Python virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    print_status "Virtual environment setup complete"
}

# Run the application locally
run_local() {
    print_status "Starting Flask application locally..."
    source venv/bin/activate
    export FLASK_APP=app.py
    export FLASK_ENV=development
    python app.py
}

# Run unit tests
run_tests() {
    print_status "Running unit tests..."
    source venv/bin/activate
    python -m pytest tests.py -v --tb=short
}

# Build Docker image
build_docker() {
    print_status "Building Docker image..."
    docker build -t python-embedding-service:latest .
    if [ $? -eq 0 ]; then
        print_status "Docker image built successfully"
    else
        print_error "Failed to build Docker image"
    fi
}

# Run Docker container
run_docker() {
    print_status "Starting Docker container..."
    docker run -p 5000:5000 \
        -e DB_HOST=db \
        -e DB_NAME=myappdb \
        -e DB_USER=postgres \
        -e DB_PASSWORD=postgres \
        python-embedding-service:latest
}

# Test API endpoints
test_api() {
    print_status "Testing API endpoints..."
    
    BASE_URL="http://localhost:5000"
    
    # Health check
    print_status "Testing health endpoint..."
    curl -X GET $BASE_URL/health | jq .
    
    # Generate single embedding
    print_status "Testing single embedding generation..."
    curl -X POST $BASE_URL/api/v1/embeddings \
        -H "Content-Type: application/json" \
        -d '{
            "address": "123 Main St, New York, NY 10001",
            "encryption_password": "test-password"
        }' | jq .
    
    # Get stats
    print_status "Testing stats endpoint..."
    curl -X GET $BASE_URL/api/v1/stats | jq .
}

# Clean up
cleanup() {
    print_status "Cleaning up..."
    deactivate 2>/dev/null || true
    rm -rf __pycache__ .pytest_cache .coverage
    print_status "Cleanup complete"
}

# Main script
case "${1:-help}" in
    setup)
        setup_env
        ;;
    run)
        run_local
        ;;
    test)
        run_tests
        ;;
    docker-build)
        build_docker
        ;;
    docker-run)
        run_docker
        ;;
    test-api)
        test_api
        ;;
    clean)
        cleanup
        ;;
    help)
        echo "Usage: $0 {setup|run|test|docker-build|docker-run|test-api|clean}"
        echo ""
        echo "Commands:"
        echo "  setup         - Set up Python virtual environment"
        echo "  run           - Run Flask application locally"
        echo "  test          - Run unit tests"
        echo "  docker-build  - Build Docker image"
        echo "  docker-run    - Run Docker container"
        echo "  test-api      - Test API endpoints"
        echo "  clean         - Clean up temporary files"
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac
