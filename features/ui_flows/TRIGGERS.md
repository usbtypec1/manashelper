# Единые события, входы и правила запуска

Этап 4 оркестратора. Telegram проходит через один resolver в
`ui_flows/application/ingress.py`; транспортное распознавание и зарегистрированные
callback codecs остаются в `manashelper`. Формы, кеши и бизнес-handlers legacy
сохранены. Этапы 5–6 добавили Call/Return, external effects и typed inputs; этап 7
связывает Settings/locale/theme с этими механизмами. Полное удаление FSM остаётся
последующей работой [ORCHESTRATION.md](ORCHESTRATION.md); итоговые проверки этапа 7
фиксируются в [PROGRESS.md](../../PROGRESS.md).

## События и порядок выбора

`IncomingEvent` содержит bot/update identity, actor, chat/type, message/thread context
и один вид входа: command, deep link, callback, text, contact, photo/video или native
reply. Для callback actor берётся из `callback.from_user`, не из автора сообщения
бота. DTO не содержит aiogram, ORM или FSMContext. Чувствительные поля исключены
из repr; DTO не сериализуется в квитанцию или мониторинг.

Команда с `@username` сверяется с именем текущего бота; чужое адресование игнорируется.
`/start` без аргументов отделён от payload. Сохранены `student_questions`, `market`
и `ad_<uuid>`; неизвестный payload и неверный UUID не превращаются в обычный `/start`.
Все 38 прежних callback codecs явно зарегистрированы; значения проверяются их
типизированными классами, а не исполняемым кодом или regex из БД.

Порядок разрешения:

1. Проверить actor, chat scope, доступ, capability и квитанцию повтора.
2. Разобрать callback, команду/deep link или native reply.
3. Для обычного текста сначала найти кнопку текущего сохранённого reply-экрана.
4. Проверить глобальные опубликованные reply bindings, включая прежние переводы/темы.
5. Передать текст ожидающему runtime-полю либо вход своему legacy-owner.
6. Отклонить неизвестный структурированный вход; неподдерживаемое сообщение игнорировать.

Команда не становится ответом поля. Исключение — legacy-пароль OBIS:
неизвестная или недоступная пользователю команда, включая `/secret@value`,
остаётся непрозрачным паролем без lookup имени бота. Доступные команды сохраняют
обычные правила запуска. Пароль маскируется в audit и не сохраняется в receipt.
Contact/media не превращаются в пустой текст
runtime v1; v2 input принимает их только при соответствующем input_type. Media
накопление сохраняется в typed state с дедупликацией message_id и declared limit;
feature-specific albums объявления остаются последующей миграцией.
Edited/channel/прочие Update не меняют исполнение.

## Хранилище и согласованная публикация

Миграция `2deed60a5bfd` добавляет:

- `ui_trigger_state`: singleton draft, optimistic revision и current release;
- `ui_trigger_releases`: immutable JSONB manifest, ревизия, автор и время;
- `ui_ingress_receipts`: `(bot_id, update_id)`, actor/chat и выбранный маршрут;
- nullable `ui_dialog_sessions.trigger_release` для закреплённого manifest.

Начальный документ содержит 78 bindings: команды/алиасы, deep links, все callback
prefixes и специальные actions Settings/Timetable, reply labels, групповой `/start`
и native reply администратора. После bootstrap БД авторитетна: рестарт не заменяет
операторский draft или выпуск. Если встроенный сценарий уже существует, но ещё не
опубликован, bootstrap сохраняет его и создаёт первоначальный compatibility manifest
с legacy-входами. Runtime draft можно сохранить и опубликовать после подготовки сценариев.

`trigger_document()` остаётся исходным immutable compatibility-каталогом.
`orchestration_trigger_document()` задаёт defaults новой установки: /language,
Settings open_language/open_theme → select_locale/theme с policy call;
menu.settings/back_to_settings → Settings с policy replace. Survey сохраняет
scenario target и student_questions fallback: уже начатые legacy-анкеты продолжают
прежнего owner, off/admin сохраняет прежний survey-вход. Это согласованное исключение
совместимости; legacy survey не удаляется на этапе 7.

Новая установка сначала seed/publish дочерние locale/theme, Settings, main_menu,
затем survey и manifest. Существующие документы/публикации не переписываются.
Неопубликованная authored dependency задерживает зависимый seed, но не startup:
используется legacy compatibility manifest. Последующая готовность dependency и
рестарт сами не переключают существующий manifest на новые defaults.

