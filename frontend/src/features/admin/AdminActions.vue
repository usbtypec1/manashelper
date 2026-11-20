<script setup lang="ts">
import { toRef } from 'vue'
import { useTelegramBottomButtons, type BottomAction } from '../../shared/telegram/bottomButtons'

const props = defineProps<{
  primary: BottomAction | null
  secondary: BottomAction | null
  loadingText: string
}>()
const { nativeMain, nativeSecondary } = useTelegramBottomButtons(toRef(props, 'primary'), toRef(props, 'secondary'))
</script>

<template>
  <div v-if="(primary && !nativeMain) || (secondary && !nativeSecondary)" class="admin-actions">
    <button v-if="primary && !nativeMain" type="button" class="admin-button primary" :disabled="primary.disabled" @click="primary.run">
      {{ primary.loading ? loadingText : primary.text }}
    </button>
    <button v-if="secondary && !nativeSecondary" type="button" class="admin-button" :disabled="secondary.disabled" @click="secondary.run">
      {{ secondary.loading ? loadingText : secondary.text }}
    </button>
  </div>
</template>
