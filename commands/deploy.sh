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
if [ ! -f ".env" ]; then
    handle_error "Missing .env file"
fi

echo "🐳 Stopping any running containers..."
docker compose -f docker-compose-prod.yml down || true

echo "🧹 Cleaning up old images..."
docker system prune -f

echo "🏗️ Building and starting containers..."
docker compose -f docker-compose-prod.yml up -d --build || handle_error "Docker Compose failed"

echo "⏳ Waiting for services to start..."
sleep 10

echo "🔍 Checking service health..."
docker compose -f docker-compose-prod.yml ps || handle_error "Failed to check services"

echo "✅ Deployment completed successfully!"
