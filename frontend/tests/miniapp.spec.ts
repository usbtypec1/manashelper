import { expect, test } from '@playwright/test'
import { mockTelegram } from './telegram'

test('collection, detail, keyboard close and leaderboard use real authenticated API', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data')).json()
  await mockTelegram(page, fixture)
  await page.goto('/app/')
  await expect(page.getByRole('heading', { name: 'Ачивки' })).toBeVisible()
  await expect(page.locator('button.achievement')).toHaveCount(15)
  await expect(page.getByRole('button', { name: /Покемон/ })).toHaveCount(0)
  await expect(page.locator('.collection')).toHaveCSS('display', 'grid')
  for (const [name, description] of [
    ['Элдин баласы', 'три итоговые оценки AA'],
    ['На грани', 'теории или практике'],
  ]) {
    await page.getByRole('button', { name: new RegExp(name) }).click()
    await expect(page.getByRole('dialog')).toContainText(description)
    await page.keyboard.press('Escape')
  }
  const boss = page.getByRole('button', { name: /Босс йемекхане/ })
  await expect(boss.locator('[data-medal]')).toHaveAttribute('data-locked', 'true')
  await expect(page.getByText('63 / 100', { exact: true })).toHaveCount(0)
  await expect(page.locator('.track, .detail-progress, .overall-track, [role=progressbar]')).toHaveCount(0)
  await boss.click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('dialog')).toContainText('не менее 10 минут')
  await expect(page.getByRole('dialog').locator('[data-medal]')).toHaveAttribute('data-locked', 'false')
  await expect(page.getByRole('dialog')).not.toContainText('63 / 100')
  await page.screenshot({ path: `test-results/achievement-detail-${test.info().project.name}.png`, animations: 'disabled' })
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(boss).toBeFocused()
  await page.screenshot({ path: `test-results/collection-${test.info().project.name}.png`, fullPage: true, animations: 'disabled' })
  await page.getByRole('button', { name: /Лидерборд/ }).click()
  await expect(page.getByText('Студент <Manas>')).toBeVisible()
  await expect(page.locator('.person script')).toHaveCount(0)
  const participant = page.getByRole('button', { name: /Участник <Manas>/ })
  await participant.click()
  await expect(participant).toHaveAttribute('aria-expanded', 'true')
  await expect(page.locator('.ranking-awards button.achievement')).toHaveCount(1)
  await page.locator('.ranking-awards button.achievement').click()
  await expect(page.getByRole('dialog')).toContainText('Чемпион')
  await page.keyboard.press('Escape')
  await expect(page.locator('.ranking-awards button.achievement')).toBeFocused()
  await page.screenshot({ path: `test-results/leaderboard-${test.info().project.name}.png`, fullPage: true, animations: 'disabled' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.getByRole('link', { name: 'Пользовательское соглашение и обработка данных' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Пользовательское соглашение и обработка данных')
  await page.getByRole('link', { name: 'Назад', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Лидерборд', exact: true })).toBeVisible()
})

test('terms are public, localized and list current academic access', async ({ page }) => {
  await page.route('**/api/**', route => { throw new Error(`Terms must not access private APIs: ${route.request().url()}`) })
  await page.goto('/app/?view=terms&lang=ru')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Пользовательское соглашение и обработка данных')
  await expect(page.getByRole('heading', { level: 2 })).toHaveCount(8)
  await expect(page.getByText('https://obistest.manas.edu.kg/vs-ders/transkript-detailed', { exact: true })).toBeVisible()
  await expect(page.locator('.terms-page')).toContainText('core_completion_update_activity_completion_status_manually')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: `test-results/terms-${test.info().project.name}.png`, fullPage: true, animations: 'disabled' })
  for (const [locale, title] of [
    ['en', 'Terms of use and data processing'], ['ky', 'Колдонуучу келишими жана маалыматтарды иштетүү'],
    ['tr', 'Kullanım koşulları ve veri işleme'], ['zh', '用户协议与数据处理'],
  ]) {
    await page.locator('select').selectOption(locale!)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(title!)
    await expect(page.locator('html')).toHaveAttribute('lang', locale!)
  }
})

test('a regular browser gets a Telegram entry prompt', async ({ page }) => {
  await page.goto('/app/')
  await expect(page.getByRole('status')).toContainText('Open this Mini App')
})


test('custom artwork loads and Telegram theme changes preserve the layout', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data')).json()
  await mockTelegram(page, { ...fixture, colorScheme: 'light' })
  await page.goto('/app/')
  await expect(page.getByRole('heading', { name: 'Ачивки' })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  expect(await page.locator('.achievement-badge').first().evaluate(async element => {
    const url = getComputedStyle(element).backgroundImage.slice(4, -1).replace(/^["']|["']$/g, '')
    const image = new Image()
    image.src = url
    await image.decode()
    return image.naturalWidth > 0
  })).toBe(true)
  await page.screenshot({ path: `test-results/collection-light-${test.info().project.name}.png`, fullPage: true, animations: 'disabled' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.evaluate(() => window.telegramTest.changeTheme('dark'))
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.getByRole('button', { name: /Продавец говна/ }).click()
  await expect(page.getByRole('dialog')).toContainText('Получено')
  await page.getByRole('button', { name: 'Закрыть', exact: true }).last().click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
})
