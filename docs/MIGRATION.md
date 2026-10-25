# Поэтапный переход к функциональным модулям

## Границы работы

Основание: `TASK.md`. Перенос выполняется по одной функциональной области, без изменения бизнес-поведения,
схемы PostgreSQL, callback payload, имён состояний FSM, переводов и форматов сохранённых данных.
Этот документ фиксирует анализ до изменения исходников и результаты завершённых этапов.

Актуальный статус на 25 октября 2026 года: перенесены **Feedback**, **Advertisements**, **Student questions**,
**Versions**, **Donations**, **Broadcast**, **Food menu**, **Schedule**, **Notifications**, **Users**, **OBIS**, **Eders** и **Study week**.
План переноса бизнес-областей выполнен. OBIS владеет credentials и предоставляет их Eders через application-границу;
Study week объединяет application-результаты Eders и Schedule. После отдельной уборки общий timezone helper
находится в core/time.py, text normalization — в Schedule; пустые legacy пакеты удалены, тесты сгруппированы по владельцам.
Общая инфраструктура выделена в Core, Telegram Platform, аудит и очередь удаления — в platform/.
Пакет db удалён полностью. ORM-классы импортируются у владельцев, bootstrap.load_models() явно загружает
модель и конфигурирует relationships для runtime, Alembic и тестов, без общего реэкспорта классов.
Отдельно исправлены REQUEST rollback при ошибке/отмене и начальные значения настроек Notifications/Food menu:
новые строки сразу содержат True, первый toggle выключает выбранные уведомления.
Общий gate с локальной OBIS/Eders simulation зелёный: **638 passed, 5 skipped**, Ruff, mypy и Alembic проходят.
Первоначальные красные результаты ниже оставлены как история baseline и не описывают текущую проверку.

## Исходное состояние — 24 октября 2026 года

Проанализированы AST и импорты всех 174 Python-модулей приложения, суммарно 10 673 строки.
Проверены composition root, ORM registry, миграции, обработчики, сервисы, задания и существующие тесты.
PyCharm Index MCP не предоставлен текущей сессии; анализ выполняется по файлам и локальному AST.

Проверки до рефакторинга:

- PostgreSQL: локальный контейнер `manashelper-db-1`, PostgreSQL 17, порт 5432; миграции до `head` применены.
- Каталоги всех пяти языков скомпилированы.
- pytest: **271 passed, 5 skipped, 1 failed**.
- Исходный сбой: `tests/test_eders.py::test_redirect_allowlist_blocks_actions_before_request_and_hides_secrets`.
  Клиент вместо `EdersUnsafeUrlError` до второго запроса выбрасывает
  `EdersFetchError: Too many authentication redirects` после обхода redirect-цепочки.
  Сбой уже зафиксирован существующим тестом и не исправляется архитектурным переносом другой feature.
- Ruff lint: исходный `F401` — неиспользуемый `safe_eders_url` в `scraping/eders_client.py`.
- Ruff format: два Python-примера внутри пользовательского `TASK.md` требуют форматирования.
- mypy strict: **Success: no issues found in 174 source files**.

Непройденный baseline не следует выдавать за зелёный. Перенос первой изолированной feature проверяется
отдельно и полным suite; следующий перенос не начинается до устранения исходных блокеров отдельным изменением.

Дополнительное исходное поведение выявлено при characterization-проверке DI: текущий Dishka передаёт
исключение из тела request scope в async generator через `asend(exception)`, а `RequestProvider.get_session`
игнорирует результат `yield`. Поэтому исключение обработчика само по себе не приводит к rollback и
провайдер выполняет commit. Ошибка самого commit вызывает rollback. Код провайдера сессии не меняется
на этапе Feedback; обе ветви зафиксированы тестом. Это отдельный дефект транзакционного управления,
а не разрешение менять его семантику при переносе файлов.

## Карта функциональных зависимостей

| Область | Владение | Внешние зависимости и важные связи |
| --- | --- | --- |
| Users | Telegram-профиль, локаль, телефонные контакты, аудит | Общая БД, middleware и множество feature-потребителей |
| Schedule | Каталог факультетов/отделений/курсов, подписки, занятия, история, поиск, синхронизация | Пользователи, настройки уведомлений, HTTP расписания; используется учебной неделей |
| Food menu | Дни меню, блюда, оценки, получение HTML, отображение, рассылки | Пользователи, локаль, настройки дней и приёмов пищи, очередь удаления сообщений |
| OBIS | Вход, учётные данные, оценки, посещаемость, сравнение состояния | Пользователи, AES-GCM, настройки уведомлений; login helper и ошибки используются eders |
| Eders | Moodle HTTP/HTML, модели активности, снимки, события, доставка | Учётные данные и вход OBIS, пользователи, локаль; модели используются учебной неделей |
| Study week | Объединение занятий, сроков и материалов на семь дней | Application-результаты Schedule и Eders; отдельная orchestration feature |
| Advertisements | Карточки, медиа, модерация, контакты, сообщения канала, истечение срока | Контакты пользователей, локаль, стартовая/основная навигация, Telegram-канал |
| Feedback | Обращения, связь с сообщением admin-чата, FSM и пересылка ответов | Локаль получателя, глобальные настройки, клавиатура настроек; собственных jobs нет |
| Notifications | Общие переключатели, настройки меню, отложенное удаление | Получатели Users и сценарии отдельных feature; доставка зависит от Telegram |
| Student questions | Опрос, ответы, согласие на beta, FSM | Users и основная навигация |
| Donations / Versions / Broadcast | QR и файловый кеш / история выпусков / административная рассылка | Файлы runtime, Users, Telegram и локализация |

## Выявленные границы и связанность

### Импорты и ORM

Прямые циклы исходных импортов найдены между `Course`, `Department`, `Faculty`, `User`, а также
`Advertisement` и его media/channel message моделями. Обратные ссылки находятся под `TYPE_CHECKING`;
это не доказательство runtime-цикла. При переносе моделей необходимо сохранить строковые relationships,
порядок регистрации всей metadata и единый `Base`.

Есть скрытые связи presentation: объявления, локаль и опрос импортируют навигацию из `bot/routers/start.py`,
а deep-link обработчик объявлений импортирует функции из другого router. OBIS и Eders presentation
импортируют исключения HTTP-клиентов/парсеров. Обработчик объявлений импортирует ORM-defined enums.
Эти зависимости требуют выделения application-level ошибок/типов и общей Telegram-навигации на своих этапах.

### Telegram вне presentation

В `services/` лежат Telegram-форматтеры объявлений, меню, eders, OBIS, расписания, поиска, недели и версий.
Там же находятся сборка `BotCommand`, адаптер отправки QR и HTML-экранирование через aiogram.
Форматтеры и QR-отправка принадлежат presentation соответствующей feature. Общая регистрация команд
и i18n-адаптер принадлежат платформенному Telegram-слою. Наличие Telegram в jobs сейчас ожидаемо,
но отправку и форматирование необходимо отделять от сценариев получения и сравнения данных.

### Бизнес-логика в заданиях

`jobs/timetable_sync.py` выбирает курсы и получателей через репозитории. `jobs/obis_notification.py`
выбирает и объединяет группы подписчиков. `jobs/food_menu.py` выбирает меню, настройки получателей,
форматирует и отправляет сообщения. `jobs/advertisement.py` выбирает и удаляет истёкшие объявления.
`jobs/scheduled_message_deletion.py` группирует очередь, отправляет удаления и очищает обработанные записи.
Эти действия должны перейти в связные application-сценарии с тонкими scheduler entry points.
Eders job уже зависит от сервисов, но всё ещё координирует группировку, доставку и отметки отправки.

### Размеры и Pythonic cleanup

`EdersTrackingService` — 160 строк, 7 методов с конструктором, 2 зависимости. Он совмещает настройки,
наблюдение снимка, планирование/отмену событий и состояние доставки. Это кандидат на дальнейшее разделение
по связным обязанностям, а не на механический класс для каждого метода.
`ObisNotificationService` — 91 строка и две операции сравнения. `FoodMenuNotificationSettingsService` —
78 строк и 10 методов с конструктором; `AdvertisementService` — 73 строки и 7 методов.
Конструкторов с 10–15 зависимостями, generic BaseService/BaseRepository и циклов `range(len(...))`
в приложении не обнаружено. Большинство результатов уже являются dataclass, форматтеры — функциями.

Один явный кандидат Java-style cleanup — `_is_meal_enabled` как `staticmethod` в настройках меню:
можно рассмотреть функцию модуля после структурного переноса. `FeedbackService` уже является небольшой
связной application responsibility (20 строк, 3 операции и конструктор); дробление на три класса не нужно.

`eders_serialization`, `eders_models`, форматтеры, HTTP-парсеры и вспомогательные функции меню имеют
конкретных feature-владельцев. Их нельзя переносить в общий `shared/`. Нормализация текста и работа
со временем требуют проверки фактических независимых потребителей перед выделением shared primitives.

## Migration map

1. **Feedback** — первый пилот: нет jobs, нет ORM relationships с обратными ссылками, один репозиторий,
   три связанные операции сервиса. Перенести целиком в плоский `modules/feedback`, добавить provider,
   сохранить callback и FSM, покрыть Telegram-сценарии characterization-тестами.
2. **Advertisements** — после снятия baseline-блокеров: совместно перенести карточки, модерацию,
   deep links, ORM, formatter, provider и expiry job. Выделять границу контактов пользователей,
   не перенося UserRepository в чужой модуль.
3. **Другие небольшие feature** — опрос, версии, donations/broadcast по фактической независимости.
4. **Food menu** — перенос вместе с рейтингами, клиентом, парсером и presentation; зафиксировать
   ephemeral/rich messages, настройки рассылки и семантику очистки.
5. **Schedule** — каталог, подписки, поиск, синхронизация и история; отделить выбор получателей от job.
6. **Users / Notifications / Platform / Core** — перенести общие владельческие области и composition,
   сохранив request session, middleware ordering и контракты остальных feature.
7. **OBIS** — учётные данные и AES-GCM без изменения формата; определить публичную границу входа для eders.
8. **Eders** — перенести после стабилизации зависимостей; сохранить snapshot serialization,
   дедупликацию, timezone, HTTP redirects/retries и транзакционную блокировку пользователя.
9. **Study week** — собрать через публичные application-результаты Schedule/Eders.

Порядок отличается от предложенного в `TASK.md`: Feedback предшествует Advertisements, поскольку имеет
меньше связей и позволяет проверить перенос ORM/DI/presentation с меньшим риском. Каждый этап делится
на структурный перенос и отдельное упрощение только после проверки эквивалентности. Если осмысленного
упрощения нет, добавлять его ради объёма изменений не требуется.

## Первый этап: границы переноса Feedback

Целевой пакет: `modules/feedback/` с `router.py`, `keyboards.py`, `callbacks.py`, `service.py`,
`repository.py`, `orm.py`, `provider.py`. Отдельные domain и четыре слоя для этой небольшой feature
не создаются. `FeedbackService` остаётся application-поверхностью с dataclass результатом.

Readers/writers: Telegram-обработчики читают/создают обращения через сервис; репозиторий пишет
`feedback_messages`; admin reply ищет обращение по ID сообщения admin-чата. Остальные feature не читают
эту таблицу. Alembic импортирует модель через общий registry `db/models/__init__.py`.

Сохраняются `FeedbackForm:message`, payload `feedback:cancel`, ID/индекс/поля таблицы, ключи переводов,
порядок ответов, локаль admin-чата и пользователя, исключения и поведение при ошибках Telegram.
Отдельной миграции схемы не требуется. APP/REQUEST scopes и фактическое поведение финализации сессии
остаются прежними, включая описанный выше дефект.

