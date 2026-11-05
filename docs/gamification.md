# Achievements and Telegram Mini App

Webhook, Mini App API, Vue static assets, scheduler and outbox run in one Python process.
Use one app replica: scheduler and in-memory FSM are not coordinated across replicas.
Node is needed only for building the Vue/Vite frontend.

## Rules and persistence

- Access is opt-in per user: `gamification_progress.enabled` defaults to false, including existing rows.
  A missing progress row is disabled. Only the configured admin chat can run
  `/gamification <Telegram user ID> on|off` for a registered user. Reopen the main menu afterward.
  Disabled users have no achievements button, receive 403 from both Mini App APIs, and are excluded from ranking.
  No activity progress or awards (including manual grants) are recorded, and the transcript-only HTTP refresh is skipped.
  Regular OBIS synchronization continues. Disabling preserves awards/progress; enabling resumes them without
  backfilling missed activity. Academic history can qualify on the next successful refresh.
- The collection contains eleven achievements. One achievement = one point. Awards are permanent and unique per Telegram user/key.
- Equal scores share competition ranks (1, 1, 3). Display ties by the time the score was reached, then user ID.
  Top ten contains only users with at least one award. The profile includes the user's rank outside that list.
- Food has one counter for both thresholds (50 and 100); ten minutes since the last counted view.
  Opening a selector, rating, errors and automatic notifications do not count. Group views count for the actor.
- Night grades count successful initial displays, not pagination or polling: `[02:00, 05:00)` in Bishkek,
  once per date, three consecutive dates. A missing date resets the current streak.
- Seller is awarded when successful channel publication message IDs are recorded, not at approval time.
- `/grant_pokemon <Telegram user ID>` is authorized only in the configured admin chat, after manual selfie
  verification through existing support. It stores actor ID/time and tolerates repeated grants.
- Eldin balasy requires at least three final AA grades in one transcript semester; progress is the best
  per-semester AA count, including historical semesters. Counts never sum across semesters.
- Thin ice requires five distinct subject codes in one current attendance snapshot, each with theory OR practice
  absence >= 18.75%. Both parts of one subject count once. Use OBIS's percentages, not a reconstructed denominator;
  do not accumulate subjects across refreshes. Account markers hide progress from a previous linked account.
- Existing food/night views and publications are not backfilled. Historical F1/FF in the transcript are eligible.

The existing 15-minute OBIS poll also fetches `/vs-ders/transkript-detailed`. Notification toggles do not stop
synchronization or achievements. F1/FF come only from the transcript's final letter-grade column.
The parser reads official semester credit/point totals and overall GPA. The baseline is the weighted sum of
previous semesters' points divided by credits, rounded half-up to two decimal places. It is frozen on the first
successful observation of the latest semester/account. Compare OBIS's overall GPA to it using Decimal:
`>= +0.20` earns Cumback; `<= -0.20` earns Fall. No previous credits/incomplete history means no invented baseline.
Account markers prevent presenting another linked account's academic progress. Parser/HTTP failures preserve
previous successful progress. Mini App reads never call OBIS.

OBIS may revise historical totals after retakes: we cannot reconstruct a value it no longer supplies before
the first observation. Afterward the frozen baseline is retained. The supplied `trans.html` was inspected
locally; committed tests use a synthetic structural fixture, without its profile/CSRF token/course history.

## Build and verify locally

Use the development PostgreSQL/settings described in AGENTS.md, never production.

```sh
uv sync --frozen
.venv/bin/pybabel compile -d src/manashelper/locales
.venv/bin/python frontend/scripts/export_messages.py
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/alembic upgrade head
.venv/bin/pytest tests/modules/gamification tests/modules/obis/test_transcript.py tests/platform/web
cd frontend
npx playwright install chromium
npm run test:e2e
```

Browser tests start a loopback-only fixture in a temporary PostgreSQL schema. Only Telegram's WebView bridge
is simulated; requests use the real local API and database. Gettext catalogs are the text source for both
bot and Mini App. Generated bundles, message exports and screenshots are ignored. Docker builds them automatically.

## Enable webhook and Mini App

The main reply keyboard has an ordinary text Achievements button. Its handler sends a separate inline
Web App button that opens the Mini App with signed initData. Never set web_app on the reply-keyboard
button: Telegram does not supply initData for that launch mode. Other navigation menus are unchanged.


1. Provide an HTTPS origin with a valid certificate; set `MANASHELPER_PUBLIC_URL=https://bot.example.com`.
2. Set a random URL-safe `MANASHELPER_WEBHOOK_SECRET` (32–256 characters).
   `MANASHELPER_HTTP_PORT` defaults to 8080; production Compose publishes it on loopback only.
3. Reverse-proxy the origin to that port, preserving Telegram's secret header. Include `/telegram/webhook`,
   `/api/`, `/app/` and `/health`; allow requests to finish (for example, a 120-second proxy timeout).
4. Configure `https://bot.example.com/app/` as the Mini App URL in @BotFather.
5. Start one instance. It binds HTTP, initializes the dispatcher and registers `setWebhook` with resolved update
   types, ten connections and `drop_pending_updates=False`.

Example Caddy configuration:

```caddy
bot.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

For rollback to polling, unset PUBLIC_URL and restart this version; it deletes the webhook without dropping
pending updates. Delete the webhook explicitly before reverting to an older polling-only image.
V28 adds new tables only. Downgrading removes achievement/progress/receipt data; keep the migration in place
unless intentionally discarding that data. Existing user/notification settings are preserved.
V29 adds access (default off), AA and attendance progress fields. It preserves existing awards and counters.
Downgrading V29 removes the access gate and these new counters, while keeping awards and prior progress fields;
re-upgrading starts everyone disabled again. Deploy the V29-aware code together with this migration.
An older application version does not enforce the opt-in gate; do not roll back code alone during the pilot.

## HTTP contract and guarantees

See [gamification.openapi.yaml](gamification.openapi.yaml).

- Webhook checks `X-Telegram-Bot-Api-Secret-Token` before decoding updates. Receipts contain only ID/time,
  never raw updates or passwords. A PostgreSQL advisory transaction lock serializes identical IDs.
- Receipts and business changes share one Dishka REQUEST session and commit. Only then is 200 returned.
  Concurrent deliveries get 503; failures get 5xx and Telegram retries. Completed duplicates get 200 without
  rerunning the handler. Receipts expire after seven days (Telegram stores pending updates for at most 24 hours).
- Telegram sends and in-memory FSM changes are not transactional: a crash after a send but before DB commit
  can repeat that send. This is not exactly-once external delivery.
- API requests use `Authorization: tma <raw initData>`. Verify Telegram's HMAC, reject duplicate fields,
  limit age to one hour (30 seconds forward-clock tolerance), and take identity only from the signed user.
  Reopen Mini App after expiration. Unknown or disabled users get 403; API reads have no-store responses.
- Leaderboard returns names/counts/ranks/is_self, not Telegram IDs, credentials, GPA or other users' collections.

Outbound registration can be tested against the repository-owned synthetic Telegram mock:

```sh
postman simulation run postman/simulations/telegram.sim.yaml --port 4903 --output ndjson --no-history
# Another terminal with development settings:
MANASHELPER_TELEGRAM_SIMULATION_URL=http://127.0.0.1:4903/telegram \
  .venv/bin/pytest tests/platform/web/test_server.py::test_real_aiogram_client_serializes_webhook_registration
```

Local tests do not register a live Telegram webhook or prove domain reachability, TLS or BotFather configuration.
