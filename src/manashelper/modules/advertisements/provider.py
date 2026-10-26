from dishka import Provider, Scope, from_context, provide

from manashelper.modules.advertisements.application.advertisement import AdvertisementService
from manashelper.modules.advertisements.application.advertisement_contact import AdvertisementContactService
from manashelper.modules.advertisements.application.advertisement_moderation import AdvertisementModerationService
from manashelper.modules.advertisements.application.expiry import ExpireAdvertisements, PublicationRemover
from manashelper.modules.advertisements.infrastructure.advertisement_contact_view_repository import (
    AdvertisementContactViewRepository,
)
from manashelper.modules.advertisements.infrastructure.advertisement_repository import AdvertisementRepository


class AdvertisementsProvider(Provider):
    scope = Scope.REQUEST

    repository = provide(AdvertisementRepository)
    contact_views = provide(AdvertisementContactViewRepository)
    advertisements = provide(AdvertisementService)
    moderation = provide(AdvertisementModerationService)
    contacts = provide(AdvertisementContactService)
    publications = from_context(provides=PublicationRemover)
    expiry = provide(ExpireAdvertisements)
