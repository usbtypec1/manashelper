class EdersFetchError(Exception):
    pass


class EdersLoginError(EdersFetchError):
    """Direct Eders authentication failed; the caller may try OBIS SSO."""


class EdersSnapshotNotReadyError(Exception):
    pass


class EdersSessionExpiredError(EdersFetchError):
    pass


class EdersParseError(Exception):
    pass


class EdersUnsafeUrlError(Exception):
    """A link is outside the explicitly supported read-only endpoints."""
