#!/usr/bin/env python3
"""
Test email sending functionality.

This command tests email sending to verify that SendGrid and Celery are working correctly.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.settings import BaseAppSettings, ProductionSettings, Settings
from src.notifications.emails import EmailSender


def get_settings() -> BaseAppSettings:
    """Get application settings based on the current environment."""
    # Check command line arguments for production flag
    if "--prod" in sys.argv:
        return ProductionSettings()
    
    environment = os.getenv("ENVIRONMENT", "developing")
    if environment == "production":
        return ProductionSettings()
    return Settings()


async def test_email_direct() -> None:
    """Test email sending directly through EmailSender."""
    print("🧪 Testing email sending directly...")
    
    settings = get_settings()
    print(f"🔧 Using environment: {settings.__class__.__name__}")
    print(f"📧 Email host: {settings.EMAIL_HOST}")
    print(f"🔗 Email port: {settings.EMAIL_PORT}")
    print(f"👤 Email user: {settings.EMAIL_HOST_USER}")
    print(f"🔒 Use TLS: {settings.EMAIL_USE_TLS}")
    
    email_sender = EmailSender(
        hostname=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        sender_email=settings.EMAIL_FROM,
        use_tls=settings.EMAIL_USE_TLS,
        template_dir="src/templates/email",
        activation_email_template_name="activation.html",
        activation_complete_email_template_name="activation_complete.html",
        password_email_template_name="password_reset.html",
        password_complete_email_template_name="password_reset_complete.html",
    )
    
    # Test email address from command line or default
    test_email = "renoxeh849@jio1.com"  # Use the same email from the test
    
    try:
        print(f"📬 Sending test activation email to {test_email}...")
        
        activation_link = "https://fast-furious.work.gd/api/accounts/activate?token=test-token-123"
        await email_sender.send_activation_email(test_email, activation_link)
        
        print(f"✅ Test email sent successfully to {test_email}!")
        print("📝 Check your inbox (including spam folder)")
        
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        import traceback
        traceback.print_exc()


async def test_celery_task() -> None:
    """Test email sending through Celery task."""
    print("🧪 Testing email sending through Celery...")
    
    try:
        from src.tasks import send_activation_email
        
        # This would require a user in database
        print("⚠️  Celery task test requires existing user in database")
        print("💡 Use: python -m src.management test-email --direct for direct test")
        
    except Exception as e:
        print(f"❌ Error importing Celery task: {e}")


async def main():
    """Main entry point."""
    print("🎬 Online Cinema API - Email Test")
    print()
    
    if "--direct" in sys.argv:
        await test_email_direct()
    elif "--celery" in sys.argv:
        await test_celery_task()
    else:
        print("Usage:")
        print("  python -m src.management test-email --direct")
        print("  python -m src.management test-email --direct --prod")
        print("  python -m src.management test-email --celery")
        print()
        print("Options:")
        print("  --direct   Test email sending directly (recommended)")
        print("  --celery   Test email sending through Celery task")
        print("  --prod     Use production environment")


if __name__ == "__main__":
    asyncio.run(main()) 