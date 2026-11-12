import { expect, test } from '@playwright/test'
import { mockTelegram } from './telegram'

test('SDK initializes once, updates theme and safe areas, and gives dialogs priority over routing', async ({ page, request }) => {
  const vueWarnings: string[] = []
  page.on('console', message => { if (message.text().startsWith('[Vue warn]')) vueWarnings.push(message.text()) })
  const fixture = await (await request.get('/_fixture/init-data')).json()
  await mockTelegram(page, fixture)
  await page.goto('/app/leaderboard')
  await expect(page.getByRole('heading', { name: 'Лидерборд', exact: true })).toBeVisible()
  await expect(page.locator('html')).toHaveCSS('--tg-viewport-content-safe-area-inset-top', '0px')
  await page.evaluate(() => window.telegramTest.emit('content_safe_area_changed', { top: 48, bottom: 32, left: 0, right: 0 }))
  await expect(page.locator('.app-shell')).toHaveCSS('padding-top', '48px')
  await page.getByRole('button', { name: /Участник <Manas>/ }).click()
  const award = page.locator('.ranking-awards button.achievement')
  await award.click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.evaluate(() => window.telegramTest.emit('back_button_pressed'))
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(page).toHaveURL('/app/leaderboard')
  await expect(award).toBeFocused()
  await page.evaluate(() => window.telegramTest.emit('back_button_pressed'))
  await expect(page).toHaveURL('/app/achievements')
  for (let visit = 0; visit < 2; visit++) {
    await page.getByRole('link', { name: 'Пользовательское соглашение и обработка данных' }).click()
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Пользовательское соглашение и обработка данных')
    await page.evaluate(() => window.telegramTest.emit('back_button_pressed'))
    await expect(page.getByRole('heading', { name: /Ачивки/ })).toBeVisible()
  }
  await page.evaluate(() => window.telegramTest.changeTheme('light'))
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  expect(await page.evaluate(() => ({
    ready: window.telegramTest.events.filter(event => event.name === 'web_app_ready').length,
    expanded: window.telegramTest.events.filter(event => event.name === 'web_app_expand').length,
  }))).toEqual({ ready: 1, expanded: 1 })
  expect(vueWarnings).toEqual([])
})

test('unanswered viewport requests do not block authenticated screens', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data?preferences=1&locale=en')).json()
  await mockTelegram(page, { ...fixture, respondViewport: false })
  await page.goto('/app/settings')
  const grades = page.getByRole('checkbox', { name: 'Exam grades', exact: true })
  await expect(grades).toBeChecked()
  await grades.click()
  await expect(page.getByRole('status')).toHaveText('Saved')
  await expect(grades).not.toBeChecked()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
})

test('clients without BackButton support still load and close achievement dialogs', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data')).json()
  await mockTelegram(page, { ...fixture, version: '6.0' })
  await page.goto('/app/achievements')
  await page.getByRole('button', { name: /Босс йемекхане/ }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()
  expect(await page.evaluate(() => window.telegramTest.events.some(event => event.name === 'web_app_setup_back_button'))).toBe(false)
})
