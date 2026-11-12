# Achievements and Telegram Mini App

Webhook, Mini App API, Vue static assets, scheduler and outbox run in one Python process.
Use one app replica: scheduler and in-memory FSM are not coordinated across replicas.
Node is needed only for building the Vue/Vite frontend.

## Rules and persistence

Pokemon is temporarily retired: its collection card and grant command are removed. Historical award
rows remain stored, but only keys in the active achievement catalog contribute to scores, ranks and tie order.

- Access is opt-in per user: `gamification_progress.enabled` defaults to false, including existing rows.
  A missing progress row is disabled. Only the configured admin chat can run
  `/gamification <Telegram user ID> on|off` for a registered user. Reopen the main menu afterward.
  Disabled users have no achievements button, receive 403 from both Mini App APIs, and are excluded from ranking.
  No activity progress or awards (including temporarily retired achievements) are recorded, and the transcript-only HTTP refresh is skipped.
  Regular OBIS synchronization continues. Disabling preserves awards/progress; enabling resumes them without
  backfilling missed activity. Academic history can qualify on the next successful refresh.
- The collection contains fifteen achievements. One achievement = one point. Awards are permanent and unique per Telegram user/key.
- Each newly earned achievement queues a localized text notification with its name and condition in
  `telegram_outbox` (category `achievement`, 24-hour TTL). The award and queue entry commit together;
  failures roll both back. Repeated observations and existing awards do not enqueue again.
  Delivery uses the recipient's locale/theme and the shared stopped-user, retry and night-silence policy.
  When the public URL is configured, each notification includes a localized View all achievements
  inline Web App button. The keyboard is persisted with the message and reused on delivery retries.
  Existing awards are not backfilled with notifications. Outbox delivery remains at least once.
- Equal scores share competition ranks (1, 1, 3). Display ties by the time the score was reached, then user ID.
  Top ten contains only users with at least one award. The profile includes the user's rank outside that list.
- Food has one counter for both thresholds (50 and 100); ten minutes since the last counted view.
  Opening a selector, rating, errors and automatic notifications do not count. Group views count for the actor.
- Night grades count successful initial displays, not pagination or polling: `[02:00, 05:00)` in Bishkek,
  once per date, three consecutive dates. A missing date resets the current streak.
- Seller is awarded when successful channel publication message IDs are recorded, not at approval time.
- Eldin balasy requires at least three final AA grades in one transcript semester; progress is the best
  per-semester AA count, including historical semesters. Counts never sum across semesters.
- On the edge requires five distinct subject codes in one current attendance snapshot, each with theory OR practice
  absence >= 18.75%. Both parts of one subject count once. Use OBIS's percentages, not a reconstructed denominator;
  do not accumulate subjects across refreshes. Account markers hide progress from a previous linked account.
- Iron attendance requires a current attendance snapshot whose every reported theory/practice percentage is 0
  (subjects without any percentage are ignored; an empty snapshot never qualifies). It is checked only in
  November–January and April–June (Bishkek time), because early-semester snapshots are trivially clean.
- Critic counts a user's first rating of each daily menu (100 menus); changing an existing score does not count.
- I'll be back (`phoenix`): the last chronological attempt of a course code is a passing letter grade (AA–DD) and the code was
  failed (F1/FF) earlier. Failed codes are remembered per academic account marker in `failed_courses`,
  because OBIS may overwrite a failed row with the retake result.
- Stability: three consecutive fall/spring semesters with official totals and a semester GPA (points/credits,
  rounded half-up to 0.01) of at least 3.00. Summer school and semesters without totals are skipped, not breaks.
- Einstein: F1/FF in a course whose transcript name contains physics in Russian/Kyrgyz, Turkish or English
  (`физик`, `fizik`/`fiziği`, `physic`), excluding the adjectives `fiziksel`, `физикалык` and `physical`.
- Existing food/night views and publications are not backfilled. Historical F1/FF in the transcript are eligible.

The existing 15-minute OBIS poll also fetches `/vs-ders/transkript-detailed`. Notification toggles do not stop
synchronization or achievements. F1/FF come only from the transcript's final letter-grade column.
The parser reads each course row's code, name and final grade, official semester credit/point totals and overall GPA. The baseline is the weighted sum of
previous semesters' points divided by credits, rounded half-up to two decimal places. It is frozen on the first
successful observation of the latest semester/account. Compare OBIS's overall GPA to it using Decimal:
`>= +0.20` earns Cumback; `<= -0.20` earns Fall. No previous credits/incomplete history means no invented baseline.
Account markers prevent presenting another linked account's academic progress. Parser/HTTP failures preserve
previous successful progress. Mini App reads never call OBIS.

