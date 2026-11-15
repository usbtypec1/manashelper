"""Match the complete CAPTCHA against overlapping PHP/GD glyph renderings."""

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps

from .core import hash_lengths


DEFAULT_BANK = Path(__file__).parent / "data" / "yii-glyphs.npz"
MAX_RELATIVE_ERROR = 0.10
MIN_MARGIN = 0.03


@dataclass(frozen=True)
class Glyph:
    char: str
    size: float
    angle: int
    advance: int
    left: int
    top: int
    pixels: NDArray[np.uint8]


@lru_cache(maxsize=2)
def load_bank(path=DEFAULT_BANK) -> list[Glyph]:
    with np.load(path, allow_pickle=False) as data:
        metadata = data["metadata"]
        offsets = data["offsets"]
        pixels = data["pixels"]
        size_unit = int(data["size_unit"]) if "size_unit" in data else 1
        glyphs = []
        for index, row in enumerate(metadata):
            char, size, angle, advance, left, top, width, height = map(int, row)
            bitmap = pixels[offsets[index]:offsets[index + 1]].reshape(height, width)
            glyphs.append(Glyph(chr(char), size / size_unit, angle, advance, left, top, bitmap))
    return glyphs


def image_mask(image_bytes: bytes) -> tuple[Image.Image, NDArray[np.bool_]]:
    with Image.open(BytesIO(image_bytes)) as image:
        if image.width * image.height > 1_000_000:
            raise ValueError("CAPTCHA image exceeds 1 million pixels")
        rgba = image.convert("RGBA")
        rgb = Image.new("RGB", rgba.size, "white")
        rgb.paste(rgba, mask=rgba.getchannel("A"))
    gray = np.asarray(ImageOps.grayscale(rgb))
    # Normalize the foreground color rather than assuming black text.
    darkness = 255 - gray.astype(np.int16)
    peak = int(darkness.max())
    if peak < 20:
        raise ValueError("CAPTCHA image is blank or has insufficient contrast")
    return rgb, np.greater(darkness, peak / 2)


def _bits(mask: NDArray[np.bool_]) -> int:
    return int.from_bytes(np.packbits(mask.ravel(), bitorder="little").tobytes(), "little")


@lru_cache(maxsize=2)
def _prepare_bank(width, height, bank_path):
    """Reuse geometry-only masks across images and the fallback placement search."""
    baseline = round(height * 27 / 40)
    prepared = []
    for glyph in load_bank(bank_path):
        canvas = np.zeros((height, width), dtype=bool)
        y, x = baseline + glyph.top, 16 + glyph.left
        top, bottom = max(0, y), min(height, y + glyph.pixels.shape[0])
        if bottom <= top or x < 0 or x + glyph.pixels.shape[1] > width:
            continue
        canvas[top:bottom, x:x + glyph.pixels.shape[1]] = glyph.pixels[top-y:bottom-y] > 127
        bits = _bits(canvas)
        if bits:
            prepared.append((glyph, glyph.advance - 2, bits))
    return prepared


