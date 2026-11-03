from dishka import AsyncContainer, Provider, Scope, provide

from manashelper.core.config import Settings
from manashelper.platform.web.auth import AdminAuthService
from manashelper.platform.web.auth_repository import AdminAuthRepository
from manashelper.platform.web.cursors import CursorCodec
from manashelper.platform.web.login import AdminLoginCoordinator
from manashelper.platform.web.miniapp import TelegramMiniAppAuth


class WebPlatformProvider(Provider):
    scope = Scope.REQUEST

    auth_repository = provide(AdminAuthRepository)
    auth_service = provide(AdminAuthService)
    miniapp = provide(TelegramMiniAppAuth, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def login(self, container: AsyncContainer) -> AdminLoginCoordinator:
        return AdminLoginCoordinator(container)

    @provide(scope=Scope.APP)
    def cursors(self, settings: Settings) -> CursorCodec:
        if settings.admin_web_signing_key is None:
            raise ValueError("Administrative web signing key is not configured")
        return CursorCodec(settings.admin_web_signing_key.get_secret_value())
