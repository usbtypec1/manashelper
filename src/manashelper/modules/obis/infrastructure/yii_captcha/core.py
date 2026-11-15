"""Yii hash operations independent of OCR, networking, and the filesystem."""


def hash_lengths(value: int, minimum: int = 3, maximum: int = 20) -> list[int]:
    """Return compatible lengths; the intervals for lowercase ASCII do not overlap."""
    return [n for n in range(minimum, maximum + 1) if 97 * ((1 << n) - 1) <= value <= 122 * ((1 << n) - 1)]


def infer_length(expected_hash: int) -> int:
    if type(expected_hash) is not int or expected_hash < 0:
        raise ValueError("expected_hash must be a nonnegative integer")
    lengths = hash_lengths(expected_hash)
    if len(lengths) != 1:
        raise ValueError("Hash is incompatible with 3 to 20 lowercase ASCII letters")
    return lengths[0]
