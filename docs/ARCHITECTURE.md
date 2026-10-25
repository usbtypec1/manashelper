# Структура и архитектура Manashelper

Состояние исходного кода и конфигурации на 25 октября 2026 года. Документ описывает реализацию в текущем
репозитории; наличие функции в `features/` само по себе не означает, что она реализована.

План переноса бизнес-областей в функциональные модули выполнен. Перенесены `feedback`,
`advertisements`, `student_questions`, `versions`, `donations`, `broadcast`, `food_menu`, `schedule`, `notifications`, `users`, `obis`, `eders` и `study_week`.
Код каждой области собран в `modules/`.
У объявлений также перенесена очистка истёкших публикаций. Versions остаётся набором функций без DI provider.
В `modules/users/` собраны профиль, локаль и контакты: application-сервисы, ORM/repositories и Telegram
presentation. Публичный UsersQuery предоставляет count, список ID и проверку существования для потребителей.
В плоском `modules/notifications/` собраны настройки расписания/оценок/пропусков, запросы получателей,
ORM, repository и Telegram presentation. Food menu/Eders сохраняют собственные настройки;
общая навигация Settings и Telegram-инфраструктура собраны в `platform/telegram/`.
ObisCredentialsService владеет credentials и предоставляет их Eders через application-границу;
поля остаются в существующей таблице User. Eders tracking использует UsersQuery.exists; его repository сохраняет
SQL eligibility и блокировку строки User. Учебная неделя объединяет публичные application-результаты Eders и Schedule.
Карта зависимостей, порядок этапов и исходные проблемы проверок описаны в [MIGRATION.md](MIGRATION.md).
Общая инфраструктура выделена в `core/`: настройки, логирование, Base/фабрики БД и управление ресурсами DI.
Telegram Platform, аудит и очередь удаления сообщений перенесены; gettext adapter находится в `platform/i18n/`.

## 1. Назначение и общий подход

Manashelper — Telegram-бот для студентов Кыргызско-Турецкого университета «Манас». Он объединяет расписание,
меню столовой, оценки и посещаемость OBIS, задания и материалы eders, объявления и общение с администратором.
Пользователь работает через команды, reply-клавиатуры и inline-кнопки Telegram.

Архитектурно это асинхронный монолит с постепенным переходом от слоёв к функциональным модулям.
Один Python-процесс принимает обновления
Telegram через long polling и выполняет фоновые задания APScheduler. Постоянные данные хранятся в PostgreSQL.
Собственного REST API, веб-интерфейса, отдельного сервиса фоновых работников и брокера сообщений в текущей
конфигурации нет. Postman в репозитории используется для локальной имитации внешнего eders при тестировании.

```mermaid
flowchart TD
    TG[Telegram Bot API] -->|long polling| DP[aiogram Dispatcher]
    DP --> MW[Middleware и фильтры]
    MW --> RT[Обработчики Telegram]
    RT --> SV[Сервисы и форматирование]
    SC[APScheduler] --> JB[Фоновые задания]
    JB --> SV
    SV --> RP[Репозитории SQLAlchemy]
    RP --> DB[(PostgreSQL)]
    SV --> CL[HTTP-клиенты и парсеры]
    CL --> UNI[Расписание, столовая, OBIS, eders]
    RT -->|ответы и публикации| TG
    JB -->|рассылки и удаление сообщений| TG
```

Основной путь зависимостей: обработчик вызывает сервис, сервис использует репозиторий или HTTP-клиент,
репозиторий работает с ORM-моделями. Форматтеры и клавиатуры превращают результаты в сообщения Telegram.
Это практическое разделение по слоям: отдельного независимого доменного пакета и интерфейсов для каждого
репозитория здесь нет.

## 2. Технологический стек

| Область | Технология и роль |
| --- | --- |
| Исполнение | Python 3.13+, `asyncio` |
| Telegram | aiogram 3: маршрутизация, фильтры, FSM, клавиатуры, HTML и rich messages |
| Доступ к данным | SQLAlchemy 2 в асинхронном режиме, драйвер `asyncpg` |
| Хранилище | PostgreSQL 17 в Docker Compose |
| Миграции | Alembic |
| Внедрение зависимостей | Dishka, области жизни `APP` и `REQUEST` |
| Фоновые задачи | APScheduler 3, `AsyncIOScheduler` |
| Получение страниц | `httpx.AsyncClient` |
| Разбор HTML | BeautifulSoup и lxml |
| Конфигурация | `pydantic-settings`, переменные окружения и `.env` |
| Шифрование паролей | `cryptography`, AES-GCM |
| Переводы | gettext, Babel, адаптер `CatalogI18n` |
| Разработка | uv, Ruff, mypy в строгом режиме, pytest и pytest-asyncio |
| Доставка | Docker, GitHub Actions, Docker Hub, SSH и Docker Compose |

Декларации зависимостей находятся в [pyproject.toml](../pyproject.toml), зафиксированные версии — в `uv.lock`.

## 3. Структура репозитория

