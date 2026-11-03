# Административный API сценариев

Первоначальный API реализован 2026-11-01. На этапе 2
[оркестратора](ORCHESTRATION.md) HTTP перенесён в общий aiohttp host `manashelper.main`:
он разделяет lifecycle и APP-container с Telegram и scheduler. Отдельные
`admin_main`, FastAPI и Uvicorn удалены. HTTP-фабрика для тестов сама не запускает
Bot, polling, scheduler или миграции. После сборки Vue-редактора
через Bun страница `/admin/` отдаёт редактор; без assets остаётся минимальная страница входа.
Команды сборки и работа оператора описаны в [src/admin-ui/README.md](../../src/admin-ui/README.md).
Веб-интерфейс и запасная страница входа теперь только EN; пользовательский контент
сценариев и preview сохраняют пять языков.

## Запуск

Установить зависимости через `uv sync`, применить `uv run alembic upgrade head`
к development-базе и скомпилировать gettext-каталоги. В общем процессе настроить:

```dotenv
MANASHELPER_ADMIN_WEB_ORIGIN=https://admin.example.com
MANASHELPER_ADMIN_WEB_SIGNING_KEY=<случайный секрет длиной не менее 32 символов>
MANASHELPER_ADMIN_CHAT_ID=<положительный ID приватного чата администратора>
MANASHELPER_HTTP_HOST=127.0.0.1
MANASHELPER_HTTP_PORT=8080
```

Origin задаётся без пути, query, fragment и учётных данных. Значения в `.env.example`
служат примером; реальные секреты не коммитятся. Прежние настройки БД и бота остаются
обязательными для общей модели Settings. Без origin/signing key бот работает,
а `/editor` сообщает, что веб-доступ не настроен.

Для локальной разработки явно выбрать polling:

```sh
env MANASHELPER_TELEGRAM_TRANSPORT=polling uv run python -m manashelper.main
```

aiohttp слушает `127.0.0.1:8080`. HTTPS-прокси должен направлять `/admin/` и
`/admin/api/v1/` на общий host под настроенным Origin. Cookie имеет флаг Secure,
поэтому браузерный вход требует HTTPS. Междоменный доступ не используется.
Штатный main применяет миграции перед стартом; HTTP-фабрика этого не делает.
Production по умолчанию использует webhook с отдельно настроенным secret. Приложение
не вызывает `setWebhook`/`deleteWebhook` при старте. Перед polling оператор отдельно
снимает ранее зарегистрированный webhook с сохранением pending updates; один token
нельзя одновременно обслуживать обоими transport. [Конфигурация выпуска](RELEASE.md).

## Вход и транзакции

Основной вход — Telegram Mini App:

1. Приватная `/editor` отправляет настроенному администратору кнопку `web_app` на
   HTTPS `/admin/`. Остальные пользователи и группы не получают административный вход.
2. POST `/auth/telegram` принимает отдельный DTO `ExchangeTelegram`: `{"init_data": "..."}`.
   Проверяются подпись исходных `initData`, возраст до пяти минут и совпадение
   `user.id` с настроенным администратором. `initDataUnsafe` не используется для auth;
   повторяющиеся query keys и неверный/просроченный контекст отклоняются с 401.
3. Ответ `MiniAppSession` содержит `user_id`, `expires_at`, `access_token`, без cookie
   и CSRF-токена. Сессия живёт восемь часов; клиент хранит token только в памяти и
   передаёт `Authorization: Bearer ...`. В URL, persistent browser storage,
   логах и экспорте сценариев credentials не сохраняются.
4. На одном host разрешены пять корректных обменов за минуту; шестой получает 429.
   В прежней таблице веб-сессий хранится только digest от `miniapp:` + token,
   без новой схемы БД. Cookie и bearer не взаимозаменяемы.
5. GET `/auth/session` в bearer-режиме возвращает `csrf_token=""`. Все изменяющие
   запросы требуют точного Origin, а CSRF в bearer-режиме не нужен. POST `/auth/logout`
   отзывает текущий bearer и возвращает 204 без тела.

Браузерный ticket/cookie-вход сохранён на период совместимости:

1. Рядом с Mini App доступна обычная браузерная ссылка. После commit профиля/аудита
   координатор сохраняет хеш случайного билета на
   пять минут. Ссылка отправляется после commit этого билета, без предпросмотра URL.
