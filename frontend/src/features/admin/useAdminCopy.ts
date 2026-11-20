import { computed } from 'vue'
import { normalizeLocale } from '../../shared/i18n/locale'
import messages from '../../shared/i18n/messages.json'
import { useTelegram } from '../../shared/telegram/telegram'

export function useAdminCopy() {
  const { languageCode } = useTelegram()
  const locale = computed(() => normalizeLocale(languageCode.value))
  const copy = computed(() => messages[locale.value])
  const languageNames = computed(() => new Intl.DisplayNames([locale.value], { type: 'language' }))
  const themeNames = computed<Readonly<Record<string, string>>>(() => copy.value.adminThemes)

  return { locale, copy, languageNames, themeNames }
}
