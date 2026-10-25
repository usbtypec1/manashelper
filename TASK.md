Ты работаешь с существующим production-like Python-проектом **Manashelper**.

Это не greenfield-проект и не задача «переписать всё красиво». Требуется провести **постепенный архитектурный рефакторинг без функциональных регрессий**, сохранив текущее внешнее поведение приложения.

# Главная цель

Перевести проект с преимущественно горизонтальной структуры:

```text
bot/routers/
services/
repositories/
db/models/
scraping/
jobs/
```

на **Vertical Slice Architecture / modular monolith**, где код в первую очередь группируется по функциональной области:

```text
modules/
├── users/
├── schedule/
├── food_menu/
├── obis/
├── eders/
├── study_week/
├── advertisements/
├── feedback/
├── notifications/
└── ...
```

При этом внутри достаточно сложной feature разрешено использовать слои:

```text
feature/
├── presentation/
├── application/
├── domain/
└── infrastructure/
```

Но НЕ создавай эти четыре директории механически для каждой маленькой feature.

Если feature состоит из 2–4 небольших файлов, допустима плоская структура:

```text
feedback/
├── router.py
├── service.py
├── repository.py
└── provider.py
```

Архитектура должна масштабироваться вместе со сложностью feature, а не создавать boilerplate заранее.

---

# Вторая важная цель: сделать код Pythonic

Проект исторически является портом Java-проекта, поэтому часть дизайна и стиля кода осталась Java-oriented.

Во время рефакторинга необходимо не просто перемещать файлы, но и постепенно заменять Java-style решения на идиоматичный современный Python 3.13.

При этом нельзя менять бизнес-поведение только ради stylistic cleanup.

Следуй принципу:

```text
preserve behavior → improve structure → simplify implementation
```

а не:

```text
rewrite everything → hope tests pass
```

---

# Текущий стек, который нужно сохранить

Используется:

```text
Python 3.13+
asyncio
aiogram 3
SQLAlchemy 2 async
asyncpg
PostgreSQL
Alembic
Dishka
APScheduler 3
httpx.AsyncClient
BeautifulSoup / lxml
pydantic-settings
gettext / Babel
cryptography / AES-GCM
pytest
pytest-asyncio
Ruff
mypy strict
uv
Docker
```

Не заменяй технологии без объективной архитектурной необходимости.

В частности НЕ нужно самовольно:

```text
- заменять Dishka
- заменять SQLAlchemy
- заменять APScheduler
- переходить на другую Telegram library
- вводить Celery
- вводить Kafka/RabbitMQ
- вводить Redis
- разбивать приложение на микросервисы
```

---

# Ключевой принцип новой структуры

На верхнем уровне код группируется по **business capability / feature**, а не по техническому слою.

Плохо:

```text
routers/schedule.py
services/schedule.py
repositories/schedule.py
models/schedule.py

routers/eders.py
services/eders.py
repositories/eders.py
models/eders.py
```

Хорошо:

```text
modules/
├── schedule/
│   ├── presentation/
│   ├── application/
│   ├── domain/
│   └── infrastructure/
│
└── eders/
    ├── presentation/
    ├── application/
    ├── domain/
    └── infrastructure/
```

Главный вопрос при размещении файла:

> К какой функциональной области принадлежит этот код?

И только после этого:

> Какую роль он выполняет внутри этой области?

---

# Желаемая зависимость слоёв

Для сложных feature придерживайся направления:

```text
Presentation
    ↓
Application
    ↓
Domain
    ↑
Infrastructure
```

Интерпретация:

```text
presentation
```

знает о Telegram / aiogram;

```text
application
```

описывает сценарии использования приложения;

```text
domain
```

содержит бизнес-правила и модели там, где они действительно нужны;

```text
infrastructure
```

содержит SQLAlchemy, PostgreSQL, HTTP, HTML parsing и другие технические реализации.

---

# Presentation layer

В presentation разрешены:

```text
aiogram Router
Message
CallbackQuery
FSMContext
Telegram keyboards
Telegram-specific formatting
HTML formatting for Telegram
callback_data
states
```

Например:

```python
@router.message(Command("schedule"))
async def schedule(
    message: Message,
    use_case: FromDishka[GetTodaySchedule],
) -> None:
    result = await use_case.execute(message.from_user.id)
    await message.answer(format_schedule(result))
```

