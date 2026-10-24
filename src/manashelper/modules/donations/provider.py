from dishka import Provider, Scope, provide

from manashelper.modules.donations.qr import DonationQrService
from manashelper.modules.donations.service import DonationService


class DonationsProvider(Provider):
    scope = Scope.REQUEST

    qr = provide(DonationQrService, scope=Scope.APP)
    service = provide(DonationService)
