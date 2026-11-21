import { computed, onMounted, ref } from 'vue'
import { normalizeLocale } from '../../shared/i18n/locale'
import messages from '../../shared/i18n/messages.json'
import { useTelegram } from '../../shared/telegram/telegram'
import { getAchievements } from './api'

export function useAchievements() {
  const { rawInitData, languageCode } = useTelegram()
  const locale = ref(normalizeLocale(languageCode.value))
  const title = ref('Manashelper')
  const result = ref<Awaited<ReturnType<typeof getAchievements>>>()
  const profile = computed(() => result.value?.profile)
  const entries = computed(() => result.value?.entries ?? [])
  const loading = ref(true)
  const error = ref(false)
  const copy = computed(() => {
    const fallback = messages[locale.value]
    const ui = profile.value?.ui
    if (!ui) return fallback
    return { ...fallback, ...ui, source_pending: ui.sourcePending ?? fallback.source_pending,
      baseline_missing: ui.baselineMissing ?? fallback.baseline_missing,
      open_telegram: ui.openTelegram ?? fallback.open_telegram }
  })

  async function load() {
    loading.value = true
    error.value = false
    try {
      const achievements = await getAchievements(rawInitData.value ?? '')
      result.value = achievements
      const me = achievements.profile
      document.documentElement.dataset.botTheme = me.theme
      locale.value = normalizeLocale(me.locale)
      document.documentElement.lang = locale.value
      title.value = me.ui.title
      document.title = me.ui.title
    } catch { error.value = true }
    finally { loading.value = false }
  }
  onMounted(() => {
    if (rawInitData.value) void load()
    else loading.value = false
  })
  return { rawInitData, locale, title, copy, profile, entries, loading, error, load }
}
