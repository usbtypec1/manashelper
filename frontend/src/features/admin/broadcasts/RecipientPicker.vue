<script setup lang="ts">
import { computed, ref } from 'vue'
import type { UserProfile } from '../users/api'
import { useAdminCopy } from '../useAdminCopy'
import { useAdminUsers } from '../users/useAdminUsers'
import { useTelegram } from '../../../shared/telegram/telegram'

const props = defineProps<{ selected: UserProfile[] }>()
const emit = defineEmits<{ toggle: [user: UserProfile] }>()
const { rawInitData } = useTelegram()
const { copy } = useAdminCopy()
const search = ref('')
const filters = computed(() => ({ q: search.value.trim() }))
const { users, status, nextCursor, loadMore, retry } = useAdminUsers(rawInitData, filters)
const selectedIds = computed(() => new Set(props.selected.map(user => user.id)))
</script>

<template>
  <div class="picker">
    <label class="admin-field">
      <span>{{ copy.admin.pick_users }}</span>
      <input v-model="search" type="search" maxlength="128" autocomplete="off" :placeholder="copy.admin.search_hint" />
    </label>
    <p v-if="selected.length" class="admin-hint" role="status">{{ copy.admin.selected_count.replace('{count}', String(selected.length)) }}</p>
    <ul v-if="selected.length" class="selected">
      <li v-for="user in selected" :key="user.id">
        <button type="button" :aria-label="copy.admin.remove_user.replace('{name}', user.full_name)"
          @click="emit('toggle', user)">{{ user.full_name }} <span aria-hidden="true">×</span></button>
      </li>
    </ul>
    <div v-if="users.length" class="results" :aria-label="copy.admin.search_results" role="group" :aria-busy="status === 'loading'">
      <label v-for="user in users" :key="user.id">
        <span>{{ user.full_name }} <small v-if="user.username">@{{ user.username }}</small></span>
        <input type="checkbox" :checked="selectedIds.has(user.id)" @change="emit('toggle', user)" />
      </label>
    </div>
    <p v-if="status === 'loading' && !users.length" class="admin-hint" role="status">{{ copy.preferences.loading }}</p>
    <p v-else-if="status === 'ready' && !users.length" class="admin-hint" role="status">{{ copy.admin.no_matches }}</p>
    <p v-else-if="status === 'session_expired'" role="alert">{{ copy.preferences.session_expired }}</p>
    <p v-else-if="status === 'denied'" role="alert">{{ copy.admin.denied }}</p>
    <button v-if="status === 'error'" type="button" class="admin-button" @click="retry">{{ copy.preferences.retry }}</button>
    <button v-else-if="nextCursor !== null" type="button" class="admin-button" :disabled="status === 'loading'"
      @click="loadMore">{{ copy.admin.load_more }}</button>
  </div>
</template>

<style scoped>
.picker { display: grid; gap: 8px; }
.results { max-height: clamp(144px, 38dvh, 288px); overflow-y: auto; border: 1px solid var(--admin-divider); border-radius: 12px; }
.results label { display: flex; justify-content: space-between; align-items: center; gap: 12px; min-height: 44px; padding: 8px 12px; cursor: pointer; }
.results label:not(:last-child) { border-bottom: 1px solid var(--admin-divider); }
.results label span { min-width: 0; overflow-wrap: anywhere; }
.results small { display: block; color: var(--admin-hint); }
.results input { flex: none; width: 18px; height: 18px; accent-color: var(--admin-accent); }
.results label:focus-within { outline: 2px solid var(--admin-accent); outline-offset: -2px; }
.selected { display: flex; flex-wrap: wrap; gap: 6px; padding: 0; margin: 0; list-style: none; }
.selected li { min-width: 0; max-width: 100%; }
.selected button { min-height: 44px; border-radius: 10px; padding: 4px 10px; background: var(--admin-control); overflow-wrap: anywhere; }
.selected span { color: var(--admin-accent); }
</style>