```text
manashelper/
├── src/manashelper/
│   ├── main.py                    # Точка входа и жизненный цикл приложения
│   ├── core/
│   │   ├── config.py              # Настройки окружения и кеш
│   │   ├── database.py            # DeclarativeBase, engine, фабрика сессий
│   │   ├── logging.py             # Консольные и файловые логи
│   │   └── provider.py            # Общие APP-ресурсы и REQUEST-сессия
│   ├── platform/
│   │   ├── i18n/catalog.py        # CatalogI18n и единый gettext context
│   │   └── telegram/
│   │       ├── dispatcher.py      # Middleware, маршрутизаторы, обработчик ошибок
│   │       ├── commands.py        # Регистрация команд
│   │       ├── command_catalog.py # Runtime JSON и перевод описаний
│   │       ├── command_extraction.py # Babel extractor
│   │       ├── navigation.py      # Общая клавиатура и приветствие
│   │       ├── callbacks.py       # Settings callback payload
│   │       ├── routers/           # Start/settings orchestration
│   │       ├── keyboards/         # Общая клавиатура Settings
│   │       ├── filters/           # TranslatedText
│   │       ├── middlewares/       # Лимиты, порядок, локаль, аудит, private guard
│   │       ├── html.py            # Telegram HTML escaping
│   │       ├── delivery.py        # Отправка и пакетное удаление
│   │       ├── audit/             # Service, repository, ORM
│   │       ├── deletions/         # Service, repository, ORM и тонкая cleanup job
│   │       └── provider.py        # Четыре REQUEST-зависимости платформы
│   ├── services/                  # Общие timezone/text helpers
│   ├── db/
│   │   └── models/                # Общий registry ORM-моделей функциональных модулей
│   ├── jobs/                      # Регистрация фоновых заданий
│   ├── modules/
│   │   ├── advertisements/
│   │   │   ├── presentation/      # Три router, formatter, callbacks, клавиатуры, Telegram adapter
│   │   │   ├── application/       # Объявления, модерация, контакты, ExpireAdvertisements
│   │   │   ├── domain/            # Статусы объявления и типы медиа
│   │   │   ├── infrastructure/    # Четыре ORM-модели и два репозитория
│   │   │   ├── jobs.py            # Тонкий scheduler entry point
│   │   │   └── provider.py        # Зависимости объявлений в Scope.REQUEST
│   │   ├── student_questions/     # Плоский модуль: router, keyboards, callbacks, service, repository, orm, provider
│   │   ├── versions/              # Плоский модуль: history, formatter, keyboards, callbacks, router
│   │   ├── donations/             # Каталог QR, APP Telegram-кеш, REQUEST service, router, клавиатуры, callback, provider
│   │   ├── broadcast/             # SendBroadcast, Telegram sender, router, клавиатура, callbacks, REQUEST-provider
│   │   ├── food_menu/             # application, presentation, infrastructure, тонкие jobs, APP/REQUEST-provider
│   │   ├── schedule/              # Каталог, подписки, расписание, поиск, sync; application/presentation/infrastructure
│   │   ├── notifications/         # Настройки, запросы получателей, ORM, Telegram и REQUEST-provider
│   │   ├── users/                 # Профиль, локаль, контакты: application/infrastructure/presentation
│   │   ├── obis/                  # Credentials, HTTP/parser/crypto, snapshots/polling, presentation, provider/jobs
│   │   ├── eders/                 # Snapshot/tracking/polling, HTTP/parser/persistence, Telegram, provider/jobs
│   │   ├── study_week/            # Плоский: GetStudyWeek/DTO, formatter, router, REQUEST-provider
│   │   └── feedback/
│   │       ├── router.py          # FSM, обращения и ответы admin-чата
│   │       ├── keyboards.py       # Кнопка отмены
│   │       ├── callbacks.py       # Неизменный payload feedback:cancel
│   │       ├── service.py         # Application-сценарии и dataclass результатов
│   │       ├── repository.py      # Доступ к обращениям
│   │       ├── orm.py             # Таблица feedback_messages
│   │       └── provider.py        # Зависимости Feedback в Scope.REQUEST
│   ├── localization/              # Локали, gettext-контекст, извлечение ключей
│   └── locales/                   # en, ru, ky, tr, zh: каталоги переводов
├── alembic/
│   ├── env.py                     # Настройка миграций и metadata моделей
│   └── versions/                  # Версии схемы и начальное заполнение справочников
├── tests/                         # Тесты логики, обработчиков, БД и интеграций
│   └── fixtures/eders/            # Обезличенные HTML-примеры
├── postman/
│   ├── mocks/eders/               # Локальный мок внешней системы
│   └── simulations/eders.sim.yaml # Конфигурация HTTP-симуляции
├── docs/
│   ├── ARCHITECTURE.md            # Этот документ
│   ├── MIGRATION.md               # Карта перехода, исходные дефекты и результаты этапов
│   ├── commands/                  # JSON-списки команд и ключей их описаний
│   ├── requisites/                # Изображения банковских QR-кодов
│   ├── versions/                  # История версий для команды /versions
│   └── eders-tracking.md          # Подробности отслеживания eders
├── features/                      # Спецификации, исследования и планы
├── docker/Dockerfile              # Многоэтапная сборка приложения
├── docker-compose.yml             # Приложение и PostgreSQL для развёртывания
├── docker-compose.dev.yml         # Локальный PostgreSQL с портом 5432
├── .github/workflows/ci-cd.yml     # Проверки, сборка и деплой
├── .pre-commit-config.yaml         # Локальные проверки перед коммитом
├── pyproject.toml                 # Пакет, зависимости, настройки инструментов
├── uv.lock                        # Зафиксированные зависимости
├── alembic.ini                    # Конфигурация Alembic
├── babel.cfg                      # Правила извлечения переводимых строк
├── README.md                      # Обзор возможностей и запуск
├── AGENTS.md                      # Рабочие правила проекта
└── CLAUDE.md                      # Архитектурные заметки и история решений
```

Внутри `services/` находятся не только классы сервисов. Там же лежат `*_formatter.py`, модели результатов,
сериализация снимков eders, нормализация текста, работа со временем и HTML. Часть этих модулей зависит от типов
aiogram; слой сервисов целиком не изолирован от Telegram.

## 4. Слои и границы ответственности

### Telegram-слой

[platform/telegram/dispatcher.py](../src/manashelper/platform/telegram/dispatcher.py) создаёт `Dispatcher`, подключает middleware и
регистрирует маршрутизаторы. Обработчики находятся в `bot/routers/`, `modules/feedback/router.py`
и presentation перенесённых модулей, включая `modules/student_questions/router.py`. Они выбирают сценарий по команде, тексту кнопки,
callback-данным или состоянию FSM. Сервисы передаются через `FromDishka[...]`.

Обработчики управляют диалогом и Telegram-операциями: отправляют и редактируют сообщения, отвечают на нажатия,
публикуют объявления, переключают состояния форм. `bot/keyboards/` строит клавиатуры, а
`bot/callback_data.py` задаёт типизированные payload для inline-кнопок.

Порядок маршрутизаторов значим: aiogram использует первый подходящий обработчик. Сейчас сначала подключены
`student_questions` и `advertisement_contact`, затем общий `start`. Это позволяет обработать
`/start student_questions` и `/start ad_<id>` до обычного приветствия. Остальные маршрутизаторы обслуживают
локаль, расписание, поиск занятий, столовую, OBIS, eders, настройки, пожертвования, телефоны, версии,
объявления, модерацию, рассылку и обратную связь.

### Сервисы

`services/` и application-компоненты перенесённых модулей содержат бизнес-правила:
подписки на курсы, сравнение снимков, настройки уведомлений,
проверку владельца объявления, сохранение учётных данных и подготовку результатов для интерфейса.
Сервисы получают конкретные зависимости через конструктор. Они могут вызывать другие сервисы:
например, `GetStudyWeek` объединяет `EdersService` и `ScheduleService`.

Результаты для обработчиков преимущественно представлены обычными dataclass: `CourseSummary`,
`DailyMenuModel`, `ScheduleLessonModel`, `AdvertisementSummary`, `EdersSnapshot` и другие.
ORM-объекты используются внутри сервисов и репозиториев. Форматирование вынесено в отдельные функции.

### Репозитории и база данных

