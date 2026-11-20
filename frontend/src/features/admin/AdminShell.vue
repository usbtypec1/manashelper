<script setup lang="ts">
import { watchEffect } from 'vue'
import { RouterLink } from 'vue-router'
import { useAdminCopy } from './useAdminCopy'
import './admin.css'

const props = defineProps<{ title: string; section: 'users' | 'broadcasts' }>()
const { copy, locale } = useAdminCopy()
watchEffect(() => {
  document.documentElement.lang = locale.value
  document.title = props.title
})
</script>

<template>
  <div class="telegram-admin">
    <main class="app-shell admin-shell">
      <header class="admin-header">
        <nav class="admin-tabs" :aria-label="copy.admin.title">
          <RouterLink :to="{ name: 'admin' }" :aria-current="section === 'users' ? 'page' : undefined">
            {{ copy.admin.users }}
          </RouterLink>
          <RouterLink :to="{ name: 'admin-broadcasts' }" :aria-current="section === 'broadcasts' ? 'page' : undefined">
            {{ copy.admin.broadcasts }}
          </RouterLink>
        </nav>
        <h1 id="admin-page-title">{{ title }}</h1>
      </header>
      <slot />
    </main>
  </div>
</template>
