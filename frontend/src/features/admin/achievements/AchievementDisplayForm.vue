<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AchievementDisplay, AdminAchievement } from './api'

const props = defineProps<{
  achievement: AdminAchievement
  copy: Record<string, string>
  disabled: boolean
  notice: 'saved' | 'error' | null
}>()
const emit = defineEmits<{ save: [display: AchievementDisplay] }>()
const name = ref('')
const hidden = ref(false)
const customName = computed(() => name.value.trim() || null)
const dirty = computed(() => customName.value !== props.achievement.custom_name
  || hidden.value !== props.achievement.hidden)

watch(() => [props.achievement.custom_name, props.achievement.hidden] as const, ([nameValue, hiddenValue]) => {
  name.value = nameValue ?? ''
  hidden.value = hiddenValue
}, { immediate: true })
</script>

<template>
  <form class="admin-card display-form" :data-achievement="achievement.key"
    @submit.prevent="emit('save', { custom_name: customName, hidden })">
    <label class="admin-field">
      <span><span aria-hidden="true">{{ achievement.emoji }}</span> {{ achievement.default_name }}</span>
      <input v-model="name" type="text" maxlength="80" :placeholder="achievement.default_name"
        :disabled="disabled" aria-describedby="achievement-name-hint" />
    </label>
    <label class="visibility">
      <input v-model="hidden" type="checkbox" :disabled="disabled" />
      <span>{{ copy.achievement_hide }}</span>
    </label>
    <div class="display-actions">
      <button type="submit" class="admin-button primary" :disabled="disabled || !dirty">
        {{ copy.achievement_save }}
      </button>
      <span v-if="notice === 'saved' && !dirty" role="status">{{ copy.achievement_saved }}</span>
      <span v-else-if="notice === 'error'" role="alert">{{ copy.achievement_save_error }}</span>
    </div>
  </form>
</template>

<style scoped>
.display-form { display: grid; gap: 8px; margin: 0; align-content: start; }
.visibility, .display-actions { display: flex; align-items: center; gap: 10px; min-height: 44px; }
.visibility { font-size: 14px; }
.visibility input { flex: 0 0 auto; width: 20px; height: 20px; accent-color: var(--admin-accent); }
.display-actions { flex-wrap: wrap; font-size: 14px; }
</style>
