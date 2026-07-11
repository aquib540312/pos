class DomainError(Exception):
    """Base class for business-rule violations raised by the service layer.

    API routers translate these into HTTP responses; services never import
    FastAPI/HTTP concepts, keeping business logic transport-agnostic.
    """


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class InsufficientStockError(DomainError):
    pass


class CreditLimitExceededError(DomainError):
    pass


class PermissionDeniedError(DomainError):
    pass


class AuthenticationError(DomainError):
    pass
