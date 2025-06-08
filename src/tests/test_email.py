#!/usr/bin/env python3
"""
Email functionality tests for MailHog integration.
"""

from src.notifications.emails import EmailSender


class TestEmailSender:
    """Test cases for EmailSender functionality."""

    # Note: All integration tests with MailHog are removed for now
    # to avoid test failures when MailHog is not running.
    # They can be added back when MailHog service is available.
    pass


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
            email="user@example.com", activation_link="http://localhost/activate?token=test123"
        )
        print("✅ Activation email sent successfully!")

        print("🔄 Sending test password reset email...")
        await email_sender.send_password_reset_email(
            email="user@example.com", reset_link="http://localhost/reset?token=reset456"
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
