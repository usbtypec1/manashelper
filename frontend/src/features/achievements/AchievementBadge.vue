<script setup lang="ts">
import { computed } from 'vue'
import atlas from '../../assets/achievements/achievement-medals.png'
import { achievementArt } from './achievementArt'

const props = defineProps<{ achievementKey: string; earned: boolean; reveal?: boolean }>()
const art = computed(() => props.earned || props.reveal ? achievementArt[props.achievementKey] : undefined)
const image = computed(() => art.value?.image)
const cell = computed(() => art.value?.cell ?? 11)
const position = computed(() => `${(cell.value % 4) * 100 / 3}% ${Math.floor(cell.value / 4) * 50}%`)
</script>

<template>
  <span
    class="achievement-badge"
    :class="{ 'is-locked': !earned && !reveal }"
    :style="{
      backgroundImage: `url(${image ?? atlas})`,
      backgroundPosition: image ? 'center' : position,
      backgroundSize: image ? 'contain' : '400% 300%',
    }"
    :data-medal="achievementKey"
    :data-locked="!earned && !reveal"
    aria-hidden="true"
  />
</template>