2. Билет передаётся во fragment `/admin/#ticket=...`. Страница удаляет fragment
   через `history.replaceState` до POST `/auth/exchange`; query и browser storage
   билет не содержат.
3. Атомарный DELETE RETURNING допускает только один успешный обмен. Сессия живёт
   восемь часов; БД хранит только хеш cookie. Cookie: HttpOnly, Secure,
   SameSite=Strict, Path=/admin.
4. GET `/auth/session` возвращает сведения текущей сессии и CSRF-токен для памяти
   страницы. Любой изменяющий запрос требует точного Origin; после входа также
   требуется `X-CSRF-Token`. POST `/auth/logout` отзывает сессию и удаляет cookie.

aiohttp middleware `admin_scope` открывает REQUEST scope вокруг выполнения и сериализации endpoint.
Ответ возвращается только после успешного commit. Ошибки выходят из scope и
запускают rollback до преобразования в HTTP-ответ. Например, сбой commit при входе
не выдаёт cookie или bearer, не создаёт сессию и не расходует ticket.

Ответы запрещают кеширование и передачу Referrer. Fallback-страница входа использует
CSP с nonce и запретом встраивания во frame. Собранный редактор допускает официальный
Telegram SDK с узкого script source и frame embedding только Telegram Web;
`unsafe-inline`/`unsafe-eval` для script не добавляются. Ошибки валидации не отражают
`initData`, ticket, credentials или содержимое формы.

## Контракт

Базовый путь — `/admin/api/v1`. Машинный контракт: [openapi.json](openapi.json).
Он генерируется из тех же Pydantic-моделей, что использует приложение.

| Метод и путь | Назначение |
| --- | --- |
| POST `/auth/telegram` | Подписанные initData → восьмичасовая bearer-сессия Mini App |
| POST `/auth/exchange` | Совместимый одноразовый ticket → cookie-сессия |
| GET `/auth/session`, POST `/auth/logout` | Текущая сессия и выход |
| GET/POST `/flows` | Список сценариев и создание черновика |
| GET `/flows/{id}` | Ревизия черновика и указатель опубликованной версии |
| GET/PUT `/flows/{id}/draft` | Чтение и сохранение с `expected_revision` |
| POST `/flows/{id}/validate` | Статическая проверка схемы и отображаемых шаблонов |
| POST `/flows/{id}/publish` | Неизменяемая версия и переключение указателя |
| GET `/flows/{id}/versions` | История публикаций |
| GET `/flows/{id}/versions/{version}` | Неизменяемый документ версии для мониторинга |
| POST `/flows/{id}/activate` | Откат/активация с `expected_published_version` |
| GET `/delegates` | Типизированные определения разрешённых делегатов |
| GET `/catalog` | Текущий DB-каталог всех локалей/тем и capabilities; `?text_catalog_release=N` выбирает исторический выпуск |
| GET `/texts` | Типизированный черновик каталога, ревизия и текущий выпуск |
| PUT `/texts/{key}` | Сохранение вариантов одного ключа с `expected_revision` |
| POST `/texts/publish` | Проверка и immutable release с `expected_revision` |
| GET `/texts/releases` | История выпусков каталога |
| POST `/texts/activate` | Откат указателя с `release_id` и `expected_current_release` |
| GET/PUT `/triggers` | Draft bindings; сохранение с `expected_revision` |
| POST `/triggers/publish` | Проверка и immutable manifest с `expected_revision` |
| GET `/triggers/releases` | История manifests с закреплёнными версиями сценариев/текстов |
| POST `/triggers/activate` | Откат указателя с `release_id` и `expected_current_release` |
| POST `/flows/{id}/preview` | Исполнение в памяти с явными заглушками |
| GET `/users/locations` | Текущий/последний runtime-шаг и статус доставки |
| GET `/users/{user_id}/location` | Положение одного зарегистрированного пользователя |
| GET `/users/{user_id}/transitions` | История переходов без ответов формы |
| GET `/rollout` | Режим запуска, ревизия, активные диалоги и автор изменения |
| PUT `/rollout` | Переключение admin/all/off с `expected_revision` |

Списки сценариев/версий/пользователей используют подписанный cursor, привязанный к виду запроса и сценарию/пользователю,
и `limit` от 1 до 100. Неправильный cursor возвращает 422. Защита ревизий возвращает
409 вместо перезаписи чужих изменений. Синтаксически корректный, но логически
незавершённый черновик можно сохранить; публикация требует успешной проверки.
Renderer проверяет шаблоны всех пяти локалей и обеих тем. Фактические динамические
значения дополнительно проверяются при исполнении.

