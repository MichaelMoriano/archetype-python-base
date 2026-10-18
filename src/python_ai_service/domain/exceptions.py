"""Framework-independent application exceptions."""


class ApplicationException(Exception):
    """Base controlled exception."""

    def __init__(self, message: str = "", *, cause: BaseException | None = None) -> None:
        self.message = message
        if cause is not None:
            self.__cause__ = cause
        super().__init__(message)

    def __str__(self) -> str:
        return self.message or type(self).__name__


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


class MissingCredentialsException(AuthenticationException):
    """Required caller authentication credentials are missing."""


class MalformedCredentialsException(AuthenticationException):
    """Caller authentication credentials have an invalid format."""


class UnsupportedAuthenticationSchemeException(AuthenticationException):
    """The caller authentication scheme is unsupported or not allowed."""
