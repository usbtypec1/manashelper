<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watchEffect } from 'vue'
import messages from './messages.json'

const params = new URLSearchParams(window.location.search)
const telegram = (window as Window & { Telegram?: { WebApp?: {
  colorScheme?: string; ready: () => void; expand: () => void
  initDataUnsafe?: { user?: { language_code?: string } }
  onEvent?: (event: string, cb: () => void) => void
  offEvent?: (event: string, cb: () => void) => void
} } }).Telegram?.WebApp
const detected = params.get('lang') ?? telegram?.initDataUnsafe?.user?.language_code?.split('-')[0] ?? 'en'
const locale = ref(detected in messages ? detected as keyof typeof messages : 'en')
const copy = computed(() => messages[locale.value].terms)
const sectionKeys = ['services', 'data', 'obis', 'eders', 'sync', 'ranking', 'controls', 'limits'] as const
const sections = computed(() => sectionKeys.map(key => ({
  key, title: copy.value[`${key}.title`], body: copy.value[`${key}.body`],
  sources: key === 'obis' || key === 'eders' ? copy.value.sources[key] : [],
})))
const origin = params.get('from')
const backView = origin === 'courses' || origin === 'achievements' ? origin : 'settings'
watchEffect(() => {
  document.title = copy.value.title
  document.documentElement.lang = locale.value
})
function applyTheme() { document.documentElement.dataset.theme = telegram?.colorScheme ?? 'light' }
onMounted(() => {
  applyTheme()
  telegram?.ready()
  telegram?.expand()
  telegram?.onEvent?.('themeChanged', applyTheme)
})
onUnmounted(() => telegram?.offEvent?.('themeChanged', applyTheme))
</script>

<template>
  <main class="app-shell terms-page">
    <label class="terms-language">{{ copy.language }}
      <select v-model="locale">
        <option value="en">English</option><option value="ru">Русский</option>
        <option value="ky">Кыргызча</option><option value="tr">Türkçe</option><option value="zh">中文</option>
      </select>
    </label>
    <h1>{{ copy.title }}</h1>
    <p>{{ copy.updated_label }}: <time :datetime="copy.updated">{{ copy.updated }}</time></p>
    <section v-for="section in sections" :key="section.key" :aria-labelledby="`terms-${section.key}`">
      <h2 :id="`terms-${section.key}`">{{ section.title }}</h2>
      <p>{{ section.body }}</p>
      <ul v-if="section.sources.length" class="terms-sources">
        <li v-for="source in section.sources" :key="source"><code>{{ source }}</code></li>
      </ul>
    </section>
    <a :href="`/app/?view=${backView}`">{{ copy.back }}</a>
  </main>
</template>
