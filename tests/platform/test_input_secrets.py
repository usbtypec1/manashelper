import base64
from uuid import uuid4

import pytest

from manashelper.core.config import get_settings
from manashelper.platform.secrets import SecretCodec, SecretUnavailableError
from ui_flows.domain.contracts import DelegateContext


@pytest.fixture
def secret_settings(monkeypatch):
    synthetic = {
        "MANASHELPER_TELEGRAM_BOT_TOKEN": "123456:synthetic-secret-test",
        "MANASHELPER_DATASOURCE_NAME": "unused",
        "MANASHELPER_DATASOURCE_USERNAME": "unused",
        "MANASHELPER_DATASOURCE_PASSWORD": "unused",
        "MANASHELPER_OBIS_ENCRYPTION_KEY": base64.b64encode(b"s" * 32).decode(),
        "MANASHELPER_ADVERTISEMENT_CHANNEL_ID": "-1",
        "MANASHELPER_ADVERTISEMENT_CHANNEL_LINK": "https://t.me/synthetic",
        "MANASHELPER_MODERATION_CHAT_ID": "-2",
        "MANASHELPER_ADMIN_CHAT_ID": "991401",
    }
    for key, value in synthetic.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    try:
        yield get_settings()
    finally:
        get_settings.cache_clear()


@pytest.fixture
def codec(secret_settings):
    return SecretCodec(secret_settings)


def test_secret_round_trip_uses_fresh_nonce_and_masks_plaintext(codec):
    owner = (uuid4(), uuid4(), 991401, 991401)
    plaintext = "/private@input — секрет 密码"
    first, second = (codec.encrypt(plaintext, *owner) for _ in range(2))
    assert first != second
    assert plaintext not in first and plaintext not in second
    assert codec.decrypt(first, *owner) == codec.decrypt(second, *owner) == plaintext
    assert len(base64.b64decode(first)) == 12 + len(plaintext.encode()) + 16
    assert plaintext not in repr(codec)
    context = DelegateContext(owner[2], owner[3], str(owner[1]), "synthetic-operation", secrets={"password": plaintext})
    assert plaintext not in repr(context) and "password" not in repr(context)


@pytest.mark.parametrize("changed", ["secret", "session", "user", "chat"])
def test_secret_ciphertext_cannot_be_transferred_to_another_owner(codec, changed):
    owner = (uuid4(), uuid4(), 991401, 991401)
    plaintext = "owner-bound-private-input"
    ciphertext = codec.encrypt(plaintext, *owner)
    other = list(owner)
    index = ("secret", "session", "user", "chat").index(changed)
    other[index] = uuid4() if index < 2 else owner[index] + 1
    with pytest.raises(SecretUnavailableError) as caught:
        codec.decrypt(ciphertext, *other)
    assert str(caught.value) == "Secret is unavailable"
    assert plaintext not in repr(caught.value) and ciphertext not in repr(caught.value)
    assert caught.value.__suppress_context__


@pytest.mark.parametrize("changed", ["nonce", "ciphertext", "tag", "truncated", "invalid_base64"])
def test_secret_tampering_and_invalid_encoding_have_one_safe_error(codec, changed):
    owner = (uuid4(), uuid4(), 991401, 991401)
    plaintext = "never-expose-private-input"
    ciphertext = codec.encrypt(plaintext, *owner)
    raw = bytearray(base64.b64decode(ciphertext))
    if changed in {"nonce", "ciphertext", "tag"}:
        index = {"nonce": 0, "ciphertext": 12, "tag": len(raw) - 1}[changed]
        raw[index] ^= 1
        modified = base64.b64encode(raw).decode()
    elif changed == "truncated":
        modified = base64.b64encode(raw[:12]).decode()
    else:
        modified = "invalid-private-base64!"
    with pytest.raises(SecretUnavailableError) as caught:
        codec.decrypt(modified, *owner)
    assert str(caught.value) == "Secret is unavailable"
    assert plaintext not in repr(caught.value) and modified not in repr(caught.value)


@pytest.mark.parametrize("key", ["invalid-key!", base64.b64encode(b"short").decode()])
def test_invalid_secret_key_fails_without_echoing_configuration(secret_settings, key):
    settings = secret_settings.model_copy(update={"obis_encryption_key": key})
    with pytest.raises(ValueError, match="Secret encryption key is invalid") as caught:
        SecretCodec(settings)
    assert key not in repr(caught.value)
