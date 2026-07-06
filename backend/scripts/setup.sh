#!/bin/bash

# TalkToData Enterprise Setup Script
# This script sets up the development environment for TalkToData Enterprise

set -e  # Exit on any error

echo "🚀 Setting up TalkToData Enterprise Development Environment"
echo "============================================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.template .env
    echo "✅ Created .env file. Please edit it with your configuration."
    echo "   Minimum required: GOOGLE_API_KEY"
    
    # Prompt for Google API Key
    read -p "Enter your Google API Key (or press Enter to skip): " google_api_key
    if [ ! -z "$google_api_key" ]; then
        sed -i.bak "s/your-google-api-key-here/$google_api_key/" .env
        rm .env.bak 2>/dev/null || true
        echo "✅ Google API Key configured"
    fi
else
    echo "✅ Found existing .env file"
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p logs
mkdir -p scripts
mkdir -p nginx
echo "✅ Directories created"

# Pull Docker images
echo "🐳 Pulling Docker images..."
docker-compose -f docker-compose.dev.yml pull

# Build the application
echo "🔨 Building TalkToData application..."
docker-compose -f docker-compose.dev.yml build

# Start the services
echo "🚀 Starting development services..."
docker-compose -f docker-compose.dev.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 20

# Check service health
echo "🏥 Checking service health..."

# Check PostgreSQL
if docker-compose -f docker-compose.dev.yml exec -T postgres pg_isready -U dev_user -d talktodb_dev > /dev/null 2>&1; then
    echo "✅ PostgreSQL is ready"
else
    echo "❌ PostgreSQL is not ready"
fi

# Check Redis
if docker-compose -f docker-compose.dev.yml exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is ready"
else
    echo "❌ Redis is not ready"
fi

# Check API
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API is ready"
else
    echo "❌ API is not ready"
fi

echo ""
echo "🎉 TalkToData Enterprise Development Environment is ready!"
echo ""
echo "📊 Available Services:"
echo "   • API Server:      http://localhost:8000"
echo "   • API Docs:        http://localhost:8000/docs"
echo "   • Flower (Celery): http://localhost:5555"
echo "   • pgAdmin:         http://localhost:5050"
echo "   • Redis Commander: http://localhost:8081"
echo ""
echo "🔐 Default Credentials:"
echo "   • pgAdmin:         admin@talktodb.com / admin"
echo "   • Default Admin:   admin / admin123 (change this!)"
echo ""
echo "📝 Useful Commands:"
echo "   • View logs:       docker-compose -f docker-compose.dev.yml logs -f"
echo "   • Stop services:   docker-compose -f docker-compose.dev.yml down"
echo "   • Restart API:     docker-compose -f docker-compose.dev.yml restart api"
echo "   • Run tests:       docker-compose -f docker-compose.dev.yml exec api pytest"
echo ""
echo "🚀 Next Steps:"
echo "   1. Open http://localhost:8000/docs to explore the API"
echo "   2. Configure your Google API Key in .env if not done already"
echo "   3. Test the system with some queries"
echo ""

# Create a simple test script
cat > test_api.sh << 'EOF'
#!/bin/bash

# Simple API test script
echo "Testing TalkToData API..."

# Test health endpoint
echo "1. Testing health endpoint..."
curl -s http://localhost:8000/health | jq .

# Test login (you'll need to create a user first)
echo "2. Testing authentication..."
echo "Use the API docs at http://localhost:8000/docs to test authentication"

echo "Test completed!"
EOF

chmod +x test_api.sh

echo "📋 Created test_api.sh for API testing"
echo ""
echo "Happy coding! 🎉"