Application/domain/infrastructure не должны принимать:

```python
Message
CallbackQuery
FSMContext
Router
```

если это не строго обоснованный Telegram adapter.

---

# Application layer

Постепенно откажись от большого количества generic `*Service`-классов в пользу **use cases / application services**.

Вместо:

```text
AdvertisementService
EdersService
FoodMenuService
ScheduleService
```

предпочитай сценарии:

```text
CreateAdvertisement
ApproveAdvertisement
DeleteAdvertisement

GetTodaySchedule
SearchLessons
SyncTimetable

GetDailyMenu
RateDailyMenu
SyncFoodMenu

GetEdersAssignments
GetEdersMaterials
RefreshEdersSnapshot
TrackEdersChanges
```

Не нужно искусственно превращать каждый метод в отдельный класс.

Если несколько операций являются одной связной application responsibility, они могут оставаться вместе.

Основная цель:

- избегать god-service;
- сделать зависимости сценария явными;
- уменьшить количество неявного coupling;
- упростить тестирование.

---

# CQRS-lite допустим, framework не нужен

Можно концептуально разделять:

```text
commands/
queries/
```

например:

```text
commands:
CreateAdvertisement
ApproveAdvertisement
RateMenu
SaveObisCredentials

queries:
GetAdvertisements
GetTodaySchedule
GetDailyMenu
GetEdersAssignments
```

Но НЕ вводи без необходимости:

```text
CommandBus
QueryBus
Mediator framework
Event Bus
Event Store
Event Sourcing
```

Простого:

```python
await approve_advertisement.execute(...)
```

достаточно.

---

# Domain layer

Не внедряй Enterprise DDD boilerplate ради самого DDD.

Domain должен появляться там, где существуют реальные бизнес-инварианты.

Допустимы:

```text
entities
value objects
domain enums
domain errors
business rules
ports
```

только когда они упрощают модель.

Не создавай автоматически:

```text
AggregateRoot
DomainService
Specification
Factory
RepositoryInterface
DomainEvent
```

для каждой таблицы.

Для простого CRUD отдельный domain layer вообще может быть не нужен.

---

# Infrastructure layer

Сюда должны постепенно перемещаться:

```text
SQLAlchemy repositories
ORM models
HTTP clients
HTML parsers
external integrations
serialization tied to persistence/external protocols
```

Например глобальный:

```text
scraping/
```

нужно постепенно демонтировать.

Вместо:

```text
scraping/eders_client.py
scraping/eders_parser.py
scraping/obis_client.py
scraping/obis_parser.py
```

предпочтительно:

```text
modules/eders/infrastructure/client.py
modules/eders/infrastructure/parser.py

modules/obis/infrastructure/client.py
modules/obis/infrastructure/parser.py
```

---

# ORM-модели

Постепенно colocation ORM-моделей допускается и приветствуется:

```text
modules/advertisements/infrastructure/orm.py
modules/schedule/infrastructure/orm.py
modules/eders/infrastructure/orm.py
```

Общие SQLAlchemy infrastructure-компоненты должны оставаться глобальными:

```text
core/database/base.py
core/database/engine.py
core/database/session.py
```

Alembic должен продолжать корректно видеть всю metadata.

Перед перемещением ORM-моделей обязательно проверь:

```text
Alembic imports
relationships
string references
metadata registration
tests
runtime imports
```

---

# Репозитории

Не создавай generic Java-style abstractions вида:

```python
class BaseRepository(Generic[T]): ...
```

если они не дают измеримой пользы.

Не вводи:

```python
IUserRepository
IAdvertisementRepository
IScheduleRepository
```

только потому, что repository существует.

Protocol/ABC имеет смысл преимущественно на реальной архитектурной границе:

```text
OBIS
Eders
Telegram sender
external timetable source
external food menu source
filesystem
other remote systems
```

Для обычного SQLAlchemy repository concrete dependency допустима.

---

# Jobs

Это важное архитектурное правило.

Background jobs НЕ должны реализовывать бизнес-сценарий сами.

Целевая зависимость:

```text
APScheduler job
      ↓
application use case
      ↓
repository / gateway
```

Плохо:

```text
job
 ↓
repository
```

если job начинает самостоятельно реализовывать application logic.

Job должен быть максимально тонким entry point.

Например:

```python
async def poll_eders_job(
    use_case: PollEders,
) -> None:
    await use_case.execute()
```

