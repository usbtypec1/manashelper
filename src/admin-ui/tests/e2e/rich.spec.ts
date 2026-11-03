import { expect, test, type Page } from '@playwright/test'
import type { Document, Schemas, Text } from '../../src/types'

const base = '/admin/api/v1'
const text = (value: string): Text => ({ kind: 'inline', translations: { en: value } })
const mediaItem: Schemas['DataField'] = {
  type: 'object',
  properties: {
    message_id: { type: 'integer' },
    type: { type: 'text' },
    file_id: { type: 'text' },
    media_group_id: { type: 'text', nullable: true },
    caption: { type: 'text', nullable: true },
  },
}

async function create(page: Page, document: Document) {
  const session = await (await page.request.get(base + '/auth/session')).json()
  const created = await page.request.post(base + '/flows', {
    headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': session.csrf_token },
    data: { document },
  })
  expect(created.status(), await created.text()).toBe(201)
  await page.reload()
  await page.locator('.flow-item').filter({ hasText: document.id }).click()
  await expect(page.locator('.flow-heading h1')).toHaveText(document.id)
}

test.beforeEach(async ({ page, request }) => {
  await request.post('/__test__/reset')
  const { ticket } = await (await request.get('/__test__/ticket')).json()
  await page.goto('/admin/#ticket=' + ticket)
  await expect(page.locator('.app-header')).toBeVisible()
})

test('author rich sources and localized chunks, persist order and preview escaped content', async ({
  page,
}, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const caption = '<img src=x onerror=window.richInjected=true> & caption'
  const document: Document = {
    schema_version: 2,
    id: 'rich_browser',
    entry: 'main',
    fields: {
      payload: {
        type: 'object',
        properties: {
          media: { type: 'list', max_items: 10, items: mediaItem },
          chunks: { type: 'list', max_items: 2, items: { type: 'text' } },
        },
      },
    },
    initial_data: {
      payload: {
        media: [
          { message_id: 1, type: 'photo', file_id: 'synthetic-browser-photo', media_group_id: null, caption },
          {
            message_id: 2,
            type: 'video',
            file_id: 'synthetic-browser-video',
            media_group_id: null,
            caption: 'Video caption',
          },
        ],
        chunks: ['<script>safe & exact</script>', 'Second sourced chunk'],
      },
    },
    nodes: [
      {
        kind: 'menu',
        id: 'main',
        text: [text('Primary rich screen')],
        keyboard: 'inline',
        buttons: [[{ kind: 'transition', id: 'finish', label: text('Finish rich screen'), target: 'end' }]],
      },
      { kind: 'end', id: 'end', status: 'completed', text: [text('Rich screen completed')] },
    ],
    layout: { main: { x: 80, y: 80 }, end: { x: 420, y: 80 } },
  }
  await create(page, document)
  await page.locator('.vue-flow__node[data-id="main"] .flow-card-head').click()
  const rich = page.getByRole('region', { name: 'Additional content', exact: true })
  const media = rich.getByRole('group', { name: 'Media source', exact: true })
  const source = rich.getByRole('group', { name: 'Message source', exact: true })
  await media.getByRole('checkbox', { name: 'Enabled', exact: true }).check()
  const path = media.getByRole('textbox', { name: 'Reference path', exact: true })
  await path.fill('[invalid')
  expect(await path.evaluate((element: HTMLInputElement) => element.validity.valid)).toBe(false)
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  expect((await (await page.request.get(base + '/flows/rich_browser/draft')).json()).revision).toBe(0)
  await path.fill('["media"]')
  await media.getByRole('checkbox', { name: 'Enabled', exact: true }).uncheck()
  await expect(media.getByRole('textbox', { name: 'Reference path', exact: true })).toHaveCount(0)
  await media.getByRole('checkbox', { name: 'Enabled', exact: true }).check()
  await media.getByRole('textbox', { name: 'Reference path', exact: true }).fill('["media"]')
  await source.getByRole('checkbox', { name: 'Enabled', exact: true }).check()
  await source.getByRole('textbox', { name: 'Reference path', exact: true }).fill('["chunks"]')
  await rich.getByRole('button', { name: 'Add message', exact: false }).click()
  await rich
    .getByRole('textbox', { name: 'Additional messages 1', exact: true })
    .fill('<b>First authored</b>')
  await rich.getByRole('combobox', { name: 'Additional messages 1 Language', exact: true }).selectOption('ru')
  await rich.getByRole('textbox', { name: 'Additional messages 1', exact: true }).fill('Первое сообщение')
  await rich.getByRole('combobox', { name: 'Additional messages 1 Language', exact: true }).selectOption('en')
  await rich.getByRole('button', { name: 'Add message', exact: false }).click()
  await rich
    .getByRole('textbox', { name: 'Additional messages 2', exact: true })
    .fill('<i>Second authored</i>')
  await rich.getByRole('button', { name: 'Add message', exact: false }).click()
  await rich.getByRole('textbox', { name: 'Additional messages 3', exact: true }).fill('Remove this chunk')
  await rich.getByRole('button', { name: 'Remove Additional messages 3', exact: true }).click()
  await rich.getByRole('button', { name: 'Move up Additional messages 2', exact: true }).click()
  await expect(rich.getByRole('textbox', { name: 'Additional messages 1', exact: true })).toHaveValue(
    '<i>Second authored</i>',
  )
  await page.locator('.vue-flow__node[data-id="end"] .flow-card-head').click()
  await expect(rich).toHaveCount(0)
  await page.locator('.vue-flow__node[data-id="main"] .flow-card-head').click()
  await expect(rich.getByRole('textbox', { name: 'Additional messages 1', exact: true })).toHaveValue(
    '<i>Second authored</i>',
  )
  await expect(source.getByRole('textbox', { name: 'Reference path', exact: true })).toHaveValue('["chunks"]')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.locator('.save-state')).not.toHaveClass(/dirty/)
  const saved = await (await page.request.get(base + '/flows/rich_browser/draft')).json()
  const main = saved.document.nodes[0]
  expect(main.media).toEqual({ kind: 'ref', scope: 'data', field: 'payload', path: ['media'] })
  expect(main.message_source).toEqual({ kind: 'ref', scope: 'data', field: 'payload', path: ['chunks'] })
  expect(main.messages.map((item: Text) => item.kind === 'inline' && item.translations.en)).toEqual([
    '<i>Second authored</i>',
    '<b>First authored</b>',
  ])
  expect(main.messages[1].translations.ru).toBe('Первое сообщение')
  await page.reload()
  await page.locator('.flow-item').filter({ hasText: document.id }).click()
  await page.getByRole('button', { name: 'Publish', exact: false }).click()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(page.locator('.published-label')).toContainText('v1')
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByRole('button', { name: 'Restart preview', exact: false }).click()
  const bubbles = page.locator('.phone-preview .message-bubble')
  await expect(bubbles).toHaveCount(7)
  await expect(bubbles.nth(0)).toHaveText('Second authored')
  await expect(bubbles.nth(1)).toHaveText('First authored')
  await expect(bubbles.nth(1).locator('strong')).toHaveText('First authored')
  await expect(bubbles.nth(2)).toHaveText('<script>safe & exact</script>')
  await expect(bubbles.nth(3)).toHaveText('Second sourced chunk')
  await expect(bubbles.nth(4)).toContainText(caption)
  await expect(bubbles.nth(5)).toContainText('Video caption')
  await expect(bubbles.nth(6)).toHaveText('Primary rich screen')
  await expect(page.locator('.phone-preview script, .phone-preview img, .phone-preview video')).toHaveCount(0)
  expect(
    await page.evaluate(() => (window as unknown as Record<string, unknown>).richInjected),
  ).toBeUndefined()
  await page.screenshot({ path: testInfo.outputPath('rich-preview.png'), fullPage: true })
  expect(errors).toEqual([])
})

