#!/bin/bash

set -e

REPO_URL="https://github.com/Oneyura/online-cinema-api.git"
APP_DIR="/home/ubuntu/online-cinema-api"
BRANCH="develop"

# Parse command line arguments
FULL_RESET=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --full-reset)
            FULL_RESET=true
            shift
            ;;
        *)
            echo "Unknown option $1"
            exit 1
            ;;
    esac
done

handle_error() {
    echo "❌ Error: $1"
    exit 1
}

clean_git_locks() {
    echo "🔓 Cleaning Git locks..."
    rm -f "$APP_DIR/.git/index.lock" || true
    rm -f "$APP_DIR/.git/refs/remotes/origin/*.lock" || true
    rm -f "$APP_DIR/.git/HEAD.lock" || true
}

init_default_data() {
    echo "🎯 Initializing default data..."
    
    # Try to run init command using docker exec
    local max_attempts=3
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        echo "  📝 Attempt $attempt/$max_attempts to initialize default data..."
        
        if docker compose -f docker-compose-prod.yml exec -T web python -m src.management.cli init-data --prod; then
            echo "  ✅ Default data initialized successfully!"
            return 0
        else
            echo "  ⚠️  Attempt $attempt failed, retrying in 5 seconds..."
            sleep 5
            attempt=$((attempt + 1))
        fi
    done
    
    echo "  ⚠️  Could not initialize default data after $max_attempts attempts"
    echo "  ℹ️  You can run this manually later:"
    echo "     docker compose -f docker-compose-prod.yml exec web python -m src.management.cli init-data --prod"
    return 1
}

echo "🚀 Starting deployment process..."

if [ ! -d "$APP_DIR" ]; then
    echo "📥 Cloning repository..."
    git clone -b $BRANCH "$REPO_URL" "$APP_DIR" || handle_error "Failed to clone repository"
else
    echo "🔄 Updating existing repository..."
    cd "$APP_DIR" || handle_error "Failed to enter app directory"
    clean_git_locks
    git fetch origin $BRANCH || handle_error "Failed to fetch"
    git reset --hard origin/$BRANCH || handle_error "Failed to reset"
fi

cd "$APP_DIR" || handle_error "Failed to enter app directory"

echo "🔒 Checking environment files..."
if [ ! -f ".env.prod" ]; then
    handle_error "Missing .env.prod file"
fi

if [ "$FULL_RESET" = true ]; then
    echo "⚠️  FULL RESET: Stopping and removing containers AND volumes..."
    docker compose -f docker-compose-prod.yml down -v || true
else
    echo "🐳 Stopping containers (preserving data volumes)..."
    docker compose -f docker-compose-prod.yml down || true
fi

docker compose -f docker-compose-prod.yml rm -f || true

echo "🧹 Removing old containers..."
containers=$(docker ps -a -q --filter "name=online-cinema-api")
if [ ! -z "$containers" ]; then
    docker rm -f $containers || true
fi

echo "🧹 Cleaning up old images..."
docker system prune -f

echo "🏗️ Building and starting containers..."
docker compose -f docker-compose-prod.yml up -d --build --remove-orphans || handle_error "Docker Compose failed"

echo "⏳ Waiting for services to start..."
sleep 30

echo "🔍 Checking service health..."
docker compose -f docker-compose-prod.yml ps || handle_error "Failed to check services"

echo "📊 Checking container logs..."
echo "  Backend logs (last 10 lines):"
docker compose -f docker-compose-prod.yml logs --tail=10 web || true

# Initialize default data after successful deployment
init_default_data

echo "✅ Deployment completed successfully!"
echo ""
if [ "$FULL_RESET" = true ]; then
    echo "⚠️  Database was reset and re-initialized with default data."
else
    echo "ℹ️  Database data preserved. Migrations and data initialization ran automatically."
fi
echo "ℹ️  Use --full-reset flag to completely reset database and volumes."
echo ""
echo "🔗 Available services:"
echo "   • API: https://fast-furious.work.gd"
echo "   • Docs: https://fast-furious.work.gd/docs"
echo "   • Flower: https://fast-furious.work.gd/flower (user: admin, pass: admin123)"
echo "   • MinIO: https://fast-furious.work.gd/minio (user: admin, pass: admin123)"
echo ""
echo "🛠️  Management commands:"
echo "   docker compose -f docker-compose-prod.yml exec web python -m src.management.cli init-data --prod"
echo "   docker compose -f docker-compose-prod.yml exec web python -m src.management.cli test-email --direct --prod"
