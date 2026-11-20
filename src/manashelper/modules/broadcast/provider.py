from dishka import Provider, Scope, provide

from manashelper.modules.broadcast.application.campaigns import CampaignDelivery
from manashelper.modules.broadcast.application.queries import CampaignsQuery
from manashelper.modules.broadcast.application.use_cases.create_campaign import CreateCampaignUseCase
from manashelper.modules.broadcast.application.use_cases.retry_campaign import RetryCampaignUseCase
from manashelper.modules.broadcast.application.use_cases.send_broadcast import SendBroadcastUseCase
from manashelper.modules.broadcast.infrastructure.repositories.campaign import CampaignRepository
from manashelper.modules.broadcast.sender import TelegramCampaignDelivery


class BroadcastProvider(Provider):
    scope = Scope.REQUEST

    send_broadcast = provide(SendBroadcastUseCase)
    campaigns = provide(CampaignRepository)
    campaign_delivery = provide(TelegramCampaignDelivery, provides=CampaignDelivery)
    create_campaign = provide(CreateCampaignUseCase)
    retry_campaign = provide(RetryCampaignUseCase)
    campaign_queries = provide(CampaignsQuery)
