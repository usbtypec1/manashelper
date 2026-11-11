# Frontend conventions

Applies to `frontend/` together with the repository's root [AGENTS.md](../AGENTS.md).
This is the target for subsequent refactoring, not a claim that every existing file already follows it.
Apply it incrementally within the requested scope; preserve unrelated uncommitted work.

## Stack and scope

- Use Vue 3 Composition API, `<script setup lang="ts">`, strict TypeScript, Vue Router 4 and Vite.
- Use Bun 1.4.3 and keep `package.json` and `bun.lock` consistent. Reuse installed dependencies.
  Run scripts with `bun run --bun`; use `bun install --frozen-lockfile` for reproducible installs.
  Keep the Bun version aligned in `packageManager`, CI and Docker; commit only the Bun lockfile.
- Prefer Vue reactivity, native HTML and browser APIs. Add dependencies when a concrete need justifies them.
- Keep product behavior, API contracts, translations and the established visual design intact during refactoring.

## Ownership and organization

Use these locations as code is extracted; create directories only when they have real content:

| Location | Responsibility |
| --- | --- |
| `src/main.ts`, `src/App.vue`, `src/router.ts` | Bootstrap, application shell and route definitions. |
| `src/pages/` | Route entry components that compose feature UI, navigation and page states. |
| `src/features/<feature>/` | Feature components, API functions, types, pure helpers and stateful composables. |
| `src/shared/api/` | Common HTTP transport and request error handling. |
| `src/shared/telegram/` | Typed Telegram WebApp access and lifecycle integration. |
| `src/shared/i18n/` | Locale selection and access to generated translations. |
| `src/shared/ui/` | Reusable UI with a feature-independent contract. |
| `src/assets/` | Bundled visual assets; retain stable achievement-art mappings. |

- Pages compose features; features may depend on shared code. Shared code must not import features or pages.
- Keep each feature's rules and state with that feature. Coordinate separate features at the page level.
- Share code when it has an actual common responsibility. A helper used once may stay beside its owner.
- Start feature folders flat (`api.ts`, `types.ts`, `useCourseSelection.ts`, components); add nesting when useful.
- Split components by responsibility and lifecycle, not an arbitrary line limit. Extract cohesive sections,
  not wrappers that only forward every prop and event. Avoid broad utility folders and re-export chains.
- Use PascalCase for Vue components and domain types, camelCase for functions and variables,
  `useX` for stateful composables, and descriptive filenames. Pure helpers are ordinary functions.

## Components and state

- A page composes the screen. A feature composable owns its loading, mutations and state transitions.
  Feature API modules own endpoint calls; UI components must not assemble authenticated requests.
- Presentation components take typed props and emit typed user intentions. Keep props immutable;
  use explicit events or typed `v-model` contracts for parent-owned state.
- Keep derived values in `computed`. Use `watch` for specific side effects, not to maintain duplicate state.
- Keep state local to its owner. Share a composable when several components need the same scenario;
  use `provide`/`inject` for a real subtree dependency. Introduce an application store only for demonstrated
  state ownership across routes. Do not use module-level mutable state as an accidental user-data cache.
- Expose a small, named composable API: state needed by the view and actions such as `load`, `save`, `selectCourse`.
  Dispose watchers, timers, SDK listeners and pending work with the owning scope.
- Represent loading, empty, denied/expired, failure, saving and success deliberately. Keep them distinct
  where the user needs a different action; never silently replace failed data with an empty success state.

## Routing

- `App.vue` renders `RouterView`; add only genuinely shared shell elements there.
- Define routes centrally in `src/router.ts`, with lazy page imports and the `/app/` history base.
- Use named routes with `RouterLink` or `useRouter`; read navigation state through `useRoute`.
  Route-derived state must react to parameter/query changes when Vue reuses a component.
- Put navigable pages and tabs in the URL. Keep transient dialogs local unless deep linking is required.
- Preserve legacy `?view=...` redirects, other launch query parameters and Telegram launch hashes.
  Keep route changes consistent with Telegram launch buttons and server history fallback.
- Support direct entry, reload, browser Back/Forward and a useful return path from terms.
  Internal navigation must preserve the WebView session rather than reload the document.
- Routes control presentation. The server remains responsible for authentication and authorization.

## API contracts and asynchronous work

- Centralize authentication headers, `cache: 'no-store'` and HTTP error classification in common transport.
  Keep endpoint names, request/response types and feature-specific mapping in the owning feature's API module.
- Use explicit types, unions and `unknown` at untrusted boundaries. Narrow before use; avoid `any`, unchecked
  assertions and non-null assertions that hide missing data. A generic `response.json()` type is not runtime validation.
- Follow documented response shapes; validate values used for security decisions or unsafe operations.
  Preserve HTTP status information. A 401 means invalid/expired authentication; a 403 means access denied,
  not proof of expiration. Handle unavailable features and unexpected failures separately where relevant.
