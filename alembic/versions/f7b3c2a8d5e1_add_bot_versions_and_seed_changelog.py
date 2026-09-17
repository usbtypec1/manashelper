"""add bot versions and seed changelog

Revision ID: f7b3c2a8d5e1
Revises: d4e8a1f2c9b6
Create Date: 2026-09-18 00:00:00.000000

"""
from datetime import date
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7b3c2a8d5e1'
down_revision: Union[str, Sequence[str], None] = 'd4e8a1f2c9b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create `bot_versions` and seed it with a user-facing changelog for every released git tag.

    `sort_order` is assigned by semantic-version order (not by tag creation time, which for a couple
    of tags — e.g. v2.0.0/v2.0.1 — doesn't match semver order), so the `/versions` command always
    lists the newest release first.

    Also drops `food_menu_cleanup_settings.delay_minutes`'s server-side default, folded in here since
    this hasn't shipped yet: with a `server_default` present, the ORM can't tell "explicitly set to
    NULL (disable auto-delete)" apart from "not set, use the default" — it omits the column from the
    INSERT and lets the server default (180) win either way, so a chat could never actually be saved
    as "disabled". `FoodMenuCleanupSettingsRepository.get_or_create` already supplies the default
    (`DEFAULT_FOOD_MENU_CLEANUP_DELAY_MINUTES`) explicitly for brand-new rows, so the server default
    was never needed for correctness.
    """
    op.alter_column('food_menu_cleanup_settings', 'delay_minutes', server_default=None)

    op.create_table(
        'bot_versions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('released_at', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sort_order'),
        sa.UniqueConstraint('version'),
    )

    bot_versions_table = sa.table(
        'bot_versions',
        sa.column('id', sa.Uuid()),
        sa.column('version', sa.String()),
        sa.column('sort_order', sa.Integer()),
        sa.column('released_at', sa.Date()),
        sa.column('description', sa.Text()),
    )

    rows = [
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000001', 'version': '1.0.0', 'sort_order': 1, 'released_at': '2026-04-20', 'description': 'Первая версия бота: можно смотреть расписание занятий и меню столовой.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000002', 'version': '1.0.1', 'sort_order': 2, 'released_at': '2026-04-20', 'description': 'Технические доработки процесса сборки и развёртывания бота. На работу бота не влияет.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000003', 'version': '1.0.2', 'sort_order': 3, 'released_at': '2026-04-20', 'description': 'Исправлена внутренняя ошибка при работе с базой данных.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000004', 'version': '1.0.3', 'sort_order': 4, 'released_at': '2026-04-20', 'description': 'Бот теперь корректно сообщает об ошибке, если не удалось получить данные с OBIS (посещаемость, оценки).'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000005', 'version': '1.0.4', 'sort_order': 5, 'released_at': '2026-04-20', 'description': 'Технические доработки, не влияющие на работу бота.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000006', 'version': '1.0.5', 'sort_order': 6, 'released_at': '2026-04-20', 'description': 'Технические доработки: улучшено логирование и очищена база данных от неиспользуемых данных.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000007', 'version': '1.0.6', 'sort_order': 7, 'released_at': '2026-04-20', 'description': 'Техническая доработка базы данных меню столовой.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000008', 'version': '1.0.7', 'sort_order': 8, 'released_at': '2026-04-20', 'description': 'Изменён интерфейс: вместо всплывающих кнопок под сообщением бот стал использовать кнопки на основной клавиатуре.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000009', 'version': '1.0.8', 'sort_order': 9, 'released_at': '2026-04-20', 'description': 'Добавлена поддержка дополнительных команд для просмотра расписания и меню столовой.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000010', 'version': '1.1.0', 'sort_order': 10, 'released_at': '2026-04-21', 'description': 'В меню столовой добавлен счётчик просмотров.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000011', 'version': '1.1.1', 'sort_order': 11, 'released_at': '2026-04-22', 'description': 'В меню столовой добавлено количество просмотров за последний час.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000012', 'version': '1.1.2', 'sort_order': 12, 'released_at': '2026-04-22', 'description': 'Улучшено отображение калорийности блюд и количества просмотров в меню столовой.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000013', 'version': '1.1.3', 'sort_order': 13, 'released_at': '2026-09-04', 'description': 'Внутренний рефакторинг кода бота. На видимую работу бота не влияет.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000014', 'version': '1.1.4', 'sort_order': 14, 'released_at': '2026-09-04', 'description': 'Исправлена ошибка сборки бота (техническое изменение).'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000015', 'version': '1.1.5', 'sort_order': 15, 'released_at': '2026-09-04', 'description': 'Технические доработки процесса развёртывания бота.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000016', 'version': '1.1.6', 'sort_order': 16, 'released_at': '2026-09-04', 'description': 'Технические доработки процесса развёртывания бота.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000017', 'version': '2.0.0', 'sort_order': 17, 'released_at': '2026-09-09', 'description': 'Бот полностью переписан на новом языке программирования (Python вместо Java). Заложена основа для дальнейшего развития.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000018', 'version': '2.0.1', 'sort_order': 18, 'released_at': '2026-09-09', 'description': 'Технические доработки после переписывания бота на Python. На видимую работу бота не влияет.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000019', 'version': '2.1.0', 'sort_order': 19, 'released_at': '2026-09-09', 'description': 'Добавлена интеграция с OBIS: теперь можно посмотреть свои оценки за экзамены и посещаемость занятий.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000020', 'version': '2.2.0', 'sort_order': 20, 'released_at': '2026-09-10', 'description': 'Добавлены уведомления и раздел «Настройки», где можно управлять ими.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000021', 'version': '2.3.0', 'sort_order': 21, 'released_at': '2026-09-10', 'description': 'Добавлена возможность смотреть собственное расписание занятий; обновлено главное меню бота.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000022', 'version': '2.4.0', 'sort_order': 22, 'released_at': '2026-09-10', 'description': 'Улучшено отображение расписания; добавлена гибкая настройка уведомлений о меню столовой (обед/ужин) с возможностью отписаться; улучшена работа с посещаемостью и оценками OBIS.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000023', 'version': '2.4.1', 'sort_order': 23, 'released_at': '2026-09-11', 'description': 'В расписании добавлены стрелки для навигации между днями недели.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000024', 'version': '2.5.0', 'sort_order': 24, 'released_at': '2026-09-11', 'description': 'Добавлен поиск предмета по названию в расписании.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000025', 'version': '2.5.1', 'sort_order': 25, 'released_at': '2026-09-13', 'description': 'Добавлены новые команды бота.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000026', 'version': '2.5.2', 'sort_order': 26, 'released_at': '2026-09-15', 'description': 'Добавлена защита от слишком частых запросов; команда /yemek теперь сразу показывает кнопки выбора дня.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000027', 'version': '2.5.3', 'sort_order': 27, 'released_at': '2026-09-15', 'description': 'Техническая версия без изменений для пользователей.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000028', 'version': '2.5.4', 'sort_order': 28, 'released_at': '2026-09-15', 'description': 'Незначительные технические исправления.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000029', 'version': '2.6.0', 'sort_order': 29, 'released_at': '2026-09-15', 'description': 'Бот заговорил на нескольких языках: добавлена поддержка русского, кыргызского и турецкого языков интерфейса.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000030', 'version': '2.6.1', 'sort_order': 30, 'released_at': '2026-09-15', 'description': 'Часть функций бота ограничена только для личных сообщений и недоступна в групповых чатах.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000031', 'version': '2.6.2', 'sort_order': 31, 'released_at': '2026-09-15', 'description': 'Продолжена работа по ограничению функций бота в групповых чатах.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000032', 'version': '2.6.3', 'sort_order': 32, 'released_at': '2026-09-15', 'description': 'Уточнён список функций, доступных только в личных сообщениях с ботом.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000033', 'version': '2.6.4', 'sort_order': 33, 'released_at': '2026-09-15', 'description': 'Улучшены настройки уведомлений о меню столовой.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000034', 'version': '2.6.5', 'sort_order': 34, 'released_at': '2026-09-15', 'description': 'Техническая версия без изменений для пользователей.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000035', 'version': '2.6.6', 'sort_order': 35, 'released_at': '2026-09-15', 'description': 'Незначительные технические исправления.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000036', 'version': '2.6.7', 'sort_order': 36, 'released_at': '2026-09-15', 'description': 'Язык интерфейса теперь определяется автоматически по настройкам Telegram.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000037', 'version': '2.6.8', 'sort_order': 37, 'released_at': '2026-09-15', 'description': 'Добавлено предупреждение об обеденном перерыве в столовой.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000038', 'version': '2.6.9', 'sort_order': 38, 'released_at': '2026-09-15', 'description': 'Предупреждение об обеденном перерыве отключено.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000039', 'version': '2.6.10', 'sort_order': 39, 'released_at': '2026-09-15', 'description': 'Полностью убрано сообщение об обеденном перерыве.'},
            {'id': '2f0a1b6e-1a3d-4a3d-9c1b-000000000040', 'version': '2.6.11', 'sort_order': 40, 'released_at': '2026-09-17', 'description': 'В групповых чатах бот больше не показывает основную клавиатуру с кнопками.'},
    ]
    for row in rows:
        row['released_at'] = date.fromisoformat(row['released_at'])
    op.bulk_insert(bot_versions_table, rows)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('bot_versions')
    op.alter_column('food_menu_cleanup_settings', 'delay_minutes', server_default='180')
