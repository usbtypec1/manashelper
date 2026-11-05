<script setup lang="ts">
import { computed } from 'vue'
import atlas from './assets/achievement-medals.png'
import { achievementArt } from './achievementArt'

const props = defineProps<{ achievementKey: string; earned: boolean; reveal?: boolean }>()
const cell = computed(() => props.earned || props.reveal ? achievementArt[props.achievementKey]?.cell ?? 11 : 11)
const position = computed(() => `${(cell.value % 4) * 100 / 3}% ${Math.floor(cell.value / 4) * 50}%`)
</script>

<template>
  <span
    class="achievement-badge"
    :class="{ 'is-locked': !earned && !reveal }"
    :style="{ backgroundImage: `url(${atlas})`, backgroundPosition: position }"
    :data-medal="achievementKey"
    :data-locked="!earned && !reveal"
    aria-hidden="true"
  />
</template>