def _solve_once(image_bytes, expected_hash, *, beam=1500, limit=5, bank_path=DEFAULT_BANK, jitter=0,
                min_length=3, max_length=20, expected_image_size=None) -> dict[str, Any]:
    lengths = hash_lengths(expected_hash, min_length, max_length)
    if not lengths:
        raise ValueError("Hash is incompatible with 3 to 20 lowercase ASCII letters")
    length = lengths[0]
    rgb, mask = image_mask(image_bytes)
    height, width = map(int, mask.shape)
    if expected_image_size is not None and (width, height) != expected_image_size:
        raise ValueError(f"Expected image size {expected_image_size}, received {(width, height)}")
    if width < 64 or width > 512 or height < 24 or height > 160:
        raise ValueError("Expected an original Yii CAPTCHA image, 64..512 by 24..160 pixels")
    target = _bits(mask)
    target_area = target.bit_count()
    baseline = round(height * 27 / 40)
    ink_rows, ink_columns = np.where(mask)
    ink_height = int(ink_rows.max() - ink_rows.min() + 1)
    right_edge = int(ink_columns.max() + 1)
    # Store each glyph at x=16. Integer shifts place it at any baseline x.
    prepared = [item for item in _prepare_bank(width, height, bank_path)
                if item[0].pixels.shape[0] >= ink_height * 0.3]
    prefix_masks = [sum(((1 << x) - 1) << (row * width) for row in range(height))
                    for x in range(width + 1)]
    options_cache = {}
    glyph_lookup = {(glyph.char, glyph.size, glyph.angle): (glyph, bits)
                    for glyph, _, bits in prepared}
    by_char = defaultdict(list)
    for glyph, _, bits in prepared:
        by_char[glyph.char].append((glyph, bits))

    def place(glyph, bits, x):
        if x + glyph.left < 0 or x + glyph.left + glyph.pixels.shape[1] > width:
            return None
        return bits << (x - 16) if x >= 16 else bits >> (16 - x)

    def refine(observations):
        poses = list(observations)
        masks = [place(*glyph_lookup[char, size, angle], x) for char, x, size, angle in poses]
        for iteration in range(3):
            changed = False
            indices = range(len(poses)) if iteration % 2 == 0 else reversed(range(len(poses)))
            for index in indices:
                char, x, size, angle = poses[index]
                rest = 0
                for other, value in enumerate(masks):
                    if other != index:
                        rest |= value
                best = ((rest | masks[index]) ^ target).bit_count()
                chosen = poses[index]
                chosen_mask = masks[index]
                for glyph, bits in by_char[char]:
                    if abs(glyph.size - size) > 1.25:
                        continue
                    sizes = [pose[2] for i, pose in enumerate(poses) if i != index] + [glyph.size]
                    if max(sizes) > min(sizes) * 32 / 26 + 2:
                        continue
                    for candidate_x in range(max(0, x - 2), min(width, x + 3)):
                        placed = place(glyph, bits, candidate_x)
                        if placed is None:
                            continue
                        error = ((rest | placed) ^ target).bit_count()
                        if error < best:
                            best = error
                            chosen = (char, candidate_x, glyph.size, glyph.angle)
                            chosen_mask = placed
                if chosen != poses[index]:
                    poses[index] = chosen
                    masks[index] = chosen_mask
                    changed = True
            if not changed:
                break
        union = 0
        for value in masks:
            union |= value
        return (union ^ target).bit_count(), poses

    def options(x):
        if x in options_cache:
            return options_cache[x]
        groups = defaultdict(list)
        for glyph, advance, bits in prepared:
            if x + glyph.left < 0 or x + glyph.left + glyph.pixels.shape[1] > width:
                continue
            placed = bits << (x - 16) if x >= 16 else bits >> (16 - x)
            area = placed.bit_count()
            outside = (placed & ~target).bit_count()
            if outside > area * 0.30:
                continue
            score = outside * 3 - area * 0.05
            groups[glyph.char, advance].append((score, glyph.size, glyph.angle, placed, glyph))
        values = []
        for (char, advance), group in groups.items():
            for _, _, _, placed, glyph in sorted(group, key=lambda item: item[:3])[:4]:
                values.append((char, advance, placed, glyph))
                # Live GD renderings can place the next letter inside q's rightward
                # descender. Keep the original spacing and a compact alternative;
                # pixels and the hash still choose between the complete strings.
                if char == "q":
                    compact_advance = advance - round(glyph.size / 4)
                    if 0 < compact_advance < advance:
                        values.append((char, compact_advance, placed, glyph))
        options_cache[x] = values
        return values

    # cost, next baseline x, remaining hash, text, union mask, font min/max, observations
    states = [(0, 10, expected_hash, "", 0, 1000, 0, ())]
    completed = []
    for index in range(length):
        following = []
        remaining = length - index - 1
        low, high = 97 * ((1 << remaining) - 1), 122 * ((1 << remaining) - 1)
        for _, x, residual, text, union, minimum, maximum, observations in states:
            for char, advance, placed, glyph in options(x):
                difference = residual - ord(char)
                if difference % 2 or not low <= difference // 2 <= high:
                    continue
                new_min, new_max = min(minimum, glyph.size), max(maximum, glyph.size)
                if new_max > new_min * 32 / 26 + 2:
                    continue
                combined = union | placed
                for displacement in range(-jitter, jitter + 1):
                    next_x = x + advance + displacement
                    if next_x < 0 or (next_x >= width and remaining):
                        continue
                    prefix = prefix_masks[max(0, min(width, next_x - 8))]
                    if remaining:
                        cost = ((combined & ~target).bit_count()
                                + (target & ~combined & prefix).bit_count())
                    else:
                        cost = (combined ^ target).bit_count()
                    observation = (char, x, glyph.size, glyph.angle)
                    following.append((cost, next_x, difference // 2, text + char, combined,
                                      new_min, new_max, observations + (observation,)))
        # Keep different visual explanations, while preventing duplicate placements
        # from consuming the entire beam.
        seen = defaultdict(int)
        by_position = defaultdict(list)
        for state in sorted(following, key=lambda item: item[0]):
            key = (state[3], state[1])
            if seen[key] >= 2:
                continue
            seen[key] += 1
            by_position[state[1]].append(state)
        quota = max(1, beam // max(1, len(by_position)))
        states = [state for values in by_position.values() for state in values[:quota]]
        remaining_slots = beam - len(states)
        if remaining_slots > 0:
            overflow = [state for values in by_position.values() for state in values[quota:]]
            states.extend(sorted(overflow, key=lambda item: item[0])[:remaining_slots])
        if not states:
            break
    seen = set()
    for cost, x, residual, text, union, minimum, maximum, observations in sorted(states, key=lambda item: item[0]):
        if len(text) != length or residual != 0 or text in seen:
            continue
        seen.add(text)
        cost, observations = refine(observations)
        completed.append({"text": text, "pixel_error": cost,
                          "relative_error": round(cost / target_area, 6),
                          "glyphs": [{"char": char, "x": x, "size": size, "angle": angle}
                                     for char, x, size, angle in observations]})
        if len(completed) >= max(limit * 2, 10):
            break
    completed.sort(key=lambda item: item["pixel_error"])
    return {"candidates": completed[:limit], "hash_lengths": lengths, "image_size": [width, height],
            "baseline": baseline, "target_ink_pixels": target_area, "right_edge": right_edge,
            "beam": beam, "search_exhaustive": False, "server_verified": False}


def solve(image_bytes: bytes, expected_hash: int, *, beam=1500, limit=5, bank_path=DEFAULT_BANK,
          min_length=3, max_length=20, expected_image_size=None) -> dict[str, Any]:
    """Return a visual hypothesis, alternatives, and an explicit abstention status.

    The known text is never an input. Scores measure pixel mismatch, not calibrated
    probabilities. Recognition does not imply server-side verification.
    """
    if not isinstance(beam, int) or not isinstance(limit, int) or beam < 50 or beam > 10000 or limit < 1 or limit > 20:
        raise ValueError("beam must be 50..10000 and limit must be 1..20")
    options = dict(beam=beam, limit=max(5, limit), bank_path=bank_path,
                   min_length=min_length, max_length=max_length, expected_image_size=expected_image_size)
    result = _solve_once(image_bytes, expected_hash, **options)
    candidates = result["candidates"]
    margin = (float(candidates[1]["relative_error"]) - float(candidates[0]["relative_error"])
              if len(candidates) > 1 else None)
    attempts = 1
    if not candidates or candidates[0]["relative_error"] > 0.07 or margin is None or margin < MIN_MARGIN:
        alternative = _solve_once(image_bytes, expected_hash, **options, jitter=1)
        attempts = 2
        unique = {}
        for candidate in candidates + alternative["candidates"]:
            if candidate["text"] not in unique or candidate["pixel_error"] < unique[candidate["text"]]["pixel_error"]:
                unique[candidate["text"]] = candidate
        candidates = sorted(unique.values(), key=lambda item: item["pixel_error"])
    margin = (round(float(candidates[1]["relative_error"]) - float(candidates[0]["relative_error"]), 6)
              if len(candidates) > 1 else None)
    if not candidates or candidates[0]["relative_error"] > MAX_RELATIVE_ERROR:
        status = "unsupported"
    elif margin is None or margin < MIN_MARGIN:
        status = "ambiguous"
    else:
        status = "recognized"
    result.update({"candidates": candidates[:limit], "status": status,
                   "answer": candidates[0]["text"] if status == "recognized" else None,
                   "best_candidate": candidates[0]["text"] if candidates else None,
                   "expected_hash": expected_hash, "engine": "yii-spicyrice-template",
                   "alphabet": "abcdefghijklmnopqrstuvwxyz", "search_attempts": attempts,
                   "decision": {"max_relative_error": MAX_RELATIVE_ERROR, "min_margin": MIN_MARGIN, "margin": margin}})
    return result
