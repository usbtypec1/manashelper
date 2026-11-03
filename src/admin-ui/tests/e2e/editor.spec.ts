import { expect, test, type Page } from '@playwright/test'

const base = '/admin/api/v1'
test.beforeAll(() => expect(process.versions.bun).toBeTruthy())

async function create(page: Page, id = 'browser_form') {
  await page.getByRole('button', { name: 'New scenario', exact: true }).first().click()
  await page.getByRole('textbox', { name: 'Scenario ID', exact: true }).fill(id)
  await page.getByRole('button', { name: 'Create', exact: true }).click()
  await expect(page.locator('.flow-heading h1')).toHaveText(id)
}
async function save(page: Page) {
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.locator('.save-state')).not.toHaveClass(/dirty/)
}
async function publish(page: Page) {
  await page.getByRole('button', { name: 'Publish', exact: false }).click()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(page.locator('.published-label')).toContainText('v1')
}
test.beforeEach(async ({ page, request }) => {
  await request.post('/__test__/reset')
  const { ticket } = await (await request.get('/__test__/ticket')).json()
  await page.goto('/admin/#ticket=' + ticket)
  await expect(page.locator('.app-header')).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await expect(page.locator('.app-header select')).toHaveCount(0)
  await expect(page).toHaveURL(/\/admin\/$/)
})

test('create a form visually, wire it, save, publish and walk through server preview', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await create(page)
  const mainText = page.getByRole('textbox', { name: 'Message text', exact: true }).first()
  await mainText.fill('Добро пожаловать в форму')
  await page.locator('.palette').getByRole('button', { name: 'Input', exact: false }).click()
  await expect(page.locator('.inspector-content .kind-badge')).toHaveText('Input')
  await page.getByRole('textbox', { name: 'Message text', exact: true }).first().fill('Как вас зовут?')
  await page.locator('.vue-flow__controls-fitview').click()
  const source = page.locator('.vue-flow__node[data-id="menu"] .source[data-handleid="button:0:0"]')
  const target = page.locator('.vue-flow__node[data-id="input_1"] .target')
  const a = await source.boundingBox(),
    b = await target.boundingBox()
  expect(a).not.toBeNull()
  expect(b).not.toBeNull()
  await page.mouse.move(a!.x + a!.width / 2, a!.y + a!.height / 2)
  await page.mouse.down()
  await page.mouse.move(b!.x + b!.width / 2, b!.y + b!.height / 2, { steps: 20 })
  await page.mouse.up()
  await save(page)
  const draft = await (await page.request.get(base + '/flows/browser_form/draft')).json()
  expect(draft.document.nodes[0].buttons[0][0].target).toBe('input_1')
  await page.getByRole('button', { name: 'Validate', exact: false }).click()
  await expect(page.getByRole('status')).toContainText('Scenario is valid')
  await publish(page)
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByRole('button', { name: 'Restart preview', exact: false }).click()
  await expect(page.locator('.phone-preview')).toContainText('Добро пожаловать в форму')
  await page.locator('.phone-preview').getByRole('button', { name: 'Continue', exact: true }).click()
  await expect(page.locator('.phone-preview')).toContainText('Как вас зовут?')
  await page.getByRole('textbox', { name: 'Input', exact: true }).fill('Browser test answer')
  await page.getByRole('button', { name: 'Send input', exact: true }).click()
  await expect(page.locator('.phone-preview')).toContainText('Scenario ended')
  await expect(page.locator('.save-state')).not.toHaveClass(/dirty/)
  const locations = await (await page.request.get(base + '/users/locations')).json()
  expect(
    locations.items.every(
      (item: { owner: string; flow_id: string | null }) => item.owner === 'unknown' && item.flow_id === null,
    ),
  ).toBe(true)
  await page.screenshot({ path: 'test-results/editor.png', fullPage: true })
  expect(errors).toEqual([])
})

test('conflict keeps local text; reload requires a deliberate discard', async ({ page }) => {
  await create(page)
  const draft = await (await page.request.get(base + '/flows/browser_form/draft')).json()
  const session = await (await page.request.get(base + '/auth/session')).json()
  const response = await page.request.put(base + '/flows/browser_form/draft', {
    headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': session.csrf_token },
    data: { document: draft.document, expected_revision: 0 },
  })
  expect(response.status()).toBe(200)
  await page
    .getByRole('textbox', { name: 'Message text', exact: true })
    .first()
    .fill('Несохранённый локальный текст')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Revision changed')
  await expect(page.getByRole('textbox', { name: 'Message text', exact: true }).first()).toHaveValue(
    'Несохранённый локальный текст',
  )
  await page.getByRole('button', { name: 'Reload from server', exact: true }).click()
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Message text', exact: true }).first()).toHaveValue(
    'Несохранённый локальный текст',
  )
})

test('HTML validation selects the responsible node and rollback preserves the draft', async ({ page }) => {
  await create(page)
  await publish(page)
  await page
    .getByRole('textbox', { name: 'Message text', exact: true })
    .first()
    .fill('<script>window.injected=true</script>')
  await page.getByRole('button', { name: 'Validate', exact: false }).click()
  await expect(page.locator('.issues-panel')).toContainText('invalid_screen')
  await expect(page.locator('.vue-flow__node[data-id="menu"] .flow-card')).toHaveClass(/invalid/)
  expect(await page.evaluate(() => (window as unknown as Record<string, unknown>).injected)).toBeUndefined()
  await page.getByRole('textbox', { name: 'Message text', exact: true }).first().fill('Вторая версия')
  await save(page)
  await page.getByRole('button', { name: 'Publish', exact: false }).click()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(page.locator('.published-label')).toContainText('v2')
  await page.getByRole('button', { name: 'Versions', exact: true }).click()
  await page.getByRole('button', { name: 'Activate', exact: true }).click()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(page.locator('.published-label')).toContainText('v1')
  await expect(page.getByRole('textbox', { name: 'Message text', exact: true }).first()).toHaveValue(
    'Вторая версия',
  )
})

test('action and condition editors use explicit stubs and safe Telegram formatting', async ({ page }) => {
  await create(page)
  await page
    .getByRole('textbox', { name: 'Message text', exact: true })
    .first()
    .fill('<b>Проверка</b> &lt;img src=x onerror=window.injected=true&gt;')
  await page.locator('.palette').getByRole('button', { name: 'Condition', exact: false }).click()
  await page.locator('.palette').getByRole('button', { name: 'Action', exact: false }).click()
  await page.getByRole('combobox', { name: 'success', exact: true }).selectOption('condition_1')
  await page.locator('.vue-flow__controls-fitview').click()
  await page.locator('.vue-flow__node[data-id="menu"] .flow-card-head').click()
  await page.getByRole('combobox', { name: 'Go to node', exact: true }).selectOption('action_1')
  await save(page)
  await page.getByRole('button', { name: 'Validate', exact: false }).click()
  await expect(page.getByRole('status')).toContainText('Scenario is valid')
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByRole('checkbox', { name: 'student_questions.has_submitted', exact: true }).check()
  await page.getByRole('button', { name: 'Restart preview', exact: false }).click()
  await expect(page.locator('.telegram-text strong')).toHaveText('Проверка')
  await expect(page.locator('.telegram-text img')).toHaveCount(0)
  expect(await page.evaluate(() => (window as unknown as Record<string, unknown>).injected)).toBeUndefined()
  await page.locator('.phone-preview').getByRole('button', { name: 'Continue', exact: true }).click()
  await expect(page.locator('.phone-preview')).toContainText('Scenario ended')
})