Каждый репозиторий получает `AsyncSession` и выполняет запросы к своей области данных. Например,
`LessonRepository` читает сохранённое расписание, а `EdersRepository` хранит снимки и события уведомлений.
Общая декларативная база и фабрики подключения находятся в [core/database.py](../src/manashelper/core/database.py).

Жизненный цикл сессии принадлежит области `REQUEST` Dishka. Фабрика использует `expire_on_commit=False`.
Отдельного класса Unit of Work нет. При успешном выходе провайдер выполняет `commit`; исключение или отмена,
вышедшие из тела scope, вызывают `rollback`. Ошибка/отмена commit также вызывает rollback с последующим
пробросом ошибки; session закрывается во всех этих случаях.

Dishka передаёт исключение тела через asend() как значение yield, а не через athrow(). CoreProvider явно
проверяет это значение. Ошибка, пойманная внутри scope, не меняет успешный статус его завершения.
Прежний дефект commit после ошибки исправлен отдельно от feature-переносов. Проверки в
`tests/test_core_transactions.py` охватывают PostgreSQL savepoints, отмену задачи, aiogram error handler,
ошибки commit/rollback и возможность следующего запроса после сбоя. История — в `docs/MIGRATION.md`.

### Внешние источники

`scraping/` разделяет получение страниц и их разбор. Клиенты выполняют HTTP-запросы, парсеры преобразуют HTML
в структурированные данные. Сервисы решают, как проверить, сохранить и показать эти данные.
Для eders общие модели находятся в `services/eders_models.py`, поэтому парсер тоже зависит от этого модуля.

### Фоновые задания

`jobs/` связывает планировщик, обновление данных и отправку сообщений. Задания открывают собственные области
`REQUEST`, обычно отдельно для курса или пользователя. Ошибки логируются и по возможности изолируются,
чтобы сбой одного элемента не останавливал весь обход.

Задания обращаются к application-сервисам и публичным query, без прямого доступа к репозиториям.
Eders и OBIS jobs делегируют per-user сценарии PollEdersUser и PollObisUser.
`platform/telegram/delivery.py` содержит общую отправку и пакетное удаление; локаль читается через Users LocaleService.

Очистка объявлений уже следует целевой границе: `modules/advertisements/jobs.py` открывает request scope,
передаёт адаптер удаления публикаций и вызывает `ExpireAdvertisements.execute()`. Application-сценарий
работает со своим репозиторием и протоколом `PublicationRemover`, без aiogram и Telegram HTML.
Адаптер в `presentation/publications.py` сохраняет пакетное удаление до 100 ID и best-effort обработку
ошибок Telegram через общий `platform/telegram/delivery.py::delete_messages`.

### Telegram Platform: аудит и удаление сообщений

`platform/telegram/` владеет общими Telegram adapters и presentation. Audit service/repository/ORM находятся
в плоском `audit/`, а очередь удаления — в `deletions/`. Их REQUEST-зависимости собирает TelegramPlatformProvider.
Middleware пишет аудит до вызова выбранного handler, после private-chat guard. Сохраняются text/caption,
callback data, пропуск событий без chat/user и маскирование `[masked]` по флагу обработчика.

Cleanup job открывает прежний request scope и передаёт UTC cutoff и async delivery в MessageDeletionService.delete_due.
Сервис выбирает группы по chat, вызывает доставку и удаляет обработанные строки после завершения всех групп.
В delivery adapter стандартный itertools.batched делит ID по 100; TelegramAPIError логируется и пропускает
batch, а неожиданная ошибка останавливает sweep без удаления строк. Этот adapter также используется объявлениями.
Расписание — прежние пять минут, retry отсутствует. Исключение, вышедшее из request scope, откатывает изменения БД.

`platform/i18n/catalog.py` сохраняет единый gettext adapter, context и English fallback. Чистые Locale/weekday
labels остаются в localization/. Файлы команд и переводов остались в docs/commands и locales; изменён только
расчёт относительных путей после перемещения. Checkout/Docker-like layout и чтение команд без перезапуска покрыты тестами.

## 5. Внедрение зависимостей и запуск

[CoreProvider](../src/manashelper/core/provider.py) владеет Settings, engine, фабрикой сессий и HTTP-клиентом
в APP scope и сессией в REQUEST scope. Settings кешируется прежним get_settings; HTTP timeout — 15 секунд,
session factory сохраняет expire_on_commit=False. Engine и HTTP-клиент закрываются при завершении APP;
request-сессия выполняет commit перед закрытием при успешном завершении; ошибка/отмена scope вызывает rollback.
CoreProvider работает самостоятельно, без feature-провайдеров. Последний legacy `di.py` удалён;
[StudyWeekProvider](../src/manashelper/modules/study_week/provider.py) владеет GetStudyWeek в REQUEST.
Отдельный [FeedbackProvider](../src/manashelper/modules/feedback/provider.py) регистрирует репозиторий и
сервис обращений. [AdvertisementsProvider](../src/manashelper/modules/advertisements/provider.py)
регистрирует два репозитория, три сервиса и сценарий очистки. Их зависимости имеют `Scope.REQUEST`;
`PublicationRemover` для очистки передаётся из контекста её entry point. `StudentQuestionsProvider` регистрирует
репозиторий и сервис опроса в том же REQUEST scope. `UsersProvider` предоставляет UsersQuery,
LocaleService, UserContactService и два репозитория пользователей в `REQUEST`.
`DonationsProvider` регистрирует QR-адаптер в `APP` и application-сервис в `REQUEST`.
`BroadcastProvider` предоставляет `SendBroadcast` в `REQUEST`; адаптер доставки создаёт обработчик с текущим Bot.
`FoodMenuProvider` сохраняет клиент/parser в `APP`, репозитории и сценарии меню — в `REQUEST`.
`ScheduleProvider` сохраняет TimetableClient в `APP`, каталог, подписки и сценарии — в `REQUEST`.
`NotificationsProvider` предоставляет NotificationRecipientsQuery, NotificationSettingsService и repository в `REQUEST`.
`TelegramPlatformProvider` регистрирует audit/deletion services и repositories в REQUEST.
`ObisProvider` сохраняет ObisClient/CryptoService в APP, семь repository/application зависимостей — в REQUEST.
Четырнадцать провайдеров собираются в `main.py`; состояние LRU-кеша сохраняется между request scopes.

| Область | Объекты | Время жизни |
| --- | --- | --- |
| `APP` | `Settings`, engine, фабрика сессий, общий HTTP-клиент, клиенты источников, `FoodMenuParser`, `CryptoService`, `DonationQrService` | Всё время работы приложения |
| `REQUEST` | `AsyncSession`, репозитории, большинство сервисов | Обработка обновления или явно открытая область фонового задания |