Manifest фиксирует bindings, выпуск проверки глобальных текстов и точные версии
целевых сценариев с их text catalog pins. Версии delegate contracts содержатся в
самих immutable flow documents и проверяются при публикации/активации. Return targets
включаются в manifest; форма, запущенная через него, возвращается к его версии меню.
Глобальные legacy labels принимают текущие и исторические переводы; показанные
runtime reply/inline actions разрешаются по сохранённому экрану.

Публикация графа сама не меняет существующий trigger manifest. Оператор сначала
публикует DB-тексты, если они изменились, затем дочерние сценарии/Settings, свежую
ревизию main_menu и свежую ревизию Triggers. Для принятия нового seed в существующей
БД оператор вносит reviewed правки через редактор; Python bootstrap не заменяет
его граф или bindings. Даже неизменённому графу нужна свежая draft revision для
новых pins. Manifest публикуется последним. Проверяются:

- уникальность IDs, пересекающиеся exact/prefix/callback/reply matchers и scopes;
- исторические подписи всех пяти языков/тем и невозможность принять их за команды;
- зарезервированный admin-доступ `/broadcast`, `/editor`, `/flow_demo`;
- зарегистрированные legacy adapters, их неизменяемые контракты и moderation chat scope;
- опубликованные targets/entries, delegate contracts и безопасное отображение;
- соответствие проверенных аргументов объявленным полям сценария.

Новый scenario target поддерживает private command/deep-link/reply entry. Callback
и native reply требуют owning action adapter; произвольная перенастройка старого
callback в новый запуск запрещена. Этап 7 допускает явно принадлежащие платформе
Settings actions open_language/open_theme/back_to_settings. Другие callback namespaces
сохраняют прежние owning adapters. Отдельные launch actions уведомлений относятся
к последующему расширению доставки.

`entry` задаёт node ID. Именованный `navigation: "study"` использует существующий
`navigation_entries.study`, поэтому переименование узла не ломает Studies.
Аргументы задаются явной картой `target.arguments`: `argument`, `actor_id`, `chat_id`.
UUID проверяется и канонизируется; argument попадает только в объявленное text-поле,
IDs — в integer-поля. В квитанции остаются исключительно метаданные маршрута.

```json
{
  "id": "item_link",
  "matcher": {"kind": "prefix", "key": "item_", "arguments": "uuid"},
  "target": {
    "kind": "scenario",
    "flow_id": "item_details",
    "arguments": {"item_id": "argument", "actor": "actor_id"}
  },
  "scope": "private",
  "access": "public",
  "policy": "reject_if_busy"
}
```

Это binding, добавляемый к документу из GET `/triggers`; `item_details` должен быть
опубликован и объявлять соответствующие поля. Бизнес-делегат повторно проверяет
доступ к сущности. Совпадение текста кнопки не доказывает полномочий.

## Политика открытого диалога

| Policy | Поведение |
| --- | --- |
| `reject_if_busy` | Сохранить открытую форму; не выполнять посторонний вход |
| `resume` | Продолжить тот же сценарий и его прежнюю версию |
| `replace` | Явно отменить прежнее исполнение и запустить цель атомарно |
| `preserve` | Выполнить совместимый legacy-вход без отмены runtime |
| `call` | Временно вызвать preference-сценарий и вернуться к сохранённому ожиданию runtime |

Пустое главное Menu без данных можно заменить другим входом; проверка повторяется
под DB chat lock при запуске. Input и формы с данными защищены. `/start` и Back —
явные переходы к корню. Locale/theme, `/language`, `/editor` и скрытие клавиатуры
сохраняют runtime. Call сохраняет frame с прежними flow/version/node/data,
resume_status/revision, trigger pin и effect_revision; возврат восстанавливает тот же
session ID и wait с новой UI revision, не повторяя entry Action. Вложенный Call/cancel
и restart сохраняют данные и pins. Confirmation ребёнка предшествует родительскому
экрану и использует text pin ребёнка в новой locale/theme. Waiting_effect result
может сохраниться во время preference-вызова, но применяется лишь после возврата.
Unknown external work не повторяется. В активной legacy-форме тот же глобальный
preference-вход использует прежний picker без очистки FSM. Admin pilot
`/flow_demo` по-прежнему открывает текущую публикацию отдельно от trigger manifest
и отказывает при другом активном диалоге. Групповая модерация проверяет настроенный
chat ID, не роль пользователя. Регистрация command menus остаётся штатной операцией
startup; публикация manifest не вызывает Telegram для их перерегистрации.

