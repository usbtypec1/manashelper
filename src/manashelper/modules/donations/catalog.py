from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

REQUISITES_DIR = Path(__file__).resolve().parents[4] / "docs" / "requisites"
SUPPORTED_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})


@dataclass(frozen=True)
class DonationBank:
    id: str
    name: str
    path: Path


def list_donation_banks() -> list[DonationBank]:
    if not REQUISITES_DIR.is_dir():
        return []
    banks = [
        DonationBank(id=sha256(path.name.encode("utf-8")).hexdigest()[:16], name=path.stem, path=path)
        for path in REQUISITES_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(banks, key=lambda bank: bank.name.casefold())
