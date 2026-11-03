<script setup lang="ts">
import { Handle, Position, useVueFlow } from '@vue-flow/core'
import { nextTick, watch } from 'vue'
import type { FlowNode, Port } from '../types'
import { t } from '../i18n'
const props = defineProps<{
  id: string
  data: {
    kind: FlowNode['kind']
    title: string
    ports: Port[]
    entry: boolean
    invalid: boolean
    current?: boolean
  }
  selected?: boolean
}>()
const { updateNodeInternals } = useVueFlow()
watch(
  () => props.data.ports.map((port) => port.id).join('|'),
  async () => {
    await nextTick()
    updateNodeInternals([props.id])
  },
)
const symbols = {
  menu: '▤',
  input: '⌨',
  condition: '◇',
  action: '⚙',
  end: '◉',
  call: '↗',
  return: '↙',
  replace: '⇥',
}
</script>
<template>
  <div class="flow-card" :class="[data.kind, { selected, invalid: data.invalid, current: data.current }]">
    <Handle type="target" :position="Position.Left" />
    <div class="flow-card-head">
      <span class="node-symbol">{{ symbols[data.kind] }}</span
      ><span>{{ t(data.kind) }}</span
      ><span v-if="data.entry" class="entry-dot" :title="t('entry')">◎</span>
    </div>
    <div class="flow-card-body">
      <strong>{{ id }}</strong
      ><span class="node-excerpt">{{ data.title }}</span>
    </div>
    <div v-for="port in data.ports" :key="port.id" class="port-row">
      <span>{{ port.label }}</span
      ><Handle :id="port.id" type="source" :position="Position.Right" />
    </div>
  </div>
</template>
