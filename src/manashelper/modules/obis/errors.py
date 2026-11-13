class UserNotFoundError(Exception):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} not found")
        self.user_id = user_id


class UserHasNoCredentialsError(Exception):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} has no OBIS credentials")
        self.user_id = user_id


class DecryptionError(Exception):
    pass


class ObisLoginError(Exception):
    pass


class ObisParseError(Exception):
    pass


class ObisSnapshotNotReadyError(Exception):
    pass


class ObisCaptchaError(Exception):
    """OBIS rejected the captcha answer or the login form expired before submission."""


class ObisSessionExpiredError(Exception):
    """No saved OBIS session exists, or OBIS rejected it; the student must log in with a captcha again."""