Это позволит вызывать один сценарий из:

```text
Telegram
APScheduler
CLI
tests
future API
```

без дублирования логики.

---

# Cross-feature dependencies

Feature не должна напрямую лазить в internals другой feature.

Плохо:

```python
EdersService(
    schedule_repository: ScheduleRepository,
)
```

Если сценарий объединяет несколько business capabilities, создай orchestration feature/use case.

Например:

```text
modules/study_week/
    application/
        get_study_week.py
```

которая зависит от публичных application/query interfaces:

```text
ScheduleQuery
EdersQuery
```

Схема:

```text
       StudyWeek
       /       \
      ↓         ↓
 Schedule     Eders
```

а не:

```text
Schedule → Eders → Schedule
```

---

# Public API feature

По возможности у каждой крупной feature должна быть понятная публичная поверхность.

Внешний код не должен импортировать случайные internals:

```python
from manashelper.modules.eders.infrastructure.repository import ...
```

если он относится к другой feature.

Предпочитай зависимости через application-level types/use cases.

Не обязательно сейчас создавать `api.py` для каждого модуля, но архитектура должна позволять сделать границы feature очевидными.

---

# Shared

`shared/` использовать крайне осторожно.

Правило:

> Если код используется только одной feature, он принадлежит этой feature.

`shared/` не должен стать новым `utils/` или новым `services/`.

Допустимы действительно общие primitives:

```text
datetime helpers
small generic types
pagination primitives
generic text utilities
```

Но перед переносом чего-либо в shared сначала проверь, действительно ли это используется несколькими независимыми feature.

---

# Pythonic refactoring

Проект был портирован с Java, поэтому отдельно ищи Java-like patterns.

Исправляй их только если можешь доказать эквивалентность поведения тестами.

## Избегай Java-style getters/setters

Плохо:

```python
class User:
    def get_name(self) -> str:
        return self._name

    def set_name(self, value: str) -> None:
        self._name = value
```

Предпочитай обычные attributes/dataclasses/properties.

---

## Используй dataclass там, где это data carrier

Например DTO/result models:

```python
@dataclass(frozen=True, slots=True)
class LessonView:
    subject: str
    teacher: str
    room: str
```

Но не добавляй `slots=True` механически, если код зависит от динамических attributes, inheritance или других несовместимых возможностей.

---

## Предпочитай Enum/StrEnum

Если значение является закрытым набором состояний:

```python
class AdvertisementStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"
```

вместо набора строковых констант.

---

## Используй structural pattern matching только там, где он улучшает код

Не заменяй каждый `if` на `match`.

---

## Предпочитай EAFP вместо чрезмерного LBYL

Python style:

```python
try:
    ...
except SomeExpectedError:
    ...
```

часто предпочтительнее длинных pre-check chains.

Но не используй exceptions для нормального control flow без необходимости.

---

## Context managers

Используй:

```python
async with ...
with ...
```

для lifecycle management вместо ручного:

```text
open
try
finally
close
```

где это возможно.

---

## Iteration

Избавляйся от Java-style index loops:

```python
for i in range(len(items)):
    item = items[i]
```

если можно:

```python
for item in items:
```

или:

```python
for index, item in enumerate(items):
```

---

## Collections

Используй comprehensions, generator expressions, `any`, `all`, `next`, `sum`, `min`, `max` там, где это повышает читаемость.

Но не превращай сложную бизнес-логику в огромные однострочные comprehensions.

---

## None

Не создавай Java-like Optional wrappers.

Используй:

```python
User | None
```

и естественную обработку `None`.

---

## Type hints

Используй современный Python syntax:

```python
list[str]
dict[str, int]
User | None
```

а не legacy:

```python
List[str]
Dict[str, int]
Optional[User]
```

кроме случаев, необходимых для совместимости.

---

## Protocol вместо Java-interface

Когда реально нужна structural abstraction, предпочитай:

```python
class TimetableSource(Protocol):
    async def fetch(...): ...
```

вместо Java-inspired interface hierarchy.

Но Protocol нужен только на реальных boundaries.

---

## Functions вместо классов

Если класс:

```text
- не имеет состояния;
- не управляет lifecycle;
- имеет один trivial method;
- существует только ради Java-style organisation;
```

рассмотри замену обычной функцией.

Например formatter почти всегда может быть функцией.

