<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import messages from './messages.json'

type Card = {
  key: string; name: string; description: string; emoji: string
  current: number; target: number; earned_at: string | null; available: boolean; blocked_reason: string | null
}
type Profile = { score: number; total: number; rank: number | null; locale: string; achievements: Card[] }
type Entry = { full_name: string; score: number; rank: number; is_self: boolean }
type TelegramApp = {
  initData: string; colorScheme?: 'light' | 'dark'; initDataUnsafe?: { user?: { language_code?: string } }
  ready: () => void; expand: () => void
  onEvent?: (name: string, cb: () => void) => void; offEvent?: (name: string, cb: () => void) => void
  BackButton?: { show: () => void; hide: () => void; onClick: (cb: () => void) => void; offClick: (cb: () => void) => void }
}
const telegram = (window as Window & { Telegram?: { WebApp?: TelegramApp } }).Telegram?.WebApp
const detected = telegram?.initDataUnsafe?.user?.language_code?.split('-')[0] ?? 'en'
const locale = ref(detected in messages ? detected : 'en')
const copy = computed(() => messages[locale.value as keyof typeof messages])
const title = ref('Manashelper')
const profile = ref<Profile>()
const entries = ref<Entry[]>([])
const tab = ref<'collection' | 'leaderboard'>('collection')
const loading = ref(true)
const error = ref(false)
const selected = ref<Card>()
const dialog = ref<HTMLDialogElement>()
let trigger: HTMLElement | null = null

async function api(path: string) {
  const response = await fetch(`/api/gamification/${path}`, {
    headers: { Authorization: `tma ${telegram?.initData ?? ''}` }, cache: 'no-store',
  })
  if (!response.ok) throw new Error('Request failed')
  return response.json()
}
async function load() {
  loading.value = true
  error.value = false
  try {
    const [me, leaderboard] = await Promise.all([api('me'), api('leaderboard')])
    profile.value = me
    entries.value = leaderboard.entries
    locale.value = me.locale in messages ? me.locale : 'en'
    document.documentElement.lang = locale.value
    title.value = me.ui.title
    document.title = me.ui.title
  } catch { error.value = true }
  finally { loading.value = false }
}
async function open(card: Card, event: MouseEvent) {
  trigger = event.currentTarget as HTMLElement
  selected.value = card
  await nextTick()
  dialog.value?.showModal()
  telegram?.BackButton?.show()
}
function close() { dialog.value?.close() }
function afterClose() {
  selected.value = undefined
  telegram?.BackButton?.hide()
  trigger?.focus()
}
function applyTheme() {
  document.documentElement.dataset.theme = telegram?.colorScheme ?? 'dark'
}
onMounted(() => {
  applyTheme()
  telegram?.onEvent?.('themeChanged', applyTheme)
  telegram?.ready()
  telegram?.expand()
  telegram?.BackButton?.onClick(close)
  if (telegram?.initData) void load()
  else loading.value = false
})
onUnmounted(() => {
  telegram?.BackButton?.offClick(close)
  telegram?.offEvent?.('themeChanged', applyTheme)
})
</script>

