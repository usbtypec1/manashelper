<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import AdminShell from '../../features/admin/AdminShell.vue'
import AchievementDisplayForm from '../../features/admin/achievements/AchievementDisplayForm.vue'
import type { AchievementDisplay } from '../../features/admin/achievements/api'
import { useAdminAchievements } from '../../features/admin/achievements/useAdminAchievements'
import { useAdminCopy } from '../../features/admin/useAdminCopy'
import { confirmTelegramAction } from '../../shared/telegram/confirmation'
import { useTelegram } from '../../shared/telegram/telegram'

const { rawInitData } = useTelegram()
const { copy } = useAdminCopy()
const { achievements, status, notice, pending, load, save, changeAward } = useAdminAchievements(rawInitData)
const selectedKey = ref('')
const displayKey = ref('')
const recipientId = ref('')
const confirming = ref(false)
let disposed = false
onScopeDispose(() => { disposed = true })

const selected = computed(() => achievements.value.find(item => item.key === selectedKey.value))
const busy = computed(() => confirming.value || pending.value !== null)
const validRecipient = computed(() => /^[1-9][0-9]{0,18}$/.test(recipientId.value)
  && (recipientId.value.length < 19 || recipientId.value <= '9223372036854775807'))
const failure = computed(() => notice.value === 'error' || notice.value === 'missing' || notice.value === 'unavailable')

watch(achievements, items => {
  if (!items.some(item => item.key === selectedKey.value)) selectedKey.value = items[0]?.key ?? ''
})
watch(selectedKey, () => { if (!displayKey.value) notice.value = null })
watch(rawInitData, () => { recipientId.value = '' })

function saveDisplay(key: string, display: AchievementDisplay) {
  if (busy.value) return
  displayKey.value = key
  void save(key, display)
}

async function confirmAwardAction(action: 'grant' | 'revoke') {
  const item = selected.value
  const initData = rawInitData.value
  if (!item || !initData || busy.value || !validRecipient.value) return
  const id = recipientId.value
  const name = Array.from(item.custom_name ?? item.default_name).slice(0, 60).join('')
  const message = copy.value.admin[`achievement_${action}_confirm`]
    .replace(/\{(name|id)\}/g, (_, key) => key === 'name' ? name : id)
  const label = copy.value.admin[`achievement_${action}`]
  displayKey.value = ''
  confirming.value = true
  try {
    const accepted = await confirmTelegramAction(message, label)
    if (accepted && !disposed && rawInitData.value === initData) await changeAward(action, item.key, id)
  } catch {
    if (!disposed && rawInitData.value === initData) notice.value = 'error'
  } finally {
    confirming.value = false
  }
}
</script>

<template>
  <AdminShell :title="copy.admin.achievements" section="achievements">
    <p v-if="status === 'open_telegram' || status === 'session_expired'" class="admin-hint" role="status">
      {{ copy.preferences[status] }}
    </p>
    <p v-else-if="status === 'denied'" role="alert">{{ copy.admin.denied }}</p>
    <div v-else-if="status === 'error'" class="admin-card">
      <p role="alert">{{ copy.preferences.error }}</p>
      <button type="button" class="admin-button" @click="load">{{ copy.preferences.retry }}</button>
    </div>
    <p v-else-if="status === 'loading'" class="admin-hint" role="status">{{ copy.preferences.loading }}</p>
    <template v-else>
        <form v-if="selected" class="admin-card" @submit.prevent="confirmAwardAction('grant')">
          <h2>{{ copy.admin.achievement_award_title }}</h2>
          <div class="achievement-fields">
            <label class="admin-field">
              <span>{{ copy.admin.achievement }}</span>
              <select v-model="selectedKey" :disabled="busy">
                <option v-for="item in achievements" :key="item.key" :value="item.key">
                  {{ item.emoji }} {{ item.custom_name ?? item.default_name }}{{ item.hidden ? ` · ${copy.admin.achievement_hidden}` : '' }}
                </option>
              </select>
            </label>
            <label class="admin-field">
              <span>Telegram ID</span>
              <input v-model.trim="recipientId" inputmode="numeric" maxlength="19" type="text" autocomplete="off"
                :disabled="busy" aria-describedby="achievement-recipient-hint" required />
            </label>
          </div>
          <p id="achievement-recipient-hint" class="admin-hint">{{ copy.admin.achievement_recipient_hint }}</p>
          <div class="admin-actions">
            <button type="submit" class="admin-button primary" :disabled="busy || !validRecipient">
              {{ copy.admin.achievement_grant }}
            </button>
            <button type="button" class="admin-button revoke" :disabled="busy || !validRecipient"
              @click="confirmAwardAction('revoke')">
              {{ copy.admin.achievement_revoke }}
            </button>
          </div>
          <p v-if="!displayKey && notice" :role="failure ? 'alert' : 'status'">
            {{ notice === 'error' ? copy.preferences.error : copy.admin[`achievement_${notice}`] }}
          </p>
        </form>
      <h2>{{ copy.admin.achievement_display }}</h2>
      <p id="achievement-name-hint" class="admin-hint">{{ copy.admin.achievement_name_hint }}</p>
      <div class="achievement-fields">
        <AchievementDisplayForm v-for="item in achievements" :key="item.key"
          :achievement="item" :copy="copy.admin" :disabled="busy"
          :notice="displayKey === item.key && (notice === 'saved' || notice === 'error') ? notice : null"
          @save="saveDisplay(item.key, $event)" />
      </div>
      <p v-if="pending" class="admin-hint" role="status">{{ copy.preferences.loading }}</p>
    </template>
  </AdminShell>
</template>

<style scoped>
.achievement-fields { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(min(18rem, 100%), 1fr)); }
.revoke { color: var(--admin-default-danger); }
</style>
