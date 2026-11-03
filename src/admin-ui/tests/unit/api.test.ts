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

test('ticket login and cookie-session recovery preserve the CSRF contract', async () => {
  const requests: { url: string; options: RequestInit }[] = []
  globalThis.fetch = mock(async (url: string, options: RequestInit) => {
    requests.push({ url, options })
    return Response.json({ user_id: 1, expires_at: '2026-11-03T00:00:00Z', csrf_token: 'cookie-csrf' })
  }) as unknown as typeof fetch
  const api = new AdminApi()
  expect((await api.login('synthetic-ticket')).csrf_token).toBe('cookie-csrf')
  expect(api.csrf).toBe('cookie-csrf')
  expect(requests[0]!.url).toBe('/admin/api/v1/auth/exchange')
  expect(requests[0]!.options.credentials).toBe('same-origin')
  expect(JSON.parse(requests[0]!.options.body as string)).toEqual({ ticket: 'synthetic-ticket' })
  await api.login(null)
  expect(requests[1]!.url).toBe('/admin/api/v1/auth/session')
  expect(requests[1]!.options.method).toBe('GET')
  expect(requests[1]!.options.credentials).toBe('same-origin')
  expect(requests[1]!.options.headers).not.toHaveProperty('Authorization')
})

test('Mini App login uses bearer-only reads, mutations and logout without leaking credentials', async () => {
  const requests: { url: string; options: RequestInit }[] = []
  globalThis.fetch = mock(async (url: string, options: RequestInit) => {
    requests.push({ url, options })
    if (url.endsWith('/auth/telegram')) {
      return Response.json({
        user_id: 1,
        expires_at: '2026-11-03T00:00:00Z',
        access_token: 'synthetic-bearer-token',
      })
    }
    return options.method === 'POST' ? new Response(null, { status: 204 }) : Response.json({ items: [] })
  }) as unknown as typeof fetch
  const api = new AdminApi()
  api.csrf = 'previous-cookie-csrf'
  const session = await api.login('unused-ticket', 'synthetic-init-data')
  expect(session).toEqual({ user_id: 1, expires_at: '2026-11-03T00:00:00Z', csrf_token: '' })
  expect(api.csrf).toBe('')
  expect(requests[0]!.url).toBe('/admin/api/v1/auth/telegram')
  expect(JSON.parse(requests[0]!.options.body as string)).toEqual({ init_data: 'synthetic-init-data' })
  expect(requests[0]!.options.headers).not.toHaveProperty('Authorization')
  await api.request('/flows')
  await api.request('/flows/demo/draft', 'PUT', { expected_revision: 0 })
  await api.logout()
  await api.request('/flows')
  for (const { url, options } of requests) {
    expect(options.credentials).toBe('omit')
    expect(options.headers).not.toHaveProperty('X-CSRF-Token')
    expect(url).not.toContain('synthetic-')
  }
  for (const index of [1, 2, 3]) {
    expect(requests[index]!.options.headers).toHaveProperty('Authorization', 'Bearer synthetic-bearer-token')
  }
  expect(requests[4]!.options.headers).not.toHaveProperty('Authorization')
})

test('rejected initData does not fall back to an existing cookie or ticket', async () => {
  const fetch = mock(async () => new Response(null, { status: 401 }))
  globalThis.fetch = fetch as unknown as typeof globalThis.fetch
  const api = new AdminApi()
  const expired = mock(() => {})
  api.onUnauthorized = expired
  await expect(api.login('synthetic-ticket', 'invalid-init-data')).rejects.toBeInstanceOf(ApiError)
  expect(fetch).toHaveBeenCalledTimes(1)
  const [url, options] = fetch.mock.calls[0] as unknown as [string, RequestInit]
  expect(url).toBe('/admin/api/v1/auth/telegram')
  expect(options.credentials).toBe('omit')
  expect(expired).toHaveBeenCalledTimes(1)
})

test('401 discards bearer credentials and subsequent requests remain cookie-free', async () => {
  const requests: RequestInit[] = []
  globalThis.fetch = mock(async (_url: string, options: RequestInit) => {
    requests.push(options)
    return requests.length === 1
      ? Response.json({ user_id: 1, expires_at: '2026-11-03T00:00:00Z', access_token: 'expired-token' })
      : new Response(null, { status: 401 })
  }) as unknown as typeof fetch
  const api = new AdminApi()
  await api.login(null, 'synthetic-init-data')
  await expect(api.request('/flows')).rejects.toBeInstanceOf(ApiError)
  await expect(api.request('/flows')).rejects.toBeInstanceOf(ApiError)
  expect(requests[1]!.headers).toHaveProperty('Authorization', 'Bearer expired-token')
  expect(requests[2]!.headers).not.toHaveProperty('Authorization')
  expect(requests[2]!.credentials).toBe('omit')
})

test('logout discards memory credentials even when revocation fails over the network', async () => {
  const requests: RequestInit[] = []
  globalThis.fetch = mock(async (url: string, options: RequestInit) => {
    requests.push(options)
    if (url.endsWith('/auth/telegram')) {
      return Response.json({ user_id: 1, expires_at: '2026-11-03T00:00:00Z', access_token: 'logout-token' })
    }
    if (url.endsWith('/auth/logout')) throw new TypeError('Synthetic network failure')
    return Response.json({ items: [] })
  }) as unknown as typeof fetch
  const api = new AdminApi()
  await api.login(null, 'synthetic-init-data')
  await expect(api.logout()).rejects.toBeInstanceOf(TypeError)
  await api.request('/flows')
  expect(requests[1]!.headers).toHaveProperty('Authorization', 'Bearer logout-token')
  expect(requests[2]!.headers).not.toHaveProperty('Authorization')
  expect(requests[2]!.credentials).toBe('omit')
  expect(api.csrf).toBe('')
})
