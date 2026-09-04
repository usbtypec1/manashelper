# Guide: adding a new Telegram handler

Background: [`../ARCHITECTURE.md`](../ARCHITECTURE.md#request-flow-a-telegram-update) explains how
`TelegramConsumer` dispatches updates to the first matching `TelegramUpdateHandler`. This guide is the
step-by-step recipe for adding one.

## 1. Pick where it lives

All handlers live flat in `manashelper-bot/src/main/java/.../controller/` — there are no per-feature subpackages. Name the class
after its feature (`Obis*Handler`, `FoodMenu*Handler`, `About*Handler`, ...) rather than nesting it in a folder;
the package tells Java it's a controller, the class name tells a reader what it does.

## 2. Write the handler

```java
@Component
public class MyFeatureHandler extends TelegramUpdateHandler {

    public MyFeatureHandler(TelegramClient telegramClient, /* + any services you need */) {
        super(telegramClient);
    }

    @Override
    public boolean shouldHandle(Update update) {
        // match on message text, or callback data, or both
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        // call domain services, then reply
    }
}
```

Reply using the inherited helpers rather than building `SendMessage`/`EditMessageText` by hand:

- `answerTextMessage(update, text)` / `answerTextMessage(update, text, markup)` — new message.
- `editTextMessage(update, text, inlineMarkup)` — edit the message a callback query came from.
- For callback-only acknowledgements with no visible message change, build an `AnswerCallbackQuery` directly
  (see `FoodMenuRatingHandler`).

**Never inject a `repository` or reference an `entity` from a handler.** Add or extend a `service` method that
returns a `model` record instead. `FacultyService`/`DepartmentService`/`CourseService` are the reference
implementations — they replaced four handlers that used to inject `*Repository` beans and manipulate `Course`/
`User` entities directly in the controller. If the data you need doesn't have a service method yet, add one
rather than reaching for the repository from the handler.

## 3. Match the right input shape

- **Command / free text**: check `update.hasMessage() && update.getMessage().hasText()` and compare
  `update.getMessage().getText()`.
- **Button press**: check `update.hasCallbackQuery()` and match `update.getCallbackQuery().getData()`.
- **Structured button data with an id** (e.g. "show course 42"): don't hand-roll the string format — pack/parse
  it with `CallbackDataByIdFilter.pack(CallbackData.MY_KIND, id)` /
  `CallbackDataByIdFilter.parseUUID(...)`/`parseInt(...)`. Add a new constant to the `CallbackData` enum
  (`model/CallbackData.java`) for it.
- **Multi-step free-text flow** (you asked a question, you need the *next* message from this chat to be the
  answer, not a new command): you need chat-scoped state. Follow the `ObisSessionManager` pattern — a
  `@Component` holding a `ConcurrentHashMap<Long, YourSessionState>` keyed by chat id — rather than trying to
  encode multi-turn state into callback data. Remember this state is in-memory and does not survive a restart.

## 4. Avoid shadowing

`TelegramConsumer` dispatches to the *first* handler bean (in Spring's registration order) whose `shouldHandle`
returns `true`, then stops — there is no explicit priority mechanism. Before adding a new handler:

- Search existing `shouldHandle` implementations for overlapping text/callback-data prefixes.
- Prefer specific, prefix-based matches (e.g. `data.startsWith("myfeature:")`) over broad ones, so you don't
  accidentally intercept another handler's updates or get intercepted yourself.

## 5. Test the parts that don't need Telegram

`TelegramUpdateHandler` subclasses are usually thin dispatch glue and aren't unit-tested directly. If your
handler's reply text has any nontrivial formatting/branching logic, pull it into a plain `service/*Formatter`
class (no Spring dependencies) and unit-test *that*, the way `CourseLessonFormatterTest` tests
`CourseLessonFormatter` — instantiate it with `new`, no Spring context needed.
