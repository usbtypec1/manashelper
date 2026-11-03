import { expect, test } from '@playwright/test'

const base = '/admin/api/v1'
test.beforeEach(async ({ page, request }) => {
  await request.post('/__test__/reset')
  const { ticket } = await (await request.get('/__test__/ticket')).json()
  await page.goto('/admin/#ticket=' + ticket)
  await expect(page.locator('.app-header')).toBeVisible()
  await page.getByRole('button', { name: 'Texts', exact: true }).click()
  await page.getByRole('searchbox', { name: 'Search keys or text' }).fill('menu.food')
  await page.getByRole('button', { name: 'menu.food', exact: true }).click()
})

test('edit a translation, publish with confirmation, and roll back the current release', async ({
  page,
}, testInfo) => {
  const catalog = page.getByTestId('text-catalog')
  const input = catalog.getByRole('textbox', { name: 'menu.food', exact: true })
  await input.fill('Browser cafeteria text')
  await catalog.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(catalog.getByRole('button', { name: 'Save', exact: true })).toBeDisabled()
  await catalog.getByRole('button', { name: 'Publish', exact: true }).click()
  await expect(page.getByRole('dialog')).toContainText('Publish this text catalog?')
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(catalog).toContainText('Current release v2')
  const texts = await page.evaluate(async () => (await fetch('/admin/api/v1/catalog')).json())
  expect(texts.texts.find((entry: { key: string }) => entry.key === 'menu.food').translations.en).toBe(
    'Browser cafeteria text',
  )
  await catalog.getByText('Catalog releases', { exact: true }).click()
  await catalog.getByRole('button', { name: 'Activate', exact: true }).last().click()
  await expect(page.getByRole('dialog')).toContainText('Activate this catalog release?')
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(catalog).toContainText('Current release v1')
  await page.screenshot({ path: testInfo.outputPath('text-catalog.png'), fullPage: true })
})

test('conflict preserves local edits; switching modes retains the unsaved translation', async ({ page }) => {
  const catalog = page.getByTestId('text-catalog')
  const input = catalog.getByRole('textbox', { name: 'menu.food', exact: true })
  await input.fill('Unsaved operator translation')
  await page.getByRole('button', { name: 'Users', exact: true }).click()
  await page.getByRole('button', { name: 'Texts', exact: true }).click()
  await expect(input).toHaveValue('Unsaved operator translation')
  await page.evaluate(async (base) => {
    const session = await (await fetch(base + '/auth/session')).json()
    const draft = await (await fetch(base + '/texts')).json()
    const entry = draft.document.entries.find((item: { key: string }) => item.key === 'menu.food')
    entry.variants.find(
      (variant: { locale: string; theme: string }) => variant.locale === 'en' && variant.theme === 'basic',
    ).text = 'Another administrator edit'
    const response = await fetch(base + '/texts/menu.food', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token },
      body: JSON.stringify({ entry, expected_revision: draft.revision }),
    })
    if (!response.ok) throw new Error('fixture edit failed')
  }, base)
  await catalog.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(catalog.getByRole('alert')).toBeVisible()
  await expect(input).toHaveValue('Unsaved operator translation')
  await catalog.getByRole('button', { name: 'Reload from server', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(input).toHaveValue('Another administrator edit')
})

test('an unchanged scenario can save a new revision and publish the updated catalog pin', async ({
  page,
}) => {
  await page.getByRole('button', { name: 'Editor', exact: true }).click()
  await page.getByRole('button', { name: 'New scenario', exact: true }).first().click()
  await page.getByRole('textbox', { name: 'Scenario ID', exact: true }).fill('browser_text_pin')
  await page.getByRole('button', { name: 'Create', exact: true }).click()
  await expect(page.locator('.flow-heading h1')).toHaveText('browser_text_pin')
  await page.locator('.toolbar-actions').getByRole('button', { name: 'Publish', exact: false }).click()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(page.locator('.published-label')).toContainText('v1')
  const original = await (await page.request.get(base + '/flows/browser_text_pin/versions/1')).json()
  expect(original.text_catalog_release).toBe(1)
  await page.getByRole('button', { name: 'Texts', exact: true }).click()
  const catalog = page.getByTestId('text-catalog')
  await catalog.getByRole('textbox', { name: 'menu.food', exact: true }).fill('New scenario catalog')
  await catalog.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(catalog.getByRole('button', { name: 'Save', exact: true })).toBeDisabled()
  await catalog.getByRole('button', { name: 'Publish', exact: true }).click()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(catalog).toContainText('Current release v2')
  await page.getByRole('button', { name: 'Editor', exact: true }).click()
  await page.locator('.toolbar-actions').getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.locator('.flow-heading .pill')).toContainText('r1')
  await page.locator('.toolbar-actions').getByRole('button', { name: 'Publish', exact: false }).click()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(page.locator('.published-label')).toContainText('v2')
  const updated = await (await page.request.get(base + '/flows/browser_text_pin/versions/2')).json()
  expect(updated.text_catalog_release).toBe(2)
  expect(updated.document).toEqual(original.document)
})
