"""Framework-independent application exceptions."""


class ApplicationException(Exception):
    """Base controlled exception."""


class AuthenticationException(ApplicationException):
    """Credentials are missing or invalid."""


class AuthorizationException(ApplicationException):
    """Authenticated caller is not allowed to perform the operation."""


class ValidationException(ApplicationException):
    """Business input is invalid."""


class NotFoundException(ApplicationException):
    """Requested resource does not exist."""


class ExternalServiceException(ApplicationException):
    """An external dependency failed."""


class ExternalServiceTimeoutException(ExternalServiceException):
    """An external dependency exceeded its time budget."""
