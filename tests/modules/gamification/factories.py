from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.gamification.application.use_cases.award_achievement import AwardAchievementUseCase
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.gamification.presentation.sender import TelegramAchievementNotificationSender
from manashelper.modules.users.application.bot_status import BotStatusQuery
from manashelper.modules.users.application.locale import LocaleQuery
from manashelper.modules.users.application.theme import ThemeQuery
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.platform.telegram.outbox.repository import OutboxRepository
from manashelper.platform.telegram.outbox.service import OutboxService


def build_awards(session: AsyncSession) -> AwardAchievementUseCase:
    users = UserRepository(session)
    outbox = OutboxService(OutboxRepository(session), BotStatusQuery(users))
    sender = TelegramAchievementNotificationSender(outbox, LocaleQuery(users), ThemeQuery(users))
    return AwardAchievementUseCase(AchievementRepository(session), sender)
