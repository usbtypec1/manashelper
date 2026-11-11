<script setup lang="ts">
import messages from './messages.json'
defineProps<{ locale: string; from: 'settings' | 'courses' | 'achievements' }>()
</script>

<template>
  <footer class="terms-link">
    <a :href="`/app/?view=terms&lang=${locale}&from=${from}`">{{ messages[locale as keyof typeof messages]?.terms.title ?? messages.en.terms.title }}</a>
  </footer>
</template>
