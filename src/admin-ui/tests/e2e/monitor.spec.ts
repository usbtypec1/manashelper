import { expect, test } from '@playwright/test'

test('monitor follows runtime steps on the pinned version and marks lost legacy FSM unknown', async ({
  page,
  request,
}) => {
  expect(process.versions.bun).toBeTruthy()
  await request.post('/__test__/reset')
  const { ticket } = await (await request.get('/__test__/ticket')).json()
  await page.goto('/admin/#ticket=' + ticket)
  await expect(page.locator('.app-header')).toBeVisible()
  await request.post('/__test__/monitor/start')
  const base = '/admin/api/v1'
  const draft = await (await page.request.get(base + '/flows/monitor_form/draft')).json()
  const auth = await (await page.request.get(base + '/auth/session')).json()
  const headers = { Origin: new URL(page.url()).origin, 'X-CSRF-Token': auth.csrf_token }
  draft.document.nodes[1].text = [
    { kind: 'inline', translations: { en: 'New draft version 2', ru: 'Новая версия 2' } },
  ]
  expect(
    (
      await page.request.put(base + '/flows/monitor_form/draft', {
        headers,
        data: { document: draft.document, expected_revision: 0 },
      })
    ).ok(),
  ).toBe(true)
  expect(
    (
      await page.request.post(base + '/flows/monitor_form/publish', {
        headers,
        data: { expected_revision: 1 },
      })
    ).ok(),
  ).toBe(true)
  await page.getByRole('button', { name: 'Users', exact: true }).click()
  await expect(page.locator('.user-detail .owner-chip')).toHaveText('Active scenario')
  await expect(page.locator('.monitor-graph-heading')).toContainText('monitor_form · v1')
  await expect(page.locator('.monitor-graph .vue-flow__node[data-id="menu"] .flow-card')).toHaveClass(
    /current/,
  )
  await expect(page.locator('.monitor-graph')).not.toContainText('Новая версия 2')
  await expect(page.getByRole('button', { name: 'Save', exact: true })).toHaveCount(0)
  await request.post('/__test__/monitor/advance')
  await expect(page.locator('.monitor-graph .vue-flow__node[data-id="answer"] .flow-card')).toHaveClass(
    /current/,
    { timeout: 8000 },
  )
  await expect(page.locator('.history-list')).toContainText('answer')
  await page.screenshot({ path: 'test-results/monitor.png', fullPage: true })
  await request.post('/__test__/monitor/legacy')
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await expect(page.locator('.user-detail .owner-chip')).toHaveText('Legacy interface')
  await expect(page.locator('.location-step')).toContainText('ObisCredentialsForm:password')
  await request.post('/__test__/monitor/restart')
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await expect(page.locator('.user-detail .owner-chip')).toHaveText('Current position unknown')
  await expect(page.locator('.location-step .eyebrow')).toHaveText('Last observed step')
})
