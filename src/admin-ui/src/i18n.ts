import { ref } from 'vue'
import messages from './generated/messages.json'
export const uiLocale = ref<'en'>('en')
export type CopyKey = keyof typeof messages.en
export function t(key: CopyKey): string {
  return messages.en[key]
}