Общий `httpx.AsyncClient` имеет таймаут 15 секунд и используется клиентами столовой и расписания.
Объекты `ObisClient` и `EdersClient` живут в `APP`, но создают отдельные короткоживущие HTTP-сессии для
получения персональных данных. Постоянная авторизованная сессия студента между вызовами не хранится.

При запуске `python -m manashelper.main` выполняются следующие действия:

1. Alembic обновляет схему до `head`. Настройки подключения берутся из `Settings`.
2. Настраиваются консольный и файловый логи. Это делается после миграций, поскольку Alembic меняет logging.
3. `asyncio.run(main())` запускает цикл событий и устанавливает обработчик необработанных исключений.
4. Создаются `Bot` с режимом HTML и контейнер Dishka.
5. Создаётся диспетчер. Вызываются `setup_dishka(container, dispatcher)` и явный `inject_router(dispatcher)`.
6. Создаётся и запускается APScheduler.
7. В Telegram регистрируются команды для языков и областей чатов.
8. Начинается `dispatcher.start_polling(...)`.

`AsyncExitStack` организует остановку планировщика, закрытие контейнера и сессии бота. Контейнер также
освобождает engine и общий HTTP-клиент. Миграции вызываются в блоке `__main__`, а не внутри `main()`.

## 6. Обработка обновлений и состояние диалога

Для сообщений и callback-запросов зарегистрированы следующие механизмы:

| Компонент | Назначение |
| --- | --- |
| `RateLimitMiddleware` | Token bucket на чат: ёмкость 10, восстановление 1 токен/с; отклоняет лишние события до ожидания блокировки |
| `PerChatOrderingMiddleware` | `asyncio.Lock` на чат; последовательно выполняет события внутри своего экземпляра middleware |
| Интеграция Dishka | Создаёт область обработки и передаёт контейнер зависимостей |
| `LocaleMiddleware` | Определяет пользователя и локаль, устанавливает gettext-контекст до фильтров и обработчика |
| `PrivateChatOnlyMiddleware` | Проверяет флаг обработчика `private_chat_only` после выбора обработчика |
| `ActionLogMiddleware` | Записывает обработанные сообщения и callback-данные в `action_logs` |

`LocaleMiddleware` подключается после `setup_dishka`, поскольку использует контейнер из middleware data.
Проверка личного чата и аудит — inner middleware: им нужны флаги уже найденного обработчика.
Аудит расположен после проверки доступа, поэтому отклонённые ею события не записываются.

Важная граница: для `message` и `callback_query` создаются отдельные экземпляры лимитера и блокировок.
Следовательно, это не единая блокировка для всех типов обновлений одного чата. Блокировки также не
координируют фоновые задания и другие процессы. Для снимков eders дополнительно применяется блокировка
строки пользователя через `SELECT ... FOR UPDATE` в `EdersRepository`.

`Dispatcher()` использует FSM с хранением в памяти процесса. Формы OBIS, объявления, обратная связь,
опросы и другие многошаговые сценарии используют `FSMContext`. После перезапуска незавершённые диалоги
и временные страницы результатов теряются; завершённые данные в PostgreSQL сохраняются.

## 7. Функциональные области и потоки данных

### Каталог, расписание и поиск занятий

`FacultyService`, `DepartmentService` и `CourseService` показывают иерархию факультетов, отделений и курсов.
Здесь `Course` обозначает курс обучения внутри отделения, а не отдельный учебный предмет. Подписки
пользователей на курсы записываются в `user_courses`.

`TimetableSyncService` получает HTML для курса, разбирает временные слоты и сравнивает их с `lessons` по
паре «день недели, диапазон времени». Изменения сохраняются в `lesson_history`, а job уведомляет подписчиков
с включённой настройкой. Первая загрузка заполняет базу без уведомлений об изменениях.

`ScheduleService` читает расписание выбранных курсов из БД. `LessonSearchService` ищет по сохранённым
занятиям; `normalized_content` и нормализация турецких букв помогают сопоставлению текста.
Форматтеры группируют соседние занятия и выделяют текущий или следующий блок.

Эта область собрана в `modules/schedule/`: application (каталог, tracking, чтение расписания, поиск,
синхронизация), presentation (два router, callbacks, клавиатуры, formatter и sender), infrastructure
(пять ORM-моделей, association `user_courses`, клиент/parser и шесть репозиториев), provider и jobs.
CourseTrackingRepository владеет прежним запросом User с selectinload tracked_courses; User ORM принадлежит
Users, а данные подписок — Schedule. CourseService сохраняет изменения ORM-коллекций и прежние
ошибки. GetStudyWeek зависит от публичных ScheduleService и моделей результатов.

Job сначала читает ID курсов через CourseService в отдельном request scope, затем открывает scope
на каждый курс. SyncCourseTimetable координирует синхронизацию и выбирает получателей через публичный
NotificationRecipientsQuery. TelegramScheduleChangeSender определяет локаль и форматирует сообщение;
TelegramAPIError доставки пропускает получателя, неожиданная ошибка или ошибка локали прерывает текущий
курс. Job логирует ошибку и продолжает следующий курс. Первый sync по-прежнему не создаёт уведомлений
и истории. Повторной отправки нет; интервал job остаётся один час с немедленным первым запуском.

Названия дней недели вынесены без изменения функций в `localization/weekdays.py`, где их используют
Food menu, Schedule и Study week. Все используют существующий `services/time_utils.py::BISHKEK_TZ`;
дублирующая константа Food menu удалена. Между Food menu и Schedule больше нет этих взаимных зависимостей.

### Столовая

`FoodMenuSyncService` получает меню сайта и сохраняет дни и блюда. `DailyMenuService` возвращает доступные
даты, блюда, фотографии, калорийность, просмотры и оценки. Оценка меню имеет диапазон 1–5.
Telegram-слой строит rich messages с кнопками оценки и настроек.

Область собрана в `modules/food_menu/`: application-сервисы, presentation (три router, callbacks,
клавиатуры, formatter, sender), infrastructure (клиент, parser, модели и репозитории), provider и jobs.
`BroadcastFoodMenu` выбирает сегодняшнее меню и получателей по дню/приёму пищи. Его Telegram-адаптер
получает локаль через LocaleService, отправляет rich message и планирует очистку. TelegramAPIError
внутри доставки пропускает одного получателя; неожиданное исключение прерывает обход и логируется job.
Функции scheduler больше не обращаются к репозиториям. Проверка пользователя в настройках идёт через UsersQuery.exists.

