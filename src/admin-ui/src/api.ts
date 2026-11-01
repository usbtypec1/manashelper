import type { Schemas } from './types'

export class ApiError extends Error {
  constructor(
    public status: number,
    public issues: Schemas['ContractIssue'][] = [],
  ) {
    super(`HTTP ${status}`)
  }
}

export class AdminApi {
  csrf = ''
  onUnauthorized: () => void = () => {}

  async request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 15000)
    try {
      const response = await fetch('/admin/api/v1' + path, {
        method,
        credentials: 'same-origin',
        signal: controller.signal,
        headers: {
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
          ...(method === 'GET' ? {} : { 'X-CSRF-Token': this.csrf }),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      })
      if (!response.ok) {
        if (response.status === 401) this.onUnauthorized()
        const error = await response.json().catch(() => ({}))
        throw new ApiError(response.status, Array.isArray(error.issues) ? error.issues : [])
      }
      return response.status === 204 ? (undefined as T) : await response.json()
    } finally {
      clearTimeout(timer)
    }
  }

  async login(ticket: string | null): Promise<Schemas['AdminSession']> {
    const session = await this.request<Schemas['AdminSession']>(
      ticket ? '/auth/exchange' : '/auth/session',
      ticket ? 'POST' : 'GET',
      ticket ? { ticket } : undefined,
    )
    this.csrf = session.csrf_token
    return session
  }

  async all<T>(path: string): Promise<T[]> {
    const items: T[] = []
    let cursor: string | null = null
    do {
      const page: { items: T[]; next_cursor: string | null } = await this.request(
        path + '?limit=100' + (cursor ? '&cursor=' + encodeURIComponent(cursor) : ''),
      )
      items.push(...page.items)
      cursor = page.next_cursor
    } while (cursor)
    return items
  }
}
