#!/bin/bash

# Wait for database to be ready
echo "Waiting for database..."
while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 1
done
echo "Database is ready!"

# Run migrations
echo "Running migrations..."
alembic upgrade head

echo "Migrations completed!"
