FROM debian:bookworm-slim

# Install necessary dependencies
RUN apt-get update && apt-get install -y \
    golang-go \
    wget \
    dos2unix \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install MailHog using Go
RUN go install github.com/mailhog/MailHog@latest

# Add Go's bin directory to the PATH to make MailHog executable globally
ENV PATH="/root/go/bin:$PATH"

# Copy the commands directory into the container
COPY commands/setup_mailhog_auth.sh /commands/setup_mailhog_auth.sh

# Ensure all scripts in the commands directory have Unix-style line endings and are executable
RUN dos2unix /commands/setup_mailhog_auth.sh && chmod +x /commands/setup_mailhog_auth.sh

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8025/api/v2/health || exit 1
