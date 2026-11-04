from unittest.mock import AsyncMock, Mock

import pytest

from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.application.models import StoredCredentials
from manashelper.modules.obis.application.ports import CredentialsStore, CredentialsVerifier, PasswordCipher
from manashelper.modules.obis.application.use_cases.save_obis_credentials import SaveObisCredentialsUseCase
from manashelper.modules.obis.errors import ObisLoginError, UserNotFoundError


@pytest.mark.parametrize("failure", [None, "login", "encryption"])
async def test_credentials_are_written_only_after_verification_and_encryption(failure):
    store = AsyncMock(spec=CredentialsStore)
    verifier = AsyncMock(spec=CredentialsVerifier)
    cipher = Mock(spec=PasswordCipher)
    previous = StoredCredentials("old-student", "old-ciphertext")
    store.get_by_user_id.return_value = previous
    order = []

    async def lock(user_id):
        assert user_id == 123
        order.append("lock")

    async def read(user_id):
        assert user_id == 123
        order.append("read")
        return previous

    async def verify(student_number, plain_password):
        assert (student_number, plain_password) == ("student", "password")
        order.append("verify")
        if failure == "login":
            raise ObisLoginError("Login failed")

    def encrypt(password):
        assert password == "password"
        order.append("encrypt")
        if failure == "encryption":
            raise RuntimeError("Encryption failed")
        return "ciphertext"

    async def save(user_id, credentials):
        assert (user_id, credentials) == (123, StoredCredentials("student", "ciphertext"))
        order.append("save")

    store.lock.side_effect = lock
    store.get_by_user_id.side_effect = read
    verifier.verify_credentials.side_effect = verify
    cipher.encrypt.side_effect = encrypt
    store.save.side_effect = save
    snapshots = AsyncMock()
    service = SaveObisCredentialsUseCase(ObisCredentialsQuery(store, cipher), store, verifier, cipher, snapshots)

    if failure:
        with pytest.raises(ObisLoginError if failure == "login" else RuntimeError):
            await service.execute(123, "student", "password")
        store.save.assert_not_awaited()
        snapshots.reset.assert_not_awaited()
    else:
        await service.execute(123, "student", "password")
    expected = ["lock", "read", "verify"]
    if failure != "login":
        expected.append("encrypt")
    if failure is None:
        expected.append("save")
    assert order == expected
    if failure is None:
        snapshots.reset.assert_awaited_once_with(123)
    assert previous == StoredCredentials("old-student", "old-ciphertext")


async def test_unknown_user_never_verifies_encrypts_or_writes():
    store = AsyncMock(spec=CredentialsStore)
    store.get_by_user_id.return_value = None
    verifier = AsyncMock(spec=CredentialsVerifier)
    cipher = Mock(spec=PasswordCipher)

    with pytest.raises(UserNotFoundError):
        await SaveObisCredentialsUseCase(
            ObisCredentialsQuery(store, cipher), store, verifier, cipher, AsyncMock()
        ).execute(123, "student", "password")
    verifier.verify_credentials.assert_not_awaited()
    cipher.encrypt.assert_not_called()
    store.save.assert_not_awaited()


async def test_student_number_read_does_not_decrypt_or_lock():
    store = AsyncMock(spec=CredentialsStore)
    store.get_by_user_id.return_value = StoredCredentials("student", None)
    cipher = Mock(spec=PasswordCipher)

    assert await ObisCredentialsQuery(store, cipher).get_student_number(123) == "student"
    cipher.decrypt.assert_not_called()
    store.lock.assert_not_awaited()


def test_stored_credentials_hide_secrets_in_repr():
    credentials = StoredCredentials("private-student", "private-ciphertext")
    assert "private-student" not in repr(credentials)
    assert "private-ciphertext" not in repr(credentials)