Временные зависимости: router использует глобальные настройки, i18n, `LocaleService` и клавиатуру настроек.
ORM использует общий `db.base.Base`; общий registry импортирует ORM feature для Alembic. Это явно
оставленные границы с ещё не перенесёнными областями, а не основание переносить весь проект сразу.

Откат: вернуть размещение и импорты файлов, DI composition и регистрацию router. Поскольку схема,
содержимое данных и Telegram-контракты не меняются, обратной миграции PostgreSQL не требуется.

## Результаты этапов

### Feedback — структурный перенос выполнен, общий gate остаётся красным

Проверка завершена 25 октября 2026 года.

- Весь код Feedback размещён в `modules/feedback/`; его provider подключён в `main.py`, router —
  на прежней позиции в dispatcher. Регистрации Feedback удалены из общего `di.py`.
- Старые пять файлов в горизонтальных пакетах удалены; все импорты приложения и тестов обновлены.
  Callback-типы также перенесены. Общий ORM registry сохраняет экспорт `FeedbackMessage` для Alembic.
- До изменения структуры добавлены 15 characterization-сценариев обработчиков: FSM и callback,
  валидация и граница 2000 символов, trimming, экранирование, локали, доступ admin-чата, caption,
  отсутствующие ответы и ошибки отправки. Вместе с четырьмя прежними тестами до переноса прошли 19 тестов.
- Добавлены два теста composition: APP/REQUEST graph, срок жизни сервиса и сессии, фактическая
  финализация транзакций, регистрация router и ORM. Smoke-проверка dispatcher выполняется отдельным
  процессом, поскольку aiogram routers — singleton-объекты, изменяемые при подключении и DI injection.
- AST всех пяти перенесённых реализаций совпал с `HEAD`, если исключить импорты и module docstring.
  Поведение сохранено структурным переносом, без изменения тел функций и классов.
- Все 27 сигнатур PostgreSQL `CREATE TABLE` и `CREATE INDEX` совпали с сохранённым baseline.
  SQLAlchemy mappers сконфигурированы; импорт всех 177 подмодулей завершился успешно.
- `alembic check`: **No new upgrade operations detected.** Миграция схемы не добавлялась.
- mypy strict: **Success: no issues found in 178 source files**.
- Ruff lint всех изменённых Python-файлов проходит. Полный lint сохраняет только исходный F401 в eders.
- Форматирование `src`, `tests`, `docs`, `AGENTS.md`, `CLAUDE.md`, `README.md` проходит:
  **271 files already formatted**. Полная команда по-прежнему отмечает только два примера в `TASK.md`;
  пользовательский файл задания не изменялся.
- Полный pytest после переноса: **288 passed, 5 skipped, 1 failed**. Единственный сбой совпадает
  с исходным тестом redirect allowlist eders. Новых регрессий в полном suite не обнаружено.
- `git diff --check` и проверка локальных ссылок новых документов проходят.

Pythonic-фаза: Feedback уже использует небольшой связный application service, immutable dataclass и
функцию преобразования результата. Дополнительное дробление или смена naming не дают пользы и не выполнялись.

Оставшиеся legacy-области: все строки migration map, кроме Feedback. Глобальные настройки, локализация,
клавиатура настроек, `LocaleService` и `db.base` остаются временными зависимостями перенесённого модуля.

По условию `TASK.md` «только после успешной проверки переходи дальше» следующий перенос не начат.
Для общего зелёного gate нужны отдельное исправление eders redirect allowlist/связанного F401 и
форматирование примеров задания. Дефект rollback при исключении request scope также зарегистрирован,
но его исправление не включено в поведенчески эквивалентный перенос Feedback.

### Отдельное исправление baseline перед следующим переносом

25 октября 2026 года восстановлена проверка разрешённых URL в `EdersClient._request` перед каждым
запросом, включая redirect-цели. SSO допускает только переход OBIS, вход по одному непустому userkey и
страницы Moodle dashboard. Чтение допускает профиль, курс, задание и тест; переход на страницу входа
считается истечением сессии. Действия, посторонние адреса и неоднозначные параметры отклоняются до запроса.
Ошибки не раскрывают секреты. Это намеренное исправление существующего дефекта, отдельное от переноса feature.

Исходный failing test стал зелёным, добавлены проверки небезопасных redirects, сохранения `lang=en` и
истечения сессии. Форматирование `TASK.md` изменило только два Python-примера. Полный baseline теперь:
**298 passed, 5 skipped**, Ruff lint и format проходят, mypy проверяет 178 файлов без ошибок.
Дополнительно **4 HTTP-теста** прошли через существующую локальную Postman Simulation на порту 4947;
её request log подтвердил реальный обмен HTTP, включая SSO, AJAX и повтор истёкшей сессии. Мок основан на
существующем контракте и обезличенных fixtures; живой OBIS/Eders не вызывался. Новый поиск мока владельца
не требовался: использована уже существующая симуляция репозитория.

PyCharm Index MCP теперь доступен: проверены ссылки на `_request`, `AdvertisementService`,
`AdvertisementStatus` и структура router объявлений. Диагностика eders client не обнаружила ошибок.

### План следующего этапа: Advertisements

Владение: три Telegram router, две клавиатуры, callback-типы, formatter, три application service,
два репозитория, четыре ORM-модели и очистка истёкших объявлений. Переносится весь связный модуль в
`modules/advertisements/`: presentation, application, infrastructure и небольшой domain с enum.
Пустые domain layers и отдельный класс для каждого CRUD-метода не создаются.

Перед переносом дополняются characterization-тесты FSM, авторизации модерации, публикации, deep link,
удаления и expiry. Сначала переносится неизменная реализация; после зелёных проверок cleanup job становится
тонким entry point application-сценария с протоколом удаления публикаций и Telegram-адаптером.
Существующие Telegram-ошибки по-прежнему обрабатываются как best effort, публикации удаляются до строк БД,
размер deletion batch остаётся 100. Схема, FSM names, callback prefixes и i18n keys сохраняются.

Внешние временные границы: `UserContactService` и его dataclass-результаты, `LocaleService`, глобальные
Settings/i18n/Telegram-навигация и общая база ORM. Они используются через application/presentation-поверхности,
доступ к UserRepository из объявлений не добавляется. Откат требует возврата размещения и DI/router imports,
без downgrade базы. Известное поведение финализации транзакций не меняется на этом этапе.

### Advertisements — этап завершён

Сначала Index MCP переместил 16 исходных файлов с семантическим обновлением ссылок. Дополнительная
сверка импортов учла новые тесты. AST перемещённых реализаций до дальнейшего выделения границ совпал
с `HEAD`, кроме импортов. На этом промежуточном этапе прошли **315 тестов**, ещё 5 были пропущены.

В результате:

- Presentation содержит три router, две клавиатуры, formatter, все callback-типы и адаптер удаления
  публикаций. Префиксы payload и имена состояний FSM сохранены; UUID в callback по-прежнему кодируется
  aiogram как hex без дефисов, а публичная deep link сохраняет прежний UUID-формат.
- Application содержит три небольших связных сервиса и `ExpireAdvertisements`. God-service и классы
  на каждый CRUD-метод не добавлялись. Чтение контактов остаётся через `UserContactService`.
- Domain содержит `AdvertisementStatus` и `AdvertisementMediaType`, поэтому presentation больше не
  импортирует enum из ORM-файлов.
- Infrastructure содержит четыре ORM-модели и два репозитория. Репозитории импортируют собственные
  модели напрямую; глобальный registry по-прежнему регистрирует их для Alembic.
- `AdvertisementsProvider` владеет REQUEST-зависимостями; прежние регистрации удалены из `di.py`,
  provider подключён в `main.py`. APP/REQUEST scopes и провайдер сессии не менялись.
- Job теперь только создаёт Telegram-адаптер, открывает request scope и вызывает application-сценарий.
  `PublicationRemover` — реальная внешняя граница; сценарий можно тестировать без Telegram.
  Best-effort обработка Telegram-ошибок и последовательность «публикации, затем строка БД» сохранены.
- После зелёного структурного переноса удалена дублирующая функция ORM-to-summary из модерации:
  оба сервиса используют одну функцию того же модуля application. Других stylistic rewrite не делалось.
- До переноса добавлены **15 handler characterization-тестов и 2 expiry-теста с настоящей БД**.
  После выделения сценария добавлены ещё **2 теста application без Telegram**: порядок операций и
  остановка при неожиданном исключении адаптера.

Сохранённые спорные исходные сценарии: статус меняется на `published` до публикации в канал;
сбой публикации не компенсируется. При отклонении в БД передаётся максимум 512 символов комментария,
но уведомление владельцу использует полный текст. Эти случаи зафиксированы тестами, не исправлены
скрытно в архитектурном изменении.

Финальная проверка этапа:

- pytest: **317 passed, 5 skipped**;
- Ruff lint и полный format check: успешно, **290 files already formatted**;
- mypy strict: **Success: no issues found in 189 source files**;
- `alembic check`: **No new upgrade operations detected**;
- DDL всех 27 таблиц и индексов совпал с первоначальной сигнатурой; SQLAlchemy mappers сконфигурированы;
- импортированы все **188 подмодулей** приложения;
- Index diagnostics проверил перемещённые application/presentation/ORM, provider, job, use case,
  adapter и enum без ошибок; call hierarchy подтвердил зависимость job от `ExpireAdvertisements`;
- старых импортов объявлений в исходниках, тестах и Alembic не осталось;
- миграции, зависимости, локализационные каталоги и расписание APScheduler не изменялись.

Временные внешние границы: глобальная навигация, Settings/i18n, `LocaleService`, `UserContactService`,
`db.base` и helper пакетного удаления из `jobs/common.py`. Старые Python-пути удалены без compatibility
shim. Следующие области migration map остаются legacy; документация архитектуры описывает это состояние.

IDE автоматически поместила semantic moves в Git index; эти staging-изменения сняты только для
перемещённых путей. Пользовательское исходное staged-состояние `TASK.md` сохранено. Коммиты не создавались.

### План следующего этапа: Student questions

Baseline перед этапом: **317 passed, 5 skipped**, Ruff lint/format и mypy проходят. Обновлённый
`AGENTS.md` перечитан; для анализа, usages, переноса и диагностики используется PyCharm Index MCP.

Опрос переносится в плоский `modules/student_questions/`: router, клавиатуры, callbacks, application
service с dataclass/enum, repository, ORM и REQUEST-provider. Полноценные четыре слоя здесь избыточны.
Функциональные зависимости ограничены основной Telegram-навигацией, локализацией и общей базой ORM.
UserRepository не нужен: ссылка на пользователя остаётся FK таблицы.

Существующие тесты покрывают ветви FSM, stale buttons, отмену, явную перезапись, гонку duplicate submit,
локализацию пяти языков, deep-link routing и PostgreSQL upsert. До переноса добавляется точный контракт
имён FSM и payload. Сохраняются `StudentQuestionsForm:*`, `student_questions_session`, `sqa`/`sqc`,
4000 символов ответа, приоритет router перед общим `/start`, формат и схема сохранённых ответов.

Границы совместимости: глобальный registry продолжает импортировать модель для Alembic, navigation и
i18n пока остаются глобальными. Откат возвращает пути файлов и DI/router imports, без миграции БД.
Тесты остаются на своих местах. Перенос не меняет провайдер сессии и его известную семантику ошибок.

### Student questions — этап завершён

