import pytest
from pydantic import ValidationError

from manashelper.core.config import Settings, get_settings


@pytest.mark.parametrize(
    "url",
    ["http://example.com", "https://user:pass@example.com", "https://example.com/path", "https://example.com?secret=x"],
)
def test_public_url_must_be_an_https_origin(url):
    values = get_settings().model_dump(by_alias=True)
    values.update(MANASHELPER_PUBLIC_URL=url, MANASHELPER_WEBHOOK_SECRET="a" * 32)
    with pytest.raises(ValidationError):
        Settings.model_validate(values)


@pytest.mark.parametrize("secret", [None, "", "short", "x" * 257, "x" * 31 + "/"])
def test_webhook_requires_a_strong_provider_compatible_secret(secret):
    values = get_settings().model_dump(by_alias=True)
    values.update(MANASHELPER_PUBLIC_URL="https://example.com", MANASHELPER_WEBHOOK_SECRET=secret)
    with pytest.raises(ValidationError):
        Settings.model_validate(values)
