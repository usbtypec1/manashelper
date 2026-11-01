import { request, type FullConfig } from '@playwright/test'

export default async function cleanup(config: FullConfig) {
  const api = await request.newContext({ ignoreHTTPSErrors: true, baseURL: config.projects[0].use.baseURL })
  try {
    const response = await api.post('/__test__/cleanup')
    if (!response.ok()) throw new Error('Browser test schema cleanup failed')
  } finally {
    await api.dispose()
  }
}
