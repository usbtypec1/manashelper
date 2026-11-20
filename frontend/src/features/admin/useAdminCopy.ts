import { computed } from 'vue'
import messages from '../../messages.json'
import { useTelegram } from '../../shared/telegram/telegram'

export const locales = Object.keys(messages)

export function useAdminCopy() {
  const { languageCode } = useTelegram()
  const locale = computed(() => {
    const code = languageCode.value
    return Object.hasOwn(messages, code) ? code as keyof typeof messages : 'en'
  })
  const copy = computed(() => messages[locale.value])
  const languageNames = computed(() => new Intl.DisplayNames([locale.value], { type: 'language' }))
  const themeNames = computed<Readonly<Record<string, string>>>(() => copy.value.adminThemes)

  return { locale, copy, languageNames, themeNames }
}
