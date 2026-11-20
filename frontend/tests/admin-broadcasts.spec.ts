import { expect, test, type Page } from '@playwright/test'
import { mockTelegram } from './telegram'

async function nativeAction(page: Page, text: string) {
  await expect.poll(() => page.evaluate(() => {
    const event = window.telegramTest.events.filter(event => event.name === 'web_app_setup_main_button').at(-1)
    return event?.data
  })).toMatchObject({ text, is_visible: true, is_active: true })
  await page.evaluate(() => window.telegramTest.emit('main_button_pressed'))
}

async function confirm(page: Page, button: string) {
  await expect.poll(() => page.evaluate(() => {
    const event = window.telegramTest.events.filter(event => event.name === 'web_app_open_popup').at(-1)
    return event?.data
  })).toMatchObject({ buttons: expect.arrayContaining([expect.objectContaining({ id: 'confirm', text: button })]) })
  await page.evaluate(() => window.telegramTest.emit('popup_closed', { button_id: 'confirm' }))
}

test('directory uses server filters across the full catalog', async ({ page, request }) => {
  const fixture = await (await request.get('/_fixture/init-data')).json()
  await mockTelegram(page, fixture)
  await page.goto('/app/admin')

  await page.getByRole('searchbox', { name: 'Search users' }).fill('@member_50')
  const users = page.getByRole('table', { name: 'Users' })
  await expect(users.getByRole('row')).toHaveCount(2)
  await expect(users.getByText('@member_50', { exact: true })).toBeVisible()
  await page.getByRole('combobox', { name: 'Language' }).selectOption('en')
  await expect(page.getByText('No matching users.', { exact: true })).toBeVisible()
  await page.getByRole('combobox', { name: 'Language' }).selectOption('ru')
  await page.getByRole('combobox', { name: 'Status' }).selectOption('active')
  await expect(users.getByText('@member_50', { exact: true })).toBeVisible()
  await page.getByRole('combobox', { name: 'Theme' }).selectOption('gta_vi')
  await expect(page.getByText('No matching users.', { exact: true })).toBeVisible()
})

test('admin searches for recipients, queues a localized broadcast, and retries failed deliveries', async ({ page, request }, testInfo) => {
  const fixture = await (await request.get('/_fixture/init-data')).json()
  await mockTelegram(page, fixture)
  await page.goto('/app/admin')
  await page.getByRole('link', { name: 'Broadcasts', exact: true }).click()
  await nativeAction(page, 'New broadcast')
  await page.getByRole('combobox', { name: 'Audience' }).selectOption('allowlist')

  const search = page.getByRole('searchbox', { name: 'Find and select users' })
  await search.fill('@member_1')
  await page.getByRole('checkbox', { name: 'Directory user 1 @member_1', exact: true }).check()
  await search.fill('@member_50')
  await page.getByRole('checkbox', { name: 'Directory user 50 @member_50', exact: true }).check()
  await expect(page.getByText('Selected users: 2')).toBeVisible()

  const text = 'Directory broadcast — ' + testInfo.project.name
  await page.getByRole('textbox', { name: 'Message text' }).fill(text)
  await page.getByRole('button', { name: 'Add variant' }).click()
  await page.getByRole('combobox', { name: 'Language' }).nth(1).selectOption('en')
  await page.getByRole('combobox', { name: 'Theme' }).nth(1).selectOption('gta_vi')
  await page.getByRole('textbox', { name: 'Message text' }).nth(1).fill('Alternate')
  await nativeAction(page, 'Queue broadcast')
  await confirm(page, 'Queue broadcast')

  await expect(page).toHaveURL(/\/app\/admin\/broadcasts\/[0-9a-f-]{36}$/)
  const deliveries = page.getByRole('table', { name: 'Deliveries' })
  await expect(deliveries.getByRole('row')).toHaveCount(3)
  await expect(deliveries.getByText('Queued', { exact: true })).toHaveCount(2)
  const campaign = new URL(page.url()).pathname.split('/').at(-1)
  expect((await request.post('/_fixture/broadcasts/' + campaign + '/fail')).ok()).toBe(true)
  await nativeAction(page, 'Refresh')
  await expect(deliveries.getByText('TelegramBadRequest')).toHaveCount(2)
  await nativeAction(page, 'Retry deliveries')
  await confirm(page, 'Retry deliveries')
  await expect(page.getByText('Queued again: 2')).toBeVisible()
  await expect(deliveries.getByText('Queued', { exact: true })).toHaveCount(2)

  await page.getByRole('link', { name: 'Broadcasts', exact: true }).click()
  await expect(page.getByText(text, { exact: true })).toBeVisible()
})
