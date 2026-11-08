<script setup lang="ts">
import AchievementsView from './AchievementsView.vue'
import PreferencesApp from './PreferencesApp.vue'
const view = new URLSearchParams(window.location.search).get('view')
</script>

<template>
  <PreferencesApp v-if="view === 'settings' || view === 'courses'" :initial-tab="view" />
  <AchievementsView v-else />
</template>
