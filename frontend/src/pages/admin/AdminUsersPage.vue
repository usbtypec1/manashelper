<script setup lang="ts">
import { computed, onScopeDispose, ref } from 'vue'
import AdminActions from '../../features/admin/AdminActions.vue'
import AdminShell from '../../features/admin/AdminShell.vue'
import { setUserBlocked, type UserProfile } from '../../features/admin/users/api'
import { useAdminCopy } from '../../features/admin/useAdminCopy'
import { useAdminUsers } from '../../features/admin/users/useAdminUsers'
import { HttpError } from '../../shared/api/http'
import { locales } from '../../shared/i18n/locale'
import type { BottomAction } from '../../shared/telegram/bottomButtons'
import { confirmTelegramAction } from '../../shared/telegram/confirmation'
import { useTelegram } from '../../shared/telegram/telegram'

const { rawInitData, userId } = useTelegram()
const { copy, languageNames, themeNames } = useAdminCopy()
const search = ref('')
const language = ref('')
const theme = ref('')
const botStatus = ref('')
const filters = computed(() => ({ q: search.value.trim(), locale: language.value, theme: theme.value, status: botStatus.value }))
const { status, users, nextCursor, pending, loadMore, refresh, retry } = useAdminUsers(rawInitData, filters)
const filtered = computed(() => Object.values(filters.value).some(Boolean))
const changingId = ref<string | null>(null)
const changeFailed = ref(false)
let disposed = false
onScopeDispose(() => { disposed = true })

function statusName(user: UserProfile) {
  if (user.is_blocked) return 'blocked'
  return user.bot_stopped ? 'stopped' : 'active'
}

async function changeBlocking(user: UserProfile) {
  const initData = rawInitData.value
  if (!initData || changingId.value !== null || pending.value !== null) return
  const blocked = !user.is_blocked
  const name = Array.from(user.full_name).slice(0, 64).join('')
  const message = copy.value.admin[blocked ? 'confirm_block' : 'confirm_unblock'].replace('{name}', name)
  const label = copy.value.admin[blocked ? 'block_user' : 'unblock_user']
  changingId.value = user.id
  changeFailed.value = false
  try {
    if (!await confirmTelegramAction(message, label) || disposed || rawInitData.value !== initData) return
    const result = await setUserBlocked(initData, user.id, blocked)
    if (disposed || rawInitData.value !== initData) return
    const entry = users.value.find(profile => profile.id === user.id)
    if (entry) entry.is_blocked = result
    if (botStatus.value) await refresh()
  } catch (error) {
    if (disposed || rawInitData.value !== initData) return
    if (error instanceof HttpError && error.unauthorized) await refresh()
    else changeFailed.value = true
  } finally {
    changingId.value = null
  }
}

const refreshAction = computed<BottomAction>(() => ({
  text: copy.value.admin.refresh, run: refresh, disabled: pending.value !== null || changingId.value !== null,
  loading: pending.value === 'refresh',
}))
const primary = computed<BottomAction | null>(() => {
  if (status.value === 'error') {
    return { text: copy.value.preferences.retry, run: retry, disabled: changingId.value !== null, loading: false }
  }
  if (nextCursor.value !== null) {
    return {
      text: copy.value.admin.load_more, run: loadMore, disabled: pending.value !== null || changingId.value !== null,
      loading: pending.value === 'more',
    }
  }
  return users.value.length ? refreshAction.value : null
})
const secondary = computed(() => nextCursor.value !== null && status.value !== 'error' ? refreshAction.value : null)
</script>

