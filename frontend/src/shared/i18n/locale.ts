import messages from './messages.json'

export type Locale = keyof typeof messages
export const locales = Object.keys(messages)

export function normalizeLocale(value: string): Locale {
  return Object.hasOwn(messages, value) ? value as Locale : 'en'
}
