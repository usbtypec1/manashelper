from types import SimpleNamespace
from unittest.mock import AsyncMock

from manashelper.modules.advertisements.application.advertisement import AdvertisementQuery
from manashelper.modules.advertisements.application.use_cases.approve_advertisement import ApproveAdvertisementUseCase
from manashelper.modules.advertisements.application.use_cases.create_advertisement import CreateAdvertisementUseCase
from manashelper.modules.advertisements.application.use_cases.delete_advertisement import DeleteAdvertisementUseCase
from manashelper.modules.advertisements.application.use_cases.record_advertisement_publications import (
    RecordAdvertisementPublicationsUseCase,
)
from manashelper.modules.advertisements.application.use_cases.reject_advertisement import RejectAdvertisementUseCase


def build_advertisement_service(advertisement_repository, users):
    query = AdvertisementQuery(advertisement_repository, users)
    return SimpleNamespace(
        get_contact_status=query.get_contact_status,
        assert_can_post=query.assert_can_post,
        get_page_by_user_id=query.get_page_by_user_id,
        get_owned_by_id=query.get_owned_by_id,
        create_advertisement=CreateAdvertisementUseCase(
            advertisement_repository=advertisement_repository, users=users
        ).execute,
        delete_owned=DeleteAdvertisementUseCase(advertisement_repository=advertisement_repository).execute,
        record_channel_messages=RecordAdvertisementPublicationsUseCase(
            activity=AsyncMock(), advertisement_repository=advertisement_repository
        ).execute,
    )


def build_advertisement_moderation_service(advertisement_repository):
    return SimpleNamespace(
        approve=ApproveAdvertisementUseCase(advertisement_repository=advertisement_repository).execute,
        reject=RejectAdvertisementUseCase(advertisement_repository=advertisement_repository).execute,
    )
