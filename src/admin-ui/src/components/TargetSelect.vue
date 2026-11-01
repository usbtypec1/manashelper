<script setup lang="ts">
defineProps<{ modelValue: string; nodes: string[]; label: string }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
</script>
<template>
  <label
    >{{ label
    }}<select
      :aria-label="label"
      :value="modelValue"
      required
      @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option v-if="!nodes.includes(modelValue)" :value="modelValue">{{ modelValue || '—' }}</option>
      <option v-for="id in nodes" :key="id">{{ id }}</option>
    </select></label
  >
</template>
