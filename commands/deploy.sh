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
sleep 20

echo "🔍 Checking service health..."
docker compose -f docker-compose-prod.yml ps || handle_error "Failed to check services"

echo "✅ Deployment completed successfully!"
echo ""
if [ "$FULL_RESET" = true ]; then
    echo "⚠️  Database was reset. You may need to create initial data."
else
    echo "ℹ️  Database data preserved. Migrations ran automatically."
fi
echo "ℹ️  Use --full-reset flag to completely reset database and volumes."
