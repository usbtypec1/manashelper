class EdersFetchError(Exception):
    pass


class EdersSessionExpiredError(EdersFetchError):
    pass


class EdersParseError(Exception):
    pass


class EdersUnsafeUrlError(Exception):
    """A link is outside the explicitly supported read-only endpoints."""
