import { expect, test } from '@playwright/test'
import { mockTelegram } from '../../fixtures/telegram'

type BottomButtonEvent = { text?: string; is_visible?: boolean }

function buttonState(method: string) {
  return window.telegramTest.events.filter(event => event.name === method).at(-1)?.data as BottomButtonEvent | undefined
}

test('admin opens the user directory with Telegram launch data and loads another page', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data')).json()
  await mockTelegram(page, { ...fixture, colorScheme: 'dark' })
  await page.goto('/app/admin')

  const users = page.getByRole('table', { name: 'Users' })
  await expect(users.getByRole('row')).toHaveCount(51)
  await expect(users.getByText('@member_1', { exact: true })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(users).toHaveCSS('color', 'rgb(255, 255, 255)')
  await expect.poll(() => page.evaluate(buttonState, 'web_app_setup_main_button'))
    .toMatchObject({ text: 'Load more', is_visible: true })
  await expect.poll(() => page.evaluate(buttonState, 'web_app_setup_secondary_button'))
    .toMatchObject({ text: 'Refresh', is_visible: true })
  await expect(page.getByRole('button', { name: 'Load more' })).toHaveCount(0)
  await page.evaluate(() => window.telegramTest.emit('main_button_pressed'))
  await expect(users.getByText('Студент <Manas>', { exact: true })).toBeVisible()
  const loadedRows = await users.getByRole('row').count()
  const firstRow = users.getByRole('row').nth(1)
  const cells = firstRow.getByRole('cell')
  const nav = page.getByRole('navigation')
  const heading = page.getByRole('heading', { name: 'Users' })
  await page.setViewportSize({ width: 1360, height: 900 })
  await expect(firstRow).toHaveCSS('display', 'table-row')
  expect((await nav.boundingBox())!.x).toBeLessThan((await heading.boundingBox())!.x)
  expect((await users.boundingBox())!.width).toBeGreaterThan(840)

  await page.setViewportSize({ width: 768, height: 800 })
  await expect(firstRow).toHaveCSS('display', 'table-row')
  expect((await nav.boundingBox())!.y).toBeLessThan((await heading.boundingBox())!.y)

  await page.setViewportSize({ width: 280, height: 740 })
  await page.evaluate(() => window.telegramTest.emit('content_safe_area_changed', {
    top: 24, right: 18, bottom: 10, left: 22,
  }))
  await expect(page.locator('.admin-shell')).toHaveCSS('padding-left', '22px')
  expect((await cells.nth(1).boundingBox())!.y).toBeGreaterThan((await cells.nth(0).boundingBox())!.y)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)

  await page.evaluate(() => window.telegramTest.changeTheme('light'))
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(users).toHaveCSS('color', 'rgb(17, 17, 20)')
  await expect(users.getByRole('row')).toHaveCount(loadedRows)

  await page.evaluate(() => window.telegramTest.emit('theme_changed', {
    theme_params: { bg_color: '#ffffff', secondary_bg_color: '#f2eedf', section_bg_color: '#fdfaf1', text_color: '#281d13' },
  }))
  await expect(page.locator('.telegram-admin')).toHaveCSS('background-color', 'rgb(242, 238, 223)')
  await expect(users).toHaveCSS('background-color', 'rgb(253, 250, 241)')
  await expect(users).toHaveCSS('color', 'rgb(40, 29, 19)')

  await expect.poll(() => page.evaluate(buttonState, 'web_app_setup_main_button'))
    .toMatchObject({ text: 'Refresh', is_visible: true })
  await page.evaluate(() => window.telegramTest.emit('main_button_pressed'))
  await expect(users.getByRole('row')).toHaveCount(51)
  await Promise.all([
    page.waitForResponse(response => new URL(response.url()).pathname === '/api/admin/users' && response.ok()),
    page.evaluate(() => window.telegramTest.emit('secondary_button_pressed')),
  ])
  await expect(users.getByRole('row')).toHaveCount(51)
  await page.reload()
  await expect(users.getByRole('row')).toHaveCount(51)
  await page.evaluate(() => {
    history.pushState(history.state, '', '/app/terms')
    dispatchEvent(new PopStateEvent('popstate', { state: history.state }))
  })
  await expect(users).toHaveCount(0)
  await expect.poll(() => page.evaluate(buttonState, 'web_app_setup_main_button'))
    .toMatchObject({ is_visible: false })
  await expect.poll(() => page.evaluate(buttonState, 'web_app_setup_secondary_button'))
    .toMatchObject({ is_visible: false })
})

test('older Telegram clients use an in-page action when SecondaryButton is unavailable', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data')).json()
  await mockTelegram(page, { ...fixture, version: '7.9' })
  await page.goto('/app/admin')

  await expect(page.getByRole('table', { name: 'Users' })).toBeVisible()
  await expect.poll(() => page.evaluate(buttonState, 'web_app_setup_main_button'))
    .toMatchObject({ text: 'Load more', is_visible: true })
  await Promise.all([
    page.waitForResponse(response => new URL(response.url()).pathname === '/api/admin/users' && response.ok()),
    page.getByRole('button', { name: 'Refresh' }).click(),
  ])
  await expect(page.getByRole('row')).toHaveCount(51)
})

test('a registered user without permission cannot see any profiles', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data?preferences=1')).json()
  await mockTelegram(page, fixture)
  await page.goto('/app/admin')
  await expect(page.getByRole('alert')).toContainText('access to the admin panel')
  await expect(page.getByRole('table')).toHaveCount(0)
  expect((await page.evaluate(buttonState, 'web_app_setup_main_button'))?.is_visible).not.toBe(true)
  expect((await page.evaluate(buttonState, 'web_app_setup_secondary_button'))?.is_visible).not.toBe(true)
})

test('administrator blocks and unblocks a user from the filtered directory', async ({ page, request }, testInfo) => {
  const fixture = await (await request.get('/_fixture/init-data')).json()
  await mockTelegram(page, fixture)
  await page.goto('/app/admin')
  const index = testInfo.project.name === 'mobile' ? 48 : 49
  const name = 'Directory user ' + index
  await page.getByRole('searchbox', { name: 'Search users' }).fill('@member_' + index)
  const row = page.getByRole('row').filter({ hasText: name })

  async function changeState(action: string) {
    await row.getByRole('button', { name: action + ' ' + name, exact: true }).click()
    await expect.poll(() => page.evaluate(() => {
      const popup = window.telegramTest.events.filter(event => event.name === 'web_app_open_popup').at(-1)
      return popup?.data
    })).toMatchObject({ buttons: expect.arrayContaining([expect.objectContaining({ id: 'confirm', text: action })]) })
    await page.evaluate(() => window.telegramTest.emit('popup_closed', { button_id: 'confirm' }))
  }

  await changeState('Block')
  await expect(row.getByText('Blocked', { exact: true })).toBeVisible()
  await page.getByRole('combobox', { name: 'Status', exact: true }).selectOption('blocked')
  await expect(row.getByText('Blocked', { exact: true })).toBeVisible()
  await changeState('Unblock')
  await expect(page.getByText('No matching users.', { exact: true })).toBeVisible()
  await page.getByRole('combobox', { name: 'Status', exact: true }).selectOption('active')
  await expect(row.getByText('Active', { exact: true })).toBeVisible()
})
