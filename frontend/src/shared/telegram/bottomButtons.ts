import { mainButton, secondaryButton } from '@tma.js/sdk-vue'
import { onScopeDispose, watchEffect, type Ref } from 'vue'
import { useTelegram } from './telegram'

export type BottomAction = {
  text: string
  run: () => void
  disabled: boolean
  loading: boolean
}

function bindButton(
  button: typeof mainButton | typeof secondaryButton,
  action: Readonly<Ref<BottomAction | null>>,
) {
  if (!button.mount.isAvailable()) return false
  button.mount()
  const offClick = button.onClick(() => {
    const current = action.value
    if (current && !current.disabled) current.run()
  })
  watchEffect(() => {
    const current = action.value
    if (current) {
      button.setParams({
        text: current.text, isVisible: true, isEnabled: !current.disabled, isLoaderVisible: current.loading,
      })
    } else {
      button.setParams({ isVisible: false, isLoaderVisible: false })
    }
  })
  onScopeDispose(() => {
    offClick()
    button.setParams({ isVisible: false, isLoaderVisible: false })
    button.unmount()
  })
  return true
}

export function useTelegramBottomButtons(
  primary: Readonly<Ref<BottomAction | null>>,
  secondary: Readonly<Ref<BottomAction | null>>,
) {
  const { available } = useTelegram()
  return {
    nativeMain: available && bindButton(mainButton, primary),
    nativeSecondary: available && bindButton(secondaryButton, secondary),
  }
}
