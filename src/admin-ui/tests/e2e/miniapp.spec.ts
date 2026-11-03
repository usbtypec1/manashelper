import { expect, test, type BrowserContext } from '@playwright/test'
import type { TelegramWebApp } from '../../src/telegram'

interface TelegramTestState {
  calls: string[]
  closingEnabled: boolean
  backVisible: boolean
  closed: number
  emit(event: string): void
  pressBack(): void
}
declare global {
  interface Window {
    __telegramTest: TelegramTestState
  }
}

async function installSdk(context: BrowserContext, initData: string) {
  await context.route('https://telegram.org/js/telegram-web-app.js*', (route) =>
    route.fulfill({ contentType: 'application/javascript', body: '' }),
  )
  await context.addInitScript(
    ({ initData }) => {
      const handlers = new Map<string, Set<() => void>>()
      const back = new Set<() => void>()
      const state: TelegramTestState = {
        calls: [],
        closingEnabled: false,
        backVisible: false,
        closed: 0,
        emit: (event) => handlers.get(event)?.forEach((callback) => callback()),
        pressBack: () => back.forEach((callback) => callback()),
      }
      const sdk: TelegramWebApp = {
        initData,
        version: '9.0',
        viewportStableHeight: 844,
        safeAreaInset: { top: 12, right: 0, bottom: 10, left: 0 },
        contentSafeAreaInset: { top: 36, right: 0, bottom: 0, left: 0 },
        isFullscreen: false,
        ready: () => state.calls.push('ready'),
        expand: () => state.calls.push('expand'),
        requestFullscreen: () => state.calls.push('requestFullscreen'),
        close: () => {
          state.closed += 1
        },
        enableClosingConfirmation: () => {
          state.closingEnabled = true
        },
        disableClosingConfirmation: () => {
          state.closingEnabled = false
        },
        onEvent: (event, callback) => {
          const listeners = handlers.get(event) ?? new Set()
          listeners.add(callback)
          handlers.set(event, listeners)
        },
        offEvent: (event, callback) => handlers.get(event)?.delete(callback),
        BackButton: {
          show: () => {
            state.backVisible = true
          },
          hide: () => {
            state.backVisible = false
          },
          onClick: (callback) => back.add(callback),
          offClick: (callback) => back.delete(callback),
        },
      }
      window.Telegram = { WebApp: sdk }
      window.__telegramTest = state
    },
    { initData },
  )
}

test.beforeEach(async ({ request }) => {
  await request.post('/__test__/reset')
})

