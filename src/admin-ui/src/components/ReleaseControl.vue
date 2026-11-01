<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { AdminApi } from '../api'
import type { Schemas } from '../types'
import { t } from '../i18n'
import ConfirmDialog from './ConfirmDialog.vue'

const props = defineProps<{ api: AdminApi }>()
const emit = defineEmits<{ failure: [unknown] }>()
const status = ref<Schemas['RolloutStatus'] | null>(null)
const modes = ['admin', 'all', 'off'] as const
type Mode = (typeof modes)[number]
const labels = { admin: 'adminOnly', all: 'allUsers', off: 'off' } as const
const selected = ref<Mode>('admin'),
  busy = ref(false),
  confirm = ref(false)

async function refresh() {
  if (busy.value) return
  busy.value = true
  try {
    status.value = await props.api.request<Schemas['RolloutStatus']>('/rollout')
    selected.value = status.value.mode
  } catch (error) {
    emit('failure', error)
  } finally {
    busy.value = false
  }
}
async function apply(yes: boolean) {
  confirm.value = false
  if (!yes || !status.value) return
  busy.value = true
  try {
    status.value = await props.api.request<Schemas['RolloutStatus']>('/rollout', 'PUT', {
      mode: selected.value,
      expected_revision: status.value.revision,
    })
  } catch (error) {
    emit('failure', error)
  } finally {
    busy.value = false
  }
}
onMounted(refresh)
</script>
<template>
  <details class="release-control" @toggle="($event.target as HTMLDetailsElement).open && refresh()">
    <summary>{{ t('release') }} · {{ status ? t(labels[status.mode]) : t('loading') }}</summary>
    <div class="release-panel stack">
      <strong>{{ t('release') }}</strong>
      <p class="hint">{{ t('releaseHint') }}</p>
      <div class="row">
        <button
          v-for="mode in modes"
          :key="mode"
          type="button"
          :aria-pressed="selected === mode"
          :disabled="busy"
          :class="{ primary: selected === mode }"
          @click="selected = mode"
        >
          {{ t(labels[mode]) }}
        </button>
      </div>
      <span v-if="status" class="hint">{{ t('activeDialogs') }}: {{ status.active_dialogs }}</span>
      <div class="row end">
        <button type="button" :disabled="busy" @click="refresh">{{ t('refresh') }}</button>
        <button type="button" :disabled="busy || !status || selected === status.mode" @click="confirm = true">
          {{ t('apply') }}
        </button>
      </div>
    </div>
  </details>
  <ConfirmDialog
    v-if="confirm"
    :message="t('releaseConfirm')"
    :detail="t(labels[selected])"
    @answer="apply"
  />
</template>
<style scoped>
.release-control {
  position: relative;
  font-size: 12px;
}
summary {
  cursor: pointer;
  padding: 9px;
  border: 1px solid var(--line, #e3e7f0);
  border-radius: 7px;
}
.release-panel {
  position: absolute;
  z-index: 30;
  right: 0;
  top: 42px;
  width: 340px;
  padding: 16px;
  background: white;
  border: 1px solid #e3e7f0;
  border-radius: 10px;
  box-shadow: 0 12px 35px #17233b20;
}
</style>
