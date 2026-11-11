<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useTelegramProvider } from './shared/telegram/telegram'

useTelegramProvider()
</script>

<template>
  <RouterView />
</template>