<template>
  <AdminShell :title="copy.admin.users" section="users">
    <fieldset
      v-if="rawInitData && status !== 'session_expired' && status !== 'denied'"
      class="admin-card directory-filters"
      :aria-label="copy.admin.filters"
    >
      <label class="admin-field directory-search">
        <span>{{ copy.admin.search }}</span>
        <input v-model="search" type="search" maxlength="128" autocomplete="off" :placeholder="copy.admin.search_hint" />
      </label>
      <label class="admin-field">
        <span>{{ copy.admin.language }}</span>
        <select v-model="language">
          <option value="">{{ copy.admin.any_language }}</option>
          <option v-for="code in locales" :key="code" :value="code">{{ languageNames.of(code) }}</option>
        </select>
      </label>
      <label class="admin-field">
        <span>{{ copy.admin.theme }}</span>
        <select v-model="theme">
          <option value="">{{ copy.admin.any_theme }}</option>
          <option v-for="(name, code) in themeNames" :key="code" :value="code">{{ name }}</option>
        </select>
      </label>
      <label class="admin-field">
        <span>{{ copy.admin.status }}</span>
        <select v-model="botStatus">
          <option value="">{{ copy.admin.any_status }}</option>
          <option value="active">{{ copy.admin.active }}</option>
          <option value="stopped">{{ copy.admin.stopped }}</option>
          <option value="blocked">{{ copy.admin.blocked }}</option>
        </select>
      </label>
    </fieldset>

    <table v-if="users.length" role="table" aria-labelledby="admin-page-title" class="directory">
      <thead role="rowgroup">
        <tr role="row">
          <th role="columnheader" scope="col">{{ copy.admin.name }}</th>
          <th role="columnheader" scope="col">Telegram ID</th>
          <th role="columnheader" scope="col">{{ copy.admin.status }}</th>
          <td role="cell" class="action-cell"></td>
        </tr>
      </thead>
      <tbody role="rowgroup">
        <tr v-for="user in users" :key="user.id" role="row">
          <td role="cell" class="person-cell">
            <div class="identity">
              <span class="initial" aria-hidden="true">{{ Array.from(user.full_name.trim())[0]?.toLocaleUpperCase() }}</span>
              <div>
                <strong>{{ user.full_name }}</strong>
                <small v-if="user.username">@{{ user.username }}</small>
                <small>{{ languageNames.of(user.locale) }} · {{ themeNames[user.theme] }}</small>
              </div>
            </div>
          </td>
          <td role="cell" class="id-cell">
            <span class="id-label" aria-hidden="true">Telegram ID</span>
            <span class="telegram-id">{{ user.id }}</span>
          </td>
          <td role="cell" class="status-cell">
            <span class="delivery-state" :class="statusName(user)">
              {{ copy.admin[statusName(user)] }}
            </span>
          </td>
          <td role="cell" class="action-cell">
            <button
              v-if="user.id !== String(userId)"
              type="button"
              class="moderation-action"
              :class="{ destructive: !user.is_blocked }"
              :aria-label="`${copy.admin[user.is_blocked ? 'unblock_user' : 'block_user']} ${user.full_name}`"
              :disabled="changingId !== null || pending !== null"
              @click="changeBlocking(user)"
            >
              {{ copy.admin[user.is_blocked ? 'unblock_user' : 'block_user'] }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <p v-if="status === 'open_telegram' || status === 'session_expired'" class="admin-hint" role="status">
      {{ copy.preferences[status] }}
    </p>
    <p v-else-if="status === 'denied'" role="alert">{{ copy.admin.denied }}</p>
    <p v-else-if="status === 'error'" role="alert">{{ copy.preferences.error }}</p>
    <p v-else-if="status === 'loading' && !users.length" class="admin-hint" role="status">{{ copy.preferences.loading }}</p>
    <p v-else-if="status === 'ready' && !users.length" class="admin-hint" role="status">
      {{ filtered ? copy.admin.no_matches : copy.admin.empty }}
    </p>
    <p v-if="changeFailed" role="alert">{{ copy.preferences.error }}</p>
    <AdminActions :primary="primary" :secondary="secondary" :loading-text="copy.preferences.loading" />
  </AdminShell>
</template>

<style scoped>
.directory-filters { display: grid; gap: 8px 12px; }
.directory-filters .admin-field:not(.directory-search) {
  grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
  align-items: center;
}
.directory-filters select { padding-inline: 8px; }
.directory-search { margin-bottom: 4px; }
.directory {
  display: block;
  width: 100%;
  table-layout: fixed;
  border-spacing: 0;
  border: 1px solid var(--admin-divider);
  border-radius: 16px;
  background: var(--admin-section);
  font-size: 14px;
}
th, td { min-width: 0; text-align: start; vertical-align: middle; }
th { font-size: 13px; font-weight: 600; color: var(--tg-theme-section-header-text-color, var(--admin-hint)); }
.identity { display: flex; align-items: center; gap: 12px; }
.identity > div { min-width: 0; }
.identity strong { display: block; font-size: 15px; font-weight: 600; }
.initial {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  border-radius: 50%;
  background: var(--admin-control);
  color: var(--admin-accent);
  font-weight: 600;
}
small { display: block; margin-top: 2px; font-size: 12px; color: var(--admin-hint); }
.id-cell { font-size: 13px; }
.id-label { color: var(--admin-hint); }
.telegram-id { font-variant-numeric: tabular-nums; }
.delivery-state { color: var(--admin-hint); font-size: 13px; font-weight: 600; }
.delivery-state.active, .moderation-action { color: var(--admin-accent); }
.moderation-action {
  min-height: 44px;
  max-width: 100%;
  padding: 4px 8px;
  border-radius: 8px;
  background: transparent;
  font-size: 13px;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.moderation-action:focus-visible { outline-offset: -2px; }
.delivery-state.blocked, .moderation-action.destructive {
  color: var(--tg-theme-destructive-text-color, var(--admin-default-danger));
}
.moderation-action:disabled { opacity: .65; }

tbody { display: block; }
/* Keep headers available to assistive tech while the same rows reflow on phones. */
thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
tbody tr {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  grid-template-areas: "person person" "id action" "status action";
  gap: 2px 12px;
  padding: 12px;
}
tbody tr + tr { border-top: 1px solid var(--admin-divider); }
.person-cell { grid-area: person; margin-bottom: 6px; }
.id-cell { grid-area: id; }
.id-label { display: block; font-size: 11px; }
.status-cell { grid-area: status; }
.action-cell { grid-area: action; align-self: center; text-align: end; }

@container admin-content (min-width: 480px) {
  .directory-filters { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
  .directory-filters .admin-field:not(.directory-search) { grid-template-columns: minmax(0, 1fr); align-items: stretch; }
  .directory-search { grid-column: 1 / -1; margin-bottom: 0; }
}

@container admin-content (min-width: 640px) {
  .directory { display: table; }
  thead { position: static; width: auto; height: auto; overflow: visible; clip-path: none; }
  tbody { display: table-row-group; }
  tbody tr { display: table-row; }
  tbody tr + tr { border: 0; }
  th, td { padding: 8px 12px; }
  thead > tr > *, tbody tr:not(:last-child) > td { border-bottom: 1px solid var(--admin-divider); }
  thead th:nth-child(2) { width: 22%; }
  thead th:nth-child(3) { width: 18%; }
  .id-label { display: none; }
  .action-cell { width: 22%; text-align: end; }
}

@container admin-content (min-width: 760px) {
  .directory-filters { grid-template-columns: minmax(0, 2fr) repeat(3, minmax(0, 1fr)); }
  .directory-search { grid-column: auto; }
}
</style>
