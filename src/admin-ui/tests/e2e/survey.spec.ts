import { expect, test } from '@playwright/test'
import type { Schemas } from '../../src/types'

test('English admin keeps all five survey languages and previews a stubbed return without a live response', async ({
  page,
  request,
}) => {
  expect(process.versions.bun).toBeTruthy()
  await request.post('/__test__/reset')
  const { ticket } = await (await request.get('/__test__/ticket')).json()
  await page.goto('/admin/#ticket=' + ticket)
  await expect(page.locator('.app-header')).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  const base = '/admin/api/v1'
  const auth = await (await page.request.get(base + '/auth/session')).json()
  const document = await Bun.file('../../tests/fixtures/ui_flows/student_questions.json').json()
  expect(
    (
      await page.request.post(base + '/flows', {
        headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': auth.csrf_token },
        data: { document },
      })
    ).ok(),
  ).toBe(true)
  await page.reload()
  await expect(page.locator('.flow-heading h1')).toHaveText('student_questions')
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  for (const id of ['student_questions.has_submitted', 'student_questions.submit']) {
    await page.getByRole('checkbox', { name: id, exact: true }).check()
  }
  const catalog: Schemas['EditorCatalog'] = await (await page.request.get(base + '/catalog')).json()
  const selector = page.locator('.preview-pane').getByRole('combobox', { name: 'Language', exact: true })
  await expect(selector.locator('option')).toHaveText(['en', 'ru', 'ky', 'tr', 'zh'])
  for (const locale of ['en', 'ru', 'ky', 'tr', 'zh'] as const) {
    await selector.selectOption(locale)
    await page.getByRole('button', { name: 'Restart preview', exact: false }).click()
    const copy = (key: string) => catalog.texts.find((item) => item.key === key)!.translations[locale]
    await expect(page.locator('.phone-preview')).toContainText(copy('student_questions.course_prompt'))
    await page
      .locator('.phone-preview')
      .getByRole('button', { name: copy('student_questions.year_1'), exact: true })
      .click()
    await page
      .locator('.phone-preview')
      .getByRole('button', { name: copy('student_questions.no'), exact: true })
      .click()
    await expect(page.locator('.phone-preview')).toContainText(copy('student_questions.beta_prompt'))
    await page
      .locator('.phone-preview')
      .getByRole('button', { name: copy('student_questions.no'), exact: true })
      .click()
    await expect(page.locator('.phone-preview')).toContainText(copy('student_questions.thanks'))
    await expect(page.locator('.phone-preview')).toContainText('Return to flow: main_menu')
    await expect(page.locator('.app-header')).toContainText('Interface editor')
  }
  const locations = await (await page.request.get(base + '/users/locations')).json()
  expect(locations.items.every((item: { owner: string }) => item.owner === 'unknown')).toBe(true)
  await page.screenshot({ path: 'test-results/survey-preview.png', fullPage: true })
})
