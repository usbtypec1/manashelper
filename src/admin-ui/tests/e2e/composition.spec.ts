import { expect, test, type Page } from '@playwright/test'
import type { Document, Schemas, Text } from '../../src/types'

const base = '/admin/api/v1'
const text = (value: string): Text => ({ kind: 'inline', translations: { en: value }, parameters: {} })
const reference = (field: string) => ({ kind: 'ref' as const, scope: 'data' as const, field })

function child(id: string, prompt = 'Child prompt'): Document {
  return {
    schema_version: 2,
    id,
    entry: 'answer',
    fields: { answer: { type: 'text' }, greeting: { type: 'text' } },
    inputs: { greeting: { type: 'text' } },
    outputs: { answer: { type: 'text' } },
    outcomes: ['completed'],
    nodes: [
      {
        kind: 'input',
        id: 'answer',
        field: 'answer',
        input_type: 'text',
        text: [text(prompt)],
        next: 'return_answer',
        error: text('Enter a value'),
        max_length: 80,
      },
      {
        kind: 'return',
        id: 'return_answer',
        outcome: 'completed',
        values: { answer: reference('answer') },
        text: [text('Child completed')],
      },
    ],
    layout: { answer: { x: 80, y: 80 }, return_answer: { x: 430, y: 80 } },
  }
}

function parent(target: string): Document {
  return {
    schema_version: 2,
    id: 'compose_parent',
    entry: 'start',
    fields: { answer: { type: 'text' }, saved_answer: { type: 'text' } },
    nodes: [
      {
        kind: 'menu',
        id: 'start',
        text: [text('Open the child')],
        keyboard: 'inline',
        buttons: [[{ kind: 'transition', id: 'open', label: text('Open child'), target: 'ask_child' }]],
      },
      {
        kind: 'call',
        id: 'ask_child',
        flow: target,
        arguments: { greeting: { kind: 'literal', value: 'Browser greeting' } },
        results: { answer: 'saved_answer' },
        outcomes: { completed: 'result' },
      },
      {
        kind: 'menu',
        id: 'result',
        text: [
          {
            kind: 'inline',
            translations: { en: 'Returned: {answer}' },
            parameters: { answer: reference('saved_answer') },
          },
        ],
        keyboard: 'inline',
        buttons: [[{ kind: 'transition', id: 'finish', label: text('Finish parent'), target: 'end' }]],
      },
      { kind: 'end', id: 'end', status: 'completed', text: [text('Parent complete')] },
    ],
    layout: {
      start: { x: 80, y: 80 },
      ask_child: { x: 430, y: 80 },
      result: { x: 780, y: 80 },
      end: { x: 1130, y: 80 },
    },
  }
}

async function mutate(page: Page, path: string, data: unknown, method = 'POST') {
  const session = await (await page.request.get(base + '/auth/session')).json()
  return page.request.fetch(base + path, {
    method,
    headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': session.csrf_token },
    data,
  })
}

async function create(page: Page, document: Document, publish = false) {
  const response = await mutate(page, '/flows', { document })
  expect(response.status(), await response.text()).toBe(201)
  if (publish) {
    const published = await mutate(page, `/flows/${document.id}/publish`, { expected_revision: 0 })
    expect(published.status(), await published.text()).toBe(200)
  }
}

test.beforeEach(async ({ page, request }) => {
  await request.post('/__test__/reset')
  const { ticket } = await (await request.get('/__test__/ticket')).json()
  await page.goto('/admin/#ticket=' + ticket)
  await expect(page.locator('.app-header')).toBeVisible()
})

