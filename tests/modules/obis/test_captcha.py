import pytest

import manashelper.modules.obis.infrastructure.yii_captcha._engine as captcha_engine
from manashelper.modules.obis.infrastructure.captcha import LocalCaptchaRecognizer
from tests.paths import FIXTURES_DIR


@pytest.mark.parametrize("status", ["ambiguous", "unsupported"])
async def test_recognizer_never_uses_an_uncertain_candidate(monkeypatch, status):
    image = (FIXTURES_DIR / "obis/auto-captcha.png").read_bytes()
    monkeypatch.setattr(
        captcha_engine, "solve", lambda *args, **kwargs: {"status": status, "answer": None, "best_candidate": "qinug"}
    )
    assert await LocalCaptchaRecognizer().solve(image, 3347) is None


@pytest.mark.parametrize(
    ("image", "expected_hash"),
    [(b"not an image", 3347), (b"", 3347), (b"unused", -1), (b"unused", 0), (b"unused", 679)],
)
async def test_invalid_challenges_allow_manual_fallback(image, expected_hash):
    assert await LocalCaptchaRecognizer().solve(image, expected_hash) is None
