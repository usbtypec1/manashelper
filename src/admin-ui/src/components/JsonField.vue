<script setup lang="ts">
import { ref, watch } from 'vue'
import { t } from '../i18n'
const props = defineProps<{ modelValue: unknown; label: string }>()
const emit = defineEmits<{ 'update:modelValue': [unknown] }>()
const text = ref('')
watch(
  () => props.modelValue,
  (value) => {
    text.value = JSON.stringify(value, null, 2)
  },
  { immediate: true, deep: true },
)
function input(event: Event) {
  const element = event.target as HTMLTextAreaElement
  text.value = element.value
  try {
    const value = JSON.parse(text.value)
    element.setCustomValidity('')
    emit('update:modelValue', value)
  } catch {
    element.setCustomValidity(t('jsonError'))
  }
}
</script>
<template>
  <label
    >{{ label }}<textarea class="code" :aria-label="label" :value="text" rows="3" @input="input" />
  </label>
</template>
