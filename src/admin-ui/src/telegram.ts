import { ref } from 'vue'

type Insets = { top: number; right: number; bottom: number; left: number }
type TelegramEvent =
  'viewportChanged' | 'safeAreaChanged' | 'contentSafeAreaChanged' | 'fullscreenChanged' | 'fullscreenFailed'

export interface TelegramWebApp {
  initData: string
  version?: string
  viewportStableHeight?: number
  safeAreaInset?: Partial<Insets>
  contentSafeAreaInset?: Partial<Insets>
  isFullscreen?: boolean
  ready(): void
  expand(): void
  close(): void
  isVersionAtLeast?(version: string): boolean
  requestFullscreen?(): void
  enableClosingConfirmation?(): void
  disableClosingConfirmation?(): void
  onEvent(event: TelegramEvent, callback: () => void): void
  offEvent(event: TelegramEvent, callback: () => void): void
  BackButton: {
    show(): void
    hide(): void
    onClick(callback: () => void): void
    offClick(callback: () => void): void
  }
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp }
  }
}

export function createTelegramShell(onBack: () => void) {
  const candidate = window.Telegram?.WebApp
  // The official SDK is also present in a normal browser. Empty launch data must
  // keep the existing browser login rather than pretend it is an authenticated app.
  const sdk = candidate?.initData ? candidate : undefined
  const fullscreen = ref<'unavailable' | 'pending' | 'fullscreen' | 'expanded'>('unavailable')
  let started = false
  let dirty = false
  let backVisible = false

  function viewport() {
    if (!sdk) return
    const root = window.document.documentElement.style
    const height = sdk.viewportStableHeight || window.innerHeight
    root.setProperty('--app-viewport-height', `${height}px`)
    for (const side of ['top', 'right', 'bottom', 'left'] as const) {
      const safe = Math.max(0, sdk.safeAreaInset?.[side] ?? 0)
      const content = Math.max(0, sdk.contentSafeAreaInset?.[side] ?? 0)
      root.setProperty(`--app-safe-area-${side}`, `${safe + content}px`)
    }
  }
  function expanded() {
    if (!sdk) return
    fullscreen.value = 'expanded'
    sdk.expand()
    viewport()
  }
  function fullscreenChanged() {
    fullscreen.value = sdk?.isFullscreen ? 'fullscreen' : 'expanded'
    viewport()
  }
  const events: [TelegramEvent, () => void][] = [
    ['viewportChanged', viewport],
    ['safeAreaChanged', viewport],
    ['contentSafeAreaChanged', viewport],
    ['fullscreenChanged', fullscreenChanged],
    ['fullscreenFailed', expanded],
  ]

  function setDirty(value: boolean) {
    dirty = value
    if (!sdk || !started) return
    if (dirty) sdk.enableClosingConfirmation?.()
    else sdk.disableClosingConfirmation?.()
  }
  function setBackVisible(value: boolean) {
    backVisible = value
    if (!sdk || !started) return
    if (backVisible) sdk.BackButton.show()
    else sdk.BackButton.hide()
  }
  function start() {
    if (!sdk || started) return
    started = true
    for (const [event, callback] of events) sdk.onEvent(event, callback)
    sdk.BackButton.onClick(onBack)
    window.addEventListener('resize', viewport)
    sdk.ready()
    viewport()
    setDirty(dirty)
    setBackVisible(backVisible)
    const supportsFullscreen = sdk.isVersionAtLeast?.('8.0') ?? Number.parseFloat(sdk.version ?? '0') >= 8
    if (supportsFullscreen && sdk.requestFullscreen) {
      fullscreen.value = sdk.isFullscreen ? 'fullscreen' : 'pending'
      if (!sdk.isFullscreen) {
        try {
          sdk.requestFullscreen()
        } catch {
          expanded()
        }
      }
    } else expanded()
  }
  function close() {
    if (!sdk) return
    // App owns the explicit discard confirmation for its native Back action.
    sdk.disableClosingConfirmation?.()
    sdk.close()
  }
  function dispose() {
    if (!sdk || !started) return
    for (const [event, callback] of events) sdk.offEvent(event, callback)
    sdk.BackButton.offClick(onBack)
    sdk.BackButton.hide()
    sdk.disableClosingConfirmation?.()
    window.removeEventListener('resize', viewport)
    const root = window.document.documentElement.style
    root.removeProperty('--app-viewport-height')
    for (const side of ['top', 'right', 'bottom', 'left']) root.removeProperty(`--app-safe-area-${side}`)
    started = false
  }

  return {
    initData: sdk?.initData,
    isMiniApp: !!sdk,
    fullscreen,
    start,
    setDirty,
    setBackVisible,
    close,
    dispose,
  }
}
