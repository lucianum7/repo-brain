class RepoBrainError(Exception):
    """Base error with a user-facing message."""


class RepositoryNotFound(RepoBrainError):
    pass


class BrainNotInitialized(RepoBrainError):
    pass


class InvalidPath(RepoBrainError):
    pass


class MigrationError(RepoBrainError):
    pass


class InvalidAnalysis(RepoBrainError):
    pass


class ConfigurationError(RepoBrainError):
    pass

