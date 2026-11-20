/** Authenticated JSON transport for the local Mini App API. */
export class HttpError extends Error {
  constructor(readonly status: number) {
    super(`Request failed with status ${status}`)
  }

  /** 401 is an invalid or expired Telegram session; 403 is denied access. */
  get unauthorized(): boolean { return this.status === 401 || this.status === 403 }
}

export async function getJson(path: string, rawInitData: string, signal?: AbortSignal): Promise<unknown> {
  return requestJson(path, rawInitData, { signal })
}

export async function postJson(path: string, rawInitData: string, body?: unknown): Promise<unknown> {
  return sendJson('POST', path, rawInitData, body)
}

export async function putJson(path: string, rawInitData: string, body: unknown): Promise<unknown> {
  return sendJson('PUT', path, rawInitData, body)
}

async function sendJson(method: 'POST' | 'PUT', path: string, rawInitData: string, body: unknown): Promise<unknown> {
  return requestJson(path, rawInitData, {
    method,
    headers: { 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  })
}

async function requestJson(path: string, rawInitData: string, options: RequestInit): Promise<unknown> {
  const response = await fetch(`/api/${path}`, {
    ...options,
    cache: 'no-store',
    headers: { ...options.headers, Authorization: `tma ${rawInitData}` },
  })
  if (!response.ok) throw new HttpError(response.status)
  return response.json() as Promise<unknown>
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function isStringRecord(value: unknown): value is Record<string, string> {
  return isRecord(value) && Object.values(value).every(item => typeof item === 'string')
}
