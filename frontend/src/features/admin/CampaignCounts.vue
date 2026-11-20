<script setup lang="ts">
import { computed } from 'vue'
import { deliveryStatuses } from './campaignApi'
import { useAdminCopy } from './useAdminCopy'

const props = defineProps<{ counts: Record<string, number> }>()
const { copy } = useAdminCopy()
const total = computed(() => Object.values(props.counts).reduce((sum, count) => sum + count, 0))
</script>

<template>
  <p v-if="total === 0" class="admin-hint">{{ copy.admin.no_recipients }}</p>
  <ul v-else class="counts">
    <template v-for="state in deliveryStatuses" :key="state">
      <li v-if="counts[state]" :class="state"><strong>{{ counts[state] }}</strong> {{ copy.admin[state] }}</li>
    </template>
  </ul>
</template>

<style scoped>
.counts { display: flex; flex-wrap: wrap; gap: 6px; list-style: none; margin: 0; padding: 0; }
.counts li { font-size: 12px; line-height: 1.4; padding: 4px 9px; border-radius: 8px; background: var(--admin-control); }
.counts strong { font-variant-numeric: tabular-nums; }
.sent strong { color: var(--admin-accent); }
.failed strong, .expired strong, .cancelled strong { color: var(--tg-theme-destructive-text-color, var(--admin-default-hint)); }
</style>
