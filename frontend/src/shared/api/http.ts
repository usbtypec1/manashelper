/** Authenticated JSON transport for the local Mini App API. */
export class HttpError extends Error {
  constructor(readonly status: number) {
    super(`Request failed with status ${status}`)
  }

  /** 401 is an invalid or expired Telegram session; 403 is denied access. */
  get unauthorized(): boolean { return this.status === 401 || this.status === 403 }
}

export async function getJson(path: string, rawInitData: string, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(`/api/${path}`, {
    cache: 'no-store',
    headers: { Authorization: `tma ${rawInitData}` },
    ...(signal ? { signal } : {}),
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