Рассылка меню учитывает день недели и отдельные настройки обеда и ужина. Автоудаление сообщений настраивается
на уровне чата, включая группы: 15 минут, 45 минут, 3 часа, сутки или отключение. Значение по умолчанию —
3 часа. `MessageDeletionService` записывает задания в БД, а отдельная job удаляет просроченные сообщения.
Repository создаёт новые настройки дня с lunch_enabled=True и dinner_enabled=True ещё до flush.
Поэтому первое нажатие выключает выбранный обед/ужин или оба при переключении дня; другие предпочтения сохраняются.
Отсутствие строки по-прежнему означает включённые уведомления, enable_all удаляет строки и возвращает эти defaults.

### Users

`modules/users/` владеет User и UserPhoneNumber, двумя репозиториями, application-сервисами локали и
контактов, публичным UsersQuery и presentation выбора языка/телефонов. Общий registry `db/models/`
по-прежнему регистрирует обе модели для Alembic. Репозитории импортируют модели через этот registry:
это сохраняет регистрацию связанных мапперов Schedule даже при отдельном импорте Users.
Все зависимости Users имеют REQUEST scope.
Обновление имени/username сохраняет локаль, credentials и ORM-коллекцию подписок. LocaleService читает
локаль без регистрации пользователя, а resolve обновляет профиль и сохраняет выбранный/определённый язык.
Некорректное сохранённое значение по-прежнему вызывает ValueError; неизвестный язык Telegram даёт русский.

PhoneNumberForm сохраняет прежнее имя состояния, валидацию, порядок номеров по created_at, точный формат
номера и проверку владельца при удалении. Callback payload `locale:*`, `phone_number_action:add` и
`phone_number_delete:*` не менялись. Общая навигация выделена в `platform/telegram/navigation.py`, поэтому feature
presentation больше не импортирует start router ради клавиатуры или приветствия. OBIS polling читает
локаль через LocaleService; дублирующий helper в `platform/telegram/delivery.py` удалён.

### OBIS

`modules/obis/` содержит application facade, credentials, сравнение снимков и polling use case;
infrastructure — HTTP/parser/crypto, credential repository и две пары snapshot ORM/repository;
presentation — router, callbacks, клавиатуры, formatter и sender. Provider сохраняет APP/REQUEST scopes.
Форма подключения собирает номер студента и пароль. `ObisService.save_credentials()` делегирует
ObisCredentialsService: сначала вход через ObisClient, затем шифрование CryptoService и сохранение в User.
При запросе оценок или посещаемости пароль расшифровывается, создаётся новая HTTP-сессия и выполняется вход.
`infrastructure/parser.py` разбирает страницы, а facade возвращает прежние dataclass-модели результатов.
ObisCredentialsRepository читает тот же User через AsyncSession.get, сохраняя identity map и schema.
Публичный ObisCredentialsService.get_credentials возвращает frozen dataclass с отключённым repr секретных полей,
student number, plain password и непрозрачным credential marker. EdersService больше не читает ORM/ciphertext
и не расшифровывает пароль сам; marker остаётся SHA-256 от сохранённого ciphertext. Ошибки определены в errors.py.
Общие функции infrastructure/client.py::login/new_http_client публичны и используются Eders с прежней cookie jar.
Порядок присваиваний при сохранении сохранён: student_number меняется до encryption; ошибка шифрования
оставляет это присваивание выполненным. Это отдельный characterized defect, не исправленный переносом.

`ObisNotificationService` сравнивает результаты с сохранёнными оценками и посещаемостью. Первая запись
посещаемости silent; первая непустая оценка уже вызывает событие. Это зафиксированное отличие от старого
описания, сохранённое без bug fix. Общие переключатели расписания, оценок и пропусков находятся
в `modules/notifications/orm.py::NotificationSettings`; отсутствие строки означает, что все три включены.
OBIS job выбирает ID через публичный `NotificationRecipientsQuery`, сохраняя отдельные наборы оценок/пропусков
и их объединение. Отдельный request scope на каждого пользователя сохраняется. PollObisUser подавляет
прежние ожидаемые auth/parse errors; TelegramObisNotificationSender форматирует в локали получателя и
пропускает TelegramAPIError. Неожиданная ошибка останавливает текущего пользователя, логируется job и
не мешает следующему. Grade отправляется раньше attendance, расписание остаётся hourly, retry отсутствует.

### Настройки уведомлений

Плоский `modules/notifications/` владеет `settings.py`, `queries.py`, `repository.py`, `orm.py`,
`callbacks.py`, `keyboards.py`, `router.py` и `provider.py`. Сервис возвращает immutable dataclass,
проверяет пользователя через `UsersQuery.exists` и сохраняет прежние SQL и ошибки неизвестного пользователя.
Router обслуживает открытие, возврат и три переключателя; общий Settings router сохраняет навигацию.
Callback payload `notification_setting:*`, `settings:open_notifications` и `settings:back_to_notifications`
не изменились. Кнопки Food menu/Eders ведут в прежние feature-specific настройки.

Repository инициализирует три флага новой строки значением True до первого flush. Первое открытие показывает
включённые настройки, а первый toggle сразу выключает выбранный флаг. Сохранённые строки не переинициализируются.
Выбор адресатов без строки настроек по-прежнему включает все уведомления. ORM/server defaults также остаются True;
дополнительный flush и миграция схемы для этого исправления не требуются.

### Eders и учебная неделя

Eders собран в `modules/eders/`: application facade/filter/tracking/polling и immutable snapshot-модели,
infrastructure HTTP/parser/URL validation, persistence serialization/repository/ORM, Telegram presentation и jobs/provider.
EdersProvider сохраняет APP client и REQUEST repository/services/PollEdersUser.
Tracking проверяет наличие пользователя через публичный UsersQuery.exists. Repository сохраняет SQL выбор
аккаунтов с обоими credential columns и блокировку User перед state lookup/flush, включая первое наблюдение.

`EdersService` получает учётные данные через ObisCredentialsService. `EdersClient` выполняет вход OBIS и переход
в eders через SSO с одной cookie jar. Затем получает список курсов через Moodle AJAX с пагинацией,
читает страницы курсов и подробности заданий и тестов. При истечении сессии весь снимок повторяется один раз;
частичный результат не возвращается как успешный снимок.

Парсер поддерживает задания, тесты, файлы, папки, ссылки, форумы и текстовые блоки. `EdersTrackingService`
сравнивает персональные снимки, планирует события и сохраняет их в очередь PostgreSQL. Снимки сериализуются
модулем `serialization.py`. Состояние включает маркер учётных данных и настройки отслеживания.

PollEdersUser выполняет refresh, чтение локали, выбор pending events и ack. TelegramEdersNotificationSender
сначала форматирует все сообщения в локали получателя, группирует материалы, затем отправляет последовательно.
Async iterator возвращает событие после успешного сообщения, поэтому application отмечает каждый event сразу,
до следующей отправки. TelegramAPIError пропускает сообщение без ack; unexpected error прекращает текущего
пользователя, но job продолжает следующий request scope. Exactly-once между Telegram и БД по-прежнему нет.
Порядок событий, JSON/legacy defaults, hashes, baseline/account/schema suppression и monotonic snapshots сохранены.
Исключения Eders вынесены в публичный errors.py; Study week не импортирует HTTP/parser implementation.

