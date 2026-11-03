import { expect, test } from '@playwright/test'
import type { Document } from '../../src/types'

const base = '/admin/api/v1'
test('typed collections render saved item actions and escaped values in the browser preview', async ({
  page,
  request,
}, testInfo) => {
  await request.post('/__test__/reset')
  const { ticket } = await (await request.get('/__test__/ticket')).json()
  await page.goto('/admin/#ticket=' + ticket)
  await expect(page.locator('.app-header')).toBeVisible()
  const document: Document = {
    schema_version: 2,
    id: 'dynamic_browser',
    entry: 'choose',
    fields: {
      choices: {
        type: 'list',
        max_items: 3,
        items: { type: 'object', properties: { id: { type: 'integer' }, label: { type: 'text' } } },
      },
      selected: { type: 'integer' },
      selected_label: { type: 'text' },
    },
    initial_data: {
      choices: [
        { id: 42, label: '<script>safe & exact</script>' },
        { id: 7, label: 'Second choice' },
      ],
    },
    nodes: [
      {
        kind: 'menu',
        id: 'choose',
        keyboard: 'inline',
        text: [{ kind: 'inline', translations: { en: 'Choose a record' } }],
        buttons: [],
        repeated: [
          {
            source: { kind: 'ref', scope: 'data', field: 'choices' },
            buttons: [
              {
                kind: 'transition',
                id: 'choose_item',
                target: 'selected',
                label: {
                  kind: 'inline',
                  translations: { en: '{label}' },
                  parameters: { label: { kind: 'ref', scope: 'item', field: 'label' } },
                },
                assignments: {
                  selected: { kind: 'ref', scope: 'item', field: 'id' },
                  selected_label: { kind: 'ref', scope: 'item', field: 'label' },
                },
              },
            ],
          },
        ],
      },
      {
        kind: 'menu',
        id: 'selected',
        keyboard: 'inline',
        text: [
          {
            kind: 'inline',
            translations: { en: 'Selected {id}: {label}' },
            parameters: {
              id: { kind: 'ref', scope: 'data', field: 'selected' },
              label: { kind: 'ref', scope: 'data', field: 'selected_label' },
            },
          },
        ],
        buttons: [],
      },
    ],
    layout: { choose: { x: 80, y: 80 }, selected: { x: 460, y: 80 } },
  }
  const session = await (await page.request.get(base + '/auth/session')).json()
  const created = await page.request.post(base + '/flows', {
    headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': session.csrf_token },
    data: { document },
  })
  expect(created.status(), await created.text()).toBe(201)
  await page.reload()
  await page.locator('.flow-item').filter({ hasText: document.id }).click()
  await expect(page.locator('.flow-heading h1')).toHaveText(document.id)
  const initialDraft = await (await page.request.get(base + '/flows/dynamic_browser/draft')).json()
  await page.getByRole('button', { name: 'Data fields', exact: true }).click()
  const choices = page
    .locator('.fields-editor > .binding')
    .filter({ has: page.locator('code').filter({ hasText: /^choices$/ }) })
  await expect(choices).toContainText('choices')
  const literal = choices.getByRole('textbox', { name: 'JSON value', exact: true })
  await literal.fill('[invalid')
  expect(await literal.evaluate((element: HTMLTextAreaElement) => element.validity.valid)).toBe(false)
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  const unchanged = await (await page.request.get(base + '/flows/dynamic_browser/draft')).json()
  expect(unchanged.revision).toBe(0)
  expect(unchanged.document.nodes).toEqual(initialDraft.document.nodes)
  await literal.fill(JSON.stringify(document.initial_data!.choices))
  expect(await literal.evaluate((element: HTMLTextAreaElement) => element.validity.valid)).toBe(true)
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.locator('.save-state')).not.toHaveClass(/dirty/)
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByRole('button', { name: 'Restart preview', exact: false }).click()
  await expect(page.locator('.phone-preview')).toContainText('Choose a record')
  await expect(page.locator('.phone-preview button')).toHaveCount(2)
  await page
    .locator('.phone-preview')
    .getByRole('button', { name: '<script>safe & exact</script>', exact: true })
    .click()
  await expect(page.locator('.phone-preview')).toContainText('Selected 42: <script>safe & exact</script>')
  await expect(page.locator('.phone-preview .telegram-text script')).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('dynamic-preview.png'), fullPage: true })
  const locations = await (await page.request.get(base + '/users/locations')).json()
  expect(locations.items.every((item: { owner: string }) => item.owner === 'unknown')).toBe(true)
})
