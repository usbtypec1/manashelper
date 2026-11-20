import { popup } from '@tma.js/sdk-vue'

export async function confirmTelegramAction(message: string, label: string): Promise<boolean> {
  if (!popup.show.isAvailable()) return window.confirm(message)
  const result = await popup.show({ message, buttons: [{ id: 'confirm', text: label }, { type: 'cancel' }] })
  return result === 'confirm'
}
