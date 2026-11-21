<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import AchievementBadge from '../features/achievements/AchievementBadge.vue'
import { achievementArt } from '../features/achievements/achievementArt'
import type { Card } from '../features/achievements/api'
import { useAchievements } from '../features/achievements/useAchievements'
import TermsLink from '../features/terms/TermsLink.vue'
import { useTelegramDialogBack } from '../shared/telegram/telegram'
import '../features/achievements/achievements.css'

const props = defineProps<{ tab: 'collection' | 'leaderboard' }>()
const router = useRouter()
const { rawInitData, locale, title, copy, profile, entries, loading, error, load } = useAchievements()
const tab = computed(() => props.tab)
const selected = ref<Card>()
const dialog = ref<HTMLDialogElement>()
const expandedEntry = ref<number>()
let trigger: HTMLElement | null = null

async function open(card: Card, event: MouseEvent) {
  trigger = event.currentTarget as HTMLElement
  selected.value = card
  await nextTick()
  dialog.value?.showModal()
}
function close() {
  selected.value = undefined
  dialog.value?.close()
}
function selectTab(value: 'collection' | 'leaderboard') {
  void router.push({ name: value === 'collection' ? 'achievements' : 'leaderboard' })
}
const selectedTone = computed(() => achievementArt[selected.value?.key ?? '']?.color ?? '#d2c5eb')
function afterClose() {
  selected.value = undefined
  trigger?.focus()
}
useTelegramDialogBack(computed(() => !!selected.value), close)
</script>

<template>
  <main class="app-shell achievements-page">
    <section v-if="!rawInitData" class="notice" role="status">
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
        <p class="section-label">{{ copy.participants }}</p>
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
      @close="afterClose" @cancel.prevent="close" @click="($event.target === dialog) && close()"
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
    <TermsLink :locale="locale" :from="tab === 'collection' ? 'achievements' : 'leaderboard'" />
  </main>
</template>
