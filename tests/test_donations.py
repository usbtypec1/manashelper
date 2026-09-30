from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from aiogram import Bot
from aiogram.types import FSInputFile

from manashelper.services import donations
from manashelper.services.donations import DonationBank, DonationQrService


class FakeBot:
    def __init__(self) -> None:
        self.photos: list[str | FSInputFile] = []
        self.captions: list[str] = []

    async def send_photo(self, *, chat_id: int, photo: str | FSInputFile, caption: str) -> SimpleNamespace:
        self.photos.append(photo)
        self.captions.append(caption)
        return SimpleNamespace(photo=[SimpleNamespace(file_id=f"file-{len(self.photos)}")])


def test_bank_list_comes_from_supported_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(donations, "REQUISITES_DIR", tmp_path)
    (tmp_path / "Z Bank.PNG").write_bytes(b"qr")
    (tmp_path / "A Bank.jpg").write_bytes(b"qr")
    (tmp_path / "notes.txt").write_text("ignore")

    banks = donations.list_donation_banks()

    assert [bank.name for bank in banks] == ["A Bank", "Z Bank"]
    assert all(len(bank.id) == 16 for bank in banks)


@pytest.mark.asyncio
async def test_qr_upload_is_reused_and_replaced_file_is_uploaded_again(tmp_path: Path) -> None:
    path = tmp_path / "Bank.png"
    path.write_bytes(b"first")
    bank = DonationBank(id="bank", name="Bank & Co", path=path)
    fake_bot = FakeBot()
    service = DonationQrService()

    await service.send_bank_qr(cast(Bot, fake_bot), 1, bank)
    await service.send_bank_qr(cast(Bot, fake_bot), 1, bank)
    path.write_bytes(b"second image")
    await service.send_bank_qr(cast(Bot, fake_bot), 1, bank)

    assert isinstance(fake_bot.photos[0], FSInputFile)
    assert fake_bot.photos[1] == "file-1"
    assert isinstance(fake_bot.photos[2], FSInputFile)
    assert fake_bot.captions == ["Bank &amp; Co"] * 3
    assert len(service._file_ids) == 1


@pytest.mark.asyncio
async def test_qr_cache_evicts_oldest_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(donations, "MAX_CACHED_FILE_IDS", 2)
    fake_bot = FakeBot()
    service = DonationQrService()
    banks = []
    for name in ("A", "B", "C"):
        path = tmp_path / f"{name}.png"
        path.write_bytes(b"qr")
        banks.append(DonationBank(id=name, name=name, path=path))

    for bank in banks:
        await service.send_bank_qr(cast(Bot, fake_bot), 1, bank)
    await service.send_bank_qr(cast(Bot, fake_bot), 1, banks[0])

    assert len(service._file_ids) == 2
    assert isinstance(fake_bot.photos[-1], FSInputFile)