Плоский `modules/study_week/` содержит application.py, formatter.py, router.py и provider.py. GetStudyWeek.execute
сначала получает снимок Eders, затем расписание; только NoTrackedCoursesError превращается в пустой timetable.
Дата начала вычисляется после обоих чтений по текущему времени Bishkek, а не по fetched_at снимка.
Formatter покрывает семь локальных календарных дней, сохраняет порядок событий, экранирование/ограничение
динамических строк и chunks по полным HTML-строкам. Все прежние eders.* msgids и private guard сохранены.
Router `/week` зарегистрирован сразу после Eders, на прежнем месте в порядке command handlers.
Зависимость направлена Study week→Eders/Schedule; Eders больше не импортирует orchestration feature.

Доступные сценарии:

- `/eders` — задания и тесты с фильтрами по срокам и статусам;
- `/materials` и `/materials текст` — каталог и текстовый поиск по материалам;
- `/eders_settings` — напоминания за 24 и 2 часа, открытия, переносы сроков и изменения материалов;
- `/week` — семь дней расписания, сроки, открытия и впервые обнаруженные материалы через `GetStudyWeek`.

Первый снимок аккаунта, появление нового курса и обновление старого формата снимка не вызывают рассылку
истории материалов. Будущие напоминания при этом создаются. Неопределённые и конфликтующие даты показываются
явно и не используются для напоминаний. Содержимое файлов, изменения внутри папок и новые сообщения форумов
не отслеживаются. Подробности реализации: [eders-tracking.md](eders-tracking.md).

### Объявления и контакты

`AdvertisementService` создаёт объявления со статусом `pending`, проверяет владельца и ограничивает
публикации пятью объявлениями в час. Форма поддерживает медиа. `AdvertisementModerationService` переводит
объявление в `published` или `rejected`; Telegram-операции выполняют обработчики.
Все эти компоненты принадлежат `modules/advertisements/`. Application возвращает dataclass-результаты,
presentation использует enum из `domain/enums.py`, не импортируя ORM-модели.

Модерация разрешена в чате `Settings.moderation_chat_id`, без пользовательских ролей в БД. Одобренные
объявления публикуются в заданный канал. Контакты открываются через `/start ad_<id>`:
`AdvertisementContactService` проверяет опубликованный статус, регистрирует просмотр и получает контакты
владельца через `UserContactService`. Номера телефонов сохраняются отдельно от Telegram username.

Идентификаторы сообщений канала хранятся в `advertisement_channel_messages`, чтобы удалить публикации
при удалении объявления владельцем или истечении срока. Меню барахолки доступно из основной клавиатуры
и через `/start market`.

При истечении срока application-сценарий сначала удаляет публикации через адаптер, затем строку объявления.
Ошибки Telegram при удалении остаются best effort. Существующее поведение модерации также сохранено:
статус `published` устанавливается до отправки в канал; при ошибке публикации автоматической компенсации
нет. Это отдельно зафиксировано тестом, а не исправлено скрытно в ходе переноса.

### Остальные сценарии

| Возможность | Реализация |
| --- | --- |
| Обратная связь | `modules/feedback/`: `FeedbackService` сохраняет обращение и связь с сообщением в admin-чате; администратор отвечает штатным reply Telegram |
| `/broadcast` | `modules/broadcast`: SendBroadcast получает все ID через UsersQuery, последовательно вызывает sender и возвращает BroadcastResult; доступ проверяет router по `admin_chat_id` |
| Опрос студентов | `modules/student_questions/`: `/start student_questions`, FSM-форма и `StudentQuestionsService`; ответы и согласие на beta сохраняются в БД, повторная отправка требует выбора перезаписи |
| `/donate` | `modules/donations/`: каталог QR из `docs/requisites/`, application-счётчик через UsersQuery и APP-адаптер с LRU до 32 Telegram file ID |
| `/versions` | `modules/versions/`: чтение Markdown-файлов из `docs/versions/` при каждом вызове; без таблицы версий и отдельного provider |
| Язык и настройки | `LocaleService`, сервисы общих уведомлений, рассылки меню и очистки сообщений |

## 8. Постоянные данные

ORM-модели находятся в [db/models/](../src/manashelper/db/models/), `modules/feedback/orm.py`,
`modules/student_questions/orm.py` и `modules/advertisements/infrastructure/`. Общий `db/models/__init__.py`
импортирует и повторно экспортирует модели перенесённых модулей, поэтому Alembic
продолжает видеть всю metadata. Основные таблицы сгруппированы ниже.

| Область | Таблицы | Содержимое и связи |
| --- | --- | --- |
| Пользователи | `users`, `user_phone_numbers` | Telegram ID, имя, username, локаль, номер студента, зашифрованный пароль, контактные телефоны |
| Каталог и подписки | `faculties`, `departments`, `courses`, `user_courses` | Факультет содержит отделения, отделение — курсы; пользователь может отслеживать несколько курсов |
| Расписание | `lessons`, `lesson_history` | Текущие слоты курса и история изменений; текущий слот уникален по курсу, дню и времени |
| Меню | `daily_menus`, `dishes`, `daily_menu_dishes`, `daily_menu_ratings` | Меню дня, блюда, связь многие-ко-многим и пользовательские оценки |
| Настройки | `notification_settings`, `food_menu_notification_settings`, `food_menu_cleanup_settings` | Общие переключатели, рассылка по дням и приёмам пищи, автоудаление по chat ID |
| История OBIS | `user_exam_grades`, `user_lesson_attendance` | Последние известные значения для обнаружения изменений |
| Eders | `eders_states`, `eders_notifications` | Снимок и настройки пользователя; события с ключами, временем отправки, сроком исполнения и признаком отмены |
| Объявления | `advertisements`, `advertisement_media`, `advertisement_channel_messages`, `advertisement_contact_views` | Карточки, медиа, сообщения канала и открытия контактов |
| Обратная связь | `feedback_messages` | Обращения и идентификатор соответствующего сообщения администратора |
| Опрос | `student_questions_responses` | Одна текущая запись ответов на пользователя |
| Отложенное удаление | `scheduled_message_deletions` | Сообщения Telegram, которые нужно удалить в заданное время |
| Аудит | `action_logs` | Обработанные сообщения и callback-запросы |

