import { afterEach, expect, mock, test } from 'bun:test'
import { createTelegramShell, type TelegramWebApp } from '../../src/telegram'

const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
afterEach(() => {
  if (originalWindow) Object.defineProperty(globalThis, 'window', originalWindow)
  else Reflect.deleteProperty(globalThis, 'window')
})

function setup(overrides: Partial<TelegramWebApp> = {}) {
  const properties = new Map<string, string>()
  const events = new Map<string, Set<() => void>>()
  const resize = new Set<() => void>()
  const back = new Set<() => void>()
  const sdk: TelegramWebApp = {
    initData: 'synthetic-signed-launch-data',
    version: '9.0',
    viewportStableHeight: 700,
    safeAreaInset: { top: 20, bottom: 15 },
    contentSafeAreaInset: { top: 10, bottom: 5 },
    isFullscreen: false,
    ready: mock(() => {}),
    expand: mock(() => {}),
    close: mock(() => {}),
    requestFullscreen: mock(() => {}),
    enableClosingConfirmation: mock(() => {}),
    disableClosingConfirmation: mock(() => {}),
    onEvent: (event, callback) => {
      const listeners = events.get(event) ?? new Set()
      listeners.add(callback)
      events.set(event, listeners)
    },
    offEvent: (event, callback) => events.get(event)?.delete(callback),
    BackButton: {
      show: mock(() => {}),
      hide: mock(() => {}),
      onClick: (callback) => back.add(callback),
      offClick: (callback) => back.delete(callback),
    },
    ...overrides,
  }
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: {
      Telegram: { WebApp: sdk },
      innerHeight: 900,
      document: {
        documentElement: {
          style: {
            setProperty: (name: string, value: string) => properties.set(name, value),
            removeProperty: (name: string) => properties.delete(name),
          },
        },
      },
      addEventListener: (_event: string, callback: () => void) => resize.add(callback),
      removeEventListener: (_event: string, callback: () => void) => resize.delete(callback),
    },
  })
  return {
    sdk,
    properties,
    events,
    resize,
    back,
    emit: (event: string) => events.get(event)?.forEach((callback) => callback()),
  }
}

test('SDK requests fullscreen and records actual fullscreen events and stable insets', () => {
  const { sdk, properties, emit } = setup()
  const shell = createTelegramShell(() => {})
  shell.start()
  shell.start()
  expect(sdk.ready).toHaveBeenCalledTimes(1)
  expect(sdk.requestFullscreen).toHaveBeenCalledTimes(1)
  expect(shell.fullscreen.value).toBe('pending')
  expect(properties.get('--app-viewport-height')).toBe('700px')
  expect(properties.get('--app-safe-area-top')).toBe('30px')
  expect(properties.get('--app-safe-area-bottom')).toBe('20px')
  sdk.isFullscreen = true
  emit('fullscreenChanged')
  expect(shell.fullscreen.value).toBe('fullscreen')
  sdk.viewportStableHeight = 640
  sdk.safeAreaInset = { top: 30 }
  emit('safeAreaChanged')
  expect(properties.get('--app-safe-area-top')).toBe('40px')
  expect(properties.get('--app-viewport-height')).toBe('640px')
  emit('fullscreenFailed')
  expect(shell.fullscreen.value).toBe('expanded')
  expect(sdk.expand).toHaveBeenCalledTimes(1)
  shell.dispose()
})

test('old and unsupported fullscreen APIs use expand without claiming fullscreen', () => {
  const { sdk } = setup({ version: '7.10' })
  const shell = createTelegramShell(() => {})
  shell.start()
  expect(sdk.requestFullscreen).not.toHaveBeenCalled()
  expect(sdk.expand).toHaveBeenCalledTimes(1)
  expect(shell.fullscreen.value).toBe('expanded')
  shell.dispose()
})

test('a rejected fullscreen request falls back to expansion', () => {
  const { sdk } = setup({
    requestFullscreen: mock(() => {
      throw new Error('Unsupported')
    }),
  })
  const shell = createTelegramShell(() => {})
  shell.start()
  expect(sdk.expand).toHaveBeenCalledTimes(1)
  expect(shell.fullscreen.value).toBe('expanded')
  shell.dispose()
})

test('BackButton, dirty close guard and all listeners are removed on disposal', () => {
  const { sdk, properties, events, resize, back } = setup()
  const onBack = mock(() => {})
  const shell = createTelegramShell(onBack)
  shell.setDirty(true)
  shell.setBackVisible(true)
  shell.start()
  expect(sdk.enableClosingConfirmation).toHaveBeenCalledTimes(1)
  expect(sdk.BackButton.show).toHaveBeenCalledTimes(1)
  back.forEach((callback) => callback())
  expect(onBack).toHaveBeenCalledTimes(1)
  shell.setDirty(false)
  expect(sdk.disableClosingConfirmation).toHaveBeenCalled()
  shell.setBackVisible(false)
  expect(sdk.BackButton.hide).toHaveBeenCalled()
  shell.close()
  expect(sdk.close).toHaveBeenCalledTimes(1)
  shell.dispose()
  expect([...events.values()].every((listeners) => listeners.size === 0)).toBe(true)
  expect(resize.size).toBe(0)
  expect(back.size).toBe(0)
  expect(properties.size).toBe(0)
})

test('a browser with the official SDK but no launch data keeps browser login', () => {
  const { sdk, properties, events } = setup({ initData: '' })
  const shell = createTelegramShell(() => {})
  shell.start()
  shell.dispose()
  expect(shell.isMiniApp).toBe(false)
  expect(shell.initData).toBeUndefined()
  expect(sdk.ready).not.toHaveBeenCalled()
  expect(sdk.requestFullscreen).not.toHaveBeenCalled()
  expect(properties.size).toBe(0)
  expect(events.size).toBe(0)
})
