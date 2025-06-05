from src.tasks import cleanup_old_files, send_email_notification


def test_send_email_notification() -> None:
    """
    Test the email notification task.
    """
    result = send_email_notification(1, "Test Subject", "Test Message")
    assert result == "Email sent to user 1"


def test_cleanup_old_files() -> None:
    """
    Test the file cleanup task.
    """
    result = cleanup_old_files()
    assert result == "Old files cleaned up"
