<script setup lang="ts">
import messages from './messages.json'
import { RouterLink } from 'vue-router'
defineProps<{ locale: string; from: 'settings' | 'courses' | 'achievements' | 'leaderboard' }>()
</script>

<template>
  <footer class="terms-link">
    <RouterLink :to="{ name: 'terms', query: { lang: locale, from } }">{{ messages[locale as keyof typeof messages]?.terms.title ?? messages.en.terms.title }}</RouterLink>
  </footer>
</template>
