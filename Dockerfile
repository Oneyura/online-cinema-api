FROM python:3.10-slim

# Setting environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    ALEMBIC_CONFIG=/usr/src/alembic/alembic.ini

# Add Poetry to PATH
ENV PATH="$POETRY_HOME/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Set working directory
WORKDIR /usr/src/app

# Copy dependency files
COPY pyproject.toml poetry.lock ./
COPY alembic.ini /usr/src/alembic/alembic.ini

# Install dependencies
RUN poetry install --no-root --only main

# Copy the source code and commands
COPY ./src ./src
COPY ./commands /commands

# Make command scripts executable
RUN chmod +x /commands/*.sh

# Set default command
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