Все компоненты опроса собраны в `modules/student_questions/`: `router.py`, `keyboards.py`, `callbacks.py`,
`service.py`, `repository.py`, `orm.py`, `provider.py`. Старые пути удалены без compatibility shim.
Provider подключён в composition root; регистрации сервиса и репозитория удалены из общего `di.py`.
Общий ORM registry сохраняет `StudentQuestionsResponse`; его поля и PostgreSQL upsert не менялись.

До переноса добавлена точная проверка семи FSM state names, session key и payload `sqa`/`sqc`.
Профильный baseline с ней: **26 passed**. После переноса профильные проверки, composition,
startup и зависимые eders-тесты: **44 passed**.

Семантические перемещения выполнены Index MCP. После file rename IDE оставила часть импортов на
промежуточные пути; они исправлены явно. Последующий Index search не нашёл старых или промежуточных
импортов. Диагностика шести ключевых файлов проанализировала их без ошибок.

Итог:

- полный pytest: **318 passed, 5 skipped**;
- Ruff lint/format проходят; format проверил **293 файла**;
- mypy strict: **192 source files**, без ошибок;
- AST пяти перенесённых реализаций совпал с `HEAD`, кроме импортов;
- DDL всех 27 таблиц и индексов совпал с исходным; Alembic не обнаружил новых upgrade operations;
- router остаётся перед advertisement deep link и общим `/start`;
- локали, callback payload, FSM, лимит 4000 символов, duplicate handling и явная перезапись сохранены.

Pythonic-фаза: сервис уже небольшой, результаты immutable dataclass, validation — функция модуля.
Дополнительных классов и переименований ради стиля не потребовалось. Временные зависимости ограничены
общими Base, Telegram-навигацией и локализацией. Известный дефект финализации транзакции не изменялся.

### План следующего этапа: Versions

После полного зелёного gate опроса отдельно переносится `/versions`: файловый каталог, formatter,
клавиатуры, router и два callback-типа. Цель — плоский `modules/versions/`; функции остаются функциями,
искусственный service/provider для неизменяемых зависимостей не вводится.

До переноса добавляются characterization-тесты чтения файлов, числовой сортировки, пагинации,
отсутствующего каталога, обновлений без рестарта, форматирования, callback payload и Telegram-навигации.
Особая граница — `VERSIONS_DIR`: глубина файла меняется, но путь к runtime `docs/versions/` должен
остаться тем же в исходном checkout и Docker `/app`. Содержимое и схема файлов версий не меняются.

Readers: router и клавиатуры; writer — существующие Markdown-файлы выпусков в `docs/versions/`,
которые команда только читает. БД и jobs у feature нет. Внешние зависимости — i18n и runtime-файлы.
Тело выпуска сохраняет исходную разметку; дополнительное HTML escaping не вводится.
Откат возвращает файлы, импорты, callbacks и вычисление корневого пути, без миграции БД.

### Versions — этап завершён

`modules/versions/` содержит `history.py`, `formatter.py`, `keyboards.py`, `callbacks.py` и `router.py`.
Четыре прежних файла перемещены Index MCP, старые пути удалены. Во время переиндексации один rename
был отклонён; после `ide_index_status` с `isDumbMode=false` он успешно повторён. Промежуточные импорты
после file rename исправлены явно и проверены Index search: старых путей не осталось.

До переноса добавлены **14 characterization-тестов**, успешно выполненных на прежнем коде. Они проверяют
числовую сортировку и страницы по 10 записей, пустой/отсутствующий каталог, игнорирование некорректных
дат и лишних расширений, чтение новых/изменённых файлов без рестарта, пять языков formatter,
раскладку клавиатур, callback payload и поведение обработчиков при неизвестной версии.

При переносе `VERSIONS_DIR` заменил `parents[3]` на `parents[4]`, сохранив фактический путь к
`docs/versions/`. Это проверено в checkout и на копии исходного модуля в синтетическом Docker-like
layout `/app/src/manashelper/...`. Docker COPY runtime-файлов не менялся. Реальная сборка образа
на этом этапе не выполнялась.

После переноса профильные тесты и composition/startup: **22 passed**. Финальный общий gate:

- pytest: **332 passed, 5 skipped**;
- Ruff lint/format проходят, формат проверен для **296 файлов**;
- mypy strict: **194 source files**, без ошибок;
- Index diagnostics проанализировал все пять файлов Versions без ошибок;
- AST четырёх перемещённых реализаций совпал с `HEAD`, кроме импортов и глубины runtime-пути;
- DDL всех 27 таблиц и индексов совпал с первоначальным; Alembic не нашёл новых upgrade operations;
- успешно импортированы все **193 подмодуля** приложения.

Список выпусков по-прежнему читается с диска на каждый вызов, тело выпуска передаётся formatter без
дополнительной обработки HTML. Названия команд, callback payload, порядок router, runtime-формат файлов
и содержимое `docs/versions/` сохранены. Pythonic-фаза не потребовала изменений: здесь уже использовались
функции и immutable dataclass; ненужные service/provider не добавлялись.

`AGENTS.md` перечитан перед этапами; его новая политика приоритета MCP сохранена. IDE не нашла
запрошенную run configuration `All Tests`, поэтому обязательные pytest/Ruff/mypy/Alembic запускались
из терминала. Это fallback проверки, а не замена доступной семантической навигации shell-поиском.

Остальные области migration map остаются legacy. Автоматический staging только девяти перемещённых
пар путей снят; исходное состояние Git index перед этими этапами было пустым. Коммиты не создавались.

### План следующего этапа: публичные Users queries и Donations

`AGENTS.md` перечитан перед продолжением. Сначала отдельным этапом выделяется маленькая публичная
application-граница `modules/users/queries.py`: подсчёт зарегистрированных пользователей и полный список
их ID. Два действительных потребителя — пожертвования и административная рассылка. Их текущие сервисы
переходят с прямого UserRepository на UsersQuery; сам UserRepository, ORM, контакты и локаль пока остаются
в legacy. Это частичное выделение границы Users, а не завершённая миграция всей области.

Причина изменения порядка: перенос Donations не должен закреплять доступ к внутреннему репозиторию
чужой области. Query возвращает только int/list[int], не ORM, использует прежние SQL-запросы и REQUEST scope.
Ни generic repository, ни Protocol для обычного SQLAlchemy repository не добавляется.

После полного зелёного gate отдельно переносится Donations: файловый каталог банков, Telegram QR adapter,
application-счётчик, router, клавиатуры, callback и provider. Файлы группируются плоско; прежний смешанный
`services/donations.py` разделяется по фактическим ролям. Кеш Telegram file ID остаётся в APP, application
service — в REQUEST. Сохраняются LRU на 32 записи, ключ кеша, повторная загрузка изменённого QR,
bank ID из SHA-256 имени, payload `donate:<id>` и runtime `docs/requisites/` в checkout и Docker layout.

До переноса добавляются characterization-проверки счётчика, handlers, runtime-пути, payload и кеша.
Изображения, переводы, команда `/donate`, модель пользователя, схема БД и транзакционная семантика не меняются.
Откат возвращает imports/provider composition и расположение файлов без downgrade БД.

### Users read boundary — этап завершён

Созданы `modules/users/queries.py` и REQUEST-scoped `UsersProvider`. DonationService и BroadcastService
используют публичный UsersQuery; сам query вызывает прежние `UserRepository.count()` и `get_all_ids()`.
Возвращаемые значения и SQL не изменились. Это частичное выделение публичной поверхности Users:
профиль, контакты, локаль, ORM и repository не объявляются перенесёнными.

До изменения зависимостей добавлены четыре проверки счётчика Donations: 0, 1, 2 и 67 пользователей.
Полный baseline с ними: **336 passed, 5 skipped**. После выделения query добавлена проверка с настоящей
БД: count и список ID отражают всех пользователей, включая добавленных после первого чтения.
Все composition-тесты обновлены для нового provider.

Gate этапа: **337 passed, 5 skipped**, Ruff lint/format проходят (**300 файлов**), mypy strict —
**197 source files** без ошибок. Index diagnostics проверил query/provider и двух потребителей без ошибок.
Поведение сессии, схема БД, локализация и Telegram-отправки не менялись.

### Donations — этап завершён

Три прежних файла перемещены Index MCP. Сначала сохранена смешанная реализация и проверены профильные
тесты; затем по отдельным файлам разделены фактические роли:

- `catalog.py`: DonationBank, поддерживаемые расширения, ID банка и чтение `docs/requisites/`;
- `qr.py`: Telegram-адаптер DonationQrService и bounded LRU file ID;
- `service.py`: application-счётчик через публичный UsersQuery, без Telegram и UserRepository;
- `router.py`, `keyboards.py`, `callbacks.py`: presentation и неизменный `donate:<bank_id>`;
- `provider.py`: DonationQrService в **APP**, DonationService в **REQUEST**.

Старые регистрации удалены из общего `di.py`; root composition собирает UsersProvider и DonationsProvider.
Пять pre-existing providers сохраняют свои области жизни; в сумме в `main.py` семь providers.
Для QR создаётся один объект на приложение, повторно используемый в разных request scopes.

До перемещения прошли **28 тестов Donations**. Добавленные characterization-проверки покрывают пять языков,
наличие/отсутствие QR, settings entry, private flags, неизвестную и исчезнувшую карточку банка,
inaccessible callback, точный payload, SHA-256 ID, каталог файлов, Docker-like layout, LRU hit refresh,
пустой photo response и повторное использование кеша между request scopes. После разделения вместе
с Users/Broadcast/composition/startup прошли **38 тестов**.

Snapshot трёх реализаций до перемещения получен через Index после завершения Users read boundary.
После перемещения AST совпал, кроме импортов и глубины runtime-пути. После разделения определения
DonationBank, list_donation_banks, DonationQrService и DonationService совпали со снимком точно;
router и keyboards — кроме импортов. `REQUISITES_DIR` использует `parents[4]`, сохраняя прежний
фактический путь. Существующие изображения и Docker COPY не менялись; Docker build не выполнялся.

Финальный gate:

- pytest: **358 passed, 5 skipped**;
- Ruff lint/format проходят, format проверил **306 файлов**;
- mypy strict: **202 source files**, без ошибок;
- Index diagnostics проверил каталог, adapter, service, provider и router без ошибок;
- Index search не нашёл старых или промежуточных imports Donations;
- DDL всех 27 таблиц и индексов совпал с исходным, Alembic не обнаружил новых upgrade operations;
- импортированы все **201 подмодуль** приложения.

Pythonic-результат — разделение смешанного legacy service на функции каталога, конкретный Telegram-адаптер
и небольшой application service. Новых generic abstractions, Protocol для обычных репозиториев,
искусственных четырёх слоёв или классов для каждой операции не добавлялось.
Подписи банков, ключ кеша, граница 32 записи, обработка замены файла, HTML caption и callback payload
сохранены. Известный дефект финализации request transaction остаётся отдельным зафиксированным поведением.

Остальные Users-компоненты и Broadcast presentation остаются legacy. Публичный UsersQuery уже обслуживает
оба сценария, поэтому последующий перенос Broadcast не потребует прямого доступа к UserRepository.
Автоматический staging трёх перемещённых пар путей снят; исходный Git index был пустым. Коммиты не создавались.

### План следующего этапа: Broadcast

`AGENTS.md` перечитан; используется Index MCP. Стартовая рабочая копия и Git index чистые.
Run configuration `All Tests` снова отсутствует, поэтому обязательные проверки выполняются через CLI.

Сначала без изменения поведения в плоский `modules/broadcast/` перемещаются router, клавиатура,
application service и callbacks. REQUEST-provider заменяет регистрацию в общем `di.py`.
Перед переносом characterization-тесты фиксируют admin chat authorization, `BroadcastForm:message`,
ключ `body`, payload `broadcast:confirm`/`broadcast:cancel`, preview, caption fallback, повторный confirm,
очистку FSM, локаль admin-чата и каждого получателя, ошибки Telegram и неожиданные исключения.

