# Матрица переноса Telegram UI: этап 1

Статус: выполнено 2026-11-02. Основа — текущий исходный код ветки, а не число
будущих сценариев. Матрица создана до смены транспорта и обновляется вместе с кодом.
Этапы 2–6 (aiohttp/Mini App, DB-локализация, единые события, композиция и эффекты)
выполнены; матрица обновлена для текущей реализации этапа 7 по
[ORCHESTRATION.md](ORCHESTRATION.md). Результаты приёмки фиксируются в PROGRESS.md.

## Источник истины и проверка

[inventory.json](inventory.json) — авторская машинно-проверяемая матрица.
Каждый элемент содержит `path`, `symbol`, `kind`, группу владельца `group` и
явный список `targets`. У группы указаны `owner`, `status`, целевые сценарии,
инварианты при переносе и замечания о текущих ограничениях. Общий helper может
обслуживать несколько сценариев. Имена будущих сценариев — границы переноса,
они ещё не означают наличие опубликованного flow или нового API.

Покрыты 467 элементов в 95 файлах. На этапе 3 девять методов проверки HTML перенесены
из Telegram presenter в общий `ui_flows/application/texts.py`; этап 4 добавил единый
ingress и фильтры owning-адаптеров, сохранив остальные mappings:

- 26 объектов Router, 112 функций-обработчиков и дополнительная явная регистрация
  runtime reply-handler; все decorator bindings, включая flags и фильтры;
- 38 типизированных callback-контрактов, их 13 локальных enum-контрактов,
  сырые callback/deep-link фильтры в bindings и три именованные payload-константы;
- восемь FSM-форм, 22 State, операции с FSM, чтение полей и девять именованных
  ключей хранения; 27 импортов `aiogram.fsm`, включая формы без активного State;
- 205 функций/методов presentation: entrypoints, keyboards, formatters,
  транспортные senders, preview, command builders и отправка ссылки `/editor`;
- восемь записей command menus по private/group/admin scope; скрытые команды
  дополнительно видны в bindings handlers;
- порядок подключения routers, четырнадцать адресатов legacy handoff и их Eders guard.

На этапе 7 FeedbackForm перемещена в owning `states.py`, а `start_feedback`
выделен в публичный entrypoint. Новые owning entrypoints Notifications, course
tracking, OBIS Settings и phone numbers обслуживают временные handoff из runtime
Settings. Это сохраняет прежние feature owners; их формы ещё не объявляются
перенесёнными. Callback ingress теперь принимает также опубликованные launch-входы;
policy call сохраняет legacy FSM, runtime coordinator исполняется после REQUEST.

Из корня репозитория:

```sh
.venv/bin/python scripts/check_ui_flow_inventory.py --check
.venv/bin/pytest -q tests/tools/test_ui_flow_inventory.py
```

Проверка не импортирует приложение, не обращается к Telegram и не требует БД.
Она сравнивает AST-факты с матрицей, отклоняет новые/удалённые элементы, изменённые
bindings/контракты/операции FSM и отсутствующего владельца или целевой сценарий.
Комментарии, форматирование и сдвиг номеров строк не делают матрицу устаревшей.
Тест актуальности включён в обычный pytest-прогон.

Для обновления сначала получить факты:

```sh
.venv/bin/python scripts/check_ui_flow_inventory.py --scan
```

Затем осознанно изменить соответствующие items/groups в JSON и повторить проверку.
Автоматического назначения сценариев нет. При переносе одного входа старый элемент
удаляется только вместе с исходным кодом; его новый владелец/вход добавляется в матрицу.

Проверка фиксирует текущие способы регистрации: Router assignments, observer
decorators и module-level register/filter. Это контроль покрытия, а не доказательство
поведения или прав доступа: тела handlers/presenters и бизнес-правила проверяются
тестами owning-модулей на каждом этапе. Если меняется сам способ регистрации или
работы с FSM, вместе с матрицей нужно обновить scanner и его mutation-тесты.

## Владельцы и границы сценариев

