# Telegram Mini App interaction guidelines

Use the Telegram client controls for actions that apply to the whole screen. Keep navigation, forms,
tables, and actions on a specific item in Vue. `@tma.js/sdk-vue` is the bridge to Telegram.

## Launch and authentication

| Entry point | When to use it |
| --- | --- |
| Personal bot MenuButton | A destination that a user opens regularly. Use per-chat `setChatMenuButton` for the admin panel. Install it only for configured personal user IDs in private chats. |
| Inline Web App button in a bot message | A contextual authenticated flow such as a particular settings or achievement screen. Inline and bot menu launches provide signed `initData`. |
| Reply-keyboard Web App button | A small, standalone input that sends up to 4096 bytes through `sendData` and closes the Mini App. Use the authenticated API for Manashelper screens. |
| Bot profile Main Mini App or `startapp` link | A discoverable or shareable entry point. Validate the requested screen and check permission on the server even when launch data is signed. |
| Inline mode, attachment menu, join request | Use only for a flow that needs that launch context. Check Telegram's availability and chat access rules first. |

Extract the actor from verified `initData` on the server. Check signature, freshness and permission on each
private request. Treat `initDataUnsafe` and the URL as display and routing inputs. Do not store raw
`initData`, user lists, academic data, or credentials in app-managed browser or Telegram storage.
Telegram's SDK may retain launch parameters within the WebView for reload. Use `Cache-Control: no-store`
for private API responses.

## Choose the control

| Control | Use it for |
| --- | --- |
| MainButton | One clear screen-level action such as Apply, Save, Continue, Load more, or Retry. Use a specific verb. Hide it on screens without an action. |
| SecondaryButton | One useful alternative to the current primary action such as Refresh while loading more is available, or Cancel a draft. When only one action remains, use MainButton. SecondaryButton requires Bot API 7.10+. |
| BackButton | Return within the app. Close an open dialog first, then honor router history or the screen's known parent. Hide it at the root. Telegram supplies the host close control. |
| SettingsButton | Open a durable settings route from Telegram's context menu. Use an in-page route link when the client lacks the capability. |
| In-page controls | Search, filters, tabs, toggles, row actions and links, which need context beside the item or section. Retain semantic labels, keyboard access and visible focus. |
| Native popup | Confirm a short, consequential action or show a brief acknowledgement when the user must respond. Give a destructive action an explicit label. Use a Vue dialog for longer content, forms or several steps and for clients without popup support. Inline errors for routine failures stay near the action. |
| Closing confirmation | Enable while there are unsaved changes a user might lose. Clear it after saving, discarding, or leaving the owning screen. Keep vertical swipes enabled unless the app requires a conflicting gesture. |
| Haptic feedback | Lightweight acknowledgement for a meaningful choice or a confirmed result. The visual or accessible status still communicates it when haptics are unavailable. |
| Telegram links, share, invoice, download | Use the matching native method for an explicit user action. Validate destinations and payloads, handle cancellation, and confirm the result server-side when it matters. Use `openTelegramLink` for Telegram destinations and `openLink` for external URLs. |
| QR, location, contact, write access, clipboard | Request only after a user takes an action that explains the need. Handle refusal or unsupported clients. Never make a background permission request. |
| Device, cloud or secure storage | Use only if the feature needs client-side persistence and the chosen scope fits it. Server data and access rules remain authoritative. |

Bot MenuButton opens the WebView from the chat. MainButton and SecondaryButton belong to the bottom bar
inside it. A screen provides its current labels, actions, disabled state and progress to the shared
Telegram adapter. Mount and subscribe once per owner. Hide controls and unsubscribe on route exit.
During a request, disable conflicting actions and show progress on the initiating button.
Give an unsupported action one equivalent in-page control wired to the same handler.

## Theme and layout

- Bind `themeParams` once in the SDK adapter. Use Telegram's live background, section, separator,
  text, hint and button colors with fallbacks for missing tokens. Test custom colors and live changes within
  the same light or dark mode. Manashelper's saved bot theme remains a separate preference.
- Use normal document flow and support mobile widths from 280 px. Use safe-area and content-safe-area
  insets for Telegram chrome and system UI. Use stable viewport height when sizing a fixed region.
  Expand when the app needs room. Reserve fullscreen or orientation lock for a feature that needs it.
- Call `ready()` after essential UI mounts. Render loading, denial, failure, and empty results in the page.
  Keep focus and state useful after theme changes or Telegram minimizes the WebView.
- Put integration in `frontend/src/shared/telegram/`. Use SDK capability checks before native calls.
  Keep supported clients' native and web fallbacks from showing duplicate actions.

## Verification

Use Playwright with the real local API and simulated Telegram launch parameters. Assert the native setup
payload, emit the click event and verify the resulting action. Cover an older client, live theme changes,
route exit cleanup and narrow layouts. For protected screens, also test missing or invalid init data and
authenticated users without permission. Check live Telegram on the supported clients before claiming native
rendering or launch behavior has been verified.

- [Telegram Mini Apps design guidelines](https://core.telegram.org/bots/webapps#designing-mini-apps)
- [Telegram client APIs and themes](https://core.telegram.org/bots/webapps#initializing-mini-apps)
- [Bottom buttons](https://core.telegram.org/bots/webapps#bottombutton)
- [Telegram launch data validation](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app)
- [tma.js Vue bindings](https://github.com/Telegram-Mini-Apps/tma.js/tree/master/packages/sdk-vue)
