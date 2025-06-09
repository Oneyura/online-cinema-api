from src.tasks import cleanup_old_cart_items, send_activation_email, send_activation_complete_email


def test_send_activation_email() -> None:
    """
    Test the activation email task.
    """
    # This would require a database connection in a real test
    # For now, just ensure the task function exists
    assert callable(send_activation_email)


def test_send_activation_complete_email() -> None:
    """
    Test the activation complete email task.
    """
    # This would require a database connection in a real test
    # For now, just ensure the task function exists
    assert callable(send_activation_complete_email)


def test_cleanup_old_cart_items() -> None:
    """
    Test the cart cleanup task.
    """
    # This would require a database connection in a real test
    # For now, just ensure the task function exists
    assert callable(cleanup_old_cart_items)
