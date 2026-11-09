import { expect, test } from '@playwright/test'

for (const view of ['settings', 'courses', 'achievements']) {
  test(`saved Pick me theme reaches ${view} in both Telegram appearances`, async ({ page, request }) => {
    await page.route('https://telegram.org/js/telegram-web-app.js', route => route.fulfill({ body: '', contentType: 'application/javascript' }))
    const fixture = await (await request.get(`/_fixture/init-data?theme=pickme&locale=ru${view === 'achievements' ? '' : '&preferences=1'}`)).json()
    await page.addInitScript(({ initData }) => {
      Object.assign(window, { Telegram: { WebApp: {
        initData, colorScheme: 'light', ready() {}, expand() {},
        onEvent(event: string, callback: () => void) {
          if (event === 'themeChanged') Object.assign(window, { changeTelegramTheme: callback })
        },
      } } })
    }, fixture)
    await page.goto(`/app/?view=${view}`)
    await expect(page.locator('html')).toHaveAttribute('data-bot-theme', 'pickme')
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
    await expect(page.locator('html')).toHaveCSS('--accent', '#a92b60')
    if (view === 'settings') {
      await expect(page.getByRole('heading', { name: '🎀 Твой уютный уголок', exact: true })).toBeVisible()
      const grades = page.getByRole('checkbox', { name: /Оценки за экзамены/ })
      await grades.click()
      await expect(page.getByRole('status')).toHaveText('💗 Сохранила для тебя')
      await expect(grades).not.toBeChecked()
      await page.reload()
      await expect(grades).not.toBeChecked()
    } else if (view === 'courses') {
      await page.getByRole('combobox', { name: /Выберите факультет/ }).selectOption({ label: 'Факультет <проверка>' })
      await page.getByRole('combobox', { name: /Выберите отделение/ }).selectOption({ label: 'Информатика' })
      await page.getByRole('checkbox', { name: 'Курс 1', exact: true }).click()
      await expect(page.getByRole('status')).toHaveText('💗 Сохранила для тебя')
      await expect(page.getByText('Факультет <проверка> · Информатика · Курс 1', { exact: true })).toBeVisible()
    } else {
      await expect(page.getByRole('heading', { name: '💗 Твои маленькие победы' })).toBeVisible()
      await page.getByRole('button', { name: /Обжора/ }).click()
      await expect(page.getByRole('dialog')).toContainText('Посмотри йемек 50 раз')
      await expect(page.getByRole('dialog')).toContainText('Пока не получена 🎀')
      await page.screenshot({ path: `test-results/pickme-detail-${test.info().project.name}.png` })
      await page.keyboard.press('Escape')
      await expect(page.getByRole('dialog')).not.toBeVisible()
      await page.getByRole('button', { name: '🎀 Звёздочки кампуса', exact: true }).click()
      await expect(page.getByRole('heading', { name: '🎀 Звёздочки кампуса' })).toBeVisible()
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await page.screenshot({ path: `test-results/pickme-${view}-light-${test.info().project.name}.png`, fullPage: true })
    await page.evaluate(() => {
      const context = window as Window & { Telegram: { WebApp: { colorScheme: string } }; changeTelegramTheme: () => void }
      context.Telegram.WebApp.colorScheme = 'dark'
      context.changeTelegramTheme()
    })
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
    await expect(page.locator('html')).toHaveAttribute('data-bot-theme', 'pickme')
    await expect(page.locator('html')).toHaveCSS('--accent', '#ffaccb')
    await page.screenshot({ path: `test-results/pickme-${view}-dark-${test.info().project.name}.png`, fullPage: true })
  })
}
