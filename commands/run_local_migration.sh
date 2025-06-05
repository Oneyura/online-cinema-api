#!/bin/bash

# Load environment variables from .env.local if it exists
if [ -f .env.local ]; then
    export $(cat .env.local | grep -v '^#' | xargs)
fi

# Check if PostgreSQL is running locally
pg_isready -h ${POSTGRES_HOST:-localhost} -p ${POSTGRES_PORT:-5433} > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Error: PostgreSQL is not running or not accessible"
    exit 1
fi

# Run migrations
echo "Running migrations..."
poetry run alembic upgrade head

echo "Migrations completed!" 