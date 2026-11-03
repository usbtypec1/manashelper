# Включение визуальных сценариев и откат

Этап 8 реализован: режим запуска хранится в БД, меняется через админку без рестарта
и не заменяет уже начатые формы. Веб-интерфейс — только EN; тексты бота и preview —
EN/RU/KY/TR/ZH. Рабочая схема БД не удаляется при отключении сценариев.
Перенос host/auth второго этапа [оркестратора](ORCHESTRATION.md) добавляет общий
aiohttp-процесс и Mini App. Итоговые проверки этого переноса фиксируются отдельно;
исторические локальные результаты в конце относятся к прежним этапам редактора.

## Режимы запуска

В заголовке редактора открыть **Release**. После выбора режима нажать **Apply**,
затем подтвердить изменение. Начальный режим — **Admin only**.

| Режим | Новые входы | Уже начатые диалоги |
| --- | --- | --- |
| Admin only | Runtime для приватного администратора, прежние маршруты для остальных | Продолжаются на закреплённой версии |
| All users | Runtime-меню и опрос для приватных пользователей | Продолжаются на закреплённой версии |
| Off | Прежние маршруты для всех, новые runtime-запуски запрещены | Можно завершить, восстановить шаг или явно отменить |

Для All users нужны проверенные опубликованные `main_menu` и `student_questions`.
Черновики не включаются автоматически. Доступ к `/editor` и `/flow_demo` остаётся
административным при любом режиме. Группы не становятся runtime-чатами.

Режим имеет отдельную ревизию; устаревшая запись получает 409 и не перезаписывает
изменение из другой вкладки. Переключатель показывает число активных диалогов.
Проверка в фильтре маршрута дополняется авторитетной проверкой в транзакции запуска.
Короткая shared-блокировка строки режима упорядочивает запуск и отключение; во время
Telegram HTTP эта блокировка уже освобождена.

После Off или отката к Admin only обычный пользователь завершает начатый опрос
без открытия новой runtime-сессии меню: ответ сохраняется и показывается прежняя
клавиатура. Повтор `/start student_questions` восстанавливает активный runtime-опрос
даже при Off. Для явного выхода подходит `/start` или глобальный Back.

## Подготовка и запуск

В единственном процессе `manashelper.main` настроить БД, приватный admin chat ID
и Telegram transport. Webhook выбран по умолчанию:

```dotenv
MANASHELPER_ADMIN_WEB_ORIGIN=https://admin.example.com
MANASHELPER_ADMIN_WEB_SIGNING_KEY=<случайный секрет не короче 32 символов>
MANASHELPER_TELEGRAM_TRANSPORT=webhook
MANASHELPER_TELEGRAM_WEBHOOK_SECRET=<случайные 16–256 ASCII-букв, цифр, _ или ->
MANASHELPER_HTTP_HOST=127.0.0.1
MANASHELPER_HTTP_PORT=8080
```

Origin/signing key включают административные маршруты на том же host. Если оба
параметра не заданы, webhook и `/health` работают без админки. Webhook secret
обязателен в webhook-режиме и не заменяет bot token или signing key.

Из корня проекта установить Python-зависимости, скомпилировать каталоги и применить
миграции к выбранной development/staging БД:

```sh
uv sync
uv run pybabel compile -d src/manashelper/locales
uv run alembic upgrade head
```

Собрать frontend:

```sh
cd src/admin-ui
bun install --frozen-lockfile
bun run build
```

Запустить один процесс из корня проекта:

```sh
uv run python -m manashelper.main
```

Он обслуживает Telegram, admin API, built assets и фоновые задания. Отдельные
FastAPI/Uvicorn и admin-служба удалены. HTTPS-прокси передаёт `/telegram/webhook`
на этот host, а `/admin/` вместе с `/admin/api/v1/` — под настроенным HTTPS Origin.
`/health` возвращает минимальный статус без конфигурации и секретов.