Не превращай use cases в функции механически: constructor injection через Dishka может делать небольшой callable object более удобным.

---

## Исключения

Не создавай глубокую Java-style hierarchy вида:

```text
ApplicationException
  ServiceException
    UserServiceException
      UserNotFoundServiceException
```

Используй небольшое количество осмысленных domain/application exceptions.

---

## `@staticmethod`

Если метод не использует `self` и не является частью meaningful class abstraction, скорее всего это должна быть module-level function.

---

## DTO mapping

Избегай Java-style цепочек:

```text
ORM
→ Entity
→ DTO
→ ResponseDTO
→ ViewModel
→ FormatterModel
```

если между ними нет реальной семантической границы.

Для read/query path допустимо возвращать специализированный immutable read model напрямую.

---

## Constructors

Избегай огромных service constructors с 10–15 dependencies.

Если это происходит, сначала проверь, не является ли класс god-service и не следует ли разбить его на несколько use cases.

---

## Utility classes

Не создавай:

```python
class StringUtils:
    @staticmethod
    def normalize(...):
        ...
```

Используй:

```python
def normalize(...):
    ...
```

на уровне модуля.

---

# Async rules

Не блокируй event loop.

Проверяй все новые/изменённые операции на наличие:

```text
sync HTTP
blocking filesystem
CPU-heavy parsing
sleep()
```

в async flow.

Используй async API, а если библиотека неизбежно blocking — выноси вызов через подходящий механизм только при необходимости.

Не добавляй `async` функциям, которым асинхронность не нужна.

Не создавай background `asyncio.create_task()` без чёткого ownership/lifecycle/error handling.

---

# Transactions

Сейчас lifecycle `AsyncSession` и commit/rollback управляется DI REQUEST scope.

Не вводи Unit of Work только ради Clean Architecture.

Сначала сохрани существующую transactional semantics.

Если конкретный use case объективно требует явной transaction boundary, задокументируй причину до внедрения UoW.

---

# Telegram boundaries

Application logic не должна:

```text
send messages
edit messages
answer callback queries
create keyboards
know Telegram HTML
operate FSMContext
```

если это можно оставить в presentation.

Если application use case должен инициировать уведомление, предпочитай abstraction вроде:

```python
class NotificationSender(Protocol): ...
```

только если это реальная архитектурная необходимость.

Не делай Protocol для каждого вызова `bot.send_message`.

---

# Formatting

Telegram formatting должен находиться рядом с presentation:

```text
modules/schedule/presentation/formatter.py
modules/food_menu/presentation/formatter.py
```

Domain/application возвращают structured data, а presentation превращает их в Telegram output.

---

# DI

Dishka сохранить.

Большой глобальный `di.py` постепенно разделить на providers по feature.

Например:

```text
core/provider.py

modules/schedule/provider.py
modules/eders/provider.py
modules/obis/provider.py
modules/advertisements/provider.py
```

Root composition собирает providers:

```python
providers = [
    CoreProvider(),
    ScheduleProvider(),
    EdersProvider(),
    ObisProvider(),
    AdvertisementProvider(),
]
```

Не ломай текущие APP/REQUEST lifecycle scopes.

---

# Не делать Big Bang Rewrite

Это критическое требование.

Рефакторинг выполнять feature-by-feature.

Во время migration допустимо временное сосуществование:

```text
services/
repositories/
scraping/
modules/
```

Не перемещай весь проект за один commit/phase.

Предпочтительный порядок migration:

```text
1. advertisements
2. feedback / другие небольшие isolated features
3. food_menu
4. schedule
5. users / notifications
6. obis
7. eders
8. study_week / orchestration
```

Порядок можешь изменить после анализа coupling, но обязательно объясни решение.

---

# Первый этап: анализ до изменений

Перед изменением кода:

1. Прочитай весь проект и существующий `ARCHITECTURE.md`.
2. Построй dependency map основных feature.
3. Найди circular imports и скрытые cross-feature dependencies.
4. Найди классы/модули, которые фактически принадлежат другим слоям.
5. Найди Java-style patterns.
6. Найди места, где jobs напрямую реализуют business logic.
7. Найди Telegram types за пределами presentation.
8. Найди SQLAlchemy ORM leakage за пределы infrastructure/application там, где это создаёт coupling.
9. Найди большие service classes и измерь их responsibilities.
10. Найди generic helpers, которые можно colocate с feature.