| Группа | Элементов / handlers | Целевые части |
| --- | --- | --- |
| Navigation | 27 / 8 | Главное меню, Studies, Settings, hide keyboard, shared Settings callbacks, command menus |
| Runtime | 73 / 10 | Unified ingress/launch, delivery, preview, monitoring, `/editor`, `/flow_demo`, уже существующие меню/опрос |
| Users | 33 / 10 | Locale, theme, список контактов, ввод, удаление |
| Schedule | 46 / 9 | Меню, tracking-каталог, день, поиск, страницы результатов |
| Food menu | 63 / 14 | Запуск, дата/день, rating, notification settings, chat cleanup |
| Notifications | 10 / 3 | Пользовательские переключатели и переходы к owning-настройкам |
| OBIS | 42 / 10 | Settings, terms, credentials, clear confirmation, grades/attendance, pages |
| Eders | 24 / 5 | Activities/materials, pages/filters, notification settings |
| Study week | 5 / 1 | Семидневная сводка |
| Advertisements | 81 / 26 | Marketplace, создание, media, expiry, свои объявления, detail/delete, contact, moderation/comment |
| Feedback | 16 / 4 | Ввод обращения и отдельный групповой native admin reply |
| Broadcast | 26 / 7 | Draft, кнопки, preview, подтверждение и delivery |
| Student questions | 21 / 5 | Существующий flow; активный legacy-путь сохраняет своего владельца |

`runtime.*` обозначает остающиеся транспортные компоненты. `*.notification_delivery`
обозначает существующие фоновые presenters: их бизнес-use-cases и jobs остаются
у владельцев; меняется источник текста и при необходимости адаптер доставки.
Они не превращаются автоматически в пользовательские диалоги.

## FSM и контекст без активного состояния

| Владелец | Состояния | Данные/контекст, требующие решения при переносе |
| --- | --- | --- |
| Users | PhoneNumberForm: 1 | Ожидание Telegram contact или текстового номера; payload keys отсутствуют |
| Feedback | FeedbackForm: 1 (`modules/feedback/states.py`) | Ожидание текущего текста; payload keys отсутствуют |
| Schedule | LessonSearchForm: 1 | `lesson_search_results`, общий кеш FSM без привязки к message ID |
| OBIS | ObisCredentialsForm: 2 | `student_number`; `obis_result_pages` по message ID, максимум пять наборов |
| Eders | Нет State | `eders_snapshot`, `eders_snapshot_opened_at`, TTL 15 минут; общий кеш FSM |
| Broadcast | BroadcastForm: 2 | `body`, `photo_id`, `buttons`; preview и явное подтверждение |
| Advertisements | AdvertisementForm: 7 | `title`, `description`, `price`, `media`, `expires_at`, `media_prompt_message_id` |
| Moderation | AdvertisementModerationForm: 1 | `advertisement_id`, `notification_chat_id`, `notification_message_id` |
| Student questions | StudentQuestionsForm: 7 | `student_questions_session`, `overwrite`, `course`, `had_questions`, `questions`, `found_answers`, `answer_sources` |

Пароль OBIS сейчас локальная переменная handler, а не FSM key. Перенос должен
сохранить masking и безопасную обработку sensitive input; сериализовать весь
FSM/Update в durable context нельзя. Runtime/monitoring не должны копировать ответы.

## Границы совместимости и обнаруженные расхождения

- Food menu уже поддерживает private/group/supergroup, rich/ephemeral ответы,
  персонального receiver и chat cleanup. Ему нужен групповой scope до переноса;
  приватных предположений пилотного runtime недостаточно.
- Moderation авторизуется по configured chat, а Feedback admin reply коррелируется
  с ID исходного admin message. Оба входа должны пережить унификацию событий.
- В Users и Advertisements присланный Telegram contact сейчас сохраняется без
  сравнения `contact.user_id` с отправителем. План требует проверку владельца
  контакта; это отдельное исправление при переносе, а не уже соблюдаемый инвариант.
- Ввод комментария модерации сейчас полагается на установленное FSM-состояние и
  не повторяет проверку moderation chat. В целевом событии нужны явные scope и права.
- Formatters расписания/поиска вставляют динамический контент без явного HTML
  escaping. Это текущее ограничение, которое нужно исправить при переносе;
  сохранение экранирования не заявляется как уже существующее поведение Schedule.
- Приоритеты active reply → deep links → legacy fallback, продолжение форм при
  Off/Admin only, immutable/pinned версии, event receipts и unknown delivery сохраняются.
- Активный legacy-опрос сохраняет owner и session ID до завершения; runtime rollout
  и новый Settings не удаляют его форму. Старые survey callbacks отклоняются без
  отмены постороннего runtime, новые runtime-опросы используют существующий flow.
- Потеря legacy-кешей после рестарта — ограничение MemoryStorage. Runtime frames,
  typed collections и waiting effects уже имеют durable storage этапов 5–6; перенос
  feature-кешей и форм требует отдельного доказательства на соответствующем этапе.

HTTP/editor DTO, frontend events и auth endpoints остаются в
[ADMIN_API.md](ADMIN_API.md), OpenAPI и E2E-тестах. Их framework parity и Mini App auth
проверены на этапе 2; эта матрица проверяет только покрытие Telegram UI, а не заменяет
HTTP/E2E-регрессию.