До переключения production оператор отдельно проверяет HTTPS-адрес, правильный
webhook secret и настройку Telegram `setWebhook`. Адрес доставки —
`https://<host>/telegram/webhook`; bot token не включается в этот URL. При старте
приложение не регистрирует и не удаляет webhook и не отбрасывает pending updates.
Этот документ и локальные проверки не выполняют переключение Telegram.

Для development явно выбрать `MANASHELPER_TELEGRAM_TRANSPORT=polling`. С тем же
bot token не должен работать webhook; отключение ранее зарегистрированного webhook
выполняется оператором отдельно с сохранением pending updates. Polling использует
тот же Dispatcher и общий HTTP-host, без отдельного процесса для админки.

В приватном чате администратора `/editor` открывает `web_app` на `/admin/`.
Подписанные `initData` принимаются только от настроенного admin user и не старше
пяти минут; шестой корректный обмен за минуту на одном host получает 429.
Сессия действует восемь часов, bearer token хранится только в памяти Mini App.
Ни `initData`, ни token не должны появляться в URL, persistent browser storage,
логах или экспорте сценария.

Рядом остаётся ссылка обычного браузерного входа: одноразовый ticket на пять минут
во fragment URL и восьмичасовая Secure/HttpOnly/SameSite=Strict cookie-сессия.
Изменяющие запросы обоих режимов требуют точного Origin; CSRF нужен cookie-режиму.
Не отключать эти проверки для разработки. Credentials выдаются после commit.
Cookie и bearer не взаимозаменяемы; logout отзывает текущую сессию. Новая схема БД
не требуется: хранится только digest с отдельным `miniapp:` namespace в прежней
таблице веб-сессий. Старые cookie и билеты сохраняют совместимость.

## Docker

