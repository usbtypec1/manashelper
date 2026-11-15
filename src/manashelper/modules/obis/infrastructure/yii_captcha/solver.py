"""Recognize an OBIS CAPTCHA locally without acquiring or submitting challenges."""

from PIL import Image

from . import _engine
from .core import infer_length


class InvalidCaptchaError(ValueError):
    """Invalid hash, image, or challenge geometry."""


def solve(image_bytes: bytes, expected_hash: int) -> str | None:
    """Return only a confident answer; the OBIS client owns server verification."""
    if not isinstance(image_bytes, bytes):
        raise TypeError("image_bytes must be bytes")
    try:
        length = infer_length(expected_hash)
        if not 5 <= length <= 6:
            raise InvalidCaptchaError(f"CAPTCHA length {length} is outside the OBIS profile (5..6)")
        _engine.image_mask(image_bytes)
        result = _engine.solve(image_bytes, expected_hash, min_length=5, max_length=6, expected_image_size=(120, 46))
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise InvalidCaptchaError(str(error)) from error
    answer: object = result["answer"]
    return answer if isinstance(answer, str) else None
