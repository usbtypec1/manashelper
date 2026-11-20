<script setup lang="ts">
import { computed, ref } from 'vue'
import AdminActions from '../features/admin/AdminActions.vue'
import AdminShell from '../features/admin/AdminShell.vue'
import { locales, useAdminCopy } from '../features/admin/useAdminCopy'
import { useAdminUsers } from '../features/admin/useAdminUsers'
import type { BottomAction } from '../shared/telegram/bottomButtons'
import { useTelegram } from '../shared/telegram/telegram'

const { rawInitData } = useTelegram()
const { copy, languageNames, themeNames } = useAdminCopy()
const search = ref('')
const language = ref('')
const theme = ref('')
const botStatus = ref('')
const filters = computed(() => ({ q: search.value.trim(), locale: language.value, theme: theme.value, status: botStatus.value }))
const { status, users, nextCursor, pending, loadMore, refresh, retry } = useAdminUsers(rawInitData, filters)
const filtered = computed(() => Object.values(filters.value).some(Boolean))

const refreshAction = computed<BottomAction>(() => ({
  text: copy.value.admin.refresh, run: refresh, disabled: pending.value !== null, loading: pending.value === 'refresh',
}))
const primary = computed<BottomAction | null>(() => {
  if (status.value === 'error') {
    return { text: copy.value.preferences.retry, run: retry, disabled: false, loading: false }
  }
  if (nextCursor.value !== null) {
    return {
      text: copy.value.admin.load_more, run: loadMore, disabled: pending.value !== null, loading: pending.value === 'more',
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
        </select>
      </label>
    </fieldset>

    <table v-if="users.length" aria-labelledby="admin-page-title" class="directory">
      <thead>
        <tr><th scope="col">{{ copy.admin.name }}</th><th scope="col">Telegram ID</th></tr>
      </thead>
      <tbody>
        <tr v-for="user in users" :key="user.id">
          <td>
            <div class="identity">
              <span class="initial" aria-hidden="true">{{ Array.from(user.full_name.trim())[0]?.toLocaleUpperCase() }}</span>
              <div>
                <strong>{{ user.full_name }}</strong>
                <small v-if="user.username">@{{ user.username }}</small>
                <small>{{ languageNames.of(user.locale) }} · {{ themeNames[user.theme] }}</small>
              </div>
            </div>
          </td>
          <td>
            <span class="telegram-id">{{ user.id }}</span>
            <small class="delivery-state" :class="{ reachable: !user.bot_stopped }">
              {{ user.bot_stopped ? copy.admin.stopped : copy.admin.active }}
            </small>
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
    <AdminActions :primary="primary" :secondary="secondary" :loading-text="copy.preferences.loading" />
  </AdminShell>
</template>

<style scoped>
.directory-filters { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; border: 0; }
.directory-search { grid-column: 1 / -1; }
.directory { width: 100%; border-spacing: 0; border-radius: 16px; background: var(--admin-section); }
th, td { padding: 12px 10px; text-align: left; }
th { font-size: 12px; font-weight: 600; color: var(--tg-theme-section-header-text-color, var(--admin-hint)); }
tbody tr:not(:last-child) td, th { box-shadow: inset 0 -1px var(--admin-divider); }
td { vertical-align: middle; min-width: 0; overflow-wrap: anywhere; font-size: 15px; }
td:last-child, th:last-child { width: 1%; text-align: right; }
th:last-child, .telegram-id { white-space: nowrap; font-variant-numeric: tabular-nums; }
.identity { display: flex; align-items: center; gap: 10px; }
.initial {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border-radius: 50%;
  background: var(--admin-control);
  color: var(--admin-accent);
  font-weight: 650;
}
small { display: block; margin-top: 3px; font-size: 12px; color: var(--admin-hint); }
.delivery-state { font-weight: 500; }
.delivery-state.reachable { color: var(--admin-accent); }
@media (max-width: 440px) {
  .directory-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 360px) {
  .directory-filters { padding: 12px; }
  .initial { display: none; }
  .telegram-id { font-size: 12px; }
}
</style>