Публикация сценария доступна pilot `/flow_demo` без рестарта. Обычные входы используют
закреплённую версию опубликованного trigger manifest: после публикации сценария
сохранить и опубликовать новую ревизию Triggers. Открытая сессия остаётся на своей
версии. Повтор публикации той же ревизии после отката не отменяет откат.
Trigger draft допускает семантически незавершённый документ; Publish/Activate проверяют
пересечения bindings, доступ, legacy contracts, target/entry и text labels.
API сохраняет прежние Origin/CSRF/commit гарантии. [Полный контракт](TRIGGERS.md).

## Preview и мониторинг

Публикация сценария возвращает `text_catalog_release`; content версии и Users
используют этот pin. Preview принимает необязательный `text_catalog_release`,
по умолчанию текущий выпуск. После изменения каталога сценарий нужно сохранить
в новой ревизии (PUT draft допускает неизменённый граф) и опубликовать заново.
Повтор Publish прежней ревизии возвращает прежнюю версию, сохраняя идемпотентность.
Существующие публикации и сессии сохраняют старый выпуск. Системная
админка остаётся EN; варианты переводов и preview поддерживают все пять языков.
Управление каталогом сохраняет те же admin/Origin/CSRF и REQUEST commit guarantees.

Preview создаёт новый реестр из определений и `delegate_results`. Реальные обработчики
делегатов не вызываются, включая делегаты чтения. Отсутствующая заглушка возвращает
ошибку preview. Исполнитель и renderer общие с runtime; сессии и ответы не сохраняются.
Контекст, узел и события задаются явно, поэтому preview не читает состояние реального
пользователя. Предпросмотр не отправляет сообщения Telegram.
Для End с возвратом preview выдаёт `screen.return_flow`: это намерение без создания
новой сессии. Реальный Telegram-адаптер возвращает к опубликованному Menu/Input
атомарно с финальным DB-делегатом. Автоматический entry цели отклоняется как
`invalid_return_entry`; отсутствующая публикация — `unpublished_return_flow`.

Мониторинг возвращает метаданные runtime и legacy: пользователя, чат, сценарий, версию,
узел, handler/FSM state, статус, время и результат runtime-доставки. Он не возвращает `session.data`, готовый
текст экрана, билеты, cookie или ответы опроса. Для завершённой сессии шаг считается
последним наблюдавшимся: `owner=unknown`, а не утверждением о текущем экране Telegram.
В списке есть все зарегистрированные пользователи: без наблюдения возвращаются
`owner=unknown`, `updated_at=null`. После перезапуска бота legacy-положение также
становится неизвестным, с сохранением последнего наблюдения. Сценарии и API-процесс
не восстанавливают MemoryStorage. Scope cursor для положения/истории обновлён до v2;
устаревший cursor возвращает 422 и требует загрузки первой страницы.
Подробности — [MONITORING.md](MONITORING.md). Сроки очистки завершённых
payload/screens и истёкшей авторизации описаны в [RELEASE.md](RELEASE.md).

Rollout по умолчанию admin-only. Для `all` проверяются обе опубликованные встроенные
схемы и их отображение. `off` запрещает новые входы, сохраняя обработку активных форм.
PUT требует существующей сессии, Origin и актуальной ревизии; cookie-режим также
требует CSRF. 409 не повторяется
автоматически. Изменение режима не публикует черновики и не перемещает пользователей.

## Проверка

API-тесты выполняют настоящее aiohttp-приложение через loopback HTTPS с временным
TLS-сертификатом и development PostgreSQL в изолированных схемах. Это проверяет
реальное поведение Secure cookies, не ASGI transport. Набор покрывает ticket/bearer
авторизацию, Origin/CSRF, конкурентный обмен билета, expiry/logout, rollback до выдачи
credentials, ревизии, публикацию/откат, подпись пагинации, изоляцию preview и мониторинга.
Отдельные тесты проверяют отправку `/editor` после commit и HTTP-фабрику без
создания Bot, polling, scheduler или запуска миграций. Итоговые результаты переноса
фиксируются отдельно; локальный TLS не доказывает production HTTPS-прокси,
настоящий webhook или fullscreen в живом Telegram.
