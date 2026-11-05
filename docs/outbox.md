# Telegram notification outbox

Broadcasts, menus, timetable changes, achievements, OBIS and Eders notifications are persisted in `telegram_outbox` in the
same transaction as their producing operation. Adapters render locale, theme, HTML and keyboards before enqueueing.
Only committed records are sent. Interactive replies, previews, feedback and advertisement publication retain
immediate delivery because they use Telegram responses or message IDs.

## Delivery

Between 22:00 (inclusive) and 08:00 (exclusive), Bishkek time, queued deliveries use
`disable_notification=true`. The flag is stored in each method's JSON payload when enqueued.
Claims also enable and persist it for remaining parts if daytime work reaches delivery at night.
Once enabled, it survives retries and multipart delivery after 08:00. Explicit silent sends remain silent during the day.

The scheduler starts one continuous worker per process. Claims use `FOR UPDATE SKIP LOCKED`, a random token and
a 60-second lease. Claims and rate reservations commit before HTTP; results commit in a separate request scope.
Requests have a 20-second timeout. Expired leases recover after a crash; stale workers cannot acknowledge new leases.
Postgres token buckets share capacity across processes and restarts: global 20 requests/second with capacity 5,
private recipient 1/second with capacity 1, group recipient 1 every 3 seconds with capacity 1. Each compound
message part consumes a token. FIFO applies per recipient; other recipients can proceed while one backs off.
Photo/text deliveries checkpoint each successful part, so a text retry does not resend an acknowledged photo.
See Telegram's [limits](https://core.telegram.org/bots/faq#my-bot-is-hitting-limits-how-do-i-avoid-this) and
[`retry_after`](https://core.telegram.org/bots/api#responseparameters).

`429` persists a shared cooldown of at least `retry_after` seconds (one second if missing or malformed).
The affected message retries after that cooldown plus one second and jitter of 0–1 second, giving other chats a turn.
HTTP `5xx`, including HTML proxy errors, and network failures use equal-jitter exponential backoff: failure `n`
waits between half and all of `min(300, 2**n)` seconds. After 12 consecutive transient failures of one part,
the message becomes `failed`; successful progress resets that counter. Permanent recipient errors set
`users.bot_stopped`. Other non-retryable errors fail the message without disabling the recipient. Delivery rechecks
stopped users and broadcast/academic preferences; Eders can cancel pending messages through their source keys.

Default expiration: broadcasts/achievements/OBIS/materials 24 hours, timetable 6 hours, menus 2 hours, other Eders notifications
24 hours or the activity's closing time, whichever comes first. Callers may set an explicit aware `expires_at`.
No attempt starts after expiration. A retry beyond expiration marks the record `expired`; this does not delete
an already delivered Telegram message. Eders event acknowledgement now means transactional handoff to the outbox.

Delivery is **at least once**. Telegram has no idempotency key for these sends. A crash after Telegram accepts
a request but before the checkpoint commits can duplicate that part. A timeout also leaves the result unknown.
Leases, source-key deduplication and checkpoints cannot eliminate this external acknowledgement gap.

## Cleanup and operations

Cleanup runs at startup and every 24 hours. It expires overdue records with inactive leases, deletes terminal
records finished more than 24 hours ago and removes inactive per-chat buckets. Valid pending work and bot cooldowns
survive cleanup. Inspect status, attempts, failures, available_at, expires_at, locked_until and last_error for diagnosis.
Error fields contain class names or fixed codes, never payloads or bot tokens. Failed records are not replayed automatically.

Migration `V27` only adds the outbox and bucket tables. Startup applies it normally. Stop producers/workers and
drain or export pending work before downgrading to `V26`: the downgrade drops these two tables.

## Verification

Run `uv run pytest -q tests/platform/telegram/test_outbox.py tests/modules/eders/test_eders_tracking.py` against
a migrated development Postgres database with compiled catalogs. For real client serialization and HTTP failures:

```sh
postman simulation run postman/simulations/telegram.sim.yaml --port 4903 --output ndjson --no-history
# In another terminal:
MANASHELPER_TELEGRAM_SIMULATION_URL=http://127.0.0.1:4903/telegram \
  uv run pytest -q tests/platform/telegram/test_outbox_http.py
```

The local HTTP tests exercise the real aiogram client and Dishka worker: 429 recovery, JSON 503, HTML 502,
permanent/content errors, expiration, serialized buttons and photo/text checkpoints. They do not send real
Telegram messages or establish live availability.
