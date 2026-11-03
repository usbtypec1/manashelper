import { expect, test } from '@playwright/test'

const base = '/admin/api/v1'
test.beforeEach(async ({ page, request }) => {
  await request.post('/__test__/reset')
  await request.post('/__test__/triggers/start')
  const { ticket } = await (await request.get('/__test__/ticket')).json()
  await page.goto('/admin/#ticket=' + ticket)
  await expect(page.locator('.app-header')).toBeVisible()
  await page.getByRole('button', { name: 'Triggers', exact: true }).click()
  await expect(page.getByTestId('trigger-editor')).toContainText('Current release v1')
})

test('configure an entry, publish its pinned manifest, and roll back without reactivation on retry', async ({
  page,
}, testInfo) => {
  const editor = page.getByTestId('trigger-editor')
  await editor.getByRole('button', { name: 'Add entry', exact: true }).click()
  await editor.getByRole('textbox', { name: 'Entry ID', exact: true }).fill('campus')
  await editor.getByRole('textbox', { name: 'Command, payload or catalog key', exact: true }).fill('campus')
  await editor.getByRole('combobox', { name: 'Target scenario', exact: true }).selectOption('main_menu')
  await editor.getByRole('textbox', { name: 'Start node', exact: true }).fill('study')
  await editor.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(editor.getByText('Saved', { exact: true })).toBeVisible()
  await editor.getByRole('button', { name: 'Publish', exact: true }).click()
  await expect(page.getByRole('dialog')).toContainText('Publish this trigger manifest for new entries?')
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(editor).toContainText('Current release v2')
  const releases = await (await page.request.get(base + '/triggers/releases')).json()
  const binding = releases.items[0].manifest.document.bindings.find(
    (item: { id: string }) => item.id === 'campus',
  )
  expect(binding.target).toMatchObject({ flow_id: 'main_menu', entry: 'study' })
  expect(
    releases.items[0].manifest.scenarios.find((item: { flow_id: string }) => item.flow_id === 'main_menu')
      .version,
  ).toBe(1)
  await editor.getByText('Trigger releases', { exact: true }).click()
  await editor.getByRole('button', { name: 'Activate', exact: true }).last().click()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(editor).toContainText('Current release v1')
  await editor.getByRole('button', { name: 'Publish', exact: true }).click()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(editor).toContainText('Current release v1')
  await expect(editor.getByRole('button', { name: 'Publish', exact: true })).toBeEnabled()
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(editor.getByRole('textbox', { name: 'Entry ID', exact: true })).toHaveValue('campus')
  await page.screenshot({ path: testInfo.outputPath('triggers-mobile.png'), fullPage: true })
  const overflow = await page.evaluate(() =>
    [...document.querySelectorAll('body *')]
      .filter((element) => element.getBoundingClientRect().right > innerWidth + 1)
      .map((element) => ({
        tag: element.tagName,
        class: element.className,
        width: element.getBoundingClientRect().width,
      }))
      .slice(0, 15),
  )
  expect(overflow).toEqual([])
})

test('a conflict preserves the entry across modes and invalid hidden fields do not block graph saving', async ({
  page,
}) => {
  const editor = page.getByTestId('trigger-editor')
  await editor.getByRole('button', { name: 'Add entry', exact: true }).click()
  const id = editor.getByRole('textbox', { name: 'Entry ID', exact: true })
  await id.fill('invalid entry')
  await page.getByRole('button', { name: 'Editor', exact: true }).click()
  await page.locator('.toolbar-actions').getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.locator('.flow-heading .pill')).toContainText('r1')
  await page.getByRole('button', { name: 'Triggers', exact: true }).click()
  await expect(id).toHaveValue('invalid entry')
  await id.fill('dirty_entry')
  await page.getByRole('button', { name: 'Users', exact: true }).click()
  await page.getByRole('button', { name: 'Triggers', exact: true }).click()
  await expect(id).toHaveValue('dirty_entry')
  await page.evaluate(async (base) => {
    const session = await (await fetch(base + '/auth/session')).json()
    const draft = await (await fetch(base + '/triggers')).json()
    const result = await fetch(base + '/triggers', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token },
      body: JSON.stringify({ document: draft.document, expected_revision: draft.revision }),
    })
    if (!result.ok) throw new Error('fixture write failed')
  }, base)
  await editor.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(editor.getByRole('alert')).toBeVisible()
  await expect(id).toHaveValue('dirty_entry')
  await editor.getByRole('button', { name: 'Reload from server', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(id).not.toHaveValue('dirty_entry')
})

