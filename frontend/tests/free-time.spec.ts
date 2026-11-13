import { expect, test } from '@playwright/test'
import { mockTelegram } from './telegram'

test('common free time follows the URL selection, catalog additions and reloads', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data?preferences=1&locale=en')).json()
  await mockTelegram(page, fixture)
  await page.goto('/app/free-time?courses=1,2')
  await expect(page.getByRole('heading', { name: 'Common free time', exact: true })).toBeVisible()
  await expect(page.getByText('Факультет <проверка> · Информатика · Year 1', { exact: true })).toBeVisible()
  await expect(page.getByText('Факультет <проверка> · Информатика · Year 2', { exact: true })).toBeVisible()
  const monday = page.locator('article.day').filter({ has: page.getByRole('heading', { name: 'Monday' }) })
  await expect(monday).toContainText('10:45–11:30')
  await expect(monday).not.toContainText('8:00')

  await page.getByRole('button', { name: 'Remove: Информатика, Year 2', exact: true }).click()
  await expect(page).toHaveURL('/app/free-time?courses=1')
  await expect(monday).toContainText('9:50–11:30')

  await page.getByRole('combobox', { name: 'Choose a faculty', exact: true }).selectOption({ label: 'Факультет <проверка>' })
  const department = page.getByRole('combobox', { name: 'Choose a department', exact: true })
  await expect(department.locator('option')).toHaveCount(2)
  await department.selectOption({ label: 'Информатика' })
  await expect(page.getByRole('button', { name: 'Add a course: Year 1', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: 'Add a course: Year 2', exact: true }).click()
  await expect(page).toHaveURL('/app/free-time?courses=1,2')
  await expect(monday).toContainText('10:45–11:30')

  await page.reload()
  await expect(monday).toContainText('10:45–11:30')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('common free time starts from tracked courses and explains an empty selection', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data?preferences=1&locale=en')).json()
  await mockTelegram(page, fixture)
  await page.goto('/app/free-time')
  await expect(page.getByText('Add at least one course.', { exact: true })).toBeVisible()
  await expect(page.locator('article.day')).toHaveCount(0)
})
