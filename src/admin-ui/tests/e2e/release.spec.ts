import { expect, test } from '@playwright/test'

test('release changes require confirmation, reject stale revisions and preserve an active dialog', async ({
  page,
  request,
}) => {
  await request.post('/__test__/reset')
  const { ticket } = await (await request.get('/__test__/ticket')).json()
  await page.goto('/admin/#ticket=' + ticket)
  await expect(page.locator('.app-header')).toBeVisible()
  const base = '/admin/api/v1'
  const auth = await (await page.request.get(base + '/auth/session')).json()
  const headers = { Origin: new URL(page.url()).origin, 'X-CSRF-Token': auth.csrf_token }
  for (const name of ['main_menu', 'student_questions']) {
    const document = await Bun.file(`../../tests/fixtures/ui_flows/${name}.json`).json()
    expect((await page.request.post(base + '/flows', { headers, data: { document } })).ok()).toBe(true)
    expect(
      (
        await page.request.post(base + `/flows/${name}/publish`, { headers, data: { expected_revision: 0 } })
      ).ok(),
    ).toBe(true)
  }
  await request.post('/__test__/monitor/start')
  const control = page.locator('.release-control')
  await control.locator('summary').click()
  await expect(control).toContainText('Active dialogs: 1')
  await control.getByRole('button', { name: 'All users', exact: true }).click()
  await control.getByRole('button', { name: 'Apply', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel', exact: true }).click()
  expect((await (await page.request.get(base + '/rollout')).json()).mode).toBe('admin')
  await control.getByRole('button', { name: 'Apply', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(control.locator('summary')).toContainText('All users')
  // Another tab changes the revision. The stale UI must not overwrite it.
  expect(
    (
      await page.request.put(base + '/rollout', { headers, data: { mode: 'admin', expected_revision: 1 } })
    ).ok(),
  ).toBe(true)
  await control.getByRole('button', { name: 'Off', exact: true }).click()
  await control.getByRole('button', { name: 'Apply', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Revision changed')
  expect((await (await page.request.get(base + '/rollout')).json()).mode).toBe('admin')
  await control.getByRole('button', { name: 'Refresh', exact: true }).click()
  await expect(control.locator('summary')).toContainText('Admin only')
  await control.getByRole('button', { name: 'Off', exact: true }).click()
  await control.getByRole('button', { name: 'Apply', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(control.locator('summary')).toContainText('Off')
  await expect(control).toContainText('Active dialogs: 1')
  await page.screenshot({ path: 'test-results/release.png', fullPage: true })
  const location = await (await page.request.get(base + '/users/991470/location')).json()
  expect(location.owner).toBe('runtime')
  expect(location.flow_id).toBe('monitor_form')
})