После зелёного структурного переноса выделяется application-сценарий `SendBroadcast`: выбор всех ID
через публичный UsersQuery, последовательная отправка и подсчёт результата. Конкретные Bot/i18n/HTML
операции остаются в Telegram-адаптере. Протокол sender оправдан реальной внешней границей доставки,
а не наличием SQLAlchemy repository. Ненужный getter-service заменяется связным сценарием.

Сохраняются порядок callback answer/edit/send, отсутствие retry, продолжение после TelegramAPIError,
остановка при ошибке локали/неожиданном исключении, очистка FSM до получения адресатов и русская итоговая
статистика. Команда по-прежнему регистрируется только для admin-чата. Новых текстов, jobs, форматов,
таблиц и миграций нет. Откат возвращает расположение, DI/dispatcher imports и orchestration в router.

### Выполнено: Broadcast

Перед изменением production-кода добавлены **25 characterization-тестов** в
`tests/test_broadcast_handlers.py`; они прошли на исходной реализации. Тесты используют настоящий
aiogram Bot с подменённой сессией, без отправки сообщений в Telegram, и настоящий application-компонент.
Проверены все пять локалей, HTML, авторизация в admin group, FSM, callback payload, caption fallback,
пустой ввод, отмена, повторное подтверждение, порядок операций и границы обработки исключений.

**Phase A.** Router, клавиатура и service перенесены средствами Index MCP; callbacks принадлежат feature.
Добавлен BroadcastProvider с прежним REQUEST scope, удалена legacy-регистрация в `di.py`, обновлены
dispatcher, root composition и тесты. AST трёх перемещённых реализаций совпал с HEAD, кроме импортов.
После переноса: **383 passed, 5 skipped**, Ruff lint/format проходят, mypy проверил 205 source files.

**Phase B.** Ненужная обёртка `BroadcastService.get_recipient_ids` заменена связным `SendBroadcast.execute`:
он получает адресатов через публичный UsersQuery, вызывает sender по порядку и возвращает immutable
`BroadcastResult(sent, total)`. Протокол BroadcastSender представляет внешнюю границу доставки.
TelegramBroadcastSender владеет Bot, локалью получателя, gettext, экранированием HTML и обработкой
TelegramAPIError. Ошибки lookup/форматирования остаются за пределами этого catch; неожиданные исключения
по-прежнему прерывают обход. Router управляет авторизацией, FSM, preview и итогом в DEFAULT_LOCALE.
Дополнительные тесты сценария проверяют порядок, подсчёт частичных ошибок, пустой список, остановку при
неожиданном исключении и REQUEST scope. Проверка с реальным Postgres подтверждает выбор зарегистрированных
пользователей через UsersQuery, без обращения Broadcast к UserRepository.

Текущий пакет плоский: `router.py`, `keyboards.py`, `callbacks.py`, `service.py`, `sender.py`, `provider.py`.
У feature нет собственных таблиц, jobs или runtime-файлов. Контейнер `main.py` собирает восемь providers.
Остальные Users-компоненты остаются legacy; публичный запрос — временная явная application-граница.

Финальные проверки:

- pytest: **388 passed, 5 skipped**; пропуски прежние: необязательный локальный corpus eders и четыре HTTP simulation tests;
- focused Broadcast/composition: **33 passed**;
- Ruff lint/format проходят; format проверил **311 файлов**;
- mypy strict: **206 source files**, без ошибок;
- Index diagnostics: ошибок в service, sender, provider и router нет;
- Index search: старые/промежуточные Python imports и BroadcastService отсутствуют;
- DDL всех **27 таблиц и индексов** совпал с исходным; Alembic: `No new upgrade operations detected.`;
- импортированы все **205 подмодулей** приложения.

Сохранены payload, FSM state/key, тексты, локали, порядок, последовательная доставка без retry,
ошибки и существующий дефект финализации request transaction. Реальные Telegram-запросы не выполнялись.
Обновлены ARCHITECTURE.md, AGENTS.md и CLAUDE.md. Автоматический staging трёх перемещённых пар путей
снят; начальный index был пустым. Коммиты не создавались. Следующий крупный этап карты — Food menu;
его перенос в этот этап не включён.

## Следующие этапы: Food menu, затем Schedule

По запросу пользователя после завершения Food menu выполняется следующий этап Schedule.
Стартовая рабочая копия и index чистые; baseline: 388 passed, 5 skipped, Ruff и mypy (206 файлов) проходят.
AGENTS.md перечитан, навигация и перемещения выполняются Index MCP. IDE run configuration All Tests
недоступна; обязательные проверки запускаются CLI.

Food menu сначала переносится без изменения тел реализаций: application-сервисы, три router, клавиатуры,
callbacks, formatter, пять ORM-моделей, пять репозиториев, HTTP-клиент, parser и jobs. Feature provider
сохраняет APP для клиента/parser и REQUEST для остальных зависимостей. Общие MessageDeletionService,
очередь удаления, LocaleService и Users остаются внешними областями.
После зелёной Phase A jobs отделяются от выбора меню/получателей, Telegram-доставка остаётся адаптером;
чистый helper настроек становится функцией. Расписание запусков, scopes, callback payload, ephemeral/rich
messages, рейтинг, SQL defaults, отсутствие retry и границы catch должны сохраниться.

Добавлены 20 characterization-тестов настроек, получателей, jobs, доставки и синхронизации;
они проходят до production-изменений. Обнаружено и сохранено существующее поведение: первое переключение
обеда для нового дня остаётся True, поскольку `not None` выполняется до flush Python-defaults ORM.
Это отдельный дефект, не исправляемый структурным переносом.
Ещё два теста реального HTTP-клиента/parser проходят против локальной Postman simulation (200 и 500).
Mock основан на текущем selector contract parser и синтетическом обезличенном HTML, без проверки
реального сайта или поиска опубликованного mock университета. Production URL и HTTP-поведение не меняются.

Откат этапа возвращает файлы, composition imports и orchestration в jobs; схема БД не должна измениться.

### Выполнено: Food menu

Phase A перенесла 24 модуля средствами Index. AST всех тел совпал с HEAD, исключая imports;
callback-классы и значения перенесены в presentation/callbacks.py. Исправлен оставшийся локальный import
в тесте доступности, затем полный suite: **410 passed, 5 skipped** с активной HTTP simulation.
FoodMenuProvider заменяет legacy-регистрации, сохраняя APP/REQUEST. Global ORM registry импортирует
все пять моделей feature и association table для Alembic.

Phase B выделила BroadcastFoodMenu и внешний протокол FoodMenuSender: выбор меню/получателей и последовательный
обход больше не находятся в jobs. TelegramFoodMenuSender сохраняет i18n/rich message/cleanup и прежнюю
границу catch. Повторяющиеся lunch/dinner entry points используют общий тонкий helper с request scope.
LocaleService заменяет эквивалентный helper чтения locale через repository. UsersQuery.exists заменяет
прямой доступ сервиса настроек к UserRepository. Чистый _is_meal_enabled стал функцией модуля.

Финальный gate: **412 passed, 5 skipped**, Ruff lint/format (326 файлов), mypy strict (218 source files).
При выключенной Food menu simulation два новых HTTP-теста пропускаются. В реальном HTTP-прогоне member
food-menu обслужил GET /menu с 200 и 500; результат проверен и до, и после переноса. Реальный сайт не проверялся.
Index diagnostics пяти изменённых компонентов без ошибок, старых imports нет. DDL 27 таблиц/индексов
не изменился, Alembic не нашёл upgrade operations; импортированы 217 подмодулей. Добавлены проверки
APP/REQUEST и прежних cron 11:00/17:00 Bishkek, sync каждые 10 минут.
Существующие дефекты request finalization и первого переключения настройки сохранены. Обновлены архитектурные
документы и инструкции. Этап завершён; далее по прямому запросу пользователя выполняется Schedule.

### План Schedule

Baseline после Food menu: 412 passed, 5 skipped. До переноса Schedule добавлены и пройдены 23 теста
callback/FSM/search, ошибок показа расписания, числовой сортировки времени, request scopes по курсам,
изоляции ошибок и реального HTTP-клиента/parser против синтетического Postman mock (200/500).

Phase A собирает в modules/schedule каталог Faculty/Department/Course, подписки user_courses,
ScheduleService, LessonSearchService, TimetableSyncService, formatter/keyboards/callbacks, два router,
клиент/parser, пять ORM-моделей с association table, пять репозиториев и job. TimetableClient остаётся APP,
остальные зависимости REQUEST. StudyWeekService и settings продолжают использовать публичные application-сервисы.

Phase B отделяет orchestration синхронизации/получателей от Telegram job. Чтение/изменение подписок
принадлежит Schedule; запрос с selectinload переносится из UserRepository в конкретный репозиторий подписок
без изменения SQL и ORM-коллекций. NotificationRecipientsQuery даёт узкую публичную границу с ещё legacy
Notifications; остальная область не переносится. LocaleService заменяет эквивалентный job helper.
Общие названия дней недели и Bishkek timezone получают фактических общих владельцев, устраняя зависимости
Schedule от Food menu и Food menu от formatter расписания. Публичные payload, FSM cache keys, нормализация,
первый sync без уведомлений, история изменений, отсутствие retry, scopes и транзакции сохраняются.

### Выполнено: Schedule

Phase A перенесла 26 модулей через Index MCP. Тела всех реализаций совпали с HEAD по AST, кроме imports.
После исправления import alias в characterization-тесте полный suite: **435 passed, 5 skipped**;
Ruff lint/format (338 файлов) и mypy strict (228 source files) проходят. Callback-классы принадлежат
presentation, global model registry сохраняет все ORM и user_courses для Alembic. Scope клиента — APP,
сервисов/репозиториев — REQUEST; root composition и её тестовые контейнеры используют ScheduleProvider.

Phase B выделила SyncCourseTimetable и протокол внешней доставки ScheduleChangeSender. Job читает ID
через CourseService, сохраняет отдельный request scope для списка и каждого курса, а Telegram-адаптер
получает locale через LocaleService и использует прежний send_notification. TelegramAPIError пропускает
получателя; неожиданные ошибки останавливают текущий курс, но не следующий. Прямых repository-зависимостей
в Schedule jobs больше нет. NotificationRecipientsQuery с собственным REQUEST-provider — узкая публичная
граница с Notifications; это не полная миграция настроек уведомлений.

Запрос подписок с selectinload перенесён из UserRepository в CourseTrackingRepository. AST метода совпал
точно; CourseService/ScheduleService используют владельца подписок, без смены SQL, association table или
ORM mutation semantics. User ORM и его relationship остаются в legacy до этапа Users. Общие функции
weekday_abbr/full переехали в localization/weekdays.py с точным совпадением AST. Для timezone переиспользован
уже существовавший services/time_utils.py, без новой копии или нового инфраструктурного слоя.
Food menu и Schedule больше не зависят от formatter/timezone друг друга.

Финальный gate с обеими локальными HTTP simulations:

- pytest: **437 passed, 5 skipped**; без переменных simulations четыре новых HTTP-теста пропускаются;
- Ruff lint/format: **346 файлов**; mypy strict: **235 source files**, без ошибок;
- Index diagnostics девяти изменённых компонентов без ошибок; старых/промежуточных imports нет;
- все **234 подмодуля** импортируются, DDL всех **27 таблиц и индексов** совпадает с исходным;
- Alembic: `No new upgrade operations detected.`;
- timetable member обслужил GET /department-printer/123 с 200/500 до и после переноса; Food menu member
  также обслужил свои HTTP-тесты. Проверены локальные fixtures, реальные университетские сайты не вызывались;
