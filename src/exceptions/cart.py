class BaseCartError(Exception):
    """Base class for cart exceptions."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class MovieAlreadyInCartError(BaseCartError):
    """Raised when trying to add a movie that's already in the cart."""

    def __init__(self, message: str = "Movie is already in your cart") -> None:
        super().__init__(message)


class MovieNotInCartError(BaseCartError):
    """Raised when trying to remove a movie that's not in the cart."""

    def __init__(self, message: str = "Movie is not in your cart") -> None:
        super().__init__(message)


class CartNotFoundError(BaseCartError):
    """Raised when user's cart is not found."""

    def __init__(self, message: str = "Cart not found") -> None:
        super().__init__(message)


class MovieNotFoundError(BaseCartError):
    """Raised when movie doesn't exist."""

    def __init__(self, message: str = "Movie not found") -> None:
        super().__init__(message)


class MovieAlreadyPurchasedError(BaseCartError):
    """Raised when trying to add a movie that's already been purchased."""

    def __init__(self, message: str = "Movie has already been purchased and cannot be added to cart again") -> None:
        super().__init__(message)
