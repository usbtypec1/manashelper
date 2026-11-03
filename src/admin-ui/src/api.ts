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
  private accessToken = ''
  private authMode: 'cookie' | 'bearer' = 'cookie'

  async request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 15000)
    try {
      const response = await fetch('/admin/api/v1' + path, {
        method,
        credentials: this.authMode === 'bearer' ? 'omit' : 'same-origin',
        signal: controller.signal,
        headers: {
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
          ...(this.authMode === 'bearer'
            ? this.accessToken
              ? { Authorization: 'Bearer ' + this.accessToken }
              : {}
            : method === 'GET'
              ? {}
              : { 'X-CSRF-Token': this.csrf }),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      })
      if (!response.ok) {
        if (response.status === 401) {
          this.accessToken = ''
          this.csrf = ''
          this.onUnauthorized()
        }
        const error = await response.json().catch(() => ({}))
        throw new ApiError(response.status, Array.isArray(error.issues) ? error.issues : [])
      }
      return response.status === 204 ? (undefined as T) : await response.json()
    } finally {
      clearTimeout(timer)
    }
  }

  async login(ticket: string | null, initData?: string): Promise<Schemas['AdminSession']> {
    this.accessToken = ''
    this.csrf = ''
    this.authMode = initData ? 'bearer' : 'cookie'
    if (initData) {
      const session = await this.request<
        Omit<Schemas['AdminSession'], 'csrf_token'> & { access_token: string }
      >('/auth/telegram', 'POST', { init_data: initData })
      this.accessToken = session.access_token
      return { user_id: session.user_id, expires_at: session.expires_at, csrf_token: '' }
    }
    const session = await this.request<Schemas['AdminSession']>(
      ticket ? '/auth/exchange' : '/auth/session',
      ticket ? 'POST' : 'GET',
      ticket ? { ticket } : undefined,
    )
    this.csrf = session.csrf_token
    return session
  }

  async logout(): Promise<void> {
    try {
      await this.request('/auth/logout', 'POST')
    } finally {
      this.accessToken = ''
      this.csrf = ''
    }
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
