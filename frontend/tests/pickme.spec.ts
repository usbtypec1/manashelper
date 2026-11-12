import { expect, test } from '@playwright/test'
import { mockTelegram } from './telegram'

for (const theme of [
  {
    key: 'pickme', title: '🎀 Твой уютный уголок', saved: '💗 Сохранила для тебя',
    achievements: '💗 Твои маленькие победы', leaderboard: '🎀 Звёздочки кампуса',
    decoration: '🎀', lightAccent: '#a92b60', darkAccent: '#ffaccb',
  },
  {
    key: 'deadinside', title: '🌑 Твой уголок мрака', saved: '🖤 Сохранено. Без лишних слов.',
    achievements: '🥀 Маленькие победы во мраке', leaderboard: '🥀 Те, кто смог',
    decoration: '🥀', lightAccent: '#843d55', darkAccent: '#d99aaa',
  },
]) {
  for (const view of ['settings', 'courses', 'achievements']) {
    test(`saved ${theme.key} theme reaches ${view} in both Telegram appearances`, async ({ page, request }) => {
      const fixture = await (await request.get(`/_fixture/init-data?theme=${theme.key}&locale=ru${view === 'achievements' ? '' : '&preferences=1'}`)).json()
      await mockTelegram(page, { ...fixture, colorScheme: 'light' })
      await page.goto(`/app/?view=${view}`)
      await expect(page.locator('html')).toHaveAttribute('data-bot-theme', theme.key)
      await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
      await expect(page.locator('html')).toHaveCSS('--accent', theme.lightAccent)
      if (view === 'settings') {
        await expect(page.getByRole('heading', { name: theme.title, exact: true })).toBeVisible()
        const grades = page.getByRole('checkbox', { name: /Оценки за экзамены/ })
        await grades.click()
        await expect(page.getByRole('status')).toHaveText(theme.saved)
        await expect(grades).not.toBeChecked()
        await page.reload()
        await expect(grades).not.toBeChecked()
      } else if (view === 'courses') {
        await page.getByRole('combobox', { name: /Выберите факультет/ }).selectOption({ label: 'Факультет <проверка>' })
        await page.getByRole('combobox', { name: /Выберите отделение/ }).selectOption({ label: 'Информатика' })
        await page.getByRole('checkbox', { name: 'Курс 1', exact: true }).click()
        await expect(page.getByRole('status')).toHaveText(theme.saved)
        await expect(page.getByText('Факультет <проверка> · Информатика · Курс 1', { exact: true })).toBeVisible()
      } else {
        await expect(page.getByRole('heading', { name: theme.achievements })).toBeVisible()
        await page.getByRole('button', { name: /Обжора/ }).click()
        await expect(page.getByRole('dialog')).toContainText('Посмотри йемек 50 раз')
        await expect(page.getByRole('dialog')).toContainText(`Пока не получена ${theme.decoration}`)
        await page.screenshot({ animations: 'disabled', path: `test-results/${theme.key}-detail-light-${test.info().project.name}.png` })
        await page.keyboard.press('Escape')
        await expect(page.getByRole('dialog')).not.toBeVisible()
        await page.getByRole('button', { name: theme.leaderboard, exact: true }).click()
        await expect(page.getByRole('heading', { name: theme.leaderboard })).toBeVisible()
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
      await page.screenshot({ animations: 'disabled', path: `test-results/${theme.key}-${view}-light-${test.info().project.name}.png`, fullPage: true })
      await page.evaluate(() => window.telegramTest.changeTheme('dark'))
      await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
      await expect(page.locator('html')).toHaveAttribute('data-bot-theme', theme.key)
      await expect(page.locator('html')).toHaveCSS('--accent', theme.darkAccent)
      await page.screenshot({ animations: 'disabled', path: `test-results/${theme.key}-${view}-dark-${test.info().project.name}.png`, fullPage: true })
      if (view === 'achievements') {
        await page.getByRole('button', { name: /Мои|Маленькие/ }).first().click()
        await page.getByRole('button', { name: /Обжора/ }).click()
        await expect(page.getByRole('dialog')).toContainText('Посмотри йемек 50 раз')
        await page.screenshot({ animations: 'disabled', path: `test-results/${theme.key}-detail-dark-${test.info().project.name}.png` })
      }
    })
  }
}
