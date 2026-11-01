import { defineConfig } from '@playwright/test'

const origin = `https://127.0.0.1:${process.env.UI_EDITOR_TEST_PORT ?? '8091'}`

export default defineConfig({
  testDir: './tests/e2e',
  globalTeardown: './tests/e2e/teardown.ts',
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  use: {
    baseURL: origin,
    ignoreHTTPSErrors: true,
    locale: 'ru-RU',
    viewport: { width: 1536, height: 960 },
    trace: 'retain-on-failure',
  },
  webServer: {
    command:
      (process.platform === 'win32' ? '".venv\\Scripts\\python.exe"' : '".venv/bin/python"') +
      ' -m tests.modules.ui_flows.editor_server',
    cwd: '../..',
    url: origin + '/admin/',
    ignoreHTTPSErrors: true,
    reuseExistingServer: false,
    timeout: 30000,
  },
})
