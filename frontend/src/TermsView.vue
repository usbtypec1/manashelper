<script setup lang="ts">
import { computed, ref, watchEffect } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import messages from './messages.json'
import { useTelegram } from './shared/telegram/telegram'

const route = useRoute()
const { languageCode } = useTelegram()
const detected = typeof route.query.lang === 'string' ? route.query.lang : languageCode.value
const locale = ref(detected in messages ? detected as keyof typeof messages : 'en')
const copy = computed(() => messages[locale.value].terms)
const sectionKeys = ['services', 'data', 'obis', 'eders', 'sync', 'ranking', 'controls', 'limits'] as const
const sections = computed(() => sectionKeys.map(key => ({
  key, title: copy.value[`${key}.title`], body: copy.value[`${key}.body`],
  sources: key === 'obis' || key === 'eders' ? copy.value.sources[key] : [],
})))
const backView = computed(() => {
  const backTo = route.meta.backTo
  return typeof backTo === 'function' ? backTo(route) : backTo
})
watchEffect(() => {
  document.title = copy.value.title
  document.documentElement.lang = locale.value
})
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
    <RouterLink :to="{ name: backView }">{{ copy.back }}</RouterLink>
  </main>
</template>
