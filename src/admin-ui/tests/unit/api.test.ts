import { afterEach, expect, mock, test } from 'bun:test'
import { AdminApi, ApiError } from '../../src/api'
const original = globalThis.fetch
afterEach(() => {
  globalThis.fetch = original
})

test('mutations include cookie credentials and CSRF and do not retry conflicts', async () => {
  const fetch = mock(
    async () =>
      new Response(JSON.stringify({ issues: [{ code: 'conflict', path: '/document', message: '' }] }), {
        status: 409,
      }),
  )
  globalThis.fetch = fetch as unknown as typeof globalThis.fetch
  const api = new AdminApi()
  api.csrf = 'synthetic-token'
  await expect(api.request('/flows/demo/draft', 'PUT', { expected_revision: 0 })).rejects.toBeInstanceOf(
    ApiError,
  )
  expect(fetch).toHaveBeenCalledTimes(1)
  const request = (fetch.mock.calls[0] as unknown as [string, RequestInit])[1]
  expect(request.credentials).toBe('same-origin')
  expect((request.headers as Record<string, string>)['X-CSRF-Token']).toBe('synthetic-token')
})
test('all pages are loaded with opaque cursors', async () => {
  const urls: string[] = []
  globalThis.fetch = mock(async (url: string) => {
    urls.push(url)
    return new Response(
      JSON.stringify(
        urls.length === 1 ? { items: [1], next_cursor: 'opaque/value' } : { items: [2], next_cursor: null },
      ),
    )
  }) as unknown as typeof fetch
  expect(await new AdminApi().all('/flows')).toEqual([1, 2])
  expect(urls[1]).toContain('cursor=opaque%2Fvalue')
})
test('401 expires the UI session; proxy HTML failures remain generic', async () => {
  const api = new AdminApi(),
    expired = mock(() => {})
  api.onUnauthorized = expired
  globalThis.fetch = mock(
    async () => new Response('<html>unavailable</html>', { status: 401 }),
  ) as unknown as typeof fetch
  await expect(api.request('/flows')).rejects.toBeInstanceOf(ApiError)
  expect(expired).toHaveBeenCalledTimes(1)
})