- дополнительные тесты подтверждают default opt-in, фильтрацию по подпискам, APP/REQUEST и прежний hourly job.

Два заказанных этапа завершены. Callback payload/FSM, история/нормализация, first-sync suppression,
расписания jobs, scopes, transaction defect и Food menu first-toggle defect сохранены.
Архитектурные документы и инструкции обновлены. Автоматический staging перемещений снят только с известных
пар путей; исходный index был пустым. Коммиты не создавались. Следующий этап карты — Users/Notifications/Platform/Core.

### План следующего этапа: Notifications

Baseline: **434 passed, 8 skipped** (HTTP simulations не включены),
Ruff lint/format и mypy strict (235 файлов) проходят. Сохранён PostgreSQL DDL всех 27 таблиц и индексов.

Один владельческий перенос: `modules/notifications/` получает настройки, repository, ORM, callbacks,
клавиатуру и три обработчика уведомлений из общего settings router. Общая навигация Settings остаётся
в Telegram-слое; настройки Food menu/Eders и OBIS polling принадлежат своим областям.
NotificationsProvider собирает REQUEST-зависимости, global model registry сохраняет Alembic metadata.

После структурного переноса Notifications использует существующий UsersQuery.exists вместо UserRepository;
OBIS job получает адресатов через NotificationRecipientsQuery. SQL, порядок запросов, set union,
request scopes, callback payload, локализация и ошибки сохраняются. HTTP-интеграции не затрагиваются.

Characterization фиксирует существующий дефект ORM defaults: до flush новая строка содержит None вместо
трёх bool; первый toggle включает выбранный флаг. Не исправлять этот дефект в архитектурном переносе.

### Выполнено: Notifications

Phase A собрала feature в плоском `modules/notifications/`: настройки, query, repository, ORM, callbacks,
клавиатура, router и REQUEST-provider. AST шести перенесённых реализаций до упрощения совпал с исходным,
кроме imports. Прошли **54 целевых теста** и mypy. Общая Settings-навигация остаётся в `bot/`,
новый router подключён рядом с settings в dispatcher; flags, фильтры, payload и кнопки возврата сохранены.

Phase B заменила UserRepository в настройках на существующий UsersQuery.exists. OBIS job получает
два списка адресатов через публичный NotificationRecipientsQuery; прежние SQL, set union, флаги проверки,
порядок запросов, обработка ошибок и request scopes не изменились. Сравнение снимков и доставка OBIS
не переносились. Новых интерфейсов, зависимостей или миграций нет.

Добавлены **28 тестов**: неизвестный пользователь, независимость/сохранение переключателей,
deferred defaults, default opt-in и фильтрация адресатов, клавиатура и payload, handlers/alerts,
маршрутизация, OBIS recipient union/load failure, scopes и model registry. Расширен root composition test.

Финальный gate:

- pytest: **461 passed, 9 skipped**; восемь HTTP-тестов требуют локальные simulations,
  корпусный тест пропущен из-за отсутствия приватной выгрузки Eders;
- Ruff lint/format: **351 файл**; mypy strict: **238 source files**, без ошибок;
- Index diagnostics девяти компонентов без ошибок, старых imports не найдено;
- все **237 подмодулей** импортируются; DDL всех **27 таблиц и индексов** совпал с baseline;
- Alembic: `No new upgrade operations detected.`;
- существующие дефекты transaction finalization и first-toggle defaults сохранены и покрыты тестами.

Этап завершён. Users, Platform/Core, OBIS, Eders и Study week остаются следующими областями карты.
Коммиты, push и deploy не выполнялись; исходные `.DS_Store` не изменялись.

### План следующего этапа: Users

Baseline: **461 passed, 9 skipped**. Рабочее дерево чистое, кроме трёх исходных `.DS_Store`.
Сохранён PostgreSQL DDL всех 27 таблиц и индексов. Используется прежний workflow safe-refactor.

Phase A собирает Users: `application/locale.py`, `application/user_contact.py`, инфраструктуру профиля и
телефонов, presentation выбора языка и управления телефонами. UsersQuery остаётся публичным query API;
UsersProvider получает все REQUEST-зависимости. User ORM сохраняет поля OBIS, association table Schedule,
relationships, defaults и строковые имена. Locale enum/i18n остаются общими, аудит — до Platform/Core.
Start/settings остаются общей Telegram-навигацией. Callback payload, PhoneNumberForm, валидация/порядок
телефонов, ошибки и локализация не меняются; перед переносом добавляются characterization tests.

Phase B выделяет общие build_main_keyboard/send_welcome из start router в bot/navigation.py и заменяет
единственного потребителя jobs/common.get_user_locale на существующий LocaleService. Legacy OBIS/Eders
пока используют UserRepository для сохранённых credentials: эта временная связь требует отдельного
этапа OBIS, а не нового API для шифротекста в Users. HTTP, шифрование и транзакции здесь не меняются.

### Выполнено: Users

Phase A перенесла 10 исходных файлов через Index MCP: application locale/contact services, профиль/телефоны,
репозитории, два router и две клавиатуры. Callback-классы теперь принадлежат Users presentation.
AST всех десяти файлов и callback-деклараций совпал с исходным, кроме imports. UsersProvider регистрирует
два repository, LocaleService, UserContactService и UsersQuery в REQUEST; регистрация в общем di.py удалена.
Целевые проверки: **70 passed**, mypy strict; полный suite до Phase B: **477 passed, 9 skipped**.

Phase B выделила build_main_keyboard/send_welcome в `bot/navigation.py` с точным совпадением AST.
Все feature-потребители обновлены: импортировать start router ради общей навигации больше не требуется.
OBIS job читает локаль через LocaleService вместо прямого UserRepository/helper; порядок запросов,
fallback, ValueError при некорректной сохранённой локали, отправка и per-user error boundary сохранены.

Добавлено **25 тестов**: сохранность локали/credentials/подписок при profile refresh, отсутствие регистрации
при чтении/смене локали неизвестного пользователя, некорректная сохранённая локаль, порядок/формат телефонов,
payload/FSM/private flags, подтверждение и приветствие на выбранном языке, phone validation/deletion errors,
OBIS locale/failure isolation, REQUEST scopes, registry и LocaleMiddleware. Root composition test дополнен
проверкой расположения обоих router. Два теста запускают импорт Users в отдельном процессе: прямой импорт
только User ORM не загружал Course mapper. Поэтому сохранён прежний импорт моделей через общий db.models
registry в обоих репозиториях; mapper registration не зависит от предварительных импортов тестового suite.

Финальный gate:

- pytest: **486 passed, 9 skipped**; как в baseline, пропущены восемь HTTP-тестов без simulations
  и корпусный тест без приватной выгрузки Eders;
- Ruff lint/format: **359 файлов**, mypy strict: **245 source files**, без ошибок;
- Index diagnostics 16 компонентов без ошибок; старых Python imports не найдено;
- все **244 подмодуля** импортируются, DDL всех **27 таблиц и индексов** совпал с baseline;
- Alembic: `No new upgrade operations detected.`;
- IDE build сообщает success с ограничением сбора build diagnostics; основная проверка — CLI gates выше.

Профиль, локаль и контакты перенесены полностью. User сохраняет credential columns OBIS и relationship
Schedule; legacy OBIS/Eders пока используют перенесённый UserRepository. Аудит, Platform/Core и дальнейшие
этапы OBIS, Eders, Study week остаются вне этой итерации. Известные дефекты defaults и request transaction
finalization не исправлялись. IDE auto-staging снят только с 28 известных task-путей; исходный index был пуст.
Коммиты, push и deploy не выполнялись; `.DS_Store` сохранены.

### План следующего этапа: Core

Baseline: **486 passed, 9 skipped**; исходное рабочее дерево чистое, кроме трёх `.DS_Store`.
Сохранён DDL 27 таблиц и индексов. Следующая владельческая граница — общая инфраструктура Core;
Telegram Platform, аудит и feature-провайдеры остаются отдельными последующими этапами.

`core/config.py` получает Settings/get_settings, `core/logging.py` — настройку логирования,
`core/database.py` — единый Base и фабрики engine/session pool. Для 17 строк реализации БД отдельные
base/engine/session пакеты не создаются. Общий registry моделей остаётся в `db/models/`.
CoreProvider получает APP-настройки, engine, session factory, HTTP-клиент и REQUEST-сессию.
В `di.py` остаются только legacy feature-зависимости, root composition явно добавляет CoreProvider.

Сохраняются все env aliases/defaults/cache, относительные пути .env/logs, format/rotation логирования,
expire_on_commit=False, timeout=15, APP/REQUEST lifetimes, порядок запуска и освобождения ресурсов,
включая существующий commit при исключении тела Dishka scope. UI, HTTP-контракты и schema не меняются.

### Выполнено: Core

Настройки, общая БД и логирование перенесены Index MCP в `core/config.py`, `core/database.py` и
`core/logging.py`. Старые модули удалены, adapters совместимости не создавались. Общий registry моделей
остаётся в `db/models/`, все ORM используют единственный Base из Core. Alembic и subprocess-тесты обновлены.

CoreProvider получил пять прежних resource factory methods. Их тела/сигнатуры совпали по AST;
декоратор get_session теперь явно задаёт REQUEST, остальные ресурсы остаются APP. AST трёх перенесённых
файлов не изменился, кроме imports. В 35 остальных исходных файлах изменились только импорты.
`di.py` содержит только legacy feature-зависимости, main и тестовые композиции явно добавляют CoreProvider.
Root composition теперь состоит из 12 providers. Дополнительного stylistic cleanup не потребовалось.

Добавлено семь characterization/lifecycle тестов: APP engine/disposal при нормальном и ошибочном выходе,
общий HTTP-клиент с timeout 15 и закрытием, .env от CWD/env aliases/cache, UTF-8/rotation/path логирования,
независимый Core container с APP/session factory и REQUEST cache, commit перед закрытием session.
Существующие тесты request body error/commit failure, startup/shutdown и standalone Users сохранены;
тест main дополнительно проверяет единственную регистрацию CoreProvider. Целевой gate: **40 passed**,
проверка main после усиления assertion: **6 passed**.

Финальный gate:

- pytest: **493 passed, 9 skipped**; пропуски прежние: восемь HTTP-тестов без локальных simulations
  и корпусный тест без приватной выгрузки Eders;
- Ruff lint/format: **362 файла**; mypy strict: **247 source files**, без ошибок;
- все **246 подмодулей** импортируются; DDL **27 таблиц и индексов** совпал с baseline;
- Alembic: `No new upgrade operations detected.`;
- Index diagnostics семи компонентов без ошибок, старых/промежуточных Python imports нет;
- IDE build сообщает success, но не предоставляет полноценные build diagnostics; проверка основана на CLI gates.

Этап Core завершён. Поведение транзакций, APP/REQUEST, start/stop ordering, env, логирование и metadata
сохранены. Telegram Platform, аудит, OBIS, Eders и Study week остаются следующими областями карты.
Коммиты, push и deploy не выполнялись. IDE auto-staging снят только с известных task-путей;
исходный index был пуст, три `.DS_Store` сохранены.

### План следующего этапа: Telegram Platform и аудит

Baseline: **493 passed, 9 skipped**. Рабочее дерево чистое, кроме трёх `.DS_Store`; DDL 27 таблиц
и индексов сохранён. Перенос следует прежнему safe-refactor workflow, без функциональных изменений.

