from dishka import Provider, Scope, provide

from manashelper.repositories.eders_repository import EdersRepository
from manashelper.scraping.eders_client import EdersClient
from manashelper.services.eders import EdersService
from manashelper.services.eders_tracking import EdersTrackingService
from manashelper.services.study_week import StudyWeekService


class AppProvider(Provider):
    scope = Scope.APP

    eders_client = provide(EdersClient)


class RequestProvider(Provider):
    scope = Scope.REQUEST

    eders_repository = provide(EdersRepository)

    eders_service = provide(EdersService)
    eders_tracking_service = provide(EdersTrackingService)
    study_week_service = provide(StudyWeekService)
