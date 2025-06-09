#!/bin/bash

echo "🔍 Checking SendGrid configuration for production..."

# Check .env.prod file exists
if [ ! -f ".env.prod" ]; then
    echo "❌ .env.prod file not found!"
    exit 1
fi

echo "✅ .env.prod file found"

# Check required variables for SendGrid
required_vars=("EMAIL_HOST" "EMAIL_PORT" "EMAIL_HOST_USER" "EMAIL_HOST_PASSWORD" "EMAIL_USE_TLS" "ENVIRONMENT")

echo "📧 Checking email variables:"
for var in "${required_vars[@]}"; do
    if grep -q "^${var}=" .env.prod; then
        value=$(grep "^${var}=" .env.prod | cut -d'=' -f2- | tr -d '\r\n')
        if [ "$var" = "EMAIL_HOST_PASSWORD" ]; then
            echo "   ✅ $var=SG.****** (hidden)"
        else
            echo "   ✅ $var=$value"
        fi
    else
        echo "   ❌ $var - missing!"
    fi
done

# Validate SendGrid configuration
echo ""
echo "🎯 Validating SendGrid settings:"

email_host=$(grep "^EMAIL_HOST=" .env.prod | cut -d'=' -f2- | tr -d '\r\n')
if [ "$email_host" = "smtp.sendgrid.net" ]; then
    echo "   ✅ EMAIL_HOST is correct"
else
    echo "   ❌ EMAIL_HOST should be smtp.sendgrid.net, not $email_host"
fi

email_port=$(grep "^EMAIL_PORT=" .env.prod | cut -d'=' -f2- | tr -d '\r\n')
if [ "$email_port" = "587" ]; then
    echo "   ✅ EMAIL_PORT is correct"
else
    echo "   ❌ EMAIL_PORT should be 587, not $email_port"
fi

email_tls=$(grep "^EMAIL_USE_TLS=" .env.prod | cut -d'=' -f2- | tr -d '\r\n')
if [ "$email_tls" = "True" ] || [ "$email_tls" = "true" ]; then
    echo "   ✅ EMAIL_USE_TLS is correct"
else
    echo "   ❌ EMAIL_USE_TLS should be True, not $email_tls"
fi

environment=$(grep "^ENVIRONMENT=" .env.prod | cut -d'=' -f2- | tr -d '\r\n')
if [ "$environment" = "production" ]; then
    echo "   ✅ ENVIRONMENT is correct"
else
    echo "   ❌ ENVIRONMENT should be production, not '$environment'"
fi

echo ""
echo "🌐 Checking network connectivity:"

# Check access to SendGrid
if command -v nslookup >/dev/null 2>&1; then
    echo "   🔍 DNS lookup for smtp.sendgrid.net:"
    nslookup smtp.sendgrid.net | grep -A 1 "Name:" || echo "   ⚠️  DNS lookup failed"
else
    echo "   ⚠️  nslookup not available"
fi

# Check access to port 587 (cross-platform)
if command -v nc >/dev/null 2>&1; then
    echo "   🔍 Checking access to smtp.sendgrid.net:587:"
    if nc -z -G 5 smtp.sendgrid.net 587 2>/dev/null; then
        echo "   ✅ Port 587 is accessible"
    else
        # Try alternative method for different nc versions
        if echo "quit" | nc smtp.sendgrid.net 587 >/dev/null 2>&1; then
            echo "   ✅ Port 587 is accessible"
        else
            echo "   ❌ Port 587 is not accessible"
        fi
    fi
else
    echo "   ⚠️  netcat not available for port checking"
fi

echo ""
echo "📋 Recommendations:"
echo "   1. Ensure ENVIRONMENT=production in .env.prod"
echo "   2. Verify SendGrid API key is valid"
echo "   3. Run docker-compose up for testing"
echo "   4. Check logs: docker-compose logs web" 