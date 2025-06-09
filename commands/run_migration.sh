#!/bin/bash

set -e

# Wait for database to be ready
echo "Waiting for database..."
while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 1
done
echo "Database is ready!"

# Change to the source directory
cd /usr/src/app || exit 1

# Run migrations
echo "Running migrations..."
alembic upgrade head

echo "Migrations completed!"