`platform/telegram/` получает dispatcher, команды/каталог/extractor, общую навигацию Settings/Start,
Settings callbacks, filters, middleware и Telegram HTML/delivery helpers. Аудит и очередь удаления
сообщений получают плоские подмодули audit/deletions с ORM, repository и application service.
TelegramPlatformProvider владеет их четырьмя REQUEST-зависимостями; соответствующие регистрации уходят из di.py.
`platform/i18n/` получает gettext adapter, а чистые Locale/weekday labels остаются в localization/.
Оставшиеся bot routers/keyboards/callbacks OBIS и Eders не переносятся до своих feature-этапов.

Phase A: точный структурный перенос, включая обновление runtime-путей команд/каталогов и Babel entrypoint.
До переноса добавляются characterization tests для audit masking/private guard, per-chat ordering,
batch cleanup/failures, checkout/Docker-like resource paths. Existing command/localization/limiter/FSM tests сохраняются.
Порядок middleware/routers, masks, flags, callback payload, локали, scopes, SQL/DDL, jobs и транзакции сохраняются.

Phase B: cleanup job делегирует связный сценарий MessageDeletionService, без прямого repository доступа.
Операция внешнего удаления передаётся как async callable; TelegramAPIError обрабатывает прежний delivery adapter.
Сохраняются batches по 100, отсутствие retry и удаление обработанных строк после TelegramAPIError;
неожиданная ошибка останавливает текущий sweep, логируется и не очищает строки.

### Выполнено: Telegram Platform и аудит

Phase A перенесла 25 реализаций и два package initializer через Index MCP. Целевой `platform/telegram/`
содержит dispatcher, команды/каталог/Babel extractor, navigation, Settings callbacks, routers/keyboards,
filters/middleware, HTML/delivery, audit и deletions. Gettext adapter находится в `platform/i18n/catalog.py`;
чистые Locale/weekday labels остаются в localization/. В bot/ осталась только presentation OBIS/Eders.

AST всех 25 реализаций и Settings callbacks до упрощения совпал с baseline, кроме imports и двух
resource root assignments. Пути команд/переводов сохранены для checkout и Docker-like layouts;
babel.cfg указывает на новый extractor. Схема моделей audit/deletions и global registry сохранены.
TelegramPlatformProvider регистрирует четыре зависимости в REQUEST, di.py больше не владеет ими.
Все композиции обновлены; root теперь содержит 13 providers. После Phase A: **511 passed, 9 skipped**.

Phase B перенесла выбор/группировку/acknowledgement cleanup sweep в MessageDeletionService.delete_due.
Job открывает request scope и передаёт прежний naive UTC cutoff и async delivery callable.
Delivery adapter использует стандартный itertools.batched(..., 100, strict=False), продолжает после
TelegramAPIError и пропускает unexpected errors наружу. Этот же adapter теперь используется удалением
публикаций объявлений; дублирующие chunk/delete_message_batch удалены. Новых Protocol/интерфейсов нет.
Порядок batch/chat, удаление строк после API error, отсутствие retry и abort/логирование unexpected errors сохранены.

Добавлен **21 тест**: audit text/caption/mask/callback/отсутствие chat/user, private guard до аудита,
per-chat ordering с параллельным другим chat, cleanup success/API/transport/load/remove/empty,
runtime-пути каталога команд/gettext, чтение JSON без рестарта, чистый async delivery use case,
независимый provider/REQUEST scope/model registry и прежний five-minute scheduler.
Root composition test дополнительно фиксирует middleware order и отдельные лимитеры/locks для двух
типов updates; main проверяет единственную регистрацию TelegramPlatformProvider.

Финальный gate:

- pytest: **514 passed, 9 skipped**; прежние восемь HTTP-тестов требуют simulations,
  корпусный тест — приватную выгрузку Eders;
- Ruff lint/format: **372 файла**; mypy strict: **256 source files**, без ошибок;
- все **255 подмодулей** импортируются; DDL **27 таблиц и индексов** совпал с baseline;
- Alembic: `No new upgrade operations detected.`;
- Index diagnostics 16 компонентов без ошибок, старых imports/удалённых helper usages нет;
- в 37 остальных исходных файлах изменились только imports;
- IDE build сообщает success с ограниченными diagnostics; основное доказательство — CLI gates.

Этап завершён. Команды/scopes/порядок handlers и middleware, FSM/callback payload, audit masks,
runtime-файлы, jobs и транзакционная семантика сохранены. Известные дефекты defaults/session finalization
не исправлялись. Далее — OBIS, затем Eders и Study week. Коммиты, push и deploy не выполнялись;
IDE auto-staging снят только с 64 известных task-путей, исходный index был пуст; `.DS_Store` сохранены.

### План следующего этапа: OBIS

Baseline: **514 passed, 9 skipped**, исходное дерево чистое кроме `.DS_Store`; сохранён DDL 27 таблиц.
Phase A переносит presentation, service/notification logic, AES-GCM, HTTP/parser, два snapshot repository/ORM
и polling job в modules/obis/. Provider сохраняет APP CryptoService/ObisClient и REQUEST остальных зависимостей.
Callback payload, FSM, format/HTML/plain-text pagination, scopes, HTTP/CSRF/redirect/timeout, snapshot SQL
и encryption serialization не меняются. HTTP проверяется локальной существующей Eders/OBIS simulation.

Phase B выделяет ObisCredentialsService с публичным dataclass-результатом для OBIS и Eders, чтобы Eders
не читал ORM/ciphertext и не расшифровывал пароль самостоятельно. Короткий repository OBIS владеет
credential columns существующего User без schema migration; get через AsyncSession сохраняет identity map.
Маркер Eders остаётся SHA-256 от ciphertext. Общий login/client factory получает публичные имена без
нового HTTP flow или persistent session. Polling получает application use case и Telegram sender boundary.

Обнаруженное расхождение с прежним описанием: первая непустая оценка уже порождает событие;
первая запись посещаемости остаётся silent baseline. Это фиксируется тестами, без bug fix в рефакторинге.

### Выполнено: OBIS

Phase A перенесла 13 реализаций в modules/obis/ через Index MCP. AST всех реализаций и callback-классов
совпал с baseline, кроме imports. ObisProvider сохраняет APP client/crypto и REQUEST остальных объектов;
root composition и тестовые контейнеры обновлены. Callback payload/FSM/password mask/plain-text pagination
не изменились. Целевой gate: **55 passed**, mypy strict. Полный gate после переноса: **542 passed, 5 skipped**
с включённой локальной OBIS/Eders simulation.

Phase B выделила ObisCredentialsRepository и ObisCredentialsService на неизменённой таблице User.
Facade ObisService сохранил публичные save/has/clear/get методы, делегируя credentials владельцу.
EdersService получает frozen read model с repr-disabled секретами и непрозрачным SHA-256(ciphertext) marker;
больше не читает ORM/ciphertext и не расшифровывает пароль. Два прежних способа exception chaining при
decryption failure сохранены: facade сохраняет cause, Eders подавляет его. Публичные ошибки — в errors.py.
Общие login/new_http_client функции публичны; их алгоритм, cookie flow, CSRF, redirects и 15s timeout прежние.

PollObisUser владеет per-user polling use case и suppress ожидаемых auth/parse ошибок. Реальный внешний
sender protocol отделяет Telegram locale/formatting/delivery. Job сохраняет recipient union, отдельные scopes,
locale lookup до fetch, порядок grades→attendance, hourly schedule и per-user failure boundary.
TelegramAPIError пропускается без retry; unexpected error aborts user, но не batch.

Добавлено **35 unit/DB/FSM/lifecycle тестов** и **5 HTTP-тестов**. Проверены verify-before-store, отсутствие
внешних вызовов без credentials, AES-GCM legacy format/random nonce, сохранность marker и secrets repr,
ошибки/exception chaining, первая оценка/attendance baseline, FSM/mask/password deletion, locale/API failures,
APP/REQUEST/model registry и scheduler. Existing first-nonempty-grade notification и assignment student_number
до encryption error зафиксированы; они не исправлены. Defaults/session-finalization defects также сохранены.

Локальный Postman mock переиспользован из postman/mocks/eders; две OBIS HTML fixtures построены из существующего
parser contract и содержат только синтетические данные. Mock дополнен read-only grades/attendance и режимами
login-denied/csrf-missing/HTTP500. Базовые Eders routes не менялись. Настоящий httpx client отправлял HTTP
в simulation на 127.0.0.1:4945; лог подтвердил OBIS login/read и Eders SSO/AJAX до и после переноса.
Использовались только fake credentials; реальный университетский сервис/аккаунты не вызывались.

Финальный gate:

- pytest с EDERS_SIMULATION_PORT=4945: **558 passed, 5 skipped**; пропущены четыре Food menu/Timetable HTTP-теста
  без их simulations и корпусный тест без приватной выгрузки Eders;
- целевой gate после Phase B: **114 passed**;
- Ruff lint/format: **384 файла**, mypy strict: **267 source files**, без ошибок;
- все **266 подмодулей** импортируются; DDL **27 таблиц и индексов** совпал с baseline;
- Alembic: `No new upgrade operations detected.`;
- Index diagnostics 17 компонентов без ошибок; старых/промежуточных imports и private factory usages нет;
- семь остальных исходных потребителей изменены только в imports; EdersService/client изменены на описанных границах;
- IDE build сообщает success с ограниченными diagnostics; основное доказательство — CLI gates и HTTP log.

Этап завершён. Далее — Eders и Study week. Simulation остановлена, временные логи оставлены вне repository;
IDE auto-staging снят только с известных task-путей, исходный index был пуст. Коммиты, push и deploy не выполнялись.
Три исходных `.DS_Store` сохранены.

### План следующего этапа: Eders

Baseline: **558 passed, 5 skipped** с локальной OBIS/Eders simulation; DDL 27 таблиц сохранён.
Phase A переносит 14 реализаций: application facade/tracking и модели снимка, persistence serialization,
HTTP/parser/URL validation, repository/ORM, Telegram router/keyboards/callbacks/formatter и polling job.
EdersProvider сохраняет APP client и REQUEST repository/services. Пустой legacy AppProvider удаляется;
RequestProvider пока сохраняет StudyWeekService. Старые import paths обновляются без compatibility wrappers.

Сохраняются OBIS→SSO→sesskey→AJAX, retry всего снимка ровно один раз, URL validation, JSON/defaults,
user-row FOR UPDATE до первого state, monotonic snapshots, account/schema baselines, event hashes,
порядок материала/напоминаний, ack только после успешного сообщения и per-user failure isolation.
Перед переносом дополняются characterization tests; AST Phase A сравнивается без imports.

Phase B отделяет PollEdersUser от Telegram sender: application координирует refresh/pending/ack,
adapter сохраняет locale lookup после refresh, форматирование всех сообщений до первой отправки,
группировку и TelegramAPIError per message. Job остаётся владельцем request scopes и per-user logging.
Tracking existence check использует публичный UsersQuery.exists; алгоритм observe/plan_events не переписывается.
Study week остаётся отдельным следующим этапом. Схема, каталоги переводов и HTTP-контракт не меняются.

### Выполнено: Eders

Phase A перенесла 14 реализаций средствами Index MCP в `modules/eders/`: application facade/filter/tracking/models,
infrastructure client/parser/URLs/serialization/repository/ORM, Telegram presentation и polling job.
До упрощения AST всех 14 тел совпал с HEAD, исключая imports. EdersProvider сохранил APP client и REQUEST
repository/services; пустой AppProvider удалён, legacy RequestProvider оставлен только для StudyWeekService.
Все root/test compositions обновлены. Полный gate после Phase A: **582 passed, 5 skipped**.

