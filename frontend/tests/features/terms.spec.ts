import { expect, test } from '@playwright/test'

test('terms are public, localized and list current academic access', async ({ page }) => {
  await page.route('**/api/**', route => { throw new Error(`Terms must not access private APIs: ${route.request().url()}`) })
  await page.goto('/app/?view=terms&lang=ru')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Пользовательское соглашение и обработка данных')
  await expect(page.getByRole('heading', { level: 2 })).toHaveCount(8)
  await expect(page.getByText('https://obistest.manas.edu.kg/vs-ders/transkript-detailed', { exact: true })).toBeVisible()
  await expect(page.locator('.terms-page')).toContainText('core_completion_update_activity_completion_status_manually')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: `test-results/terms-${test.info().project.name}.png`, fullPage: true, animations: 'disabled' })
  for (const [locale, title] of [
    ['en', 'Terms of use and data processing'], ['ky', 'Колдонуучу келишими жана маалыматтарды иштетүү'],
    ['tr', 'Kullanım koşulları ve veri işleme'], ['zh', '用户协议与数据处理'],
  ]) {
    await page.locator('select').selectOption(locale!)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(title!)
    await expect(page.locator('html')).toHaveAttribute('lang', locale!)
  }
})