test('Mini App uses memory bearer auth, fullscreen events and safe mobile editing', async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const { init_data } = await (await request.get('/__test__/init-data')).json()
  await installSdk(page.context(), init_data)
  const authenticatedRequests: Promise<{ bearer: boolean; cookie: boolean; csrf: boolean }>[] = []
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/admin/api/v1/flows') {
      authenticatedRequests.push(
        request.allHeaders().then((headers) => ({
          bearer: !!headers.authorization?.startsWith('Bearer '),
          cookie: !!headers.cookie,
          csrf: !!headers['x-csrf-token'],
        })),
      )
    }
  })
  const exchanged = page.waitForResponse((response) => response.url().endsWith('/auth/telegram'))
  await page.goto('/admin/')
  const exchange = await exchanged
  expect(exchange.status()).toBe(200)
  const { access_token } = await exchange.json()
  expect(typeof access_token).toBe('string')
  expect(access_token.length).toBeGreaterThan(20)
  await expect(page.locator('.app-header')).toBeVisible()
  await expect(page.locator('.app-shell')).toHaveAttribute('data-mini-app', 'true')
  await expect(page.locator('.app-shell')).toHaveAttribute('data-fullscreen', 'pending')
  expect(await page.evaluate(() => window.__telegramTest.calls)).toEqual(['ready', 'requestFullscreen'])
  expect(await page.context().cookies()).toEqual([])
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length, location.hash])).toEqual([
    0,
    0,
    '',
  ])
  expect(
    await page.evaluate((token) => document.documentElement.outerHTML.includes(token), access_token),
  ).toBe(false)
  expect(authenticatedRequests.length).toBeGreaterThan(0)
  expect(
    (await Promise.all(authenticatedRequests)).every(
      (request) => request.bearer && !request.cookie && !request.csrf,
    ),
  ).toBe(true)
  expect(
    await page.evaluate(() => document.documentElement.style.getPropertyValue('--app-safe-area-top')),
  ).toBe('48px')
  await page.evaluate(() => {
    window.Telegram!.WebApp!.isFullscreen = true
    window.__telegramTest.emit('fullscreenChanged')
  })
  await expect(page.locator('.app-shell')).toHaveAttribute('data-fullscreen', 'fullscreen')
  await page.evaluate(() => window.__telegramTest.emit('fullscreenFailed'))
  await expect(page.locator('.app-shell')).toHaveAttribute('data-fullscreen', 'expanded')
  expect(await page.evaluate(() => window.__telegramTest.calls)).toContain('expand')

  await page.getByRole('button', { name: 'New scenario', exact: true }).first().click()
  await page.getByRole('textbox', { name: 'Scenario ID', exact: true }).fill('miniapp_form')
  await page.getByRole('button', { name: 'Create', exact: true }).click()
  await expect(page.locator('.flow-heading h1')).toHaveText('miniapp_form')
  await expect(page.locator('.palette')).toBeHidden()
  await expect(page.locator('.properties-panel')).toBeHidden()
  await page.locator('.mobile-editor-tools').getByRole('button', { name: 'Add nodes', exact: true }).click()
  await expect(page.locator('.palette')).toBeVisible()
  await expect(page.locator('.properties-panel')).toBeHidden()
  await page.locator('.palette').getByRole('button', { name: 'Input', exact: false }).click()
  await expect(page.locator('.palette')).toBeHidden()
  await expect(page.locator('.properties-panel')).toBeVisible()
  await page
    .locator('.properties-panel')
    .getByRole('textbox', { name: 'Message text', exact: true })
    .first()
    .fill('Telegram draft')
  await expect.poll(() => page.evaluate(() => window.__telegramTest.closingEnabled)).toBe(true)
  await expect.poll(() => page.evaluate(() => window.__telegramTest.backVisible)).toBe(true)
  await page.evaluate(() => window.__telegramTest.pressBack())
  await expect(page.locator('.properties-panel')).toBeHidden()
  await page.evaluate(() => window.__telegramTest.pressBack())
  await expect(page.getByRole('dialog')).toContainText('Discard unsaved changes?')
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  expect(await page.evaluate(() => window.__telegramTest.closed)).toBe(0)
  await page.evaluate(() => window.__telegramTest.pressBack())
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect.poll(() => page.evaluate(() => window.__telegramTest.closed)).toBe(1)
  expect(await page.evaluate(() => window.__telegramTest.closingEnabled)).toBe(false)
})

test('invalid Mini App identity cannot fall back to an existing browser cookie', async ({
  page,
  request,
}) => {
  await page
    .context()
    .route('https://telegram.org/js/telegram-web-app.js*', (route) =>
      route.fulfill({ contentType: 'application/javascript', body: '' }),
    )
  const { ticket } = await (await request.get('/__test__/ticket')).json()
  await page.goto('/admin/#ticket=' + ticket)
  await expect(page.locator('.app-header')).toBeVisible()
  expect((await page.context().cookies()).length).toBeGreaterThan(0)
  await installSdk(page.context(), 'auth_date=1&user=%7B%22id%22%3A1%7D&hash=invalid')
  const paths: string[] = []
  page.on('request', (request) => paths.push(new URL(request.url()).pathname))
  const rejected = page.waitForResponse((response) => response.url().endsWith('/auth/telegram'))
  await page.reload()
  const response = await rejected
  expect(response.status()).toBe(401)
  expect((await response.request().allHeaders()).cookie).toBeUndefined()
  await expect(page.locator('.login-card')).toContainText('Administrative session required')
  expect(paths).not.toContain('/admin/api/v1/auth/session')
  await expect(page.locator('.app-header')).toHaveCount(0)
})
