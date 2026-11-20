import type { Page } from '@playwright/test'

type Appearance = 'light' | 'dark'
type NativeEvent = { name: string; data: unknown }

declare global {
  interface Window {
    telegramTest: {
      events: NativeEvent[]
      emit: (name: string, data?: unknown) => void
      changeTheme: (appearance: Appearance) => void
    }
  }
}

export async function mockTelegram(page: Page, options: {
  initData: string; colorScheme?: Appearance; version?: string; respondViewport?: boolean
}) {
  await page.addInitScript(({ initData, colorScheme = 'dark', version = '9.0', respondViewport = true }) => {
    const theme = (appearance: Appearance) => ({ bg_color: appearance === 'dark' ? '#111111' : '#ffffff' })
    const emit = (eventType: string, eventData?: unknown) => window.dispatchEvent(new MessageEvent('message', {
      source: window.parent, data: JSON.stringify({ eventType, eventData }),
    }))
    // Synthetic signed data from the local API, in the SDK's launch-session format.
    sessionStorage.setItem('tapps/launchParams', JSON.stringify(new URLSearchParams({
      tgWebAppData: initData, tgWebAppPlatform: 'tdesktop', tgWebAppVersion: version,
      tgWebAppThemeParams: JSON.stringify(theme(colorScheme)),
    }).toString()))
    window.telegramTest = {
      events: [], emit,
      changeTheme: appearance => emit('theme_changed', { theme_params: theme(appearance) }),
    }
    Object.assign(window, {
      TelegramWebviewProxy: {
        postEvent(name: string, data: string) {
          window.telegramTest.events.push({ name, data: data ? JSON.parse(data) : undefined })
          if (!respondViewport) return
          queueMicrotask(() => {
            if (name === 'web_app_request_viewport') emit('viewport_changed', {
              height: window.innerHeight, width: window.innerWidth, is_state_stable: true, is_expanded: true,
            })
            if (name === 'web_app_request_safe_area') emit('safe_area_changed', { top: 0, right: 0, bottom: 0, left: 0 })
            if (name === 'web_app_request_content_safe_area') emit('content_safe_area_changed', { top: 0, right: 0, bottom: 0, left: 0 })
          })
        },
      },
    })
  }, options)
}
