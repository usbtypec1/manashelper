<script setup lang="ts">
import { computed, onScopeDispose, ref } from 'vue'
import { useRouter } from 'vue-router'
import AdminActions from '../features/admin/AdminActions.vue'
import AdminShell from '../features/admin/AdminShell.vue'
import RecipientPicker from '../features/admin/RecipientPicker.vue'
import type { UserProfile } from '../features/admin/api'
import { audiences, createCampaign, getCampaigns, type Audience, type Variant } from '../features/admin/campaignApi'
import { locales, useAdminCopy } from '../features/admin/useAdminCopy'
import { useAdminPages } from '../features/admin/useAdminPages'
import { HttpError } from '../shared/api/http'
import type { BottomAction } from '../shared/telegram/bottomButtons'
import { confirmTelegramAction } from '../shared/telegram/confirmation'
import { useTelegram } from '../shared/telegram/telegram'

const { rawInitData } = useTelegram()
const { copy, languageNames, themeNames } = useAdminCopy()
const { status, refresh } = useAdminPages(rawInitData, getCampaigns)
const router = useRouter()
const audience = ref<Audience>('all')
const selected = ref<UserProfile[]>([])
const variants = ref<(Variant & { key: number })[]>([{ key: 0, locale: null, theme: null, text: '' }])
const campaignId = crypto.randomUUID()
let nextKey = 1
let disposed = false
onScopeDispose(() => { disposed = true })

const sending = ref(false)
const confirming = ref(false)
const busy = computed(() => sending.value || confirming.value)
const error = ref('')
const duplicate = computed(() => {
  const keys = variants.value.map(variant => `${variant.locale ?? ''}:${variant.theme ?? ''}`)
  return new Set(keys).size !== keys.length
})
const canSend = computed(() => status.value === 'ready' && !duplicate.value
  && variants.value.every(variant => variant.text.trim().length > 0)
  && (audience.value === 'all' || selected.value.length > 0))

function toggleRecipient(user: UserProfile) {
  const index = selected.value.findIndex(entry => entry.id === user.id)
  if (index === -1) selected.value.push(user)
  else selected.value.splice(index, 1)
}

async function send() {
  const initData = rawInitData.value
  if (!initData || !canSend.value || busy.value) return
  const draft = {
    id: campaignId,
    audience: audience.value,
    user_ids: audience.value === 'all' ? [] : selected.value.map(user => user.id),
    variants: variants.value.map(({ locale, theme, text }) => ({ locale, theme, text })),
  }
  const confirmation = audience.value === 'all' ? copy.value.admin.confirm_all
    : copy.value.admin[audience.value === 'allowlist' ? 'confirm_allowlist' : 'confirm_blocklist']
      .replace('{count}', String(selected.value.length))
  confirming.value = true
  error.value = ''
  try {
    if (!await confirmTelegramAction(confirmation, copy.value.admin.queue) || disposed || rawInitData.value !== initData) return
    confirming.value = false
    sending.value = true
    const id = await createCampaign(initData, draft)
    if (!disposed) await router.replace({ name: 'admin-broadcast', params: { id } })
  } catch (failure) {
    if (disposed) return
    if (failure instanceof HttpError && failure.unauthorized) {
      await refresh()
    } else {
      error.value = failure instanceof HttpError && failure.status === 400
        ? copy.value.admin.invalid_broadcast
        : copy.value.preferences.error
    }
  } finally {
    confirming.value = false
    sending.value = false
  }
}

const primary = computed<BottomAction | null>(() => status.value === 'ready' ? {
  text: copy.value.admin.queue, run: send, disabled: !canSend.value || busy.value, loading: sending.value,
} : null)
</script>

<template>
  <AdminShell :title="copy.admin.new_broadcast" section="broadcasts">
    <template v-if="status === 'ready'">
      <fieldset class="admin-card editor" :disabled="busy">
        <legend>{{ copy.admin.audience }}</legend>
        <label class="admin-field">
          <span>{{ copy.admin.audience }}</span>
          <select v-model="audience">
            <option v-for="mode in audiences" :key="mode" :value="mode">{{ copy.admin[mode] }}</option>
          </select>
        </label>
        <RecipientPicker v-if="audience !== 'all'" :selected="selected" @toggle="toggleRecipient" />
        <p class="admin-hint">{{ copy.admin.eligibility }}</p>
      </fieldset>

      <section aria-labelledby="broadcast-variants">
        <h2 id="broadcast-variants">{{ copy.admin.variants }}</h2>
        <p class="admin-hint">{{ copy.admin.fallback }}</p>
        <fieldset v-for="(variant, index) in variants" :key="variant.key" class="admin-card editor" :disabled="busy">
          <div class="variant-options">
            <label class="admin-field">
              <span>{{ copy.admin.language }}</span>
              <select v-model="variant.locale">
                <option :value="null">{{ copy.admin.any_language }}</option>
                <option v-for="code in locales" :key="code" :value="code">{{ languageNames.of(code) }}</option>
              </select>
            </label>
            <label class="admin-field">
              <span>{{ copy.admin.theme }}</span>
              <select v-model="variant.theme">
                <option :value="null">{{ copy.admin.any_theme }}</option>
                <option v-for="(name, code) in themeNames" :key="code" :value="code">{{ name }}</option>
              </select>
            </label>
          </div>
          <label class="admin-field">
            <span>{{ copy.admin.message }}</span>
            <textarea v-model="variant.text" maxlength="4096" required />
          </label>
          <button v-if="variants.length > 1" type="button" class="admin-button" @click="variants.splice(index, 1)">
            {{ copy.admin.remove_variant }}
          </button>
        </fieldset>
        <p v-if="duplicate" role="alert">{{ copy.admin.duplicate_variant }}</p>
        <button class="admin-button" type="button"
          :disabled="busy || variants.length >= (locales.length + 1) * (Object.keys(themeNames).length + 1)"
          @click="variants.push({ key: nextKey++, locale: null, theme: null, text: '' })">{{ copy.admin.add_variant }}</button>
      </section>
      <p v-if="error" role="alert">{{ error }}</p>
    </template>
    <p v-else-if="status === 'loading'" class="admin-hint" role="status">{{ copy.preferences.loading }}</p>
    <p v-else-if="status === 'open_telegram' || status === 'session_expired'" class="admin-hint" role="status">
      {{ copy.preferences[status] }}
    </p>
    <p v-else-if="status === 'denied'" role="alert">{{ copy.admin.denied }}</p>
    <div v-else role="alert">
      <p>{{ copy.preferences.error }}</p>
      <button class="admin-button" type="button" @click="refresh">{{ copy.preferences.retry }}</button>
    </div>
    <AdminActions :primary="primary" :secondary="null" :loading-text="copy.preferences.loading" />
  </AdminShell>
</template>

<style scoped>
.editor { display: grid; gap: 12px; border: 0; }
.editor legend { position: absolute; width: 1px; height: 1px; clip-path: inset(50%); overflow: hidden; }
.editor p { margin: 0; }
.variant-options { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
h2 { margin: 24px 0 8px; font-size: 21px; }
</style>
