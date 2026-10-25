import runpy
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import FSInputFile
from dishka import make_async_container

from manashelper.core.provider import CoreProvider
from manashelper.di import AppProvider, RequestProvider
from manashelper.modules.donations import catalog as donations
from manashelper.modules.donations import qr as qr_adapter
from manashelper.modules.donations.catalog import DonationBank
from manashelper.modules.donations.provider import DonationsProvider
from manashelper.modules.donations.qr import DonationQrService
from manashelper.modules.donations.service import DonationService
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.schedule.provider import ScheduleProvider
from manashelper.modules.users.infrastructure.user_repository import UserRepository
from manashelper.modules.users.provider import UsersProvider
from manashelper.modules.users.queries import UsersQuery


@pytest.mark.parametrize(("users_count", "expected"), [(0, 0), (1, 0), (2, 1), (67, 66)])
async def test_other_users_count_preserves_exclusion_and_nonnegative_result(users_count, expected):
    repository = AsyncMock(spec=UserRepository)
    repository.count.return_value = users_count
    assert await DonationService(UsersQuery(repository)).other_users_count() == expected
    repository.count.assert_awaited_once_with()


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
    (tmp_path / "Folder.png").mkdir()

    banks = donations.list_donation_banks()

    assert [bank.name for bank in banks] == ["A Bank", "Z Bank"]
    assert all(len(bank.id) == 16 for bank in banks)
    assert [bank.id for bank in banks] == [
        sha256(name.encode()).hexdigest()[:16] for name in ("A Bank.jpg", "Z Bank.PNG")
    ]


def test_runtime_requisites_path_points_to_repository():
    assert Path(__file__).resolve().parents[1] / "docs" / "requisites" == donations.REQUISITES_DIR
    assert donations.list_donation_banks()


def test_runtime_requisites_path_is_preserved_in_docker_like_layout(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = Path(donations.__file__).resolve()
    app = tmp_path / "app"
    copied = app / source.relative_to(root)
    copied.parent.mkdir(parents=True)
    copied.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    assert runpy.run_path(str(copied))["REQUISITES_DIR"] == app / "docs" / "requisites"


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
    monkeypatch.setattr(qr_adapter, "MAX_CACHED_FILE_IDS", 2)
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


async def test_qr_cache_hit_refreshes_lru_order(tmp_path, monkeypatch):
    monkeypatch.setattr(qr_adapter, "MAX_CACHED_FILE_IDS", 2)
    bot = FakeBot()
    service = DonationQrService()
    banks = []
    for name in ("A", "B", "C"):
        path = tmp_path / f"{name}.png"
        path.write_bytes(b"qr")
        banks.append(DonationBank(name, name, path))
    for index in (0, 1, 0, 2, 0, 1):
        await service.send_bank_qr(cast(Bot, bot), 1, banks[index])
    assert bot.photos[2] == "file-1"
    assert bot.photos[4] == "file-1"
    assert isinstance(bot.photos[5], FSInputFile)
    assert len(service._file_ids) == 2


async def test_missing_photo_in_telegram_response_does_not_populate_cache(tmp_path):
    path = tmp_path / "Bank.png"
    path.write_bytes(b"qr")
    bank = DonationBank("bank", "Bank", path)
    bot = AsyncMock(spec=Bot)
    bot.send_photo.return_value = SimpleNamespace(photo=[])
    service = DonationQrService()
    await service.send_bank_qr(bot, 1, bank)
    await service.send_bank_qr(bot, 1, bank)
    assert all(isinstance(call.kwargs["photo"], FSInputFile) for call in bot.send_photo.await_args_list)
    assert not service._file_ids


async def test_qr_cache_is_shared_across_request_scopes_while_application_service_is_not(tmp_path):
    path = tmp_path / "Bank.png"
    path.write_bytes(b"qr")
    bank = DonationBank("bank", "Bank", path)
    bot = FakeBot()
    async with make_async_container(
        CoreProvider(),
        AppProvider(),
        RequestProvider(),
        ScheduleProvider(),
        NotificationsProvider(),
        UsersProvider(),
        DonationsProvider(),
    ) as container:
        qr = await container.get(DonationQrService)
        async with container() as request:
            service = await request.get(DonationService)
            assert service is await request.get(DonationService)
            assert await request.get(DonationQrService) is qr
            await qr.send_bank_qr(cast(Bot, bot), 1, bank)
        async with container() as request:
            assert await request.get(DonationService) is not service
            assert await request.get(DonationQrService) is qr
            await qr.send_bank_qr(cast(Bot, bot), 1, bank)
    assert isinstance(bot.photos[0], FSInputFile)
    assert bot.photos[1] == "file-1"