Изменения схемы оформляются миграциями в `alembic/versions/`; `alembic/env.py` использует `Base.metadata`
и настройки приложения. В миграциях также есть начальное заполнение факультетов, отделений и курсов.
Пересоздание таблиц на каждом запуске не выполняется.

## 9. Планировщик и доставка уведомлений

Расписание задано в [jobs/scheduler.py](../src/manashelper/jobs/scheduler.py). Часовой пояс планировщика —
`Asia/Bishkek`. Интервальные задания получают `next_run_time=now` и впервые запускаются сразу после старта.

| Задание | Периодичность | Назначение |
| --- | --- | --- |
| `sync_daily_menus_job` | Каждые 10 минут | Обновление меню |
| `broadcast_lunch_menu_job` | Ежедневно в 11:00 | Рассылка меню обеда |
| `broadcast_dinner_menu_job` | Ежедневно в 17:00 | Рассылка меню ужина |
| `poll_obis_notifications_job` | Каждый час | Изменения оценок и посещаемости |
| `poll_eders_job` | По умолчанию каждые 30 минут | Снимки eders и доставка накопленных событий |
| `sync_timetable_job` | Каждый час | Обновление расписания всех курсов и уведомления подписчиков |
| `cleanup_scheduled_message_deletions_job` | Каждые 5 минут | Пакетное удаление сообщений, срок которых наступил |
| `cleanup_expired_advertisements_job` | Каждый час | Удаление истёкших объявлений и публикаций |

Для eders можно задать интервал от 15 до 60 минут. Если значение `Settings.eders_poll_minutes` равно `None`,
задание не регистрируется. Оно использует `max_instances=1` и `coalesce=True`, чтобы не запускать несколько
экземпляров одного задания и объединять пропущенные срабатывания в пределах этого планировщика.

Гарантии доставки различаются:

- **Eders:** событие сохраняется в БД и отмечается отправленным после успешного вызова Telegram.
  Ошибка отправки оставляет его для следующей попытки. Сбой между отправкой и commit может вызвать повтор.
- **Расписание и OBIS:** состояние сравнивается и сообщения отправляются в ходе job; отдельной постоянной
  очереди повторной доставки для них нет. Ошибка Telegram логируется, но состояние может быть сохранено.
- **Удаление сообщений:** задания удаляются из БД после обработки даже при ошибке Telegram. Бесконечного
  повторения попыток удалить уже отсутствующее или недоступное сообщение нет; размер пакета — до 100 ID.

Планировщик встроен в процесс и не использует постоянное хранилище расписания APScheduler. Сохраняемые события
eders и задания удаления — отдельные прикладные таблицы, которые переживают перезапуск приложения.

## 10. Интеграции и безопасность данных

| Источник | Адрес в коде | Способ работы |
| --- | --- | --- |
| Расписание | `http://timetable.manas.edu.kg/department-printer/{course_id}` | HTML по идентификатору курса |
| Столовая | `https://beslenme.manas.edu.kg/menu` | HTML меню |
| OBIS | `https://obistest.manas.edu.kg` | Вход с CSRF, чтение `/vs-ders/taken-grades` и `/vs-ders/taken-lessons` |
| Eders | `https://eders.manas.edu.kg` | SSO из OBIS, чтение Moodle AJAX и HTML |
| Telegram | Через aiogram | Получение обновлений, ответы, каналы, рассылки и удаление сообщений |

Это адреса, заданные в исходниках, а не результат проверки доступности внешних сайтов.

`CryptoService` шифрует пароль OBIS алгоритмом AES-GCM со случайным nonce длиной 12 байт. Результат
с nonce хранится в base64, ключ берётся из `OBIS_ENCRYPTION_KEY`. Пароль нужен для повторного входа,
поэтому используется обратимое шифрование. Потеря или замена ключа без переноса данных нарушает
расшифровку сохранённых паролей.

Обработчик ввода пароля помечен `mask_logged_message`: аудит сохраняет `[masked]`. Обработчик также пытается
удалить исходное сообщение с паролем из Telegram. Остальной аудит может содержать пользовательский текст;
`action_logs` и технический файловый лог — разные механизмы.

Доступ к личным сценариям ограничивается флагами обработчиков, к модерации и административным действиям —
настроенными ID чатов. Проверка владельца объявления и телефонного номера выполняется сервисами.
Динамический текст для HTML-сообщений экранируется через `platform/telegram/html.py::escape_html`.

Интеграция eders предназначена для чтения. Она не отправляет формы сдачи работ, запуска тестов или изменения
профиля. POST к Moodle используется для получения списка курсов. URL для публичных карточек обрабатываются
через `urls.py`; ключи сессии не должны попадать в сохранённые публичные ссылки и сообщения.
`modules/eders/infrastructure/client.py::_request` проверяет разрешённый адрес перед каждым HTTP-запросом, включая redirect-цели.
SSO и чтение имеют разные списки разрешённых адресов; небезопасные действия блокируются до обращения к ним.

## 11. Локализация и команды

Поддерживаются пять языков: русский (`ru`), кыргызский (`ky`), английский (`en`), турецкий (`tr`) и
упрощённый китайский (`zh`). Сохранённая локаль пользователя имеет приоритет; иначе используется язык
Telegram с запасным русским. Для отсутствующих переводов `CatalogI18n` подключает английский каталог.
Это два разных механизма: выбор языка и подстановка отсутствующего перевода.

Строки хранятся в `locales/<locale>/LC_MESSAGES/` под стабильными ключами. `.po` находятся в Git,
скомпилированные `.mo` создаются при подготовке окружения и сборке Docker. Фильтр `TranslatedText`
позволяет обработчикам распознавать подписи reply-кнопок с учётом перевода.

При отправке другому пользователю сообщение форматируется в контексте его локали. Фоновые задания
дополнительно устанавливают `i18n.context()`. Общие admin/moderation-чаты и канал объявлений используют
`DEFAULT_LOCALE`, то есть русский.

Списки команд находятся в `docs/commands/private.json`, `group.json` и `admin.json`.
`platform/telegram/command_catalog.py` читает JSON и переводит описания, а `platform/telegram/commands.py` регистрирует команды
по языкам и областям чатов. `/broadcast` регистрируется только для `admin_chat_id`; это дополняет
проверку доступа в обработчике. `babel.cfg` включает извлечение ключей описаний из JSON.

## 12. Конфигурация, развёртывание и логи

[core/config.py](../src/manashelper/core/config.py) читает `.env` и окружение. `get_settings()` кешируется через `lru_cache`.

