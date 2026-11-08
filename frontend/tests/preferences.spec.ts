import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('https://telegram.org/js/telegram-web-app.js', route => route.fulfill({ body: '', contentType: 'application/javascript' }))
})

test('settings persist for a user without achievement access', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data?preferences=1&locale=en')).json()
  const headers = { Authorization: `tma ${fixture.initData}` }
  expect((await request.get('/api/gamification/me', { headers })).status()).toBe(403)
  await page.addInitScript(({ initData }) => {
    Object.assign(window, { Telegram: { WebApp: { initData, ready() {}, expand() {} } } })
  }, fixture)
  await page.goto('/app/?view=settings')
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible()
  const grades = page.getByRole('checkbox', { name: 'Exam grades', exact: true })
  await expect(grades).toBeChecked()
  await grades.click()
  await expect(page.getByRole('status')).toHaveText('Saved')
  await expect(grades).not.toBeChecked()
  await page.reload()
  await expect(grades).not.toBeChecked()
  const settings = await (await request.get('/api/settings', { headers })).json()
  expect(settings.notifications.exam_grades_enabled).toBe(false)
  expect(settings.notifications.lesson_skips_enabled).toBe(true)
})

test('course selection and removal survive reload with escaped catalog names', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data?preferences=1&locale=en')).json()
  await page.addInitScript(({ initData }) => {
    Object.assign(window, { Telegram: { WebApp: { initData, ready() {}, expand() {} } } })
  }, fixture)
  await page.goto('/app/?view=courses')
  await expect(page.getByText('No courses selected. Choose a faculty and department below.')).toBeVisible()
  await page.getByRole('combobox', { name: 'Choose a faculty', exact: true }).selectOption({ label: 'Факультет <проверка>' })
  const department = page.getByRole('combobox', { name: 'Choose a department', exact: true })
  await expect(department.locator('option')).toHaveCount(2)
  await expect(department).toBeEnabled()
  await department.selectOption({ label: 'Информатика' })
  const year = page.getByRole('checkbox', { name: 'Year 1', exact: true })
  await expect(year).toBeEnabled()
  await year.click()
  await expect(page.getByRole('status')).toHaveText('Saved')
  await expect(year).toBeChecked()
  await expect(page.getByText('Факультет <проверка> · Информатика · Year 1', { exact: true })).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: 'Remove: Информатика, Year 1', exact: true }).click()
  await expect(page.getByText('No courses selected. Choose a faculty and department below.')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('a rejected write keeps the last saved checkbox value', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data?preferences=1&locale=en')).json()
  await page.addInitScript(({ initData }) => {
    Object.assign(window, { Telegram: { WebApp: { initData, ready() {}, expand() {} } } })
  }, fixture)
  await page.goto('/app/?view=settings')
  const grades = page.getByRole('checkbox', { name: 'Exam grades', exact: true })
  await expect(grades).toBeChecked()
  await page.route('**/api/settings/notifications', route => route.fulfill({ status: 500, body: '{}' }))
  await grades.click()
  await expect(page.getByRole('alert')).toContainText('Could not complete the action')
  await expect(grades).toBeChecked()
})

test('settings require a Telegram session in a regular browser', async ({ page }) => {
  await page.goto('/app/?view=settings')
  await expect(page.getByRole('status')).toContainText('Open this Mini App')
  await expect(page.getByRole('checkbox')).toHaveCount(0)
})
