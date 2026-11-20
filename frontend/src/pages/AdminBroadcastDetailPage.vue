<script setup lang="ts">
import { computed, onScopeDispose, shallowRef, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AdminActions from '../features/admin/AdminActions.vue'
import AdminShell from '../features/admin/AdminShell.vue'
import CampaignCounts from '../features/admin/CampaignCounts.vue'
import {
  deliveryStatuses, getCampaign, getDeliveries, retryableStatuses, retryCampaign, type CampaignDetail,
} from '../features/admin/campaignApi'
import { useAdminCopy } from '../features/admin/useAdminCopy'
import { useAdminPages } from '../features/admin/useAdminPages'
import { HttpError } from '../shared/api/http'
import type { BottomAction } from '../shared/telegram/bottomButtons'
import { confirmTelegramAction } from '../shared/telegram/confirmation'
import { useTelegram } from '../shared/telegram/telegram'

const route = useRoute()
const { rawInitData } = useTelegram()
const { copy, locale, languageNames, themeNames } = useAdminCopy()
const campaignId = computed(() => String(route.params.id))
const campaign = shallowRef<CampaignDetail | null>(null)
const retrying = ref(false)
const retryError = ref(false)
const retried = ref<number | null>(null)
let disposed = false
onScopeDispose(() => { disposed = true })
watch([campaignId, rawInitData], () => {
  campaign.value = null
  retryError.value = false
  retried.value = null
})

const { status, items, nextCursor, refresh, loadMore } = useAdminPages(rawInitData, async (initData, cursor, signal) => {
  const id = campaignId.value
  const [detail, page] = await Promise.all([
    getCampaign(initData, id, signal),
    getDeliveries(initData, id, cursor, signal),
  ])
  if (!signal.aborted) campaign.value = detail
  return page
}, campaignId)
const dateFormat = computed(() => new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }))
const canRetry = computed(() => retryableStatuses.some(state => campaign.value?.counts[state]))
const statusText = (state: string) => deliveryStatuses.find(value => value === state)

async function retry() {
  const id = campaignId.value
  const initData = rawInitData.value
  if (!initData || retrying.value || status.value !== 'ready') return
  retrying.value = true
  retryError.value = false
  retried.value = null
  try {
    if (!await confirmTelegramAction(copy.value.admin.confirm_retry, copy.value.admin.retry_deliveries)
      || disposed || id !== campaignId.value || initData !== rawInitData.value) return
    const count = await retryCampaign(initData, id)
    if (!disposed && id === campaignId.value && initData === rawInitData.value) {
      retried.value = count
      await refresh()
    }
  } catch (failure) {
    if (!disposed && id === campaignId.value && initData === rawInitData.value) {
      if (failure instanceof HttpError && failure.unauthorized) await refresh()
      else retryError.value = true
    }
  } finally {
    retrying.value = false
  }
}
const refreshAction = computed<BottomAction>(() => ({
  text: copy.value.admin.refresh, run: refresh, disabled: retrying.value || status.value === 'loading',
  loading: status.value === 'loading' && !retrying.value,
}))
const primary = computed<BottomAction | null>(() => {
  if (status.value === 'error') return { ...refreshAction.value, text: copy.value.preferences.retry }
  if (status.value !== 'ready' && !campaign.value) return null
  if (status.value === 'denied' || status.value === 'session_expired' || status.value === 'open_telegram') return null
  return canRetry.value ? {
    text: copy.value.admin.retry_deliveries, run: retry, disabled: retrying.value || status.value !== 'ready',
    loading: retrying.value,
  } : refreshAction.value
})
const secondary = computed(() => primary.value && canRetry.value && status.value !== 'error' ? refreshAction.value : null)
</script>