OBIS may revise historical totals after retakes: we cannot reconstruct a value it no longer supplies before
the first observation. Afterward the frozen baseline is retained. The supplied `trans.html` was inspected
locally; committed tests use a synthetic structural fixture, without its profile/CSRF token/course history.

## Mini App artwork and editable copy

The collection uses illustrated round medals featuring the human mascot from `reference/mascot.JPG` and a locked medal for unearned achievements.
Opening an achievement reveals its illustration, description, status and earned date.
Intermediate progress counters, bars and source-readiness messages are hidden in the UI;
server-side counters and award conditions are preserved. The collection total and rank remain visible.

Names and descriptions come from `src/manashelper/locales/<locale>/LC_MESSAGES/messages.po`:

- `gamification.<key>.name` — achievement name.
- `gamification.<key>.description` — achievement condition/description.
- Example: `gamification.cafeteria_boss.name` and `gamification.cafeteria_boss.description`.
- Edit the corresponding `msgstr`; keep stable msgids and formatting placeholders.
- Available locales: `ru`, `ky`, `en`, `tr`, `zh`. Compile catalogs and restart the bot after editing.
  Docker builds compile them automatically. Editing copy does not change award rules.

Shared interface copy uses `gamification.ui.*` in the same catalogs. After changing UI copy,
export messages and rebuild the frontend using the commands below.
The medal sprite atlas is `frontend/src/assets/achievement-medals.png`; cell order and
sheet colors are mapped by stable achievement key in `frontend/src/achievementArt.ts`.
An individual `achievement-<key with dashes>.png` in the same directory (for example `achievement-thin-ice.png`)
is picked up automatically by `achievementArt.ts`; a key without an image or atlas cell shows the locked medal.
Current images:
Seller (suit meme), Formula One (racing-driver portrait), Champion (military salute),
Comeback/Negative growth (contrasting smiling and grim meme portraits), Cafeteria boss (chubby mascot
with a fried-chicken bucket), Night owl (Anxiety character fusion), Eldin balasy (GigaChad fusion),
Foodie (Naruto at Ichiraku with ramen and stacked bowls), On the edge (tightrope between skyscrapers),
Iron attendance (Hannibal Lecter fusion wearing his restraint mask behind bars in a glass cell),
Critic (Anton Ego fusion stunned after tasting ratatouille), I'll be back (Terminator fusion sinking into lava with a thumbs-up),
Stability (mascot as a meditating monk beside three equal graph bars),
and Einstein (tongue-out portrait with wild white hair, E=mc² and a red FF on the chalkboard).
The key mapping selects these images for earned medals and detail sheets; locked medals still use the atlas.
Display names retain stable storage keys: `fall` is Negative growth, `thin_ice` is On the edge,
and `phoenix` is I'll be back.
Reference screenshots/video under `reference/` are design inputs only, never served to clients.

## Build and verify locally

Use the development PostgreSQL/settings described in AGENTS.md, never production.

```sh
uv sync --frozen
.venv/bin/pybabel compile -d src/manashelper/locales
.venv/bin/python frontend/scripts/export_messages.py
bun install --cwd frontend --frozen-lockfile
bun run --cwd frontend --bun build
.venv/bin/alembic upgrade head
.venv/bin/pytest tests/modules/gamification tests/modules/obis/test_transcript.py tests/platform/web
cd frontend
bunx --bun --no-install playwright install chromium
bun run --bun test:e2e
```

Browser tests start a loopback-only fixture in a temporary PostgreSQL schema. Only Telegram's WebView bridge
is simulated; requests use the real local API and database. Gettext catalogs are the text source for both
bot and Mini App. Generated bundles, message exports and screenshots are ignored. Docker builds them automatically.
Use Bun 1.4.3 for frontend installation and scripts; `frontend/bun.lock` pins dependency versions.

Telegram integration uses stable `@tma.js/sdk-vue@1.0.23` through `shared/telegram/telegram.ts`.
Bootstrap initializes the SDK once; Vue `useSignal` bindings drive appearance and the shared viewport CSS
variables. One native BackButton handler closes an active achievement dialog first, otherwise navigates
back within the Mini App, with parent-route fallback for direct entry. Public terms work outside Telegram.
The official `telegram-web-app.js` script is not loaded in parallel. The SDK's standard tab-session launch
cache retains raw initData for route reloads; server authentication still checks its HMAC and one-hour expiry.
Browser fixtures provide synthetic signed launch data and emulate native bridge requests/events; they do not
mock the SDK or the local application API.

## Enable webhook and Mini App