test('edit Call bindings and continuations, publish and return a child input into the parent preview', async ({
  page,
}, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await create(page, child('compose_child', 'Original child prompt'), true)
  await create(page, child('compose_alternate', 'Alternate child prompt'), true)
  const document = parent('compose_child')
  const call = document.nodes.find((node) => node.kind === 'call')!
  if (call.kind !== 'call') throw new Error('Missing Call fixture')
  call.results = { answer: 'answer' }
  call.outcomes = { completed: 'end' }
  await create(page, document)
  const beforeLocations = await (await page.request.get(base + '/users/locations')).json()
  const beforeTransitions = await (await page.request.get(base + '/users/991470/transitions')).json()
  await page.reload()
  await page.locator('.flow-item').filter({ hasText: 'compose_parent' }).click()
  await expect(page.locator('.flow-heading h1')).toHaveText('compose_parent')
  await page.locator('.vue-flow__controls-fitview').click()
  await page.locator('.vue-flow__node[data-id="ask_child"] .flow-card-head').click()
  const inspector = page.locator('.inspector-content')
  await expect(inspector.locator('.kind-badge')).toHaveText('Call scenario')
  await inspector.getByRole('textbox', { name: 'Target scenario', exact: true }).fill('compose_alternate')
  await inspector.getByRole('combobox', { name: 'answer', exact: true }).selectOption('saved_answer')
  await inspector.getByRole('combobox', { name: 'completed', exact: true }).selectOption('result')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.locator('.save-state')).not.toHaveClass(/dirty/)
  const saved = await (await page.request.get(base + '/flows/compose_parent/draft')).json()
  expect(saved.document.nodes.find((node: { id: string }) => node.id === 'ask_child')).toMatchObject({
    flow: 'compose_alternate',
    arguments: { greeting: { kind: 'literal', value: 'Browser greeting' } },
    results: { answer: 'saved_answer' },
    outcomes: { completed: 'result' },
  })
  await page.getByRole('button', { name: 'Publish', exact: false }).click()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(page.locator('.published-label')).toContainText('v1')
  const published = await (await page.request.get(base + '/flows/compose_parent/versions/1')).json()
  expect(published.dependencies).toEqual({ compose_alternate: 1 })
  await page.screenshot({ path: testInfo.outputPath('composition-call.png'), fullPage: true })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByRole('button', { name: 'Restart preview', exact: false }).click()
  await expect(page.locator('.phone-preview')).toContainText('Open the child')
  await page.locator('.phone-preview').getByRole('button', { name: 'Open child', exact: true }).click()
  await expect(page.locator('.phone-preview')).toContainText('Alternate child prompt')
  await page.getByRole('textbox', { name: 'Input', exact: true }).fill('Browser composition answer')
  await page.getByRole('button', { name: 'Send input', exact: true }).click()
  await expect(page.locator('.phone-preview')).toContainText('Returned: Browser composition answer')
  await expect(page.locator('.phone-preview .phone-title')).toContainText('result')
  await page.screenshot({ path: testInfo.outputPath('composition-return.png'), fullPage: true })
  expect(await (await page.request.get(base + '/users/locations')).json()).toEqual(beforeLocations)
  expect(await (await page.request.get(base + '/users/991470/transitions')).json()).toEqual(beforeTransitions)
  expect(errors).toEqual([])
})

test('an incompatible child blocks a new parent publication while old dependency pins and preview survive', async ({
  page,
}) => {
  const childDocument = child('compose_child', 'Pinned child version one')
  const parentDocument = parent(childDocument.id)
  await create(page, childDocument, true)
  await create(page, parentDocument, true)
  const started = await mutate(page, '/flows/compose_parent/preview', {
    document: parentDocument,
    user: { id: 1, chat_id: 1, locale: 'en', theme: 'basic' },
    eders_enabled: true,
  })
  expect(started.status(), await started.text()).toBe(200)
  const preview: Schemas['PreviewResult'] = await started.json()
  expect(preview.position?.dependencies).toEqual({ compose_child: 1 })
  childDocument.fields!.answer = { type: 'integer' }
  childDocument.outputs!.answer = { type: 'integer' }
  const input = childDocument.nodes[0]
  if (input.kind !== 'input') throw new Error('Missing Input fixture')
  input.input_type = 'integer'
  input.text = [text('Incompatible child version two')]
  const childSaved = await mutate(
    page,
    '/flows/compose_child/draft',
    { document: childDocument, expected_revision: 0 },
    'PUT',
  )
  expect(childSaved.status(), await childSaved.text()).toBe(200)
  const childPublished = await mutate(page, '/flows/compose_child/publish', { expected_revision: 1 })
  expect(childPublished.status(), await childPublished.text()).toBe(200)
  expect((await childPublished.json()).version).toBe(2)
  const parentSaved = await mutate(
    page,
    '/flows/compose_parent/draft',
    { document: parentDocument, expected_revision: 0 },
    'PUT',
  )
  expect(parentSaved.status(), await parentSaved.text()).toBe(200)
  const rejected = await mutate(page, '/flows/compose_parent/publish', { expected_revision: 1 })
  expect(rejected.status()).toBe(422)
  expect(
    (await rejected.json()).issues.some((issue: { code: string }) => issue.code === 'scenario_contract'),
  ).toBe(true)
  const draft = await (await page.request.get(base + '/flows/compose_parent/draft')).json()
  expect(draft.revision).toBe(1)
  expect(draft.document.nodes.find((node: { id: string }) => node.id === 'ask_child').flow).toBe(
    'compose_child',
  )
  const current = await (await page.request.get(base + '/flows/compose_parent')).json()
  expect(current.published_version).toBe(1)
  const original = await (await page.request.get(base + '/flows/compose_parent/versions/1')).json()
  expect(original.dependencies).toEqual({ compose_child: 1 })
  const resumed = await mutate(page, '/flows/compose_parent/preview', {
    document: parentDocument,
    user: { id: 1, chat_id: 1, locale: 'en', theme: 'basic' },
    eders_enabled: true,
    position: preview.position,
    event: {
      kind: 'button',
      update_id: 1,
      user_id: 1,
      chat_id: 1,
      session_id: 'preview',
      expected_revision: 0,
      button_id: 'open',
    },
  })
  expect(resumed.status(), await resumed.text()).toBe(200)
  const inside: Schemas['PreviewResult'] = await resumed.json()
  expect(inside.issues).toEqual([])
  expect(inside.screen?.text).toBe('Pinned child version one')
  expect(inside.position).toMatchObject({ flow_id: 'compose_child', flow_version: 1 })
})
