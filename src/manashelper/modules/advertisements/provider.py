from dishka import Provider, Scope, from_context, provide

from manashelper.modules.advertisements.application.advertisement import AdvertisementQuery
from manashelper.modules.advertisements.application.expiry import PublicationRemover
from manashelper.modules.advertisements.application.use_cases.approve_advertisement import ApproveAdvertisementUseCase
from manashelper.modules.advertisements.application.use_cases.create_advertisement import CreateAdvertisementUseCase
from manashelper.modules.advertisements.application.use_cases.delete_advertisement import DeleteAdvertisementUseCase
from manashelper.modules.advertisements.application.use_cases.expire_advertisements import ExpireAdvertisementsUseCase
from manashelper.modules.advertisements.application.use_cases.record_advertisement_publications import (
    RecordAdvertisementPublicationsUseCase,
)
from manashelper.modules.advertisements.application.use_cases.reject_advertisement import RejectAdvertisementUseCase
from manashelper.modules.advertisements.application.use_cases.reveal_advertisement_contact import (
    RevealAdvertisementContactUseCase,
)
from manashelper.modules.advertisements.infrastructure.repositories.advertisement import AdvertisementRepository
from manashelper.modules.advertisements.infrastructure.repositories.advertisement_contact_view import (
    AdvertisementContactViewRepository,
)


class AdvertisementsProvider(Provider):
    scope = Scope.REQUEST

    reject_advertisement_use_case = provide(RejectAdvertisementUseCase)

    approve_advertisement_use_case = provide(ApproveAdvertisementUseCase)

    record_advertisement_publications_use_case = provide(RecordAdvertisementPublicationsUseCase)

    delete_advertisement_use_case = provide(DeleteAdvertisementUseCase)

    create_advertisement_use_case = provide(CreateAdvertisementUseCase)

    repository = provide(AdvertisementRepository)
    contact_views = provide(AdvertisementContactViewRepository)
    advertisements = provide(AdvertisementQuery)
    contacts = provide(RevealAdvertisementContactUseCase)
    publications = from_context(provides=PublicationRemover)
    expiry = provide(ExpireAdvertisementsUseCase)
