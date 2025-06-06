#!/bin/bash

generate_password_hash() {
    local password=$1
    echo $(openssl passwd -apr1 "$password")
}

create_htpasswd() {
    local username=$1
    local password=$2
    local htpasswd_file="nginx/auth/.htpasswd"
    
    local password_hash=$(generate_password_hash "$password")
    
    echo "$username:$password_hash" > "$htpasswd_file"
    
    echo "Created .htpasswd file with user: $username"
    echo "Location: $htpasswd_file"
}

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <username> <password>"
    echo "Example: $0 admin your_secure_password"
    exit 1
fi

create_htpasswd "$1" "$2"

chmod 644 nginx/auth/.htpasswd

echo "Basic auth configuration completed!" 