Phase B выделила PollEdersUser и TelegramEdersNotificationSender. Application сохраняет refresh→locale→pending,
затем отмечает каждый event сразу после успешного сообщения. Async iterator на внешней sender-границе позволяет
сохранить ack до следующей отправки и остановку при ack failure. Telegram adapter сначала форматирует все сообщения,
группирует материалы и пропускает TelegramAPIError без ack. Неожиданная ошибка прекращает пользователя, job логирует
её и продолжает следующий отдельный request scope. Получение списка ID также осталось в отдельном scope.
Tracking проверяет пользователя через существующий UsersQuery.exists; он выполняет прежний get_by_id.
Алгоритмы observe/plan_events, JSON, hashes, SQL locks/eligibility, default timing и HTTP/parser не менялись.

Добавлен **31 тест**: state lock/lookup/flush, формат JSON и legacy defaults, callback payloads всех значений,
monotonic observations, refresh/locale/pending failures и scopes, load failure, UsersQuery rejection,
credential eligibility, частичный success/API/transport/ack failures, eager formatting, локаль и APP/REQUEST/model registry.
Existing tests продолжают проверять deduplication, pending retry, account/schema baselines, группировку и Settings return path.

Финальный gate:

- pytest с EDERS_SIMULATION_PORT=4945: **589 passed, 5 skipped**; четыре Food menu/Timetable HTTP-теста
  требуют своих simulations, корпусный тест — приватную выгрузку Eders;
- Ruff lint/format: **392 файла**; mypy strict: **274 source files**, без ошибок;
- все **273 подмодуля** импортируются; DDL **27 таблиц и индексов** совпал с baseline;
- Alembic: `No new upgrade operations detected.`;
- Index diagnostics 20 компонентов без ошибок; старых Python imports и AppProvider usages нет;
- IDE build сообщает success с ограниченными diagnostics; основное доказательство — CLI gates.

Существующая локальная Postman simulation переиспользована без изменения mock/HTTP-контракта.
Реальный httpx прошёл OBIS login→SSO→profile→AJAX pagination→course/details; проверены HTTP500,
invalid JSON и session-expired retry. Лог подтвердил эти запросы до и после переноса, включая AJAX 200/302/500.
Использовались только fake credentials, настоящие university endpoints/accounts не вызывались.

Этап завершён; далее — отдельный Study week. Схема и данные, публичные команды, callback/FSM, локали,
scopes, scheduler и transaction/default defects сохранены. Коммиты, push и deploy не выполнялись.
Simulation остановлена; IDE auto-staging снят с 36 проверенных task-путей при исходно пустом index.
Три исходных `.DS_Store` сохранены. Финальная AST-проверка подтвердила неизменность 12 реализаций и пяти
исходных потребителей без imports; в tracking изменились только constructor/existence boundary, отдельно от job extraction.

### План следующего этапа: Study week

Рабочее дерево чистое кроме трёх исходных `.DS_Store`; сохранён DDL 27 таблиц.
StudyWeekService/DTO и formatter пока находятся в services/, а `/week` фактически зарегистрирован последним
handler в Eders router. Отдельного legacy router Study week нет; прежнее описание этого места уточняется.

Phase A собирает небольшой плоский `modules/study_week/`: application.py, formatter.py, router.py, provider.py.
Provider переносится из последнего legacy di.py, сохраняет REQUEST scope; root/test containers обновляются.
Handler переносится без изменения тела и private flag, новый router регистрируется сразу после Eders.
Eders больше не зависит от Study week; orchestration зависит от application-результатов Eders и Schedule.

До переноса фиксируются последовательность Eders→Schedule, отсутствие подписок, propagation ошибок,
семь календарных дней от текущей даты Bishkek, UTC/local boundaries, стабильный порядок событий,
HTML escaping/truncation/chunking, сообщения и ошибки `/week`. Phase A сверяется по AST и тем же тестам.

Phase B переименовывает односценарный StudyWeekService.get_week в GetStudyWeek.execute без дополнительной обёртки.
Ошибки Eders получают публичный errors.py: Study week presentation не должна импортировать HTTP/parser internals.
Алгоритмы объединения/форматирования, gettext keys, SSO/HTTP, FSM, callbacks, схема и данные не меняются.
Чистые dataclass/helper-функции сохраняются; новые repository/Protocol/DI abstractions не вводятся.

### Выполнено: Study week

Исходный полный gate без simulations: **580 passed, 14 skipped**. Девять Eders/OBIS HTTP-тестов затем включены
через существующую локальную Postman simulation. До source edits добавлены 22 characterization-сценария;
исходный DDL 27 таблиц сохранён. Рабочее дерево было чистым кроме трёх `.DS_Store`.

Phase A собрала плоский `modules/study_week/`: application.py, formatter.py, router.py, provider.py.
Application/formatter и последний legacy di.py перенесены через Index MCP; provider переименован в StudyWeekProvider.
`/week` извлечён из конца Eders router и зарегистрирован сразу после него. Тела двух файлов и полного handler
с декораторами совпали с HEAD по AST без imports. Все root/test containers обновлены, в том числе subprocess composition.
Полный gate после Phase A: **611 passed, 5 skipped**; mypy strict без ошибок.

Phase B переименовала односценарный StudyWeekService.get_week в GetStudyWeek.execute; лишнего фасада нет.
StudyWeekProvider сохраняет REQUEST scope. Eders больше не импортирует Study week.
Четыре прежних exception-класса Eders собраны в публичном errors.py; Study week и остальные потребители
не импортируют их через HTTP/parser internals. Классы и HTTP/URL/parser algorithms сохранены по AST.
Отброшенный time-key генератора formatter переименован из `_` в `_time`, чтобы не смешивать его с gettext alias.
Динамический test clock заменяет module globals через monkeypatch.setitem; PyCharm diagnostics теперь чистые.

Финальная AST-проверка допускает только описанные imports/names; тела сценария, formatter, handler,
провайдера и exception-классов эквивалентны исходным. NoTrackedCoursesError остаётся единственной подавляемой
ошибкой источника. Дата берётся после Eders→Schedule из текущего Bishkek clock, не из snapshot.fetched_at.
Семь локальных дней, sort order, HTML escaping/truncation/chunking, partial delivery failures и eders.* msgids сохранены.

Добавлено **24 теста**: источник/порядок чтений/date/отсутствие подписок, propagation ошибок, UTC/local boundaries,
submitted/conflict/unverified/material behavior, сортировка, HTML и chunks во всех пяти языках,
все ожидаемые ошибки `/week`, loading/no-sender/success/unexpected/partial delivery, command/private flag и REQUEST lifecycle.
Root composition дополнительно фиксирует единственный Study week router сразу после Eders и до Settings.

Финальный gate:

- pytest с EDERS_SIMULATION_PORT=4945: **613 passed, 5 skipped**; четыре Food menu/Timetable HTTP-теста
  требуют собственных simulations, корпусный Eders тест — приватную выгрузку;
- целевой gate: **127 passed**;
- Ruff lint/format: **396 файлов**, mypy strict: **277 source files**, без ошибок;
- все **276 подмодулей** импортируются; DDL **27 таблиц и индексов** совпал с baseline;
- Alembic: `No new upgrade operations detected.`;
- Index diagnostics 14 компонентов без ошибок после уточнения двух имён/динамического clock mock;
- локальные Markdown link targets существуют; `git diff --check` чист;
- IDE build сообщает success с ограниченными diagnostics; основное доказательство — CLI gates.

Postman mock/контракт не менялись. Настоящий httpx прошёл локальные OBIS→SSO→AJAX→HTML routes;
лог подтверждает обычные ответы, AJAX 302/500, OBIS read 500 и session retry. Использованы только fake credentials;
настоящие university endpoints/accounts не вызывались. Известные transaction/default defects не исправлялись.

Этап Study week и план feature-переноса завершены. Общие timezone/text helpers остаются в services/;
пустые исторические package initializers не затрагивались. Коммиты, push и deploy не выполнялись.
Simulation остановлена; IDE auto-staging снят с 10 проверенных task-путей при исходно пустом index.
Три исходных `.DS_Store` сохранены; изменения остаются в рабочем дереве для review.

### Отдельное исправление: rollback при ошибке REQUEST scope

После feature-переносов исправлен ранее сохранённый дефект транзакций. Installed Dishka передаёт exception
через agen.asend(exception), а не athrow(); прежний yield session игнорировал это значение и выполнял commit.
Сначала существующий Feedback composition test изменён на ожидаемый rollback и воспроизвёл лишний commit.
Новые PostgreSQL-тесты подтвердили, что flushed row действительно оставалась после ошибки и отмены тела scope.

CoreProvider.get_session теперь имеет явный AsyncGenerator[AsyncSession, BaseException | None] и учитывает
полученное исключение. Нормальное завершение выполняет commit, вышедшая из scope ошибка/отмена — rollback.
Ошибка/отмена самого commit также вызывает rollback с последующим пробросом. Rollback failure не повторяется
и не скрывается: Dishka сообщает cleanup ExceptionGroup, исходная ошибка тела остаётся в exception context.
Session закрывается во всех проверенных исходах. Ошибки, пойманные внутри scope, по-прежнему допускают commit.

Добавлено **11 регрессионных тестов**, прежний Feedback composition test теперь проверяет исправленное поведение.
Покрыты RuntimeError/CancelledError тела, настоящая task.cancel(), caught error, commit error/cancellation,
rollback failure и порядок rollback→close→aiogram error handler. Три PostgreSQL-сценария используют реальные
savepoints: отмена/ошибка убирает flushed row, соседние успешные запросы сохраняются, IntegrityError на commit
откатывает неудачный savepoint и не мешает следующему запросу. Внешняя тестовая транзакция всегда откатывается.

Проверки:

- целевые Core/Feedback проверки: **20 passed**;
- полный pytest с локальной OBIS/Eders simulation: **624 passed, 5 skipped**;
  пропуски прежние: четыре Food menu/Timetable HTTP-теста без их simulations и приватный корпус Eders;
- Ruff lint/format: **397 файлов**, mypy strict: **277 source files**, без ошибок;
- Alembic: `No new upgrade operations detected.`; ORM, схема и migrations не менялись;
- Index diagnostics трёх изменённых Python-файлов без ошибок; `git diff --check` чист;
- IDE build сообщает success с ограниченными diagnostics; основное доказательство — pytest/CLI gates;
- существующий Postman mock не менялся; лог подтвердил локальный OBIS login/read и Eders SSO/AJAX 200/302/500.
  Настоящие университетские endpoints/аккаунты не использовались.

Изменение находится только в session provider; feature workflows, middleware order и настройки уведомлений не менялись.
Документы AGENTS/CLAUDE/ARCHITECTURE теперь описывают исправленный lifecycle; прежние записи выше остаются историей.
Коммиты, push и deploy не выполнялись. Следующий отдельный дефект — timing defaults первого переключения уведомлений.

### Отдельное исправление: первое переключение уведомлений

У новых ORM-объектов значения mapped_column(default=True) применялись при INSERT, а не при создании.
NotificationSettingsService возвращал None в initial summary и выполнял not None→True при первом toggle.
Food menu показывал отсутствие строки как включённые обед/ужин, но первый toggle создавал строку с None
и оставлял выбор включённым. Переключение всего нового дня было затронуто той же причиной.

До исправления пять обновлённых characterization-сценариев воспроизвели неверные defaults/первый toggle.
NotificationSettingsRepository теперь явно задаёт True для трёх флагов при создании строки;
FoodMenuNotificationSettingsRepository — для lunch_enabled/dinner_enabled. Другие пути создания этих моделей
в production-коде отсутствуют. Services, callback payloads и handlers не менялись; лишних flush/commit нет.
ORM/server defaults остаются True, схема и существующие пользовательские настройки не изменяются.