<template>
  <main>
    <header class="masthead"><span class="brand-mark">m<span>✦</span></span><span>MANASHELPER</span><span class="edition">STUDENT CLUB</span></header>
    <section v-if="!telegram?.initData" class="notice" role="status"><span class="notice-icon">✦</span><p>{{ copy.open_telegram }}</p></section>
    <section v-else-if="loading" class="notice" role="status" aria-live="polite"><span class="spinner"></span><p>{{ copy.loading }}</p></section>
    <section v-else-if="error" class="notice" role="alert"><p>{{ copy.error }}</p><button class="primary" @click="load">{{ copy.retry }}</button></section>
    <template v-else-if="profile">
      <section class="hero">
        <span class="eyebrow">{{ copy.collection }}</span>
        <h1>{{ title }}<span class="spark">✦</span></h1>
        <p class="subtitle">{{ copy.subtitle }}</p>
        <div class="stats">
          <div><span class="stat-label">{{ copy.earned }}</span><strong>{{ profile.score }}<small>/ {{ profile.total }}</small></strong><div class="overall-track"><span :style="{ width: `${profile.score / profile.total * 100}%` }"></span></div></div>
          <div><span class="stat-label">{{ copy.rank }}</span><strong v-if="profile.rank">#{{ profile.rank }}</strong><span v-else class="unranked">{{ copy.unranked }}</span></div>
        </div>
      </section>
      <nav class="tabs" :aria-label="copy.collection">
        <button :aria-pressed="tab === 'collection'" :class="{ active: tab === 'collection' }" @click="tab = 'collection'">{{ copy.collection }} <span>{{ profile.score }}</span></button>
        <button :aria-pressed="tab === 'leaderboard'" :class="{ active: tab === 'leaderboard' }" @click="tab = 'leaderboard'">{{ copy.leaderboard }} ↗</button>
      </nav>
      <section v-if="tab === 'collection'" class="collection" :aria-label="copy.collection">
        <button v-for="card in profile.achievements" :key="card.key" class="achievement" :class="{ earned: card.earned_at, pending: !card.available && !card.earned_at }" @click="open(card, $event)">
          <span class="card-top"><span class="badge">{{ card.emoji }}</span><span class="status" :aria-label="card.earned_at ? copy.earned : copy.locked">{{ card.earned_at ? '✓' : '↗' }}</span></span>
          <span class="card-name">{{ card.name }}</span>
          <span class="card-state">{{ card.earned_at ? copy.earned : !card.available ? (card.blocked_reason === 'baseline' ? copy.baseline_missing : copy.source_pending) : `${card.current} / ${card.target}` }}</span>
          <span class="track"><span :style="{ width: `${card.current / card.target * 100}%` }"></span></span>
        </button>
      </section>
      <section v-else class="leaderboard" :aria-label="copy.leaderboard">
        <p class="eyebrow">{{ copy.top_ten }}</p>
        <p v-if="!entries.length" class="empty">{{ copy.empty }}</p>
        <ol v-else>
          <li v-for="(entry, index) in entries" :key="index" :class="{ self: entry.is_self }"><span class="place">{{ entry.rank }}</span><span class="avatar">{{ entry.full_name.charAt(0) }}</span><span class="person">{{ entry.full_name }}<small v-if="entry.is_self">{{ copy.you }}</small></span><strong>{{ entry.score }} <span>✦</span></strong></li>
        </ol>
        <div class="your-place"><span>{{ copy.rank }}</span><strong>{{ profile.rank ? `#${profile.rank}` : '—' }}</strong><span>{{ profile.score }} / {{ profile.total }}</span></div>
      </section>
    </template>
    <footer>MANAS UNIVERSITY <span>✦</span> MANASHELPER</footer>
    <dialog ref="dialog" aria-labelledby="achievement-title" @close="afterClose" @click="($event.target === dialog) && close()">
      <template v-if="selected">
        <button class="close" :aria-label="copy.close" @click="close">×</button>
        <div class="detail-badge">{{ selected.emoji }}</div><p class="eyebrow">{{ selected.earned_at ? copy.earned : copy.locked }}</p>
        <h2 id="achievement-title">{{ selected.name }}</h2><p class="description">{{ selected.description }}</p>
        <div class="detail-progress"><span>{{ copy.progress }}</span><strong>{{ selected.current }} / {{ selected.target }}</strong></div>
        <div class="track"><span :style="{ width: `${selected.current / selected.target * 100}%` }"></span></div>
        <p v-if="!selected.available && !selected.earned_at" class="source-note">{{ selected.blocked_reason === 'baseline' ? copy.baseline_missing : copy.source_pending }}</p>
        <p v-if="selected.earned_at" class="earned-date">{{ new Date(selected.earned_at).toLocaleDateString(profile?.locale, { dateStyle: 'long' }) }}</p>
      </template>
    </dialog>
  </main>
</template>
