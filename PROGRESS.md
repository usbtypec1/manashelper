# Полный переход UI на оркестратор

Пользователь разрешил выполнить все оставшиеся этапы плана
`features/ui_flows/ORCHESTRATION.md`. Рабочие незакоммиченные изменения сохраняются.
Коммиты/push/deploy и регистрация webhook не входят в запрос.

| Этап | Состояние | Условие готовности |
| --- | --- | --- |
| 1–4 | Выполнены | Inventory, aiohttp/Mini App, DB localization, unified ingress/triggers |
| 5 | Выполнен | v2 Call/Return/Replace, pinned dependencies, durable frames; v1 совместим |
| 6 | Выполнен | Typed collections, action snapshots, effects, rich delivery, secret handles |
| 7 | Выполнен с сохранением legacy-совместимости | Navigation/locale/theme/settings/survey через сценарии, legacy-совместимость |
| 8 | Ожидает | Schedule/Food/Notifications через сценарии |
| 9 | Ожидает | Users/OBIS/Eders/Study week; кеши и формы переживают рестарт |
| 10 | Ожидает | Advertisements, albums, contact gate, scoped moderation |
| 11 | Ожидает | Feedback/native reply/Broadcast с прежними delivery guarantees |
| 12 | Ожидает | Полный cutover, удаление FSM/legacy UI handlers и handoff |

Последняя доказанная граница: этапы 5–6, 1125 Python passed/41 skipped, 21 frontend unit,
19 browser E2E, 17 Telegram HTTP simulation, Docker smoke (45 таблиц), Ruff/mypy/artifact checks.
Полная приёмка требует проверок каждого нового пути, миграции/отката, restart/replay,
сохранности данных, актуальных контрактов/редактора и итоговой полной регрессии.

Этап 5: 342 UI/локализационных теста прошли, 12 HTTP optional пропущены;
40 focused ingress/composition, 21 schema/migration и 3 browser composition/survey прошли.
При review исправлены pinned rollback, валидация preview frames и ложный запрет
циклического вызова интерактивного дочернего сценария.

Этап 6: полная Python-регрессия и все указанные frontend/HTTP проверки прошли
2026-11-03. Внешние операции сохраняют unknown до I/O, не повторяются после
cancellation; saved results применяются отдельно с корреляцией позиции. Pending
intent после committed apply восстанавливается без повторного внешнего вызова.
Одна APP ChatOrdering сериализует message/callback updates и effect completion
до завершения доставки; поздний экран не накладывается на новую навигацию.

Typed contact/media/secret ingress, TTL5min encrypted handles, cleanup closed
payloads через семь дней и сохранность active/recent/receipts проверены.
Rich delivery сохраняет все известные message IDs при TelegramAPIError,
unexpected error и cancellation; unknown не пересылается при restart/replay.
HTTP simulation покрывает photo/video/mixed album/10 items/partial inline failure.
Редактор позволяет авторить media/message_source refs с path, локализованные chunks,
порядок и удаление; preview экранирует динамический контент и использует sample
contact/media/secret events. Невалидные shape/capacity/HTML отклоняются до публикации.

Проверки выполнялись в disposable PostgreSQL БД/схемах и через loopback HTTPS;
рабочая БД, бот и webhook не менялись. Live Telegram/реальные аккаунты этими
проверками не подтверждены. Docker image smoke проверил health, built assets/CSP,
401/404 и отсутствие FastAPI/Uvicorn/Node/Bun в Python runtime.

Этап 7: main_menu/Studies вызывает Settings; Settings вызывает сценарии выбора
языка и темы с возвращением к родителю. Глобальный выбор сохраняет вложенную форму,
её pinned версии, данные и ожидаемую внешнюю операцию после рестарта. Старые
callback становятся stale; replay не повторяет запись. Миграция a7572f78b034
добавляет nullable effect_revision и запрещает небезопасный downgrade с активными
interrupt frames. Отдельные PostgreSQL проверки охватывают старых writers,
rollback, pending/succeeded/unknown операции и конкуренцию.

В соответствии с актуальными инструкциями начатые legacy-анкеты сохраняют владельца,
а fallback остаётся доступен при off/admin. Существующие операторские draft и release
не перезаписываются: для перехода существующей установки нужны проверенные новые
публикации дочерних сценариев, main_menu и затем Triggers. На новой установке seed
публикует их в порядке зависимостей. Если авторский черновик ещё не опубликован,
запуск использует совместимый manifest и не заменяет его.

Локальная проверка 2026-11-03: 70 focused Python tests, 19 browser E2E и отдельный
новый browser E2E для политики Call; 21 frontend unit; 17 Telegram HTTP tests
через Postman stand-in; Docker smoke на 45 таблицах; Ruff, mypy, Alembic check,
генерация схем и inventory. Реальный Telegram при проверках не использовался.
Полная Python-регрессия: 1198 passed, 41 skipped; отдельные focused-проверки
нового Trigger Call и сохранности unpublished seed прошли. После этапа 7 пользователь
просил остановиться и создать коммит без push/deploy. Этапы 8–12 не начаты в рамках
этого продолжения; подготовленные ранее Schedule сценарии пока не интегрированы.
