# Поэтапный переход к функциональным модулям

## Границы работы

Основание: `TASK.md`. Перенос выполняется по одной функциональной области, без изменения бизнес-поведения,
схемы PostgreSQL, callback payload, имён состояний FSM, переводов и форматов сохранённых данных.
Этот документ фиксирует анализ до изменения исходников и результаты завершённых этапов.

Актуальный статус на 25 октября 2026 года: перенесены **Feedback**, **Advertisements**, **Student questions**, **Versions** и **Donations**.
В Users отдельно выделена публичная read-граница; вся область пользователей пока не перенесена.
Общий gate зелёный: **358 passed, 5 skipped**, Ruff, mypy и проверка Alembic проходят.
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
