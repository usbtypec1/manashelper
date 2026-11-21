<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import AdminShell from '../../features/admin/AdminShell.vue'
import { useAdminAchievements } from '../../features/admin/achievements/useAdminAchievements'
import { useAdminCopy } from '../../features/admin/useAdminCopy'
import { confirmTelegramAction } from '../../shared/telegram/confirmation'
import { useTelegram } from '../../shared/telegram/telegram'

const { rawInitData } = useTelegram()
const { copy } = useAdminCopy()
const { achievements, status, notice, pending, load, save, grant } = useAdminAchievements(rawInitData)
const selectedKey = ref('')
const customName = ref('')
const hidden = ref(false)
const recipientId = ref('')
const confirming = ref(false)
let disposed = false
onScopeDispose(() => { disposed = true })

const selected = computed(() => achievements.value.find(item => item.key === selectedKey.value))
const busy = computed(() => confirming.value || pending.value !== null)
const normalizedName = computed(() => customName.value.trim() || null)
const dirty = computed(() => selected.value !== undefined
  && (normalizedName.value !== selected.value.custom_name || hidden.value !== selected.value.hidden))
const validRecipient = computed(() => /^[1-9][0-9]{0,18}$/.test(recipientId.value)
  && (recipientId.value.length < 19 || recipientId.value <= '9223372036854775807'))
const failure = computed(() => notice.value === 'error' || notice.value === 'missing' || notice.value === 'unavailable')

watch(achievements, items => {
  if (!items.some(item => item.key === selectedKey.value)) selectedKey.value = items[0]?.key ?? ''
})
watch(() => [selected.value?.key, selected.value?.custom_name, selected.value?.hidden] as const, () => {
  customName.value = selected.value?.custom_name ?? ''
  hidden.value = selected.value?.hidden ?? false
})
watch(selectedKey, () => { notice.value = null })
watch(rawInitData, () => { recipientId.value = '' })

function saveDisplay() {
  if (!selected.value || busy.value || !dirty.value) return
  void save(selected.value.key, { custom_name: normalizedName.value, hidden: hidden.value })
}

async function confirmGrant() {
  const item = selected.value
  const initData = rawInitData.value
  if (!item || !initData || busy.value || !validRecipient.value) return
  const id = recipientId.value
  const name = Array.from(item.custom_name ?? item.default_name).slice(0, 60).join('')
  const { achievement_grant_confirm, achievement_grant } = copy.value.admin
  const message = achievement_grant_confirm.replace(/\{(name|id)\}/g, (_, key) => key === 'name' ? name : id)
  confirming.value = true
  try {
    const accepted = await confirmTelegramAction(message, achievement_grant)
    if (accepted && !disposed && rawInitData.value === initData) await grant(item.key, id)
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
      <div class="admin-card achievement-picker">
        <label class="admin-field">
          <span>{{ copy.admin.achievement }}</span>
          <select v-model="selectedKey" :disabled="busy">
            <option v-for="item in achievements" :key="item.key" :value="item.key">
              {{ item.emoji }} {{ item.custom_name ?? item.default_name }}{{ item.hidden ? ` · ${copy.admin.achievement_hidden}` : '' }}
            </option>
          </select>
        </label>
      </div>
      <div v-if="selected" class="admin-split">
        <form class="admin-card" @submit.prevent="saveDisplay">
          <h2>{{ copy.admin.achievement_display }}</h2>
          <div class="achievement-fields">
            <label class="admin-field">
              <span>{{ copy.admin.achievement_custom_name }}</span>
              <input v-model="customName" type="text" maxlength="80" :placeholder="selected.default_name"
                :disabled="busy" aria-describedby="achievement-name-hint" />
            </label>
            <p id="achievement-name-hint" class="admin-hint field-hint">{{ copy.admin.achievement_name_hint }}</p>
            <label class="visibility">
              <input v-model="hidden" type="checkbox" :disabled="busy" />
              <span>{{ copy.admin.achievement_hide }}</span>
            </label>
          </div>
          <div class="admin-actions">
            <button type="submit" class="admin-button primary" :disabled="busy || !dirty">
              {{ copy.admin.achievement_save }}
            </button>
          </div>
        </form>
        <form class="admin-card" @submit.prevent="confirmGrant">
          <h2>{{ copy.admin.achievement_grant_title }}</h2>
          <label class="admin-field">
            <span>Telegram ID</span>
            <input v-model.trim="recipientId" inputmode="numeric" maxlength="19" type="text" autocomplete="off"
              :disabled="busy" aria-describedby="achievement-recipient-hint" required />
          </label>
          <p id="achievement-recipient-hint" class="admin-hint">{{ copy.admin.achievement_recipient_hint }}</p>
          <div class="admin-actions">
            <button type="submit" class="admin-button primary" :disabled="busy || !validRecipient">
              {{ copy.admin.achievement_grant }}
            </button>
          </div>
        </form>
      </div>
      <p v-if="pending" class="admin-hint" role="status">{{ copy.preferences.loading }}</p>
      <p v-else-if="notice" :role="failure ? 'alert' : 'status'">
        {{ notice === 'error' ? copy.preferences.error : copy.admin[`achievement_${notice}`] }}
      </p>
    </template>
  </AdminShell>
</template>

<style scoped>
.achievement-picker { max-width: 32rem; }
.achievement-fields { display: grid; gap: 8px; }
.field-hint { margin: 0; }
.visibility { display: flex; align-items: center; gap: 10px; min-height: 44px; font-size: 14px; }
.visibility input { flex: 0 0 auto; width: 20px; height: 20px; accent-color: var(--admin-accent); }
</style>