| Переменные | Назначение |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Токен бота |
| `DATASOURCE_HOST` | Хост PostgreSQL; по умолчанию `db`, для локального процесса обычно `localhost` |
| `DATASOURCE_NAME`, `DATASOURCE_USERNAME`, `DATASOURCE_PASSWORD` | База и учётные данные; порт подключения в коде — 5432 |
| `OBIS_ENCRYPTION_KEY` | Ключ AES-GCM в base64 |
| `ADVERTISEMENT_CHANNEL_ID`, `ADVERTISEMENT_CHANNEL_LINK` | Канал объявлений |
| `MODERATION_CHAT_ID`, `ADMIN_CHAT_ID` | Чаты модерации и административных действий |
| `EDERS_POLL_MINUTES` | Необязательный интервал eders, по умолчанию 30 минут |
| `VERSION` | Тег Docker-образа в production Compose; не поле `Settings` |

`docker-compose.dev.yml` поднимает только PostgreSQL и публикует порт 5432 на машине разработчика.
`docker-compose.yml` поднимает PostgreSQL и готовый образ `usbtypec1/manashelper:${VERSION}`. База хранится
в томе `postgres_data`, технические логи приложения — в `app_logs`.

Dockerfile устанавливает зависимости через `uv sync --frozen --no-dev`, копирует исходники, миграции и
runtime-файлы из `docs/commands`, `docs/requisites`, `docs/versions`, затем компилирует переводы.
Финальный образ работает от `appuser` и запускает `python -m manashelper.main`.

Текущий [.github/workflows/ci-cd.yml](../.github/workflows/ci-cd.yml) запускает проверки на pull request
в `main` и push тега `v*`. После успешных проверок тега собираются образы с номером версии и `latest`,
публикуются в Docker Hub, затем по SSH обновляется Docker Compose на сервере. Обычный push ветки
в текущих триггерах workflow не указан.

`core/logging.py` пишет события уровня INFO и выше в консоль и `logs/manashelper.log`.
Ротация ограничена примерно 50 МиБ на файл с двумя резервными копиями, то есть примерно 150 МиБ суммарно.
Есть обработчики ошибок обновлений aiogram, исключений цикла событий и фатального завершения приложения.

## 13. Проверки и рабочий цикл

В `tests/` проверяются сервисы и репозитории, обработчики и FSM, middleware, форматирование и экранирование,
локализация, синхронизация и уведомления. Для БД используется настоящий PostgreSQL. Фикстура из
`tests/conftest.py` создаёт внешнюю транзакцию и savepoint; изменения откатываются после теста даже при
внутреннем `commit` тестируемого кода.

Парсеры и сценарии eders проверяются на HTML-примерах. Дополнительный корпусный тест читает локальную
выгрузку из `EDERS_HTML_DIR` или `r` и пропускается, если файлов нет. HTTP-тест
`tests/test_eders_http_flow.py` использует локальную Postman Simulation и запускается при заданном
`EDERS_SIMULATION_PORT`; без него тесты этого модуля пропускаются. Симуляция не входит в production Compose.

Базовые команды из корня проекта:

```sh
uv sync
docker compose -f docker-compose.dev.yml up -d db
uv run pybabel compile -d src/manashelper/locales
uv run alembic upgrade head
uv run python -m manashelper.main
```

Перед миграциями и запуском нужны обязательные настройки из таблицы выше. Для локального процесса следует
задать `DATASOURCE_HOST=localhost`. Проверки БД выполняются только против базы разработки.

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy src/manashelper
uv run pytest
```

Ruff использует длину строки 120 и целевую версию Python 3.13; mypy проверяет `src/manashelper` в строгом
режиме. Pre-commit содержит Ruff lint, форматирование и mypy. CI дополнительно компилирует переводы,
применяет миграции и выполняет тесты с PostgreSQL.

## 14. Границы текущей реализации

- Развёртывание рассчитано на один экземпляр приложения. FSM, middleware-блокировки, лимиты и кеш QR-кодов
  находятся в памяти процесса; распределённой координации планировщиков нет.
- Telegram-операции и commit PostgreSQL не составляют общую атомарную транзакцию. Возможны частично
  выполненные внешние действия; очереди и правила повторов различаются по сценариям.
- Rollback БД не отменяет уже выполненные внешние действия, например отправку сообщения Telegram.
  Ошибки, обработанные внутри scope, сами по себе не отменяют его транзакцию.
- Сроки eders зависят от подтверждённого часового пояса источника. Неизвестное время не заменяется
  предположением ради напоминания.
- Формат HTML внешних сайтов является частью фактической зависимости: изменение страниц может потребовать
  обновления парсеров и тестовых примеров.
- `features/` содержит историю требований и планы. Например, `RAG_KNOWLEDGE_BASE.md` явно описывает план
  без реализации; наличие опроса студентов не означает наличия RAG или LLM-подсистемы.
- Старые описания могут расходиться с кодом: в текущей реализации пять языков, отсутствуют роли
  пользователей для модерации, а деплой запускается по тегам `v*`.

Код и зависимости feature изменяются внутри `modules/<feature>/`; новый provider
подключается в composition root. Общие timezone/text helpers пока остаются в `services/`.
Общая Telegram-навигация в `platform/telegram/navigation.py`, i18n, `core.config.Settings` и `core.database.Base`
остаются внешними зависимостями перенесённых модулей. `LocaleService` принадлежит Users.
Объявления используют `UserContactService`
через application-поверхность, без доступа к репозиториям Users. Donations и Broadcast используют UsersQuery
из `modules/users/`. Старые Python-пути Feedback, объявлений, опроса, версий, Donations,
Broadcast, Food menu, Schedule, Notifications, Users, OBIS, Eders и Study week удалены;
адаптеров совместимости для них нет, все потребители в проекте используют новые импорты.

Broadcast остаётся небольшим плоским модулем. `service.py` содержит `SendBroadcast`, immutable dataclass
`BroadcastResult` и протокол `BroadcastSender`, обозначающий внешнюю границу доставки. Здесь нет типов
Telegram, gettext, HTML, FSM или прямого доступа к репозиторию пользователей. `sender.py` реализует
Telegram-доставку: локаль каждого получателя, экранирование текста и продолжение после `TelegramAPIError`.
Ошибки получения локали и неожиданные ошибки доставки по-прежнему останавливают рассылку без итогового
сообщения. Router сохраняет авторизацию, preview, очистку FSM до выбора адресатов и русскую статистику.
Отправка последовательная, без retry; фильтры NotificationSettings для административной рассылки не применяются.

Новый маршрутизатор подключается в `platform/telegram/dispatcher.py`, job — в `jobs/scheduler.py`, изменение схемы —
через модели и Alembic. Перенос моделей Feedback, объявлений и опроса сохранил DDL всех 27 таблиц и индексов, поэтому новой
миграции нет. Пользовательские строки добавляются во все пять каталогов; новая публичная команда также
требует записи в соответствующем JSON из `docs/commands/`.
