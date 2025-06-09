#!/usr/bin/env python3
"""
Email functionality tests for MailHog integration.
"""
import pytest

from src.notifications.emails import EmailSender


class TestEmailSender:
    """Test cases for EmailSender functionality."""

    @pytest.fixture
    def email_sender(self):
        """Create EmailSender instance for testing."""
        return EmailSender(
            hostname="mailhog",  # MailHog host (Docker service name)
            port=1025,           # MailHog SMTP port
            email="test@cinema.com",
            password="",         # No password needed for MailHog
            use_tls=False,       # No TLS for MailHog
            template_dir="src/templates/email",
            activation_email_template_name="activation.html",
            activation_complete_email_template_name="activation_complete.html",
            password_email_template_name="password_reset.html",
            password_complete_email_template_name="password_reset_complete.html",
        )

    @pytest.mark.asyncio
    async def test_send_activation_email(self, email_sender):
        """Test sending activation email."""
        try:
            await email_sender.send_activation_email(
                email="user@example.com",
                activation_link="http://localhost/activate?token=test123"
            )
            # If no exception is raised, the test passes
            assert True
        except Exception as e:
            pytest.fail(f"Failed to send activation email: {e}")

    @pytest.mark.asyncio
    async def test_send_activation_complete_email(self, email_sender):
        """Test sending activation complete email."""
        try:
            await email_sender.send_activation_complete_email(
                email="user@example.com",
                login_link="http://localhost/login"
            )
            assert True
        except Exception as e:
            pytest.fail(f"Failed to send activation complete email: {e}")

    @pytest.mark.asyncio
    async def test_send_password_reset_email(self, email_sender):
        """Test sending password reset email."""
        try:
            await email_sender.send_password_reset_email(
                email="user@example.com",
                reset_link="http://localhost/reset?token=reset456"
            )
            assert True
        except Exception as e:
            pytest.fail(f"Failed to send password reset email: {e}")

    @pytest.mark.asyncio
    async def test_send_password_reset_complete_email(self, email_sender):
        """Test sending password reset complete email."""
        try:
            await email_sender.send_password_reset_complete_email(
                email="user@example.com",
                login_link="http://localhost/login"
            )
            assert True
        except Exception as e:
            pytest.fail(f"Failed to send password reset complete email: {e}")

    @pytest.mark.asyncio
    async def test_email_with_invalid_template(self):
        """Test email sending with invalid template directory."""
        email_sender = EmailSender(
            hostname="mailhog",
            port=1025,
            email="test@cinema.com",
            password="",
            use_tls=False,
            template_dir="invalid/path",  # Invalid template directory
            activation_email_template_name="activation.html",
            activation_complete_email_template_name="activation_complete.html",
            password_email_template_name="password_reset.html",
            password_complete_email_template_name="password_reset_complete.html",
        )
        
        with pytest.raises(Exception):
            await email_sender.send_activation_email(
                email="user@example.com",
                activation_link="http://localhost/activate?token=test123"
            )


# Standalone function for manual testing (can be run directly)
async def manual_email_test():
    """Manual email test function that can be run independently."""
    email_sender = EmailSender(
        hostname="mailhog",
        port=1025,
        email="test@cinema.com",
        password="",
        use_tls=False,
        template_dir="src/templates/email",
        activation_email_template_name="activation.html",
        activation_complete_email_template_name="activation_complete.html",
        password_email_template_name="password_reset.html",
        password_complete_email_template_name="password_reset_complete.html",
    )
    
    try:
        print("🔄 Sending test activation email...")
        await email_sender.send_activation_email(
            email="user@example.com",
            activation_link="http://localhost/activate?token=test123"
        )
        print("✅ Activation email sent successfully!")
        
        print("🔄 Sending test password reset email...")
        await email_sender.send_password_reset_email(
            email="user@example.com",
            reset_link="http://localhost/reset?token=reset456"
        )
        print("✅ Password reset email sent successfully!")
        
        print("\n🎉 All emails sent successfully!")
        print("📧 Check MailHog UI at: http://localhost:8025")
        print("📧 Or via nginx at: http://localhost/mail/")
        
        return True
        
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False


if __name__ == "__main__":
    """Run manual test when script is executed directly."""
    import asyncio
    import sys
    
    success = asyncio.run(manual_email_test())
    sys.exit(0 if success else 1) 