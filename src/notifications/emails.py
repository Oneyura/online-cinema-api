import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from jinja2 import Environment, FileSystemLoader

from src.exceptions.email import BaseEmailError
from src.notifications.interfaces import EmailSenderInterface


class EmailSender(EmailSenderInterface):

    def __init__(
        self,
        hostname: str,
        port: int,
        username: str,
        password: str,
        sender_email: str,
        use_tls: bool,
        template_dir: str,
        activation_email_template_name: str,
        activation_complete_email_template_name: str,
        password_email_template_name: str,
        password_complete_email_template_name: str,
    ):
        self._hostname = hostname
        self._port = port
        self._username = username  # For SMTP auth (e.g. "apikey")
        self._password = password
        self._sender_email = sender_email  # For From header (e.g. "noreply@fast-furious.work.gd")
        self._use_tls = use_tls
        self._activation_email_template_name = activation_email_template_name
        self._activation_complete_email_template_name = activation_complete_email_template_name
        self._password_email_template_name = password_email_template_name
        self._password_complete_email_template_name = password_complete_email_template_name

        self._env = Environment(loader=FileSystemLoader(template_dir))

    async def _send_email(self, recipient: str, subject: str, html_content: str) -> None:
        """
        Asynchronously send an email with the given subject and HTML content.

        Args:
            recipient (str): The recipient's email address.
            subject (str): The subject of the email.
            html_content (str): The HTML content of the email.

        Raises:
            BaseEmailError: If sending the email fails.
        """
        message = MIMEMultipart()
        message["From"] = self._sender_email  # Use sender_email instead of username
        message["To"] = recipient
        message["Subject"] = subject
        message.attach(MIMEText(html_content, "html"))

        try:
            # Configure SMTP connection based on service
            if self._hostname == "mailhog":
                # MailHog (development) - no encryption, no auth
                smtp = aiosmtplib.SMTP(hostname=self._hostname, port=self._port)
                await smtp.connect()

            elif self._hostname == "smtp.sendgrid.net":
                # SendGrid specific configuration
                if self._port == 587:
                    # Use start_tls=True for port 587 (avoids double TLS)
                    smtp = aiosmtplib.SMTP(
                        hostname=self._hostname, 
                        port=self._port,
                        start_tls=True  # This handles STARTTLS automatically
                    )
                    await smtp.connect()
                elif self._port == 465:
                    # Use SSL/TLS for port 465
                    smtp = aiosmtplib.SMTP(hostname=self._hostname, port=self._port, use_tls=True)
                    await smtp.connect()
                else:
                    # Fallback for other ports
                    smtp = aiosmtplib.SMTP(hostname=self._hostname, port=self._port)
                    await smtp.connect()
                    if self._use_tls:
                        await smtp.starttls()

            else:
                # Generic SMTP configuration
                smtp = aiosmtplib.SMTP(hostname=self._hostname, port=self._port)
                await smtp.connect()
                
                if self._use_tls:
                    await smtp.starttls()

            # Login with credentials if provided and not MailHog
            if self._username and self._password and self._hostname != "mailhog":
                await smtp.login(self._username, self._password)

            await smtp.sendmail(self._sender_email, [recipient], message.as_string())
            await smtp.quit()

            logging.info(f"Email sent successfully to {recipient}")

        except aiosmtplib.SMTPException as error:
            logging.error(f"Failed to send email to {recipient}: {error}")
            raise BaseEmailError(f"Failed to send email to {recipient}: {error}")
        except Exception as error:
            logging.error(f"Unexpected error sending email to {recipient}: {error}")
            raise BaseEmailError(f"Unexpected error sending email to {recipient}: {error}")

    async def send_activation_email(self, email: str, activation_link: str) -> None:
        """
        Send an account activation email asynchronously.

        Args:
            email (str): The recipient's email address.
            activation_link (str): The activation link
             to be included in the email.
        """
        template = self._env.get_template(self._activation_email_template_name)
        html_content = template.render(email=email, activation_link=activation_link)
        subject = "Account Activation"
        await self._send_email(email, subject, html_content)

    async def send_activation_complete_email(self, email: str, login_link: str) -> None:
        """
        Send an account activation completion email asynchronously.

        Args:
            email (str): The recipient's email address.
            login_link (str): The login link to be included in the email.
        """
        template = self._env.get_template(self._activation_complete_email_template_name)
        html_content = template.render(email=email, login_link=login_link)
        subject = "Account Activated Successfully"
        await self._send_email(email, subject, html_content)

    async def send_password_reset_email(self, email: str, reset_link: str) -> None:
        """
        Send a password reset request email asynchronously.

        Args:
            email (str): The recipient's email address.
            reset_link (str): The reset link to be included in the email.
        """
        template = self._env.get_template(self._password_email_template_name)
        html_content = template.render(email=email, reset_link=reset_link)
        subject = "Password Reset Request"
        await self._send_email(email, subject, html_content)

    async def send_password_reset_complete_email(self, email: str, login_link: str) -> None:
        """
        Send a password reset completion email asynchronously.

        Args:
            email (str): The recipient's email address.
            login_link (str): The login link to be included in the email.
        """
        template = self._env.get_template(self._password_complete_email_template_name)
        html_content = template.render(email=email, login_link=login_link)
        subject = "Your Password Has Been Successfully Reset"
        await self._send_email(email, subject, html_content)

    async def send_custom_template_email(self, email: str, subject: str, template_name: str, context: dict) -> None:
        """
        Send an email with a custom template and subject.

        Args:
            email (str): The recipient's email address.
            subject (str): The subject of the email.
            template_name (str): Jinja2 template file name.
            context (dict): Context data for template rendering.
        """
        template = self._env.get_template(template_name)
        html_content = template.render(**context)
        await self._send_email(email, subject, html_content)