`docker/Dockerfile` собирает Python и frontend раздельно. Frontend использует
`oven/bun:1.4.3`, frozen lockfile, Bun typecheck и Vite через Bun; в конечный Python-
образ копируется готовый `dist`. Английский bundle выводится из скомпилированного
каталога во время сборки. Node.js и npm не нужны в runtime. Подход соответствует
[официальной инструкции Bun для Docker](https://bun.sh/guides/ecosystem/docker).

```sh
docker build -f docker/Dockerfile -t usbtypec1/manashelper:ui-flows-local .
```

Задать `MANASHELPER_VERSION=ui-flows-local` для compose. Единственный сервис `app`
запускает общий host; Docker задаёт `MANASHELPER_HTTP_HOST=0.0.0.0`, а опубликованный
порт остаётся loopback. По умолчанию используется `127.0.0.1:8080`.
Сначала применить миграции, затем запустить приложение и удалить прежний отдельный
admin-контейнер, если он остался от предыдущей compose-конфигурации:

```sh
docker compose --project-directory . --env-file .env -f docker/docker-compose.prod.yaml run --rm --no-deps --entrypoint alembic app upgrade head
docker compose --project-directory . --env-file .env -f docker/docker-compose.prod.yaml up -d --remove-orphans app
```

Команды предполагают уже доступную БД выбранного окружения. При её первом запуске
поднять сервис `db` и дождаться healthcheck. HTTPS-прокси размещается перед loopback-
портом; открытый HTTP-порт не заменяет настроенный HTTPS Origin.

## Проверка включения и отката

Сначала в режиме Admin only пройти меню и обе ветки опроса отдельным тестовым
ботом. Проверить отмену замены старого ответа, устаревшую кнопку, смену локали/темы
и вход `/editor`. В Users сравнить шаг с показанным экраном. Затем выбрать All users.

Для отката публикации открыть Versions и активировать предыдущую версию. Новые
сессии используют её; уже начатые читают собственную неизменяемую версию. Для
отключения новых запусков выбрать Off либо вернуть Admin only. Начатые формы
продолжают обслуживаться; удаление таблиц и downgrade миграций для этого не нужны.

Неопределённая доставка не повторяется автоматически. Повторный вход в активный
опрос восстанавливает экран без повторения DB-делегата. После перезапуска runtime
сохраняет шаг, а потерянный legacy MemoryStorage обозначается unknown.

Откат host/auth не требует downgrade БД: прежние tickets/cookies и таблица сессий
сохраняются. До возврата к polling явно выбрать transport и отдельно снять webhook
в Telegram без удаления pending updates; остановить новый процесс перед запуском
предыдущей версии. Старый браузерный ticket/cookie-путь остаётся доступен на период
совместимости. Откат приложения не равен переключению runtime rollout в Off.

## Очистка данных

Бот ежедневно в 04:15 по Бишкеку очищает payload закрытых runtime-сессий старше
семи дней и удаляет их старые screen intents. Активные формы и их экраны остаются.
Погрешность срока — до следующего ежедневного прогона. Сохранённые бизнес-ответы
опроса не удаляются. Сессии, версии, история без ответов и event receipts сохраняются,
чтобы очистка не разрешала повторное выполнение старого бизнес-события.

В 04:20 удаляются истёкшие билеты и веб-сессии администратора. Время истечения
проверяется при каждом входе независимо от запуска очистки. Ошибка задания
откатывает его REQUEST, логируется и не запускает повторную отправку сообщений.

## Исторические локальные доказательства этапов редактора 1–8

Числа ниже зафиксированы до переноса HTTP на aiohttp и Mini App. Они не доказывают
новый webhook/fullscreen. Для второго этапа нужны отдельные HTTP/транзакционные,
auth и browser E2E-проверки; live webhook и fullscreen в Telegram Android/iOS/Desktop
и выбранных Web-клиентах остаются отдельной приёмкой перед выпуском.

Проверены публичные входы на пяти языках, переходы All users → Off/Admin only,
завершение и восстановление старой формы после отключения, новые legacy-входы,
ревизии режима и ожидание транзакции запуска. Проверены публикация/откат без
смены версии активной формы, сохранность бизнес-ответов/receipts при очистке и
upgrade/downgrade миграции `17f4cf2162e2` без удаления прежних данных.

Регрессия: 915 Python-тестов прошли, 32 необязательные проверки пропущены; полный
прогон использовал отдельную временную development-БД, удалённую после тестов.
UI-flow fixtures также используют отдельные схемы, поэтому авторские документы
и наблюдения живого тестового бота не мешают проверкам. Тест выбора получателей
создаёт собственный курс и не зависит от содержимого учебного каталога.
Frontend — 9 unit и 7 E2E через Bun. Docker-
образ собран и запущен: EN assets, CSP, защищённый API, отсутствие выдачи исходников,
38 зарегистрированных таблиц и отсутствие Node.js в runtime проверены отдельно.
Ruff, format, strict mypy, OpenAPI validator и `alembic check` прошли.
Настоящий aiogram HTTP проверен через локальную Postman-симуляцию: 9 passed.
При живой проверке найдена и исправлена попытка редактировать ReplyKeyboardRemove.
Исправленный production sender успешно отправил отдельные text/inline-сообщения
тестовому администратору; callbacks привязаны к ID второго сообщения. Диагностические
сообщения удалены. [Подробности доставки](TELEGRAM.md).
Через локальный HTTPS-прокси отдельно проверены обмен настоящего одноразового
билета, Secure/HttpOnly/SameSite cookie, чтение rollout/catalog, отказ при неверном
CSRF и logout. В этом Windows-окружении localhost и host.docker.internal попадали
в разные экземпляры PostgreSQL; для живого прогона HTTP-процесс запущен нативно
с той же БД, что у бота. Исходный `.env` не изменялся, web-параметры заданы только
для тестовых процессов. Polling ограничен настроенным приватным администратором;
планировщик и фоновые рассылки в этом тестовом обработчике не запускаются.
Доказательства локального/смоделированного исполнения не заменяют проход с живым
тестовым ботом и проверку HTTPS Origin выбранного окружения перед общим выпуском.

## Проверки общего host и Mini App: 2026-11-02

Admin API перенесён на aiohttp с сохранением URL/operation ID и DTO, отдельно добавлен
`POST /auth/telegram`. Настоящий loopback HTTPS проверяет ticket/cookie и bearer,
Origin/CSRF, commit failure без выдачи credentials, JSON/Content-Type, 204,
валидацию query/path и запрет выдачи исходников/внешних symlink assets.
Сигналы/ошибки запуска проверены lifecycle-тестами; реальная coroutine-задача scheduler
доказывает ожидание её финализатора до закрытия DI/БД.

Frontend: 19 unit и 9 E2E прошли через Bun, включая подписанный synthetic initData,
отказ чужому/просроченному контексту, bearer без cookies/storage, SDK fullscreen/fallback,
safe areas, BackButton, dirty-close guard и взаимоисключающие мобильные панели.
E2E использует SDK mock и реальный aiohttp API с временной схемой PostgreSQL.

Десять HTTP-тестов прошли через существующую локальную Postman-симуляцию Telegram.
Добавлены реальный aiogram sendMessage с web_app-кнопкой `/editor` и путь webhook →
Dispatcher → завершение опроса: повтор финального update сохраняет один ответ и
не отправляет второй экран. Только Telegram API заменён stand-in; Python, HTTP,
координатор и PostgreSQL работают реально. Это гарантия проверенного runtime-пути;
legacy handlers ещё не имеют универсальных durable update receipts.

Docker-образ собран и smoke-проверен: aiohttp health, built assets, CSP, защищённый API,
404 для исходников, 38 таблиц; FastAPI/Starlette/Uvicorn и Node/Bun отсутствуют в runtime.
Реальная регистрация webhook, доставка Telegram и fullscreen на устройствах не запускались.

Полная Python-регрессия: 984 passed, 34 skipped на отдельной временной development-БД
PostgreSQL 18 после `alembic upgrade head`; `alembic check` не нашёл расхождений.
База удалена после прогона. Исходная локальная БД оставлена на прежней ревизии.
Ruff, format, strict mypy, актуальность контрактов/API-типов/editor copy и матрица UI
прошли. Optional HTTP-проверки Telegram выполнены отдельно через указанную симуляцию;
остальные пропуски не объявляются проверенным upstream-поведением.

## Локальные доказательства этапа 3 оркестратора — 2026-11-02

DB-каталог импортирует 356 пользовательских ключей и 3576 вариантов пяти языков,
двух тем и множественных форм. Texts позволяет редактировать, публиковать и откатывать
выпуски. Сценарий закрепляет выпуск при публикации; активные формы, исторический
preview, мониторинг и delivery intent сохраняют pin. Для новых текстов черновик
сценария снова сохраняется (даже без изменения графа) и публикуется в новой ревизии.
Повторы Publish сохраняют идемпотентность. [Совместимость и откат](LOCALIZATION.md).

Полная Python-регрессия: **1009 passed, 35 skipped** на отдельной временной
development-БД PostgreSQL 18. Применены все миграции, `alembic check` не обнаружил
расхождений; временная БД удалена. Тест миграции отдельно проверяет upgrade,
immutable trigger, старый writer с nullable pin и downgrade без изменения прежних
документов/ответов. Рабочая локальная БД и `.env` не изменялись.

Ruff, format и strict mypy прошли. Экспорт OpenAPI/schema, generated API types,
editor copy, инвентарь текстов и матрица 442 UI surfaces актуальны. Новые ссылки
документации и `git diff --check` проверены.

Frontend: сборка, 19 unit и **12 E2E** через Bun прошли. Новые браузерные сценарии
покрывают сохранение/публикацию/откат перевода, 409 без потери правок, подтверждённый
Reload и сохранение текста при переключении режима. Отдельный E2E сохраняет граф
без изменений в новой ревизии, публикует его и проверяет переход text pin с 1 на 2,
не меняя документ и не обходя идемпотентность Publish. Проверен screenshot редактора.

**11 HTTP-тестов** прошли через существующую локальную Postman-симуляцию Telegram;
вместе с DB-каталогом и экранированием расписания — 32 focused tests. Реальный
aiogram/coordinator/PostgreSQL доставил два меню с выпуском 2 после публикации
выпуска 3, сохранил pin в intents и ответил на expired callback после закрытия
REQUEST. В этом тесте нет ambient catalog, а файловое чтение переводов запрещено.
Лог симуляции подтверждает два запроса с закреплённой подписью и callback alert.

Docker-образ собран и smoke-проверен: health/assets/CSP/401/404, 40 таблиц,
отсутствие FastAPI/Starlette/Uvicorn/Node/Bun в runtime. Реальная доставка Telegram,
регистрация webhook и fullscreen на устройствах на этом этапе не запускались.
Коммиты, push и deploy не выполнялись. Следующий этап — единые события и launch policy;
он не входит в эти результаты.

## Локальные доказательства этапа 4 оркестратора — 2026-11-02

Реализованы [единые события, trigger registry и launch policy](TRIGGERS.md).
Production Dispatcher использует один resolver и явные legacy adapters. Начальный
документ содержит 78 bindings и 38 типизированных callback codecs. Manifest закрепляет
версии сценариев, тексты и return targets; опубликованные releases неизменяемы.
Композиция, durable frames и перенос тел legacy-форм относятся к этапу 5 и далее.

Полная Python-регрессия: **1045 passed, 36 skipped** на отдельной временной БД
PostgreSQL 18 после всех миграций. `alembic check` не обнаружил расхождений; временная
БД удалена, исходная локальная БД и `.env` не изменялись. Пропущенные optional/upstream
сценарии не считаются проверенным поведением. Дополнительно **31 focused test**
проверил resolver/adapter и настоящий production Dispatcher: роли/scope/capabilities,
busy policy, immutable pins, return через старый manifest, optimistic conflicts,
receipts/races/rollback и повторы с проверкой исходной session/revision.
Completed replay не очищает позднее открывшуюся legacy-форму; pending replay
не применяет старый ввод к новой форме и повторно проверяет доступ к запуску.
Пароль OBIS сохраняет совместимость со slash/@ вводом, включая недоступные команды;
audit содержит `[masked]`, receipt не содержит секрета.

API-тесты проверили auth/Origin/CSRF, публикацию/активацию, 409/422 и rollback.
Миграция `2deed60a5bfd` проверена на реальном PostgreSQL: три таблицы, nullable pin,
реальные FK, immutable release trigger, старые writers, downgrade/re-upgrade
без изменения прежних session payloads. Это расширение схемы; штатный rollback
переключает manifest, сохраняя историю и активные сессии.

Frontend: build, **19 unit** и **14 E2E** через Bun прошли. Браузерные проверки
в реальном loopback HTTPS aiohttp + PostgreSQL покрывают создание/публикацию/откат
manifest, идемпотентный Publish после rollback, сохранение правок при конфликте
и переключении режимов, dirty guards и сохранение графа при невалидной скрытой
trigger-форме. Проверен мобильный screenshot Triggers. Live Telegram client/fullscreen
этим прогоном не проверяется.

**12 HTTP-тестов** прошли через существующую локальную Postman-симуляцию Telegram.
Python/webhook/Dispatcher/coordinator/PostgreSQL исполнялись реально. Unified webhook
сохранил четыре metadata-only admission receipts, один ответ анкеты, один финальный
event и return session с pin manifest 1. Replay финального callback не отправил
второй экран. Лог подтвердил sendMessage/answerCallbackQuery и прежние моделируемые
ошибки доставки. [Контекст доказательств](../../postman/simulations/telegram.context.yaml)
дополнен без удаления прежних результатов. Симуляция не доказывает live-поведение Telegram.

Ruff, format, strict mypy (367 source files), OpenAPI/schema, generated API types,
editor copy, инвентарь текстов и матрица **452 surfaces / 91 files / 13 groups** прошли.
Новые ссылки документации и `git diff --check` проверены. Docker-образ пересобран
из финального backend и smoke-проверен: **43 таблицы**, health/assets/CSP/401/404;
FastAPI/Starlette/Uvicorn/Node/Bun отсутствуют в runtime.

Этап 4 завершён. Следующий — контракт v2 и композиция (этап 5), ещё не начат.
Реальная доставка Telegram, регистрация webhook, коммиты, push и deploy не выполнялись.