test('a call entry survives reload and publishes a pinned manifest without changing other policies', async ({
  page,
}) => {
  const editor = page.getByTestId('trigger-editor')
  const original = await (await page.request.get(base + '/triggers')).json()
  await editor.getByRole('button', { name: 'Add entry', exact: true }).click()
  await editor.getByRole('textbox', { name: 'Entry ID', exact: true }).fill('language_dialog')
  await editor
    .getByRole('textbox', { name: 'Command, payload or catalog key', exact: true })
    .fill('language_dialog')
  await editor.getByRole('combobox', { name: 'Target scenario', exact: true }).selectOption('select_locale')
  const policy = editor.getByRole('combobox', { name: 'When another dialog is open', exact: true })
  await expect(policy).toHaveValue('reject_if_busy')
  await policy.selectOption('call')
  await editor.getByRole('button', { name: 'Add entry', exact: true }).click()
  await editor.getByRole('textbox', { name: 'Entry ID', exact: true }).fill('standard_entry')
  await editor
    .getByRole('textbox', { name: 'Command, payload or catalog key', exact: true })
    .fill('standard_entry')
  await editor.getByRole('combobox', { name: 'Target scenario', exact: true }).selectOption('main_menu')
  await expect(policy).toHaveValue('reject_if_busy')
  await editor.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(editor.getByText('Saved', { exact: true })).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: 'Triggers', exact: true }).click()
  await editor.getByRole('button', { name: 'language_dialog', exact: true }).click()
  await expect(policy).toHaveValue('call')
  await expect(editor.getByRole('combobox', { name: 'Target scenario', exact: true })).toHaveValue(
    'select_locale',
  )
  await editor.getByRole('button', { name: 'standard_entry', exact: true }).click()
  await expect(policy).toHaveValue('reject_if_busy')
  await editor.getByRole('button', { name: 'Publish', exact: true }).click()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(editor).toContainText('Current release v2')
  const published = (await (await page.request.get(base + '/triggers/releases')).json()).items[0]
  const bindings = published.manifest.document.bindings
  expect(bindings.find((item: { id: string }) => item.id === 'language_dialog')).toMatchObject({
    policy: 'call',
    target: { kind: 'scenario', flow_id: 'select_locale', entry: null },
  })
  expect(bindings.find((item: { id: string }) => item.id === 'standard_entry').policy).toBe('reject_if_busy')
  for (const binding of original.document.bindings)
    expect(bindings.find((item: { id: string }) => item.id === binding.id)).toEqual(binding)
  const pin = published.manifest.scenarios.find(
    (item: { flow_id: string }) => item.flow_id === 'select_locale',
  )
  expect(pin).toMatchObject({ version: 1, text_catalog_release: 1 })

  const session = await (await page.request.get(base + '/auth/session')).json()
  const draft = await (await page.request.get(base + '/flows/select_locale/draft')).json()
  const headers = { Origin: new URL(page.url()).origin, 'X-CSRF-Token': session.csrf_token }
  const saved = await page.request.put(base + '/flows/select_locale/draft', {
    headers,
    data: { document: draft.document, expected_revision: draft.revision },
  })
  expect(saved.status(), await saved.text()).toBe(200)
  const savedDraft = await saved.json()
  const revision = await page.request.post(base + '/flows/select_locale/publish', {
    headers,
    data: { expected_revision: savedDraft.revision },
  })
  expect(revision.status(), await revision.text()).toBe(200)
  expect((await revision.json()).version).toBe(2)
  const unchanged = (await (await page.request.get(base + '/triggers/releases')).json()).items[0]
  expect(unchanged.id).toBe(published.id)
  expect(
    unchanged.manifest.scenarios.find((item: { flow_id: string }) => item.flow_id === 'select_locale'),
  ).toEqual(pin)
})