<template>
  <AdminShell :title="copy.admin.broadcast" section="broadcasts">
    <p v-if="status === 'open_telegram' || status === 'session_expired'" class="admin-hint" role="status">
      {{ copy.preferences[status] }}
    </p>
    <p v-else-if="status === 'denied'" role="alert">{{ copy.admin.denied }}</p>
    <template v-else>
      <p v-if="status === 'error'" role="alert">{{ copy.preferences.error }}</p>
      <p v-if="status === 'loading' && !campaign" class="admin-hint" role="status">{{ copy.preferences.loading }}</p>
      <template v-if="campaign">
        <div class="admin-card">
          <div class="campaign-meta">
            <strong>{{ copy.admin[campaign.audience] }}</strong>
            <time :datetime="campaign.created_at">{{ dateFormat.format(new Date(campaign.created_at)) }}</time>
          </div>
          <p v-if="campaign.audience !== 'all'" class="admin-hint">
            {{ copy.admin.selected_count.replace('{count}', String(campaign.user_ids.length)) }}
          </p>
          <CampaignCounts :counts="campaign.counts" />
        </div>

        <details class="admin-card variants">
          <summary>{{ copy.admin.variants }} · {{ campaign.variants.length }}</summary>
          <article v-for="(variant, index) in campaign.variants" :key="index">
            <h3>{{ variant.locale ? languageNames.of(variant.locale) : copy.admin.any_language }} ·
              {{ variant.theme ? themeNames[variant.theme] : copy.admin.any_theme }}</h3>
            <p>{{ variant.text }}</p>
          </article>
        </details>

        <h2 id="delivery-title">{{ copy.admin.deliveries }}</h2>
        <p v-if="retryError" role="alert">{{ copy.preferences.error }}</p>
        <p v-if="retried !== null" role="status" class="admin-hint">
          {{ retried ? copy.admin.retried_count.replace('{count}', String(retried)) : copy.admin.none_retried }}
        </p>
        <table v-if="items.length" class="deliveries" aria-labelledby="delivery-title">
          <thead><tr><th scope="col">Telegram ID</th><th scope="col">{{ copy.admin.status }}</th>
            <th scope="col">{{ copy.admin.attempts }}</th></tr></thead>
          <tbody>
            <tr v-for="delivery in items" :key="delivery.user_id">
              <td>{{ delivery.user_id }}</td>
              <td>{{ copy.admin[statusText(delivery.status) ?? 'pending'] }}
                <small v-if="delivery.last_error">{{ delivery.last_error }}</small></td>
              <td>{{ delivery.attempts }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="admin-hint">{{ copy.admin.no_recipients }}</p>
        <button v-if="nextCursor !== null && status !== 'error'" class="admin-button" type="button"
          :disabled="retrying || status === 'loading'" @click="loadMore">{{ copy.admin.load_more }}</button>
      </template>
    </template>
    <AdminActions :primary="primary" :secondary="secondary" :loading-text="copy.preferences.loading" />
  </AdminShell>
</template>

<style scoped>
.campaign-meta { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 12px; margin-bottom: 12px; }
.campaign-meta time { color: var(--admin-hint); font-size: 14px; }
.variants summary { cursor: pointer; font-weight: 600; }
article { margin: 12px 0 0; padding-top: 12px; border-top: 1px solid var(--admin-divider); }
article h3 { margin: 0; color: var(--admin-hint); font-size: 13px; }
article p { white-space: pre-wrap; overflow-wrap: anywhere; }
.deliveries { width: 100%; border-spacing: 0; border-radius: 16px; background: var(--admin-section); font-size: 13px; }
th, td { padding: 10px 8px; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
th { font-weight: 600; color: var(--admin-hint); }
tr:not(:last-child) td, th { box-shadow: inset 0 -1px var(--admin-divider); }
td:first-child, td:last-child { font-variant-numeric: tabular-nums; }
td:last-child, th:last-child { text-align: right; }
td small { display: block; color: var(--admin-hint); }
.deliveries + button { margin-top: 12px; }
</style>
