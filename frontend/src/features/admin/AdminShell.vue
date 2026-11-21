<script setup lang="ts">
import { watchEffect } from 'vue'
import { RouterLink } from 'vue-router'
import { useAdminCopy } from './useAdminCopy'
import './admin.css'

const props = defineProps<{ title: string; section: 'users' | 'broadcasts' | 'achievements' }>()
const { copy, locale } = useAdminCopy()
watchEffect(() => {
  document.documentElement.lang = locale.value
  document.title = props.title
})
</script>

<template>
  <div class="telegram-admin">
    <div class="app-shell admin-shell">
      <nav class="admin-tabs" :aria-label="copy.admin.title">
        <RouterLink :to="{ name: 'admin' }" :aria-current="section === 'users' ? 'page' : undefined">
          {{ copy.admin.users }}
        </RouterLink>
        <RouterLink :to="{ name: 'admin-broadcasts' }" :aria-current="section === 'broadcasts' ? 'page' : undefined">
          {{ copy.admin.broadcasts }}
        </RouterLink>
        <RouterLink :to="{ name: 'admin-achievements' }" :aria-current="section === 'achievements' ? 'page' : undefined">
          {{ copy.admin.achievements }}
        </RouterLink>
      </nav>
      <main class="admin-main">
        <h1 id="admin-page-title">{{ title }}</h1>
        <slot />
      </main>
    </div>
  </div>
</template>
