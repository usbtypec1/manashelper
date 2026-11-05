import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  // The real API is used; only Telegram's native WebView bridge is simulated.
  await page.route('https://telegram.org/js/telegram-web-app.js', route => route.fulfill({ body: '', contentType: 'application/javascript' }))
})

test('collection, detail, keyboard close and leaderboard use real authenticated API', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data')).json()
  await page.addInitScript(({ initData }) => {
    Object.assign(window, { Telegram: { WebApp: {
      initData, initDataUnsafe: { user: { language_code: 'ru' } }, ready() {}, expand() {},
    } } })
  }, fixture)
  await page.goto('/app/')
  await expect(page.getByRole('heading', { name: 'Ачивки' })).toBeVisible()
  await expect(page.locator('button.achievement')).toHaveCount(11)
  await expect(page.locator('.collection')).toHaveCSS('display', 'grid')
  for (const [name, description] of [
    ['Элдин баласы', 'три итоговые оценки AA'],
    ['По тонкому льду', 'теории или практике'],
  ]) {
    await page.getByRole('button', { name: new RegExp(name) }).click()
    await expect(page.getByRole('dialog')).toContainText(description)
    await page.keyboard.press('Escape')
  }
  const boss = page.getByRole('button', { name: /Босс йемекхане/ })
  await expect(boss).toContainText('63 / 100')
  await boss.click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('dialog')).toContainText('не менее 10 минут')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(boss).toBeFocused()
  await page.screenshot({ path: `test-results/collection-${test.info().project.name}.png`, fullPage: true })
  await page.getByRole('button', { name: /Лидерборд/ }).click()
  await expect(page.getByText('Студент <Manas>')).toBeVisible()
  await expect(page.locator('.person script')).toHaveCount(0)
  await page.screenshot({ path: `test-results/leaderboard-${test.info().project.name}.png`, fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('a regular browser gets a Telegram entry prompt', async ({ page }) => {
  await page.goto('/app/')
  await expect(page.getByRole('status')).toContainText('Open this Mini App')
})