Rollout admin/all/off управляет новыми runtime-запусками. Active input/actions и
возобновление уже начатой анкеты не зависят от mode. Call preference поверх активного
runtime остаётся доступен при off; при отсутствии активного runtime применяется
совместимый legacy fallback. Survey fallback и начатые legacy-анкеты сохраняют
прежний маршрут. Сессии со старым NULL pin
сохраняют прежнюю v1-семантику; документы и ответы не переписываются.

## Транзакции, повторы и откат

Квитанция legacy-входа и его DB-записи используют исходный REQUEST. Runtime admission
сохраняет только исходные session ID/revision. Уникальность
квитанции сериализует повторную admission; при rollback квитанция исчезает вместе
с DB-записями. Runtime запускается через AfterRequestActions после commit профиля,
затем использует свои транзакционные event/screen receipts. DB chat lock не удерживается
на время Telegram I/O. Не сохраняются исходные updates, текст/пароли, контакты,
file IDs, caption или снимки FSM.

Один APP ChatOrdering объединяет message/callback обработку и effect completion
от apply до delivery; REQUEST закрывается до ожидания этой gate. Внешний delegate
исполняется вне неё и вне DB chat lock, поэтому долгий HTTP не блокирует preference
interrupt или отмену формы.

Повтор admitted legacy update не вызывает handler снова. Уже исполненный runtime
update также не входит в handler, поэтому не очищает более новую legacy-форму.
Неисполненный replay сохраняет прежний маршрут и требует прежние session ID/revision;
устаревший текст не становится ответом новой формы. При повторном запуске ещё раз
проверяются текущие права и capabilities. Неизвестная попытка доставки
автоматически не отправляется повторно. Это не exactly-once гарантия legacy network
I/O при ошибке commit и не durable FSM: прежние MemoryStorage-ограничения сохраняются.

Save требует `expected_revision`; Publish одной ревизии идемпотентен и после rollback
не реактивирует её. Activate требует `expected_current_release`, меняет только указатель
и сохраняет draft/active sessions. DB trigger запрещает UPDATE/DELETE release. Сначала
откатывают указатель или приложение, сохраняя расширенную схему. Схемный downgrade
удаляет только три новые таблицы и pin, сохраняя прежние flow/session/answer данные;
он удаляет историю bindings/receipts, поэтому не служит штатным rollback оператора.

Откат на бинарник до durable interrupts небезопасен при frames с resume_status.
Миграция `a7572f78b034` сохраняет прежние writers через nullable effect_revision;
guarded downgrade под table lock отказывает до DDL при новых frames/корреляции.
Сохраняют расширенную схему и совместимый runtime до завершения таких продолжений,
а не удаляют данные и receipts ради старого исполнителя.

## API, редактор и проверка

Все пути ниже относительно `/admin/api/v1`, с прежними admin/Origin/CSRF гарантиями:

| Метод | Контракт |
| --- | --- |
| GET `/triggers` | Draft, revision, current_release |
| PUT `/triggers` | `{document, expected_revision}`; структурно валидный draft |
| POST `/triggers/publish` | `{expected_revision}`; semantic validation и manifest |
| GET `/triggers/releases` | Immutable manifests, newest first |
| POST `/triggers/activate` | `{release_id, expected_current_release}` |

Вкладка **Triggers** создаёт scenario entry, настраивает matcher, target/entry, доступ,
policy и аргументы. Compatibility entries read-only. Save создаёт новую ревизию даже
без изменения bindings, Publish и Activate требуют подтверждения. 409 не повторяется
и сохраняет правки; Reload требует явного discard. Переход между режимами и closing
guard учитывают несохранённый manifest. [OpenAPI](openapi.json) и generated TS types актуальны.

Доказательства: [resolver/adapter/DB](../../tests/modules/ui_flows/test_ingress.py),
[production Dispatcher](../../tests/modules/ui_flows/test_ingress_production.py),
[Settings/preferences transport](../../tests/modules/ui_flows/test_stage7_navigation.py),
[durable interrupts](../../tests/modules/ui_flows/test_interrupts.py),
[API](../../tests/modules/ui_flows/test_trigger_api.py),
[миграция](../../tests/modules/ui_flows/test_trigger_migration.py),
[browser E2E](../../src/admin-ui/tests/e2e/triggers.spec.ts) и
[webhook/HTTP](../../tests/modules/ui_flows/test_telegram_http.py).
Итоги локальных прогонов — в [RELEASE.md](RELEASE.md). Live Telegram и deploy этим
этапом не выполняются.
