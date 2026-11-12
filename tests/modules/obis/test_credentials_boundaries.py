from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.application.models import (
    ObisLoginAttempt,
    ObisLoginChallenge,
    PendingObisLogin,
    StoredCredentials,
    StoredObisSession,
)
from manashelper.modules.obis.application.ports import CredentialsStore, ObisAuthenticator, PasswordCipher
from manashelper.modules.obis.application.sessions import ObisSessions
from manashelper.modules.obis.application.use_cases.complete_obis_login import CompleteObisLoginUseCase
from manashelper.modules.obis.application.use_cases.start_obis_login import StartObisLoginUseCase
from manashelper.modules.obis.errors import (
    DecryptionError,
    ObisCaptchaError,
    ObisLoginError,
    UserHasNoCredentialsError,
    UserNotFoundError,
)

ATTEMPT = ObisLoginAttempt({"PHPSESSID": "form"}, "csrf")
PENDING = PendingObisLogin("student", "ciphertext", ATTEMPT)


def _complete(store, authenticator, cipher, snapshots, sessions):
    return CompleteObisLoginUseCase(
        ObisCredentialsQuery(store, cipher), store, authenticator, cipher, snapshots, sessions
    )


@pytest.mark.parametrize("failure", [None, "captcha", "login", "decryption"])
async def test_credentials_and_session_are_written_only_after_captcha_login(failure):
    store = AsyncMock(spec=CredentialsStore)
    authenticator = AsyncMock(spec=ObisAuthenticator)
    cipher = Mock(spec=PasswordCipher)
    snapshots, sessions = AsyncMock(), AsyncMock(spec=ObisSessions)
    previous = StoredCredentials("old-student", "old-ciphertext")
    order = []

    async def lock(user_id):
        assert user_id == 123
        order.append("lock")

    async def read(user_id):
        order.append("read")
        return previous

    def decrypt(ciphertext):
        assert ciphertext == "ciphertext"
        order.append("decrypt")
        if failure == "decryption":
            raise DecryptionError
        return "password"

    async def login(attempt, student_number, password, code):
        assert (attempt, student_number, password, code) == (ATTEMPT, "student", "password", "AbC12")
        order.append("login")
        if failure == "captcha":
            raise ObisCaptchaError
        if failure == "login":
            raise ObisLoginError
        return {"PHPSESSID": "session"}

    store.lock.side_effect = lock
    store.get_by_user_id.side_effect = read
    cipher.decrypt.side_effect = decrypt
    authenticator.complete_login.side_effect = login
    use_case = _complete(store, authenticator, cipher, snapshots, sessions)

    if failure:
        with pytest.raises(ObisCaptchaError if failure == "captcha" else ObisLoginError):
            await use_case.execute(123, PENDING, "AbC12")
        store.save.assert_not_awaited()
        snapshots.reset.assert_not_awaited()
        sessions.save.assert_not_awaited()
    else:
        await use_case.execute(123, PENDING, "AbC12")
        store.save.assert_awaited_once_with(123, StoredCredentials("student", "ciphertext"))
        snapshots.reset.assert_awaited_once_with(123)
        sessions.save.assert_awaited_once_with(123, {"PHPSESSID": "session"})
    expected = ["lock", "read", "decrypt"]
    if failure != "decryption":
        expected.append("login")
    assert order == expected


async def test_login_again_with_saved_account_keeps_cached_results():
    store = AsyncMock(spec=CredentialsStore)
    store.get_by_user_id.return_value = StoredCredentials("student", "ciphertext")
    authenticator = AsyncMock(spec=ObisAuthenticator)
    authenticator.complete_login.return_value = {"PHPSESSID": "session"}
    cipher = Mock(spec=PasswordCipher)
    cipher.decrypt.return_value = "password"
    snapshots, sessions = AsyncMock(), AsyncMock(spec=ObisSessions)

    await _complete(store, authenticator, cipher, snapshots, sessions).execute(123, PENDING, "code")
    store.save.assert_not_awaited()
    snapshots.reset.assert_not_awaited()
    sessions.save.assert_awaited_once_with(123, {"PHPSESSID": "session"})


async def test_unknown_user_never_logs_in_or_writes():
    store = AsyncMock(spec=CredentialsStore)
    store.get_by_user_id.return_value = None
    authenticator = AsyncMock(spec=ObisAuthenticator)
    cipher = Mock(spec=PasswordCipher)
    sessions = AsyncMock(spec=ObisSessions)

    with pytest.raises(UserNotFoundError):
        await _complete(store, authenticator, cipher, AsyncMock(), sessions).execute(123, PENDING, "code")
    with pytest.raises(UserNotFoundError):
        await StartObisLoginUseCase(ObisCredentialsQuery(store, cipher), authenticator, cipher).execute(
            123, "student", "password"
        )
    authenticator.start_login.assert_not_awaited()
    authenticator.complete_login.assert_not_awaited()
    cipher.encrypt.assert_not_called()
    store.save.assert_not_awaited()
    sessions.save.assert_not_awaited()


@pytest.mark.parametrize("saved", [StoredCredentials("student", "saved"), StoredCredentials("student", None)])
async def test_start_login_encrypts_new_password_or_reuses_saved_account(saved):
    store = AsyncMock(spec=CredentialsStore)
    store.get_by_user_id.return_value = saved
    authenticator = AsyncMock(spec=ObisAuthenticator)
    authenticator.start_login.return_value = ObisLoginChallenge(ATTEMPT, b"png")
    cipher = Mock(spec=PasswordCipher)
    cipher.encrypt.return_value = "new"
    use_case = StartObisLoginUseCase(ObisCredentialsQuery(store, cipher), authenticator, cipher)

    captcha = await use_case.execute(123, "another", "password")
    assert captcha.pending == PendingObisLogin("another", "new", ATTEMPT) and captcha.image == b"png"
    cipher.encrypt.assert_called_once_with("password")

    authenticator.start_login.reset_mock()
    if saved.encrypted_password is None:
        with pytest.raises(UserHasNoCredentialsError):
            await use_case.execute(123)
        authenticator.start_login.assert_not_awaited()
    else:
        captcha = await use_case.execute(123)
        assert captcha.pending == PendingObisLogin("student", "saved", ATTEMPT)
    cipher.decrypt.assert_not_called()


async def test_student_number_read_does_not_decrypt_or_lock():
    store = AsyncMock(spec=CredentialsStore)
    store.get_by_user_id.return_value = StoredCredentials("student", None)
    cipher = Mock(spec=PasswordCipher)

    assert await ObisCredentialsQuery(store, cipher).get_student_number(123) == "student"
    cipher.decrypt.assert_not_called()
    store.lock.assert_not_awaited()


def test_login_state_hides_secrets_in_repr():
    secrets = ("private-student", "private-ciphertext", "private-cookie", "private-csrf")
    values = (
        StoredCredentials("private-student", "private-ciphertext"),
        PendingObisLogin(
            "private-student", "private-ciphertext", ObisLoginAttempt({"a": "private-cookie"}, "private-csrf")
        ),
        StoredObisSession("private-ciphertext", datetime.now(UTC)),
    )
    assert all(secret not in repr(value) for secret in secrets for value in values)
