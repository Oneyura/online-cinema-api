# Email Testing Guide

This file contains instructions for testing email functionality in Cinema API.

## 📧 Test Files

- `test_email.py` - Main file with email functionality tests

## 🔧 Running Tests

### 1. Pytest Tests (Automated)

Run all email tests with pytest:
```bash
docker exec backend_cinema python -m pytest src/tests/test_email.py -v
```

Run a specific test:
```bash
docker exec backend_cinema python -m pytest src/tests/test_email.py::TestEmailSender::test_send_activation_email -v
```

### 2. Manual Test (Interactive)

Run manual test to send real emails:
```bash
docker exec backend_cinema python /usr/src/app/src/tests/test_email.py
```

## 📨 Email Verification

After sending emails, check them in MailHog:

### Locally:
- **MailHog UI direct**: http://localhost:8025
- **MailHog via nginx**: http://localhost/mail/

### Production:
- **MailHog via nginx**: https://your-domain.com/mail/

## 🧪 Test Types

### Automated pytest tests:
1. `test_send_activation_email` - Test sending activation email
2. `test_send_activation_complete_email` - Test activation confirmation email
3. `test_send_password_reset_email` - Test password reset email
4. `test_send_password_reset_complete_email` - Test password reset confirmation email
5. `test_email_with_invalid_template` - Test with invalid templates (negative test)

### Manual test:
- Sends real emails to MailHog for visual verification

## 🔍 Troubleshooting

### If emails are not being sent:

1. **Check MailHog status**:
   ```bash
   docker-compose -f docker-compose-dev.yml logs mailhog
   ```

2. **Check connection to MailHog**:
   ```bash
   docker exec backend_cinema ping mailhog
   ```

3. **Check ports**:
   ```bash
   curl -I http://localhost:8025  # MailHog UI
   curl -I http://localhost:1025  # MailHog SMTP (may not respond via HTTP)
   ```

### If tests are failing:

1. **Check email templates**:
   ```bash
   ls -la src/templates/email/
   ```

2. **Check backend logs**:
   ```bash
   docker-compose -f docker-compose-dev.yml logs web
   ```

## 📝 Additional Information

- Email templates are located in `src/templates/email/`
- Email configuration is in `src/config/settings.py`
- Email class is in `src/notifications/emails.py`

## 🎯 Useful Commands

```bash
# Run all tests
docker exec backend_cinema python -m pytest src/tests/ -v

# Run only email tests
docker exec backend_cinema python -m pytest src/tests/test_email.py -v

# Send test emails
docker exec backend_cinema python /usr/src/app/src/tests/test_email.py

# Check MailHog
curl http://localhost:8025/api/v2/messages | jq .
``` 