- Backend data is authoritative. Send desired values for idempotent writes, wait for confirmation before
  showing saved state, and preserve the previous value on failure. Never retry non-idempotent writes blindly.
- Prevent conflicting submissions. Cancel obsolete reads or ignore their results; an old faculty/department
  response must not overwrite a newer selection. Clear dependent selections when their parent changes.
- Frontend code calls the local Mini App API. Academic fetching, achievement qualification, permissions
  and persistence belong to the backend; do not reproduce those rules in UI state.

## Telegram and privacy

- Define the WebApp bridge types and optional capabilities once in the Telegram adapter.
  Components must not repeat `Window` casts or independently install the same global SDK listeners.
  Use the pinned stable `@tma.js/sdk-vue` API (`useSignal` in 1.0.23); do not copy RC examples from `master`.
  `shared/telegram/telegram.ts` owns initialization, theme/viewport binding and BackButton coordination.
- Pair every event registration with cleanup. Coordinate Telegram BackButton with router navigation
  and active dialogs so one click performs one action and closing a dialog restores focus.
- Use signed `initData` only for the server authentication flow. `initDataUnsafe` may provide display hints,
  never trusted identity or permission. Never send a client-selected user ID as the acting user.
- Never add application-managed persistence or logging of raw initData, passwords or other credentials
  in URLs, browser storage, screenshots or diagnostics. The SDK's standard launch cache in `sessionStorage`
  retains signed launch data for reloads within the current tab; do not copy it into other storage.
  Keep private API responses out of persistent browser caches. The backend still enforces signature and expiry.
- Settings and courses remain available to registered users without achievement access. Terms remain public
  and must not call private APIs. Hidden or disabled UI is not a substitute for the server's access checks.
- Leaderboard UI consumes only the public earned-award projection. Preserve the exclusion of credentials,
  student numbers, raw academic data and unfinished progress.

## Localization and styling

- English, Russian, Kyrgyz, Turkish and simplified Chinese `.po` catalogs are the source of user-facing copy.
  Export with `frontend/scripts/export_messages.py`; do not edit generated `src/messages.json` or add a parallel
  handwritten translation dictionary. Keep new keys extractable by Babel and preserve placeholders.
- Centralize locale normalization and English fallback. Validate external locale values against supported
  own keys. Set `document.documentElement.lang`; format dates/numbers with `Intl` or locale-aware native APIs.
- Keep saved bot theme (`data-bot-theme`) separate from Telegram appearance (`data-theme`). Keep legal text
  factually stable across themes and update its shared source instead of duplicating terms in components.
- Use existing CSS custom properties for shared colors and surfaces. Keep resets, tokens and application
  themes global; keep component-specific layout/styles scoped or explicitly namespaced.
- Preserve achievement artwork and meaningful status distinctions. Keep layouts usable from 280px wide,
  including long translations, safe-area insets and light/dark appearances.
- Use semantic HTML, associated labels, visible keyboard focus and adequately sized controls.
  Dialogs need accessible names, keyboard closing and focus restoration. Respect reduced-motion preferences.
- Render dynamic content as text. Use `v-html` only with an explicit sanitization boundary; validate externally
  supplied URLs and protocols before using them in navigation or resource attributes.

## Verification and refactoring

Before extraction, trace the route, component, request, backend contract and existing tests. Identify the
behavior to preserve. Move one responsibility at a time, update all consumers and remove the replaced path.
Keep the intermediate app runnable. Do not combine structural work with redesign or product changes.

From the repository root, prepare translations when needed and run the build:

```sh
.venv/bin/pybabel compile -d src/manashelper/locales
.venv/bin/python frontend/scripts/export_messages.py
bun run --cwd frontend --bun build
```

The build runs `vue-tsc --noEmit` and Vite. `bun install --cwd frontend --frozen-lockfile` restores dependencies,
not a prerequisite to repeat on every edit. Generated messages, bundles and test screenshots stay uncommitted.

- For changed interaction paths, run the relevant Playwright spec, for example
  `bun run --cwd frontend --bun test:e2e router.spec.ts`. Use the full E2E suite for shared routing,
  transport, Telegram lifecycle, localization or theme changes that affect multiple pages.
- E2E needs the development Postgres, compiled catalogs, built assets and development environment from the
  root instructions. Its fixture uses real local APIs/database in an isolated schema and simulates the
  Telegram bridge. Never aim it at production; do not replace integration coverage with successful mocks.
- Cover observable risks: route reload/history, expired/denied access, failed saves, stale responses,
  keyboard/dialog behavior and mobile overflow as relevant. Add unit tests for extracted nontrivial logic
  when an appropriate runner is available; avoid tests that merely repeat the implementation.
- If backend routes/contracts change, run their focused Python checks under root instructions too.
  There is currently no frontend lint script; do not invent a passing lint result.
- Review the final diff, including new files and generated-artifact exclusions. Report precisely which
  checks ran, their results and remaining limitations. Browser fixtures do not establish live Telegram behavior.
