#!/bin/bash

# Function to log messages with timestamps
log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Check if MailHog is installed and accessible
if ! command -v MailHog &> /dev/null; then
    log_message "ERROR: MailHog is not installed or not in PATH"
    exit 1
fi

# Check if environment variables are set
if [ -z "$MAILHOG_USER" ]; then
    log_message "ERROR: MAILHOG_USER is not set"
    exit 1
fi

if [ -z "$MAILHOG_PASSWORD" ]; then
    log_message "ERROR: MAILHOG_PASSWORD is not set"
    exit 1
fi

# Generate bcrypt-hashed password
log_message "Generating hashed password for user: $MAILHOG_USER"
HASHED_PASSWORD=$(MailHog bcrypt "$MAILHOG_PASSWORD")

if [ $? -ne 0 ]; then
    log_message "ERROR: Failed to generate hashed password"
    exit 1
fi

# Create authentication file
AUTH_FILE="/mailhog.auth"
echo "$MAILHOG_USER:$HASHED_PASSWORD" > "$AUTH_FILE"

if [ $? -ne 0 ]; then
    log_message "ERROR: Failed to create auth file: $AUTH_FILE"
    exit 1
fi

log_message "Successfully created auth file with user: $MAILHOG_USER"
log_message "Auth file location: $AUTH_FILE"

# Set proper permissions for the auth file
chmod 600 "$AUTH_FILE"

log_message "MailHog authentication setup completed successfully"