Не начинай рефакторинг, пока не составишь краткую migration map.

---

# Тестовая стратегия против регрессий

Ключевое требование:

> Рефакторинг не должен менять observable behavior без отдельного явно аргументированного изменения.

Перед переносом feature:

1. Запусти полный test suite.
2. Зафиксируй baseline.
3. Если важный observable behavior feature не покрыт тестами — сначала добавь characterization test.
4. Только потом меняй структуру.
5. После каждого логического шага снова запускай релевантные тесты.
6. После завершения feature запускай полный suite.

Особенно сохранять:

```text
Telegram command behavior
callback payloads
FSM transitions
localization keys
message formatting
DB transaction behavior
Alembic compatibility
notification semantics
APScheduler behavior
HTTP integration semantics
parsing semantics
timeouts
retry behavior
ordering
rate limits
authorization/moderation checks
encryption format
stored DB formats
```

Не изменяй публичные callback data и persisted serialization formats без миграции.

---

# Golden rule

Если во время рефакторинга обнаружен подозрительный existing behavior:

```text
не исправляй его молча.
```

Сначала:

```text
1. зафиксируй существующее поведение тестом;
2. отметь возможный bug отдельно;
3. продолжи behavior-preserving refactor;
```

Bug fix должен быть отдельным изменением.

---

# DB safety

Нельзя генерировать Alembic migration только потому, что Python-файл с ORM model был перемещён.

Если schema не изменилась, migration не должна появляться.

После перемещения моделей сравни metadata/schema и проверь:

```text
table names
column names
indexes
constraints
foreign keys
server defaults
relationships
enums
```

---

# Import safety

Не создавай circular import workaround через хаотичные local imports без анализа.

Если появляется cycle — это сигнал неправильной dependency direction или ownership.

Сначала измени архитектурную границу.

---

# Naming

Предпочитай Python/project terminology:

```text
repository
client
parser
formatter
use_case
query
command
gateway
provider
model
```

Избегай Java Enterprise naming без смысла:

```text
Manager
ManagerImpl
ServiceImpl
HelperImpl
FacadeImpl
DAO
DTOMapperFactory
AbstractBaseService
```

---

# Avoid abstractions without consumers

Правило:

> Не создавать abstraction раньше, чем появилась реальная причина.

Если abstraction имеет ровно одну реализацию и не представляет внешнюю boundary, сначала подумай, нужна ли она вообще.

---

# Metrics, по которым оценивать улучшение

Хороший результат должен приводить к тому, что:

```text
- большая часть файлов feature находится рядом;
- application layer меньше знает о Telegram;
- infrastructure детали меньше протекают наружу;
- меньше god-services;
- меньше giant constructors;
- меньше cross-feature repository access;
- jobs становятся thin entry points;
- DI собирается по feature;
- тесты можно писать на use case без Telegram;
- новая feature добавляется преимущественно внутри одного modules/<feature>;
- количество boilerplate не растёт без причины.
```

---

# Ожидаемая примерная структура

Не копируй её механически, адаптируй под фактический код:

```text
src/manashelper/
├── main.py
│
├── core/
│   ├── config.py
│   ├── logging.py
│   ├── database/
│   │   ├── base.py
│   │   ├── engine.py
│   │   └── session.py
│   ├── scheduler.py
│   └── provider.py
│
├── platform/
│   ├── telegram/
│   │   ├── dispatcher.py
│   │   ├── commands.py
│   │   ├── middlewares/
│   │   └── filters/
│   │
│   └── i18n/
│
├── modules/
│   ├── users/
│   ├── schedule/
│   ├── food_menu/
│   ├── obis/
│   ├── eders/
│   ├── study_week/
│   ├── advertisements/
│   ├── feedback/
│   └── notifications/
│
└── shared/
```

Пример крупной feature:

```text
modules/eders/
├── presentation/
│   ├── router.py
│   ├── keyboards.py
│   ├── formatter.py
│   └── states.py
│
├── application/
│   ├── get_assignments.py
│   ├── get_materials.py
│   ├── refresh_snapshot.py
│   ├── track_changes.py
│   └── models.py
│
├── domain/
│   ├── models.py
│   ├── rules.py
│   └── ports.py
│
├── infrastructure/
│   ├── client.py
│   ├── parser.py
│   ├── repository.py
│   ├── orm.py
│   └── serialization.py
│
├── jobs.py
└── provider.py
```

