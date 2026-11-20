<script setup lang="ts">
import { computed, watchEffect } from 'vue'
import { useAdminUsers } from '../features/admin/useAdminUsers'
import messages from '../messages.json'
import { useTelegramBottomButtons, type BottomAction } from '../shared/telegram/bottomButtons'
import { useTelegram } from '../shared/telegram/telegram'

const { rawInitData, languageCode } = useTelegram()
const { status, users, nextCursor, pending, loadMore, refresh, retry } = useAdminUsers(rawInitData)
const locale = computed(() => {
  const code = languageCode.value
  return Object.hasOwn(messages, code) ? code as keyof typeof messages : 'en'
})
const copy = computed(() => messages[locale.value])

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
const { nativeMain, nativeSecondary } = useTelegramBottomButtons(primary, secondary)

watchEffect(() => {
  document.documentElement.lang = locale.value
  document.title = copy.value.admin.title
})
</script>

<template>
  <div class="telegram-admin">
    <main class="app-shell admin-users">
      <header>
        <p class="panel-title">{{ copy.admin.title }}</p>
        <h1 id="users-title">{{ copy.admin.users }}</h1>
      </header>

      <table v-if="users.length" aria-labelledby="users-title">
        <thead>
          <tr><th scope="col">{{ copy.admin.name }}</th><th scope="col">Telegram ID</th></tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td>
              <span>{{ user.full_name }}</span>
              <small v-if="user.username">@{{ user.username }}</small>
            </td>
            <td>{{ user.id }}</td>
          </tr>
        </tbody>
      </table>

      <p v-if="status === 'open_telegram' || status === 'session_expired'" role="status">
        {{ copy.preferences[status] }}
      </p>
      <p v-else-if="status === 'denied'" role="alert">{{ copy.admin.denied }}</p>
      <p v-else-if="status === 'error'" role="alert">{{ copy.preferences.error }}</p>
      <p v-else-if="status === 'loading' && !users.length" role="status">{{ copy.preferences.loading }}</p>
      <p v-else-if="status === 'ready' && !users.length" role="status">{{ copy.admin.empty }}</p>
      <div v-if="(primary && !nativeMain) || (secondary && !nativeSecondary)" class="fallback-actions">
        <button v-if="primary && !nativeMain" type="button" :disabled="primary.disabled" @click="primary.run">
          {{ primary.loading ? copy.preferences.loading : primary.text }}
        </button>
        <button v-if="secondary && !nativeSecondary" type="button" class="secondary-action" :disabled="secondary.disabled" @click="secondary.run">
          {{ secondary.loading ? copy.preferences.loading : secondary.text }}
        </button>
      </div>
    </main>
  </div>
</template>

<style scoped>
.telegram-admin {
  --admin-default-bg: #efeff4;
  --admin-default-section: #fff;
  --admin-default-text: #000;
  --admin-default-hint: #707579;
  --admin-default-divider: rgb(0 0 0 / 8%);
  --admin-default-accent: #007aff;
  --admin-accent: var(--tg-theme-button-color, var(--admin-default-accent));
  --admin-hint: var(--tg-theme-hint-color, var(--admin-default-hint));
  --admin-divider: var(--tg-theme-section-separator-color, var(--admin-default-divider));
  --admin-section: var(--tg-theme-section-bg-color, var(--tg-theme-bg-color, var(--admin-default-section)));
  min-height: 100dvh;
  background: var(--tg-theme-secondary-bg-color, var(--tg-theme-bg-color, var(--admin-default-bg)));
  color: var(--tg-theme-text-color, var(--admin-default-text));
}
html[data-theme='dark'] .telegram-admin {
  --admin-default-bg: #0f0f0f;
  --admin-default-section: #212121;
  --admin-default-text: #fff;
  --admin-default-hint: #aaa;
  --admin-default-divider: rgb(255 255 255 / 2%);
  --admin-default-accent: #2990ff;
}
header { margin: 10px 0 24px; }
.panel-title { margin: 0 0 6px; font-size: 14px; }
h1 { margin: 0; font-size: 28px; line-height: 1.2; }
table { width: 100%; border-collapse: collapse; background: var(--admin-section); }
th, td { padding: 12px; border-bottom: 1px solid var(--admin-divider); text-align: left; }
th { color: var(--tg-theme-section-header-text-color, var(--admin-hint)); font-size: 13px; font-weight: 600; }
td { font-size: 14px; vertical-align: top; overflow-wrap: anywhere; }
th:last-child, td:last-child { width: 1%; text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
small { display: block; margin-top: 3px; font-size: 12px; }
p, small { color: var(--admin-hint); }
.fallback-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.fallback-actions button {
  min-height: 44px;
  padding: 8px 16px;
  border-radius: 8px;
  background: var(--admin-accent);
  color: var(--tg-theme-button-text-color, #fff);
}
.fallback-actions .secondary-action { background: var(--admin-section); color: var(--admin-accent); }
.fallback-actions button:disabled { opacity: .65; }
</style>
