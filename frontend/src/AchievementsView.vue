<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import messages from './messages.json'
import AchievementBadge from './AchievementBadge.vue'
import { achievementArt } from './achievementArt'
import TermsLink from './TermsLink.vue'

type Card = {
  key: string; name: string; description: string; earned_at: string | null
}
type Profile = { score: number; total: number; rank: number | null; locale: string; theme: string; ui: Record<string, string>; achievements: Card[] }
type Entry = { full_name: string; score: number; rank: number; is_self: boolean; achievements: Card[] }
type TelegramApp = {
  initData: string; colorScheme?: 'light' | 'dark'; initDataUnsafe?: { user?: { language_code?: string } }
  ready: () => void; expand: () => void
  onEvent?: (name: string, cb: () => void) => void; offEvent?: (name: string, cb: () => void) => void
  BackButton?: { show: () => void; hide: () => void; onClick: (cb: () => void) => void; offClick: (cb: () => void) => void }
}
const telegram = (window as Window & { Telegram?: { WebApp?: TelegramApp } }).Telegram?.WebApp
const detected = telegram?.initDataUnsafe?.user?.language_code?.split('-')[0] ?? 'en'
const locale = ref(detected in messages ? detected : 'en')
const copy = computed(() => {
  const fallback = messages[locale.value as keyof typeof messages]
  const ui = profile.value?.ui
  if (!ui) return fallback
  return { ...fallback, ...ui, source_pending: ui.sourcePending ?? fallback.source_pending,
    baseline_missing: ui.baselineMissing ?? fallback.baseline_missing,
    open_telegram: ui.openTelegram ?? fallback.open_telegram, top_ten: ui.topTen ?? fallback.top_ten }
})
const title = ref('Manashelper')
const profile = ref<Profile>()
const entries = ref<Entry[]>([])
const tab = ref<'collection' | 'leaderboard'>('collection')
const loading = ref(true)
const error = ref(false)
const selected = ref<Card>()
const dialog = ref<HTMLDialogElement>()
const expandedEntry = ref<number>()
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
    document.documentElement.dataset.botTheme = me.theme
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
function selectTab(value: 'collection' | 'leaderboard') {
  tab.value = value
}
const selectedTone = computed(() => achievementArt[selected.value?.key ?? '']?.color ?? '#d2c5eb')
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
  <main class="app-shell">
    <section v-if="!telegram?.initData" class="notice" role="status">
      <span class="notice-icon" aria-hidden="true">✧</span><p>{{ copy.open_telegram }}</p>
    </section>
    <section v-else-if="loading" class="notice" role="status" aria-live="polite">
      <span class="spinner" aria-hidden="true"></span><p>{{ copy.loading }}</p>
    </section>
    <section v-else-if="error" class="notice" role="alert">
      <p>{{ copy.error }}</p><button class="primary" @click="load">{{ copy.retry }}</button>
    </section>

    <template v-else-if="profile">
      <nav class="view-switch" :aria-label="title">
        <button :aria-pressed="tab === 'collection'" @click="selectTab('collection')">{{ copy.collection }}</button>
        <button :aria-pressed="tab === 'leaderboard'" @click="selectTab('leaderboard')">{{ copy.leaderboard }}</button>
      </nav>

      <template v-if="tab === 'collection'">
        <section class="collection-intro">
          <span class="intro-spark" aria-hidden="true">✧</span>
          <h1>{{ title }}</h1>
          <p class="collection-count">{{ copy.earned }} <strong>{{ profile.score }}</strong> / {{ profile.total }}</p>
          <button class="rank-link" @click="selectTab('leaderboard')">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M8 3h8v6a4 4 0 0 1-8 0V3Z"/><path d="M8 5H4v2a4 4 0 0 0 4 4m8-6h4v2a4 4 0 0 1-4 4m-4 2v5m-4 3h8m-6-3h4"/></svg>
            <span>{{ profile.rank ? `${copy.rank} · ${profile.rank}` : copy.unranked }}</span>
            <span class="chevron" aria-hidden="true">›</span>
          </button>
        </section>
        <section class="collection" :aria-label="copy.collection">
          <button
            v-for="card in profile.achievements" :key="card.key"
            class="achievement" :class="{ earned: card.earned_at }"
            :aria-label="`${card.name}. ${card.earned_at ? copy.earned : copy.locked}`"
            @click="open(card, $event)"
          >
            <span class="medal-wrap">
              <AchievementBadge :achievement-key="card.key" :earned="!!card.earned_at" />
              <span v-if="card.earned_at" class="earned-check" aria-hidden="true">✓</span>
            </span>
            <span class="card-name">{{ card.name }}</span>
          </button>
        </section>
      </template>

      <section v-else class="leaderboard" :aria-label="copy.leaderboard">
        <header class="leaderboard-heading">
          <h1>{{ copy.leaderboard }}</h1>
          <p>{{ copy.rank }} <strong>{{ profile.rank ? `#${profile.rank}` : '—' }}</strong></p>
        </header>
        <p class="section-label">{{ copy.top_ten }}</p>
        <p v-if="!entries.length" class="empty">{{ copy.empty }}</p>
        <ol v-else class="ranking-list">
          <li v-for="(entry, index) in entries" :key="index" :class="{ self: entry.is_self }">
            <button class="ranking-person" :aria-expanded="expandedEntry === index" :aria-controls="`awards-${index}`"
              @click="expandedEntry = expandedEntry === index ? undefined : index">
              <span class="place" :class="{ 'podium-place': entry.rank <= 3 }">
                <svg v-if="entry.rank <= 3" class="podium-medal" :class="`podium-${entry.rank}`" viewBox="0 0 32 42" aria-hidden="true">
                  <path d="M7 1h8l4 14-8 3Z" fill="#c995ed"/><path d="M17 1h8l-5 17-8-3Z" fill="#7cc8f5"/>
                  <circle cx="16" cy="26" r="13" fill="currentColor"/><circle cx="16" cy="26" r="10" fill="none" stroke="white" stroke-opacity=".5"/>
                </svg>
                <span>{{ entry.rank }}</span>
              </span>
              <span class="avatar" :class="`avatar-${index % 5}`" aria-hidden="true">{{ entry.full_name.trim().charAt(0).toUpperCase() }}</span>
              <span class="person">{{ entry.full_name }}<small v-if="entry.is_self">{{ copy.you }}</small></span>
              <strong class="score-pill">{{ entry.score }}</strong>
              <span class="chevron" aria-hidden="true">{{ expandedEntry === index ? '⌃' : '⌄' }}</span>
            </button>
            <section v-if="expandedEntry === index" :id="`awards-${index}`" class="ranking-awards" :aria-label="`${entry.full_name}: ${copy.earned}`">
              <p>{{ copy.earned }} · {{ entry.achievements.length }}</p>
              <div class="collection">
                <button v-for="card in entry.achievements" :key="card.key" class="achievement earned"
                  :aria-label="`${card.name}. ${copy.earned}`" @click="open(card, $event)">
                  <span class="medal-wrap"><AchievementBadge :achievement-key="card.key" earned /></span>
                  <span class="card-name">{{ card.name }}</span>
                </button>
              </div>
            </section>
          </li>
        </ol>
        <div class="your-place"><span>{{ copy.you }}</span><strong>{{ profile.rank ? `#${profile.rank}` : '—' }}</strong><span>{{ copy.earned }} {{ profile.score }}</span></div>
      </section>
    </template>
    <dialog ref="dialog" class="achievement-sheet" :style="{ '--medal-tone': selectedTone }"
      aria-labelledby="achievement-title" aria-describedby="achievement-description"
      @close="afterClose" @click="($event.target === dialog) && close()"
    >
      <template v-if="selected">
        <span class="sheet-handle" aria-hidden="true"></span>
        <button class="close" :aria-label="copy.close" @click="close">×</button>
        <div class="sheet-art"><AchievementBadge :achievement-key="selected.key" :earned="!!selected.earned_at" reveal /></div>
        <p class="achievement-status" :class="{ 'status-earned': selected.earned_at }">{{ selected.earned_at ? copy.earned : copy.locked }}</p>
        <h2 id="achievement-title">{{ selected.name }}</h2>
        <p id="achievement-description" class="description">{{ selected.description }}</p>
        <p v-if="selected.earned_at" class="earned-date">{{ new Date(selected.earned_at).toLocaleDateString(profile?.locale, { dateStyle: 'long' }) }}</p>
        <button class="sheet-dismiss" @click="close">{{ copy.close }}</button>
      </template>
    </dialog>
    <TermsLink :locale="locale" from="achievements" />
  </main>
</template>
