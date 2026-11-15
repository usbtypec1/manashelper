"""Disposable recognition worker; accepts image bytes, never account credentials."""

import json
import sys


def recognize(image: bytes, expected_hash: int) -> str | None:
    # Keep NumPy, Pillow, glyph caches and search allocations out of the bot process.
    from manashelper.modules.obis.infrastructure.yii_captcha.solver import InvalidCaptchaError, solve

    try:
        return solve(image, expected_hash)
    except InvalidCaptchaError:
        return None


def main() -> None:
    answer = recognize(sys.stdin.buffer.read(), int(sys.argv[1]))
    sys.stdout.write(json.dumps(answer))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
