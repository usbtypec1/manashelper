import { expect, test } from '@playwright/test'
import { mockTelegram } from '../../fixtures/telegram'

test('admin can rename an achievement and retry a grant without a duplicate', async ({ page, request }, testInfo) => {
  const fixture = await (await request.get('/_fixture/init-data')).json()
  await mockTelegram(page, fixture)
  await page.goto('/app/admin')
  await page.getByRole('link', { name: 'Achievements', exact: true }).click()
  const picker = page.getByRole('combobox', { name: 'Achievement', exact: true })
  const key = testInfo.project.name === 'mobile' ? 'iron_attendance' : 'einstein'
  const name = 'Custom achievement ' + testInfo.project.name
  await picker.selectOption(key)
  await page.getByRole('textbox', { name: 'Custom name' }).fill(name)
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByRole('status')).toHaveText('Changes saved.')
  await page.reload()
  await picker.selectOption(key)
  await expect(page.getByRole('textbox', { name: 'Custom name' })).toHaveValue(name)
  await expect(page.getByRole('checkbox', { name: 'Hide from the collection and leaderboard' })).not.toBeChecked()
  await page.getByRole('textbox', { name: 'Custom name' }).clear()
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByRole('status')).toHaveText('Changes saved.')

  await picker.selectOption('foodie')
  const user = JSON.parse(new URLSearchParams(fixture.initData).get('user') ?? '{}')
  await page.getByRole('textbox', { name: 'Telegram ID' }).fill(String(user.id))
  await page.getByRole('button', { name: 'Grant', exact: true }).click()
  await expect.poll(() => page.evaluate(() => (
    window.telegramTest.events.filter(event => event.name === 'web_app_open_popup').at(-1)?.data
  ))).toMatchObject({ buttons: expect.arrayContaining([expect.objectContaining({ id: 'confirm', text: 'Grant' })]) })
  await page.evaluate(() => window.telegramTest.emit('popup_closed', { button_id: 'confirm' }))
  await expect(page.getByRole('status')).toHaveText('The user already has this achievement.')
  await page.setViewportSize({ width: 280, height: 740 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('a signed non-admin cannot open the achievement editor', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data?preferences=1')).json()
  await mockTelegram(page, fixture)
  await page.goto('/app/admin/achievements')
  await expect(page.getByRole('alert')).toContainText('access to the admin panel')
  await expect(page.getByRole('combobox')).toHaveCount(0)
})
