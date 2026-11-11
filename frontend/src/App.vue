<script setup lang="ts">
import AchievementsView from './AchievementsView.vue'
import PreferencesApp from './PreferencesApp.vue'
import TermsView from './TermsView.vue'
const view = new URLSearchParams(window.location.search).get('view')
</script>

<template>
  <TermsView v-if="view === 'terms'" />
  <PreferencesApp v-else-if="view === 'settings' || view === 'courses'" :initial-tab="view" />
  <AchievementsView v-else />
</template>
