#!/bin/bash

set -e

REPO_URL="https://github.com/Oneyura/online-cinema-api.git"
APP_DIR="/home/ubuntu/online-cinema-api"
BRANCH="develop"

handle_error() {
    echo "❌ Error: $1"
    exit 1
}

echo "🚀 Starting deployment process..."

if [ ! -d "$APP_DIR" ]; then
    echo "📥 Cloning repository..."
    git clone -b $BRANCH "$REPO_URL" "$APP_DIR" || handle_error "Failed to clone repository"
else
    echo "🔄 Updating existing repository..."
    cd "$APP_DIR" || handle_error "Failed to enter app directory"
    git fetch origin $BRANCH || handle_error "Failed to fetch"
    git reset --hard origin/$BRANCH || handle_error "Failed to reset"
fi

cd "$APP_DIR" || handle_error "Failed to enter app directory"

echo "🔒 Checking environment files..."
if [ ! -f ".env.prod" ]; then
    handle_error "Missing .env.prod file"
fi

echo "🐳 Stopping and removing containers..."
docker compose -f docker-compose-prod.yml down -v || true
docker compose -f docker-compose-prod.yml rm -f || true

echo "🧹 Removing old containers and volumes..."
containers=$(docker ps -a -q --filter "name=online-cinema-api")
if [ ! -z "$containers" ]; then
    docker rm -f $containers || true
fi

echo "🧹 Cleaning up old images..."
docker system prune -f

echo "🏗️ Building and starting containers..."
docker compose -f docker-compose-prod.yml up -d --build --remove-orphans || handle_error "Docker Compose failed"

echo "⏳ Waiting for services to start..."
sleep 15

echo "🔍 Checking service health..."
docker compose -f docker-compose-prod.yml ps || handle_error "Failed to check services"

echo "✅ Deployment completed successfully!"
