class EdersFetchError(Exception):
    pass


class EdersLoginError(EdersFetchError):
    """Direct Eders authentication failed; the caller may try OBIS SSO."""


class InvalidEdersLoginLinkError(Exception):
    """The browser grant expired, was consumed or belongs to changed credentials."""


class EdersCompletionUnavailableError(Exception):
    """The current account snapshot has no manually completable task with this ID."""


class EdersSnapshotNotReadyError(Exception):
    pass


class EdersSessionExpiredError(EdersFetchError):
    pass


class EdersParseError(Exception):
    pass


class EdersUnsafeUrlError(Exception):
    """A link is outside the explicitly supported read-only endpoints."""
