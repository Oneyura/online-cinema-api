class BaseS3Error(Exception):
    """Base class for S3 storage exceptions."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class S3ConnectionError(BaseS3Error):
    """Raised when connection to S3 storage fails."""

    def __init__(
            self,
            message: str = "Failed to connect to S3 storage"
    ) -> None:
        super().__init__(message)


class S3BucketNotFoundError(BaseS3Error):
    """Raised when S3 bucket is not found."""

    def __init__(
            self,
            message: str = "S3 bucket not found"
    ) -> None:
        super().__init__(message)


class S3FileUploadError(BaseS3Error):
    """Raised when file upload to S3 storage fails."""

    def __init__(
            self,
            message: str = "Failed to upload file to S3 storage"
    ) -> None:
        super().__init__(message)


class S3FileNotFoundError(BaseS3Error):
    """Raised when file is not found in S3 storage."""

    def __init__(
            self,
            message: str = "File not found in S3 storage"
    ) -> None:
        super().__init__(message)


class S3PermissionError(BaseS3Error):
    """Raised when permission is denied for S3 storage operation."""

    def __init__(
            self,
            message: str = "Permission denied for S3 storage operation"
    ) -> None:
        super().__init__(message)