---

# Качество Python

После каждого этапа должны проходить:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/manashelper
uv run pytest
```

Не ослабляй Ruff/mypy/test configuration только для того, чтобы рефакторинг прошёл.

Не добавляй:

```text
# type: ignore
# noqa
```

без конкретной причины.

Если unavoidable — используй максимально узкий код ошибки и объясни причину.

---

# Коммиты / этапы изменений

Каждый логический этап должен быть reviewable.

Предпочтительные единицы:

```text
1. characterization tests
2. create feature package
3. move presentation
4. move application logic
5. move infrastructure
6. fix DI composition
7. move jobs
8. remove old dead paths
9. pythonic cleanup
10. architecture docs
```

Не смешивай одновременно:

```text
architecture migration
business feature changes
DB schema changes
mass rename
style rewrite
```

если их можно разделить.

---

# Pythonic cleanup должен идти после структурного переноса

Для каждой feature придерживайся двух фаз:

```text
Phase A:
переместить код и сохранить behavior почти без изменений

Phase B:
после зелёных тестов провести Pythonic simplification
```

Так легче понять источник regression.

---

# Особо опасные места

Проявляй повышенную осторожность вокруг:

```text
Eders snapshots
Eders serialization
OBIS credentials
AES-GCM encryption
notification deduplication
notification scheduling
schedule synchronization
lesson history
advertisement moderation
callback_data
FSM state names
locale handling
APScheduler registration
Dishka scopes
SQLAlchemy session lifecycle
message deletion jobs
rate limiting
per-chat ordering
```

Здесь приоритет correctness выше архитектурной красоты.

---

# Что делать с tests

По возможности тесты тоже постепенно группировать рядом с feature или отражать feature structure:

```text
tests/
├── schedule/
├── food_menu/
├── obis/
├── eders/
└── advertisements/
```

Но не перемещай тесты только ради симметрии, если это создаёт шум.

Главное — чтобы новая архитектура оставалась хорошо покрытой.

---

# Documentation

После каждого законченного migration stage обновляй `ARCHITECTURE.md`.

Документ должен описывать фактическое состояние, а не желаемую архитектуру.

Если migration ещё не закончен, явно описывай:

```text
current state
migrated modules
legacy modules remaining
temporary compatibility boundaries
```

---

# Definition of Done

Рефакторинг считается успешно завершённым только если:

```text
1. Все существующие тесты проходят.
2. Для критичных непокрытых сценариев добавлены characterization tests.
3. Ruff проходит.
4. Форматирование проходит.
5. mypy strict проходит.
6. Alembic видит корректную metadata.
7. Схема БД не изменилась без намерения.
8. Telegram behavior сохранён.
9. Callback payloads и FSM behavior сохранены.
10. Jobs продолжают запускать те же сценарии.
11. External HTTP integrations ведут себя эквивалентно.
12. DI scopes APP/REQUEST сохранены.
13. Нет новых необоснованных circular imports.
14. Нет массовых `type: ignore`.
15. Нет новых generic BaseService/BaseRepository abstraction без необходимости.
16. Каждая крупная feature стала существенно более self-contained.
17. Telegram-specific code преимущественно находится в presentation.
18. HTTP/SQLAlchemy/parser implementation преимущественно находится в infrastructure.
19. Cross-feature зависимости проходят через application-level boundary.
20. Код после migration стал более idiomatic Python, а не Java, переписанной синтаксисом Python.
```

---

# Режим выполнения

Не пытайся сразу рефакторить весь repository.

Сначала:

```text
1. проанализируй проект;
2. предложи конкретную migration map;
3. выбери первую feature с хорошим соотношением "низкий риск / высокая польза";
4. выполни её migration полностью;
5. запусти все проверки;
6. только после успешной проверки переходи дальше.
```

Если обнаруживаешь, что моя предполагаемая target structure не соответствует фактическим зависимостям проекта, не следуй ей слепо.

Сохраняй основной принцип:

```text
feature-first organization
+
clear dependency direction
+
behavior preservation
+
idiomatic Python
+
minimal necessary abstractions
```

При любых сомнениях приоритеты следующие:

```text
1. Correctness
2. No regression
3. Clear ownership
4. Simplicity
5. Pythonic implementation
6. Architectural purity
```

Архитектура должна обслуживать проект, а не проект 2архитектуру.