test('typed preview uses explicit sample contact, media and secret events', async ({ page }) => {
  const events: { kind: string; phone?: string; owner_id?: number; handle?: string; media_type?: string }[] =
    []
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/preview')) {
      const event = request.postDataJSON()?.event
      if (event) events.push(event)
    }
  })
  await create(page, {
    schema_version: 2,
    id: 'typed_preview_browser',
    entry: 'contact',
    fields: { phone: { type: 'text' }, upload: mediaItem, password: { type: 'secret' } },
    nodes: [
      {
        kind: 'input',
        id: 'contact',
        input_type: 'contact',
        field: 'phone',
        text: [text('Contact preview')],
        error: text('Invalid contact'),
        next: 'media',
      },
      {
        kind: 'input',
        id: 'media',
        input_type: 'media',
        field: 'upload',
        text: [text('Media preview')],
        error: text('Invalid media'),
        next: 'secret',
      },
      {
        kind: 'input',
        id: 'secret',
        input_type: 'secret',
        field: 'password',
        text: [text('Secret preview')],
        error: text('Invalid secret'),
        next: 'end',
      },
      { kind: 'end', id: 'end', status: 'completed', text: [text('Typed preview completed')] },
    ],
    layout: {
      contact: { x: 80, y: 80 },
      media: { x: 420, y: 80 },
      secret: { x: 80, y: 420 },
      end: { x: 420, y: 420 },
    },
  })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByRole('button', { name: 'Restart preview', exact: false }).click()
  await expect(page.locator('.phone-preview')).toContainText('Contact preview')
  await expect(page.locator('.preview-input input')).toHaveCount(0)
  await page.getByRole('button', { name: 'Use sample contact', exact: true }).click()
  await expect(page.locator('.phone-preview')).toContainText('Media preview')
  await page.getByRole('button', { name: 'Add sample video', exact: true }).click()
  await expect(page.locator('.phone-preview')).toContainText('Secret preview')
  await expect(page.locator('.preview-input input')).toHaveCount(0)
  await page.getByRole('button', { name: 'Use sample secret', exact: true }).click()
  await expect(page.locator('.phone-preview')).toContainText('Typed preview completed')
  expect(events.map((event) => event.kind)).toEqual(['contact', 'media', 'secret'])
  expect(events[0].phone).toBe('+996000000000')
  expect(events[0].owner_id).toBe(1)
  expect(events[1].media_type).toBe('video')
  expect(events[2].handle).toMatch(/^[a-f0-9-]{36}$/)
})
