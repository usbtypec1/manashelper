<script setup lang="ts">
import { RouterLink } from 'vue-router'
import type { Locale } from '../../shared/i18n/locale'
import messages from '../../shared/i18n/messages.json'
import './terms.css'
defineProps<{ locale: Locale; from: 'settings' | 'courses' | 'achievements' | 'leaderboard' | 'free-time' }>()
</script>

<template>
  <footer class="terms-link">
    <RouterLink :to="{ name: 'terms', query: { lang: locale, from } }">{{ messages[locale].terms.title }}</RouterLink>
  </footer>
</template>
