#!/bin/bash

set -e

echo "🚀 Starting development environment..."

# Зупинити та видалити існуючі контейнери
echo "🛑 Stopping existing containers..."
docker compose -f docker-compose-dev.yml down -v || true

# Очистити Docker resources
echo "🧹 Cleaning up Docker resources..."
docker compose -f docker-compose-dev.yml rm -f || true

# Перевірити .env файл
echo "🔒 Checking environment file..."
if [ ! -f ".env" ]; then
    echo "❌ Missing .env file! Please create it before running dev environment."
    exit 1
fi

# Побудувати та запустити контейнери
echo "🏗️ Building and starting containers..."
docker compose -f docker-compose-dev.yml up -d --build

# Чекати поки сервіси запустяться
echo "⏳ Waiting for services to start..."
sleep 10

# Перевірити статус
echo "🔍 Checking service status..."
docker compose -f docker-compose-dev.yml ps

# Перевірити здоров'я сервісів
echo "💚 Waiting for database to be ready..."
timeout=60
while ! docker exec postgres_cinema pg_isready -U postgres 2>/dev/null; do
    echo "Waiting for database..."
    sleep 2
    timeout=$((timeout-2))
    if [ $timeout -le 0 ]; then
        echo "❌ Database failed to start"
        exit 1
    fi
done

echo "💚 Database is ready!"

echo "🎉 Development environment is ready!"
echo ""
echo "🌐 Available services:"
echo "   📱 API (direct): http://localhost:8000"
echo "   📱 API (nginx): http://localhost/api/"
echo "   📚 Docs: http://localhost/api/docs"
echo "   📖 ReDoc: http://localhost/api/redoc"
echo "   🌸 Flower: http://localhost/flower/"
echo "   💾 MinIO Console: http://localhost/minio/"
echo "   📧 MailHog: http://localhost/mail/"
echo "   🗄️ Database: localhost:5433"
echo "   🔥 Redis: localhost:6379"
echo ""
echo "📝 To view logs: docker compose -f docker-compose-dev.yml logs -f [service_name]"
echo "🛑 To stop: docker compose -f docker-compose-dev.yml down" 