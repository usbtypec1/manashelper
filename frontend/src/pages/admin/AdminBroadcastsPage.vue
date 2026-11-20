<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import AdminActions from '../../features/admin/AdminActions.vue'
import AdminShell from '../../features/admin/AdminShell.vue'
import CampaignCounts from '../../features/admin/broadcasts/CampaignCounts.vue'
import { getCampaigns } from '../../features/admin/broadcasts/api'
import { useAdminCopy } from '../../features/admin/useAdminCopy'
import { useAdminPages } from '../../features/admin/broadcasts/useAdminPages'
import type { BottomAction } from '../../shared/telegram/bottomButtons'
import { useTelegram } from '../../shared/telegram/telegram'

const router = useRouter()
const { rawInitData } = useTelegram()
const { copy, locale } = useAdminCopy()
const { status, items, nextCursor, refresh, loadMore } = useAdminPages(rawInitData, getCampaigns)
const dateFormat = computed(() => new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }))
const primary = computed<BottomAction | null>(() => status.value === 'ready' ? {
  text: copy.value.admin.new_broadcast, run: () => void router.push({ name: 'admin-broadcast-new' }),
  disabled: false, loading: false,
} : null)
const secondary = computed<BottomAction | null>(() => status.value === 'ready' ? {
  text: copy.value.admin.refresh, run: refresh, disabled: false, loading: false,
} : null)
</script>

<template>
  <AdminShell :title="copy.admin.broadcasts" section="broadcasts">
    <p v-if="status === 'open_telegram' || status === 'session_expired'" class="admin-hint" role="status">
      {{ copy.preferences[status] }}
    </p>
    <p v-else-if="status === 'denied'" role="alert">{{ copy.admin.denied }}</p>
    <template v-else>
      <p v-if="status === 'loading' && !items.length" class="admin-hint" role="status">{{ copy.preferences.loading }}</p>
      <p v-if="status === 'ready' && !items.length" class="admin-hint" role="status">{{ copy.admin.no_broadcasts }}</p>
      <div v-if="status === 'error'" role="alert">
        <p>{{ copy.preferences.error }}</p>
        <button class="admin-button" type="button" @click="refresh">{{ copy.preferences.retry }}</button>
      </div>
      <div v-if="items.length" class="campaigns">
        <RouterLink v-for="campaign in items" :key="campaign.id" class="admin-card campaign"
          :to="{ name: 'admin-broadcast', params: { id: campaign.id } }">
          <div class="campaign-meta">
            <span>{{ copy.admin[campaign.audience] }}</span>
            <time :datetime="campaign.created_at">{{ dateFormat.format(new Date(campaign.created_at)) }}</time>
          </div>
          <strong>{{ campaign.preview }}</strong>
          <CampaignCounts :counts="campaign.counts" />
        </RouterLink>
      </div>
      <button v-if="nextCursor !== null && status !== 'error'" class="admin-button" type="button" :disabled="status === 'loading'"
        @click="loadMore">{{ copy.admin.load_more }}</button>
    </template>
    <AdminActions :primary="primary" :secondary="secondary" :loading-text="copy.preferences.loading" />
  </AdminShell>
</template>

<style scoped>
.campaigns { display: grid; gap: 12px; margin-bottom: 16px; }
.campaign { display: grid; grid-template-rows: auto 1fr auto; gap: 12px; margin: 0; color: inherit; text-decoration: none; }
.campaign strong { font-weight: 600; }
.campaign-meta { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 12px; font-size: 13px; color: var(--admin-hint); }
@media (hover: hover) {
  .campaign:hover { border-color: var(--admin-accent); }
}
@container admin-content (min-width: 640px) {
  .campaigns { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
