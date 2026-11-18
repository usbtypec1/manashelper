# Eders browser login

Eders notifications offer **Log in to Eders** when Eders and `MANASHELPER_PUBLIC_URL`
are enabled. The existing completion/undo button stays available. Pressing login
in a private chat issues a protected message with a personal link valid for 60 seconds.
Only the owner of that chat can issue it. There is no browser-login feature for OBIS.

The bot origin cannot set cookies for the university's domains. Instead, the backend
uses the existing `ObisAccessService` to request `/site/eders` with saved OBIS cookies
and returns the native `https://eders.manas.edu.kg/auth/userkey/login.php?key=...` link
without visiting it. The user's browser consumes the native key; Eders sets its own
session cookies and redirects to its home page. Passwords and OBIS cookies stay on the server.
If the saved OBIS session expired, the existing automatic recovery/manual-login and
backoff rules apply. Expected auth failures commit that state and show an actionable error.

## Link handling

- A random 256-bit grant is issued only from the authenticated Telegram callback.
  It contains no user ID or credentials and is stored by SHA-256 digest in process memory.
- One outstanding grant per user; issuing another revokes the previous one.
  Consumption is synchronous before any await, so concurrent requests cannot reuse it.
  Expiry is checked with a monotonic clock. Restarting the single application process
  revokes all grants. Multiple replicas would require a shared atomic grant store first.
- The grant is in the URL fragment, outside HTTP access logs and referrers. The landing
  page removes it from browser history and submits it in a same-origin POST body.
  GET/HEAD previews do not consume it. Request-body logging must remain disabled for this route.
- The POST checks Origin, body size, token shape and single token field. It locks the
  user row and rejects grants issued before a student-number/password change or deletion.
  Grants are spent even when upstream authentication fails; request a new one to retry.
- Responses are no-store. The landing page uses same-origin referrers to retain the
  browser's POST Origin header; redirects and error pages use no-referrer. The fragment
  is never part of any referrer. The page uses a restrictive nonce CSP and disallows
  framing. Only the exact HTTPS Eders userkey endpoint is returned;
  unrelated onward-redirect parameters are discarded. No bot session cookies are exported.
- The protected Telegram message discourages forwarding, but the URL is still a bearer
  credential for its short lifetime. Users are explicitly told not to share it.

## Verification boundary

The existing local Postman fixture models a fresh, one-use native browser key separately
from its legacy SSO fixture. Tests exercise real HTTP/cookie behavior with a separate browser
client, PostgreSQL session-cookie rotation, replay/expiry/concurrency, owner checks,
credential-change revocation and preservation of completion buttons in all five locales.
Chromium was also exercised against local HTTP/HTTPS servers through a proxy that serves
only the synthetic Eders host: fragment removal, the browser's real Origin header,
POST/303 navigation, Secure/HttpOnly session cookies, no bot referrer and grant replay rejection.

The upstream auth_userkey source deletes keys during login and defaults to a 60-second
key lifetime with IP restriction disabled:
https://github.com/catalyst/moodle-auth_userkey/blob/master/auth.php.
The actual Eders plugin version, key lifetime and IP restriction setting have not been
verified with a real university account. If Eders binds generated keys to the backend IP,
browser handoff requires the university to change that setting; no cross-domain-cookie
workaround is implemented.

## OBIS result timestamps

Grades and attendance pages display the saved snapshot's `fetched_at` in Bishkek time,
including empty snapshots and every pagination page. The read boundary returns data
and time from the same database row, without a separate timestamp lookup or HTTP refresh.
Each Telegram message caches its rendered pages, retaining its original date during
pagination. Failed refreshes preserve both the previous results and their timestamp.