The main reply keyboard has an ordinary text 🏆 Achievements button. Its handler shows the earned count
out of the active total and the user's global rank (or an unranked label), then sends a separate inline
Web App button that opens the Mini App with signed initData. Never set web_app on the reply-keyboard
button: Telegram does not supply initData for that launch mode. Old text labels without the trophy remain accepted.
Other navigation menus are unchanged.

To enable access for all users registered at the time of execution, run this SQL against the intended database:

```sql
INSERT INTO gamification_progress (user_id, enabled)
SELECT id, TRUE FROM users
ON CONFLICT (user_id) DO UPDATE SET enabled = TRUE;
```

Existing progress and awards are preserved. Future registrations still default to disabled; repeat the SQL
or use the per-user admin command for them. Users must refresh the main menu (for example with `/start`)
to see the button. A configured public URL remains required.


1. Provide an HTTPS origin with a valid certificate; set `MANASHELPER_PUBLIC_URL=https://bot.example.com`.
2. Set a random URL-safe `MANASHELPER_WEBHOOK_SECRET` (32–256 characters).
   `MANASHELPER_HTTP_PORT` defaults to 8080; production Compose publishes it on loopback only.
3. Reverse-proxy the origin to that port, preserving Telegram's secret header. Include `/telegram/webhook`,
   `/api/`, `/app/` and `/health`; allow requests to finish (for example, a 120-second proxy timeout).
4. Configure `https://bot.example.com/app/` as the Mini App URL in @BotFather.
5. Start one instance. It binds HTTP, initializes the dispatcher and registers `setWebhook` with resolved update
   types, ten connections and `drop_pending_updates=False`.

Webhook receipts share the handler's request transaction to suppress completed duplicate updates.
SQL persistence and transaction-scoped locking belong to `WebhookReceiptRepository`; middleware uses
`WebhookReceiptService`. A separate cleanup job runs at startup and daily, deleting receipts older than
two days. Webhook requests do not perform cleanup.

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
V31 adds `menu_ratings` and `failed_courses` progress columns; downgrading drops only those counters.
An older application version does not enforce the opt-in gate; do not roll back code alone during the pilot.

## HTTP contract and guarantees

See [gamification.openapi.yaml](gamification.openapi.yaml).

- Webhook checks `X-Telegram-Bot-Api-Secret-Token` before decoding updates. Receipts contain only ID/time,
  never raw updates or passwords. A PostgreSQL advisory transaction lock serializes identical IDs.
- Receipts and business changes share one Dishka REQUEST session and commit. Only then is 200 returned.
  Concurrent deliveries get 503; failures get 5xx and Telegram retries. Completed duplicates get 200 without
  rerunning the handler. Daily cleanup removes receipts older than two days.
- Telegram sends and in-memory FSM changes are not transactional: a crash after a send but before DB commit
  can repeat that send. This is not exactly-once external delivery.
- API requests use `Authorization: tma <raw initData>`. Verify Telegram's HMAC, reject duplicate fields,
  limit age to one hour (30 seconds forward-clock tolerance), and take identity only from the signed user.
  Reopen Mini App after expiration. Unknown or disabled users get 403; API reads have no-store responses.
- Leaderboard returns names/counts/ranks/is_self and earned awards (key, localized name/description and award date).
  Expanding a participant shows their earned medals; selecting a medal opens its detail sheet.
  It never returns Telegram IDs, credentials, raw grades/GPA/attendance or unfinished progress.
  Award conditions can still reveal academic information; this visibility is disclosed in the terms.
- `/app/terms?lang=ru` is a public terms page, available before registration or account connection.
  It supports all five locales without calling private APIs. Links in both Mini Apps and the OBIS consent
  keyboard lead there. Polling without PUBLIC_URL shows the same localized content in Telegram instead.
  The source text lives in the `terms.*` gettext entries; `platform/legal.py` owns section order, date and source URLs.
- Vue Router owns `/app/achievements`, `/app/leaderboard`, `/app/settings`, `/app/courses` and `/app/terms`.
  `App.vue` only renders `RouterView`; page components load on demand. The server serves the application shell
  for history routes, while `/app/assets/` keeps ordinary static-file handling. `/app/` defaults to achievements;
  old `?view=...` links redirect to their corresponding route without discarding other query parameters or the hash.

Outbound registration can be tested against the repository-owned synthetic Telegram mock:

```sh
postman simulation run postman/simulations/telegram.sim.yaml --port 4903 --output ndjson --no-history
# Another terminal with development settings:
MANASHELPER_TELEGRAM_SIMULATION_URL=http://127.0.0.1:4903/telegram \
  .venv/bin/pytest tests/platform/web/test_server.py::test_real_aiogram_client_serializes_webhook_registration
```

Local tests do not register a live Telegram webhook or prove domain reachability, TLS or BotFather configuration.