Добавлено **11 регрессионных тестов**, пять прежних characterization-сценариев проверяют исправленное поведение.
Проверены начальная клавиатура Notifications, первое выключение каждого из трёх флагов, callback→реальный
service→PostgreSQL→клавиатура и сохранность после commit/expire/reload. Для Food menu проверены первое
переключение обеда/ужина, целого дня и каждого приёма пищи за всю неделю, повторное включение и сохранность
чужих дней. Реальные handlers показывают ✅ до первого клика и ❌ после него для обоих приёмов пищи.
Existing recipient/default opt-in, enable_all/disable_all и неизвестный пользователь также покрыты целевым набором.

Проверки:

- Notifications/Food menu целевые тесты: **61 passed**;
- полный pytest с локальной OBIS/Eders simulation: **635 passed, 5 skipped**;
  пропуски прежние: четыре Food menu/Timetable HTTP-теста без их simulations и приватный корпус Eders;
- Ruff lint/format: **397 файлов**, mypy strict: **277 source files**, без ошибок;
- Alembic: `No new upgrade operations detected.`; миграция и backfill не требуются;
- Index diagnostics обоих repository и Notifications tests без ошибок. В Food menu tests IDE отмечает
  существующую строку monkeypatch.setattr(jobs, "TelegramFoodMenuSender", ...); соответствующая test-функция
  не менялась по AST, runtime-тест проходит. Это не ошибка нового кода;
- IDE build сообщает success с ограниченными diagnostics; основное доказательство — CLI gates;
- `git diff --check` чист. Postman mock/HTTP-контракт не менялись; локальный лог подтверждает OBIS login/read
  и Eders SSO/AJAX 200/302/500. Настоящие университетские endpoints/аккаунты не использовались.

Документы AGENTS/CLAUDE/ARCHITECTURE обновлены; старые записи сохранены как история этапов.
Изменение ограничено двумя repository и проверками настроек; незавершённой работы в этом исправлении нет.
Коммиты, push и deploy не выполнялись.

### План уборки: helpers, пустые пакеты и тесты

Пользователь выбрал только косметическую доводку. Runtime-алгоритмы, зависимости, схема, HTTP-контракт и поведение
OBIS/уведомлений не меняются. Исходное дерево чистое кроме трёх `.DS_Store`; коллекция тестов сохраняется до переносов.

Общий BISHKEK_TZ переносится из services/time_utils.py в core/time.py. fold_turkish используется только двумя
application-компонентами Schedule, поэтому принадлежит modules/schedule/application/text_normalization.py.
После проверки отсутствия потребителей удаляются пустые legacy bot/, repositories/, scraping/ и services/.

54 тестовых модуля группируются в tests/modules/<feature>/, tests/core/ и tests/platform/{telegram,i18n}/.
Имена файлов и тестов сохраняются. tests/conftest.py продолжает владеть PostgreSQL transaction/savepoint fixtures;
данные остаются в tests/fixtures/, поскольку их переиспользуют HTTP-моки. Корни ресурсов получают единый tests/paths.py.
Прямые импорты из test_eders_tracking заменяются общим factory-модулем; одинаковая tracking fixture принадлежит
локальному Eders conftest.py. Package initializers нужны для штатных Python imports, sys.path не изменяется вручную.

Проверки: одинаковая коллекция тестов без учёта нового directory prefix, AST runtime/тестовых сценариев,
полный pytest, Ruff, mypy, Alembic, import walk и актуальность текущих команд/путей в документации.

### Выполнено: helpers, пустые пакеты и тесты

Baseline с существующей локальной OBIS/Eders simulation: **635 passed, 5 skipped**. До изменений сохранена
коллекция **640 тестовых случаев**. Дерево было чистым кроме трёх пользовательских `.DS_Store`.

Через Index MCP перенесены BISHKEK_TZ в `core/time.py` и fold_turkish в
`modules/schedule/application/text_normalization.py`. Первый используется несколькими features и scheduler,
второй — только Schedule. Оба файла побайтно совпадают с исходными; в 12 runtime-потребителях изменились только imports.
После проверки отсутствия потребителей удалены шесть пустых package initializers и каталоги legacy
bot/routers, bot/keyboards, bot, repositories, scraping, services; удалены только их сгенерированные pyc-файлы.

54 тестовых файла перенесены через Index MCP без переименования: 13 feature-пакетов в tests/modules/,
Core в tests/core/, Telegram/i18n в tests/platform/. tests/conftest.py и исходные data fixtures сохранены.
Новые test package initializers обеспечивают обычные Python imports; pyproject, зависимости и sys.path не менялись.
tests/paths.py задаёт устойчивые PROJECT_ROOT/FIXTURES_DIR. Пять resource-dependent тестовых модулей получили
новые anchors; проверки runtime checkout/Docker-like layouts и Babel работают с теми же файлами, что раньше.

Общие Eders NOW/item вынесены в factories.py, одинаковая tracking fixture — в локальный conftest.py.
Импортов из test_eders_tracking больше нет. Factory и typed fixture совпали с исходными по AST;
AST всех 54 тестовых модулей совпал с baseline после исключения imports, перенесённых helpers и замены resource anchors.
Нормализованная коллекция из 640 случаев совпала полностью, включая parameter IDs; ни один тест не потерян и не добавлен.

Проверки:

- полный pytest в новой структуре: **635 passed, 5 skipped**, как до переноса;
  пропуски прежние: четыре Food menu/Timetable HTTP-теста без их simulations и приватный корпус Eders;
- Ruff lint/format: **413 файлов**; mypy strict: **271 source files**, без ошибок;
- все **270 подмодулей приложения** импортируются; старых legacy packages и imports нет;
- Alembic: `No new upgrade operations detected.`; ORM и migrations не менялись;
- Index diagnostics helpers/test support и остальных проверенных moved files без ошибок, кроме прежних
  IDE inspections в неизменённых тестовых сценариях: dynamic new_http_client monkeypatch и Babel Message.id typing;
  их runtime-тесты проходят, сценарии совпали по AST. Никаких suppressions или несвязанных исправлений не добавлялось;
- IDE build сообщает success с ограниченными diagnostics; основное доказательство — CLI gates;
- `git diff --check` чист; текущие Markdown links и Python test paths разрешаются;
- существующая Postman simulation переиспользована без изменения mock/контракта. HTTP-тесты после переносов
  прошли; реальные university endpoints/accounts не вызывались.

AGENTS/CLAUDE/ARCHITECTURE, Eders testing commands и Postman context test paths обновлены.
Исторические записи MIGRATION сохраняют пути соответствующего этапа. Уборка завершена без изменения
runtime-алгоритмов, транзакций, настроек, локалей и внешнего поведения. Коммиты, push и deploy не выполнялись.
Simulation остановлена; IDE auto-staging снят со 140 проверенных task-путей при исходно пустом index.
Три исходных `.DS_Store` сохранены; изменения остаются в рабочем дереве для review.

### План: убрать реэкспорт db.models

Пользователь попросил обойтись без общего фасада всех ORM-классов. Уже staged изменения предыдущей уборки
сохраняются; index snapshot и DDL 27 таблиц сохранены отдельно перед новым этапом.
Обычные потребители переходят с db.models на owning ORM modules. Глобальный реэкспорт и пустой models-пакет удаляются.

Строковые relationships и Alembic по-прежнему требуют регистрации полной модели. Явный bootstrap.load_models
загружает ORM и конфигурирует mappers; функция вызывается в main bootstrap, alembic/env.py и tests/conftest.py.
Импорт отдельной feature больше не должен неявно подтягивать все 27 таблиц. Автопоиск, новый DI provider и generic
registry abstractions не вводятся. Bootstrap module не экспортирует конкретные ORM-классы.
По уточнённому запросу пользователя удаляется весь пакет db, а не только models: Base/engine/session
остаются в core/database.py, регистрация ORM принадлежит корневому composition bootstrap.py.

Проверки: cold-process import/load, полный metadata/relationships, idempotence, startup before resources,
baseline DDL, Alembic, полный pytest и strict checks. Runtime-алгоритмы и модель данных сохраняются.

### Выполнено: полностью удалён пакет db

Исходный gate: **635 passed, 5 skipped** с локальной OBIS/Eders simulation. До изменений сохранены DDL
27 таблиц/индексов и исходный index: пользователь уже staged предыдущую уборку, её записи не изменяются.
Cold-process regression сначала воспроизвела скрытый side effect: импорт Users repository загружал всю схему.

Все 55 потребителей прежнего фасада переведены на owning ORM imports или bootstrap. db/models/__init__.py
с __all__ удалён; по уточнённому запросу удалён и весь db package. Base, engine/session factories остаются в
core/database.py, ORM-классы — в features и platform. Ни модели, ни схема не перемещались.

Корневой bootstrap.py предоставляет load_models(): явные импорты внутри функции регистрируют модели,
затем Base.registry.configure() разрешает строковые relationships. Конкретные классы не появляются в namespace
bootstrap и не экспортируются. Функция вызывается в main() до ресурсов, в alembic/env.py до target_metadata
и в tests/conftest.py. Core не зависит от feature registry; standalone compositions используют тот же explicit bootstrap.
Автопоиска модулей, новых DI abstractions или дополнительных зависимостей нет. F401 в bootstrap отключён адресно
для намеренных registration imports, без type suppressions.

В 27 runtime-потребителях изменились только imports, что подтверждено AST относительно исходного index.
В main/alembic/test entry points добавлен только вызов load_models(). Старые assertions identity между facade
и owning model удалены; metadata/DI lifecycle assertions сохранены. Изолированные Users import-тесты теперь
проверяют отсутствие полной схемы до bootstrap и корректную регистрацию после него.

Добавлены три проверки: полный cold-start metadata/relationships без reexports, idempotent registration
с отсутствующим db package, и ошибка model setup до создания Bot/container. Existing шесть main lifecycle cases
также проверяют вызов bootstrap. User↔Course и DailyMenu→Dish relationships, association FK и все 27 таблиц проверены
в отдельном процессе; прогретые pytest imports не могут скрыть ошибки model registration.

Финальные проверки:

- целевой Core/Users gate: **34 passed**;
- полный pytest: **638 passed, 5 skipped**; прежние четыре Food menu/Timetable HTTP-теста требуют своих simulations,
  корпусный Eders тест — приватную выгрузку;
- Ruff lint/format: **413 файлов**, mypy strict: **270 source files**, без ошибок;
- DDL всех **27 таблиц и индексов** совпал с baseline; Alembic: `No new upgrade operations detected.`;
- все **269 подмодулей приложения** импортируются, db package физически отсутствует;
- Index diagnostics исходников, Alembic, conftest и cold-bootstrap tests без ошибок. test_main.py сохраняет
  IDE inspections для стандартных monkeypatch.setattr(module, "name", ...) targets; runtime-тесты проходят;
- IDE build сообщает success с ограниченными diagnostics; основное доказательство — CLI gates;
- `git diff --check` чист, текущие doc links/test paths разрешаются, старых db imports нет;
- существующий Postman mock/контракт не менялся; HTTP-лог подтвердил OBIS login/read и Eders SSO/AJAX 200/302/500.
  Настоящие university endpoints/accounts не использовались.

AGENTS/CLAUDE/ARCHITECTURE описывают imports у владельцев и explicit bootstrap вместо db facade.
Пакет db удалён полностью, незавершённой работы в этом изменении нет. Коммиты, push и deploy не выполнялись.
